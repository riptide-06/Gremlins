"""Offline policy, authentication, Drive boundary, and official SDK tests."""
from contextlib import contextmanager
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import json
import asyncio
import re
import threading
import time

import httpx
import pytest
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role, SendMessageRequest, SendMessageResponse
from cryptography.fernet import Fernet
from google.protobuf.json_format import MessageToDict, ParseDict

from cloud_app import Auth, CALLER, Settings, campus_claims, create_app
from cubbies import Fault, Service, digest, drive_folder_url
from cubby_drive import Drive

A, B, ADMIN = "a@ucsc.edu", "b@ucsc.edu", "admin@ucsc.edu"


class MemoryRepo:
    def __init__(self):
        self.data = {}
        self.mutex = threading.RLock()
        self.hook = None
        self.fail_delivery = False

    def get(self, kind, key):
        return deepcopy(self.data.get((kind, key)))

    def put(self, kind, key, data):
        if kind == "deliveries" and data["status"] == "delivered" and self.fail_delivery:
            self.fail_delivery = False
            raise RuntimeError("backend unavailable")
        self.data[kind, key] = deepcopy(data)

    def delete(self, kind, key):
        self.data.pop((kind, key), None)

    def change(self, kind, key, fn):
        with self.mutex:
            data, result = fn(self.get(kind, key))
            self.put(kind, key, data)
            return result

    def exchange(self, pairing_key, token_key, fn):
        with self.mutex:
            pairing = self.get("pairings", pairing_key)
            user = self.get("users", digest(pairing["email"])) if pairing and pairing["email"] else None
            data, token = fn(pairing, user)
            self.put("pairings", pairing_key, data)
            if token:
                self.put("tokens", token_key, token)
            return token

    def atomic(self, refs, fn):
        with self.mutex:
            writes, result = fn([self.get(kind, key) for kind, key in refs])
            previous = deepcopy(self.data)
            try:
                for (kind, key), data in writes.items():
                    self.put(kind, key, data)
            except Exception:
                self.data = previous
                raise
            return result

    def owner_deliveries(self, owner):
        return [deepcopy(v) for (kind, key), v in self.data.items() if kind == "deliveries" and v["dst"] == owner]

    def event_ref(self, owner, sequence):
        return ("feeds/" + digest(owner) + "/events", f"{sequence:020d}")

    def events(self, owner, after, through, limit):
        kind = "feeds/" + digest(owner) + "/events"
        return [deepcopy(v) for k, v in sorted((key, value) for (collection, key), value in self.data.items()
                if collection == kind and after < value["sequence"] <= through)][:limit]

    @contextmanager
    def lock(self, key):
        with self.mutex:
            if self.hook:
                hook, self.hook = self.hook, None
                hook()
            yield

    def scan(self, kind, cursor="", limit=100):
        rows = sorted((k, v) for (c, k), v in self.data.items() if c == kind and k > cursor)
        return ([{"id": k, **deepcopy(v)} for k, v in rows[:limit]], rows[limit - 1][0] if len(rows) > limit else "")


class FakeDrive:
    def __init__(self):
        self.files = {}
        self.serial = 0
        self.created = 0

    def seal(self, value):
        return "sealed:" + value

    def setup(self, user):
        user.setdefault("folder", "folder-" + digest(user["email"]))
        return user

    def allocate(self, user):
        self.serial += 1
        return "file-" + str(self.serial)

    def deliver(self, user, file_id, name, text):
        if file_id not in self.files:
            self.created += 1
            self.files[file_id] = {"owner": user["email"], "name": name, "text": text, "revision": "1"}

    def create(self, user, name, text):
        file_id = self.allocate(user)
        self.deliver(user, file_id, name, text)
        return {"file_id": file_id}

    def read(self, user, file_id):
        data = self.files[file_id]
        if data["owner"] != user["email"]:
            raise Fault("Outside your cubby")
        return deepcopy(data)

    def list(self, user, cursor=""):
        return {"files": [k for k, v in self.files.items() if v["owner"] == user["email"]], "cursor": ""}


@pytest.fixture
def system():
    repo, drive = MemoryRepo(), FakeDrive()
    settings = Settings(url="http://localhost", project="test", session_secret="test-secret",
                        local_http=True, admins=(ADMIN,))
    for email in (A, B, ADMIN):
        repo.put("users", digest(email), {"email": email, "sub": email, "folder": "folder-" + digest(email),
                 "initialized": True, "generation": 0, "created_at": "today", "refresh_token": "SECRET"})
    return Service(repo, drive, settings)


def call(s, who, action, **kwargs):
    return s.call(who, {"action": action, **kwargs})


def test_hello_owner_folder_isolation(system):
    for owner in (A, B, ADMIN):
        result = call(system, owner, "hello")
        folder = system.repo.get("users", digest(owner))["folder"]
        assert result["cubby"] == {"folder_id": folder,
                                   "folder_url": "https://drive.google.com/drive/folders/" + folder}
        assert sum("Share cubby.folder_url" in instruction for instruction in result["instructions"]) == 1
        for other in {A, B, ADMIN} - {owner}:
            assert system.repo.get("users", digest(other))["folder"] not in json.dumps(result)
        with pytest.raises(Fault, match="Unknown arguments"):
            call(system, owner, "hello", owner=B)


@pytest.mark.parametrize("folder", [None, 123, "", "../folder", "folder/path", "folder?x=1", "https://evil", "a" * 201])
def test_folder_url_validation(folder):
    with pytest.raises(Fault, match="Invalid file ID"):
        drive_folder_url(folder)


def test_relationship_and_admin_paths_do_not_leak_folders(system):
    s = system
    grant = call(s, ADMIN, "admin_set_contributor", owner=A, email=B,
                 managed_by="admin", reason="collaborator")
    results = [grant, call(s, A, "list_contributors"),
               call(s, B, "can_contribute", email=A),
               call(s, B, "contribute", to=A, subject="Note", body="Data", request_id="isolation"),
               call(s, ADMIN, "admin_list_contributors", owner=A),
               call(s, ADMIN, "admin_list_users"), call(s, ADMIN, "admin_audit"),
               call(s, ADMIN, "admin_remove_contributor", owner=A, email=B, reason="done")]
    for result in results:
        serialized = json.dumps(result)
        assert "drive.google.com" not in serialized
        assert "folder_id" not in serialized and "folder_url" not in serialized
        for owner in (A, B, ADMIN):
            assert s.repo.get("users", digest(owner))["folder"] not in serialized


def test_separation_permissions_revocation(system):
    s = system
    file_id = call(s, A, "create_file", name="notes", text="private")["file_id"]
    assert call(s, B, "list_files")["files"] == []
    assert call(s, B, "can_contribute", email=A) == {"allowed": False}
    note = dict(to=A, subject="subject", body="outside data", request_id="r1")
    with pytest.raises(Fault):
        call(s, B, "contribute", **note)
    call(s, A, "add_contributor", email=B, reason="collaborator")
    assert call(s, B, "can_contribute", email=A) == {"allowed": True}
    receipt = call(s, B, "contribute", **note)
    assert set(receipt["receipt"]) == {"message_id", "time", "status"}
    with pytest.raises(Fault):
        call(s, B, "read_file", file_id=file_id)
    call(s, A, "remove_contributor", email=B)
    with pytest.raises(Fault):
        call(s, B, "contribute", **{**note, "request_id": "r2"})


def test_admin_overlay_preconnection_and_owner_race(system):
    s = system
    args = dict(owner=A, email=B, managed_by="admin", reason="course cohort", source="course:123")
    call(s, ADMIN, "admin_set_contributor", **args)
    grant = call(s, A, "list_contributors")["contributors"][0]
    assert grant["source"] == {"kind": "admin", "identifier": "course:123"}
    assert grant["managed_by"] == "admin" and grant["reason"] == "course cohort"
    for actor in (A, ADMIN):
        # Make the recipient the actor's own folder, even for admin owner tools.
        call(s, ADMIN, "admin_set_contributor", **{**args, "owner": actor})
        with pytest.raises(Fault):
            call(s, actor, "add_contributor", email=B)
        with pytest.raises(Fault):
            call(s, actor, "remove_contributor", email=B)
    call(s, ADMIN, "admin_remove_contributor", owner=A, email=B, reason="end of course")
    s.repo.hook = lambda: call(s, ADMIN, "admin_set_contributor", **args)
    with pytest.raises(Fault):
        call(s, A, "add_contributor", email=B)
    assert s.grants(A)[B]["managed_by"] == "admin"
    call(s, ADMIN, "admin_set_contributor", **{**args, "owner": "future@ucsc.edu"})
    assert s.grants("future@ucsc.edu")[B]
    assert not call(s, B, "can_contribute", email="future@ucsc.edu")["allowed"]
    for managed in ("admin", "owner"):
        with pytest.raises(Fault):
            call(s, ADMIN, "admin_set_contributor", **{**args, "managed_by": managed, "reason": ""})


def test_discovery_argument_injection_and_admin_read_boundary(system):
    s = system
    names = {t["action"] for t in call(s, A, "hello")["tools"]}
    assert not any(n.startswith("admin_") for n in names)
    assert not any("outbound" in n for n in names)
    assert call(s, ADMIN, "hello")["roles"] == ["owner", "contributor", "admin"]
    for action in ("admin_audit", "admin_list_users", "admin_list_contributors"):
        with pytest.raises(Fault):
            call(s, A, action)
    for injection in ({"owner": B}, {"uid": B}, {"sender": B}, {"role": "admin"}):
        with pytest.raises(Fault):
            call(s, A, "list_files", **injection)
    for request in ({}, {"action": "read_file", "file_id": False}, {"action": "read_file"},
                    {"action": "create_file", "name": "n", "text": "x" * 24001}):
        with pytest.raises(Fault):
            s.call(A, request)
    file_id = call(s, A, "create_file", name="notes", text="SECRET")["file_id"]
    with pytest.raises(Fault):
        call(s, ADMIN, "read_file", file_id=file_id)
    users = json.dumps(call(s, ADMIN, "admin_list_users"))
    assert "SECRET" not in users and "refresh_token" not in users and "folder" not in users
    s.repo.put("audit", "corrupt", {"event": "test", "src": A, "dst": B, "time": "now",
                                  "body": "BODY_CANARY", "access_token": "SECRET"})
    assert "CANARY" not in json.dumps(call(s, ADMIN, "admin_audit"))
    assert "SECRET" not in json.dumps(call(s, ADMIN, "admin_audit"))


def test_retry_after_backend_failure_and_attribution(system):
    s = system
    call(s, A, "add_contributor", email=B)
    note = dict(to=A, subject="SUBJECT_CANARY", body="BODY_CANARY", request_id="stable")
    with pytest.raises(Fault):
        call(s, B, "contribute", **note, sender=ADMIN)
    s.repo.fail_delivery = True
    with pytest.raises(RuntimeError):
        call(s, B, "contribute", **note)
    receipt = call(s, B, "contribute", **note)
    assert call(s, B, "contribute", **note) == receipt
    assert s.drive.created == 1
    text = json.loads(next(iter(s.drive.files.values()))["text"])
    assert text["from"] == B and text["to"] == A
    assert text["message_id"] == receipt["receipt"]["message_id"]
    with pytest.raises(Fault):
        call(s, B, "contribute", **{**note, "body": "changed"})
    stored = json.dumps(list(s.repo.data.values()))
    assert "SUBJECT_CANARY" not in stored and "BODY_CANARY" not in stored
    audit = call(s, ADMIN, "admin_audit")["events"]
    assert len([r for r in audit if r["event"] == "delivered"]) == 1


def test_pairing_lifecycle_expiry_revocation(system, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    auth = Auth(system.repo)
    device, code = auth.start()
    with pytest.raises(Fault, match="authorization_pending"):
        auth.exchange(code, device)
    with pytest.raises(Fault, match="slow_down"):
        auth.exchange(code, device)
    clock[0] += 5
    with pytest.raises(Fault, match="expired_token"):
        auth.exchange(code, "wrong")
    auth.approve(code, A)
    with pytest.raises(Fault):
        auth.approve(code, B)
    result = auth.exchange(code, device)
    token = result["access_token"]
    assert auth.authorize(token) == A
    with pytest.raises(Fault, match="expired_token"):
        auth.exchange(code, device)
    call(system, A, "revoke_agents")
    assert auth.authorize(token) is None
    device, code = auth.start()
    auth.approve(code, B)
    token = auth.exchange(code, device)["access_token"]
    clock[0] += 172800
    assert auth.authorize(token) is None
    device, code = auth.start()
    clock[0] += 601
    with pytest.raises(Fault):
        auth.exchange(code, device)
    with pytest.raises(Fault):
        auth.approve("missing", A)


def claims(email=A, sub=A):
    return {"iss": "https://accounts.google.com", "email_verified": True, "hd": "ucsc.edu", "sub": sub, "email": email}


@pytest.mark.parametrize("change", [{"iss": "evil"}, {"email_verified": "true"}, {"hd": "other.edu"},
                                   {"sub": ""}, {"email": "a@other.edu"}, {"email": None}])
def test_google_claim_validation(system, change):
    with pytest.raises(Fault):
        campus_claims({**claims(), **change}, system)


def test_onboarding_idempotent_subject_and_missing_pairing(system):
    app = create_app(system.settings, system.repo, system.drive)
    device, code = app.state.auth.start()
    with pytest.raises(Fault):
        app.state.onboard(claims(sub="different-sub"), {}, code)
    with pytest.raises(Fault):
        app.state.onboard(claims(), {}, "missing")
    app.state.onboard(claims(), {}, code)
    device, code = app.state.auth.start()
    app.state.onboard(claims(), {}, code)
    assert system.drive.created == 0  # Already initialized users are not rewritten.
    email = "new@ucsc.edu"
    device, code = app.state.auth.start()
    app.state.onboard(claims(email, "new-sub"), {"refresh_token": "PRIVATE"}, code)
    assert system.drive.created == 2
    device, code = app.state.auth.start()
    app.state.onboard(claims(email, "new-sub"), {}, code)
    assert system.drive.created == 2
    assert system.repo.get("users", digest(email))["refresh_token"] == "sealed:PRIVATE"


def credential(s, email):
    auth = Auth(s.repo)
    device, code = auth.start()
    auth.approve(code, email)
    return auth.exchange(code, device)["access_token"]


def documented_request(guide, token):
    """Test-only extraction: execute the served guide, not a separate client recipe."""
    envelope = json.loads(re.search(r"```json\n(.*?)\n```", guide, re.S)[1])
    lines = re.search(r"```http\n(.*?)\n```", guide, re.S)[1].splitlines()
    assert lines[0] == "POST /a2a HTTP/1.1"
    headers = dict(line.split(": ", 1) for line in lines[1:])
    assert headers["Authorization"] == "Bearer YOUR_PRIVATE_TOKEN"
    headers["Authorization"] = "Bearer " + token
    return envelope, headers


@pytest.mark.asyncio
@pytest.mark.parametrize("origin", ["http://localhost", "https://cubby.bayleaf.dev"])
async def test_landing_discovery_to_documented_pairing_and_hello(system, monkeypatch, origin):
    """Start with only the root URL, following published links, not guessed paths."""
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.anchors, self.metadata = [], []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a":
                self.anchors.append(attrs)
            elif tag == "link":
                self.metadata.append(attrs)

    system.settings.url = origin
    clock = [time.time()]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=origin) as http:
        root = await http.get(origin)
        assert root.headers["content-security-policy"] == "default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        links = Links()
        links.feed(root.text)
        # One visible, meaningful agent navigation link, also available to plain fetches.
        agent_links = [a for a in links.anchors if a["href"].startswith("/")]
        assert len(agent_links) == 1
        assert ">Agents: start here to connect</a>" in root.text
        guide_url = urljoin(str(root.url), agent_links[0]["href"])
        guide_response = await http.get(guide_url)
        assert guide_response.status_code == 200
        guide = guide_response.text
        assert guide == Path(__file__).with_name("SKILL.md").read_text()
        describedby = next(m for m in links.metadata if m["rel"] == "describedby")
        assert urljoin(origin, describedby["href"]) == guide_url
        header_paths = re.findall(r"<([^>]+)>", root.headers["link"])
        assert header_paths == [describedby["href"], next(m["href"] for m in links.metadata if m["rel"] == "alternate")]
        published = {label: urljoin(guide_url, target) for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", guide)}
        card_response = await http.get(published["Agent Card"])
        assert card_response.status_code == 200
        card = card_response.json()
        root_card_url = urljoin(str(root.url), header_paths[1])
        assert root_card_url == published["Agent Card"]
        assert (await http.get(root_card_url)).json() == card
        assert card["documentationUrl"] == guide_url
        assert (await http.get(card["documentationUrl"])).text == guide
        pointer = (await http.get("/llms.txt")).text
        pointer_target = re.search(r"\[Agent connection guide\]\(([^)]+)\)", pointer)[1]
        assert pointer_target == guide_url
        started = await http.post(published["start pairing"], content=b"")
        assert started.status_code == 200
        pairing = started.json()
        assert pairing["verification_uri"] == origin + "/connect"
        approval = await http.get(pairing["verification_uri_complete"])
        assert approval.status_code == 200 and "Only approve a request you started" in approval.text
        form = {key: pairing[key] for key in ("user_code", "device_code")}
        clock[0] += pairing["interval"]
        pending = await http.post(published["pairing exchange"], data=form)
        assert pending.status_code == 400 and pending.json()["error"] == "authorization_pending"
        # Offline human approval fixture only. Never impersonate live OAuth consent.
        app.state.auth.approve(pairing["user_code"], A)
        clock[0] += pairing["interval"]
        exchanged = await http.post(published["pairing exchange"], data=form)
        assert exchanged.status_code == 200
        envelope, headers = documented_request(guide, exchanged.json()["access_token"])
        endpoint = card["supportedInterfaces"][0]["url"]
        assert endpoint == origin + "/a2a"
        response = await http.post(endpoint, json=envelope, headers=headers)
        assert response.status_code == 200 and "error" not in response.json()
        result = json.loads("".join(p["text"] for p in response.json()["result"]["message"]["parts"]))
        assert result["ok"] and result["identity"] == A and result["tools"] and result["instructions"]
        assert result["cubby"]["folder_url"] == drive_folder_url(system.user(A)["folder"])


@pytest.mark.asyncio
async def test_canonical_onboarding_and_evolving_reconnect_instructions(system):
    """Published instruction contract, not evidence that an LLM will follow it."""
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=system.settings.url) as http:
        card = (await http.get("/.well-known/agent-card.json")).json()
        guide = (await http.get(card["documentationUrl"])).text
        milestones = ["**Explain discovery.**", "**Ask for human approval.**",
                      "**Share the Drive link.**", "**Make the first read-only check**",
                      "**Offer a reconnect skill.**"]
        assert [guide.index(m) for m in milestones] == sorted(guide.index(m) for m in milestones)
        first_check = guide.split("### First read-only check\n", 1)[1].split("### Make future checks easy", 1)[0]
        # Check required decisions, allowing sentence structure and markup to change.
        first_check = " ".join(first_check.replace("**", "").split())
        for requirement in (
            r'changes_since.*without a cursor.*beginning.*not.*start: "now"',
            r'no feed events.*not.*empty cubby',
            r'cursor only after every event.*assessed/reported or durably recorded as unresolved',
            r'stopping midway.*preceding cursor.*replay',
            r'untrusted data.*not.*instructions',
        ):
            assert re.search(requirement, first_check), requirement
        reconnect = guide.split("### Make future checks easy\n", 1)[1].split("### Catch up", 1)[0]
        assert "fetch the current guide and Agent Card" in reconnect and "fresh `hello`" in reconnect
        assert "before sending credentials" in reconnect and "never silently reset it to now" in reconnect
        assert "not a copied guide" in reconnect and "bounded read-only replay" in reconnect
        assert "Monitoring is optional, not part of a generic setup request" in guide
        assert "same onboarding milestones and bounded first read-only check" in guide
        instructions = call(system, A, "hello")["instructions"]
        assert any("SKILL.md's bounded read-only first check" in text and "separate request" in text
                   for text in instructions)


@pytest.mark.asyncio
async def test_published_pairing_capture_and_human_handoff(system):
    """Instruction contract for observed agent mistakes, not background-host support."""
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=system.settings.url) as http:
        guide = (await http.get("/SKILL.md")).text
        pairing = guide.split("## 2. Request human approval", 1)[1].split("## 3. Call A2A", 1)[0]
        pairing = " ".join(pairing.split())
        for required in (
            "resume reasoning without another user turn", "say ‘Done’",
            "I can't check approval in the background", "unless a polling workflow is actually running",
            "not the A2A contribution `monitor`", "cannot wake your host or complete pairing",
            "device code, user code, exact origin, absolute ten-minute deadline",
            "current poll interval privately", "original browser helper tab",
            "message itself is not evidence of approval", "expired or state was lost",
            "fresh pairing", "only one poller, at least five seconds",
            "Prepare private capture before the first exchange", "without displaying it",
            "atomically save the bearer and absolute expiry", "before returning only a safe status",
            "Redacting a token in tool output does not save it", "later tool call",
            "retain the captured response privately", "if it is lost, reconnect",
            "error code: 1010", "not `authorization_pending`", "Stop unchanged retries",
            "do not bypass host egress policy or weaken service security",
        ):
            assert required in pairing, required
        assert pairing.index("Before handing off") < pairing.index("After waiting at least")
        assert pairing.index("Prepare private capture") < pairing.index("POST to the [pairing exchange]")
        assert "Identify each tool by its `action` field" in guide
        assert re.search(r'“Done”.*handoff above', guide)
        assert "A live monitor does **not** wake an agent's reasoning by itself" in guide
        # Confirm the schema identifier against real hello, not an invented guide convention.
        tools = call(system, A, "hello")["tools"]
        assert tools and all("action" in tool and "input_schema" in tool for tool in tools)


@pytest.mark.asyncio
async def test_published_inference_trust_prerequisite_and_saved_skill(system):
    """Instruction ordering/content contract, not provider detection or LLM compliance."""
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=system.settings.url) as http:
        guide = (await http.get("/SKILL.md")).text
        trust_start = guide.index("## Before connecting: use an approved AI environment")
        assert trust_start < guide.index("## Onboarding:") < guide.index("POST to [start pairing]")
        assert trust_start < guide.index("## 3. Call A2A and discover tools") < guide.index("### First read-only check")
        trust = guide[trust_start:guide.index("## Onboarding:")]
        for required in (
            "pairing, loading or using credentials", "metadata/file reads",
            "every new or reconnected agent", "provider/model routing or data handling changes",
            "same approved processing boundary", "stored bearer", "saved local",
            "user explicitly identifies this environment as trusted", "available policy",
            "before transmitting protected information", "known to be untrusted",
            "abort setup or ongoing operations", "UCSC email/login or model",
            "not a verified technical", "cannot\ndetect or enforce",
            "do not load a private credential to test", "stop local polling/streams",
            "already-fetched contents", "previously processed data cannot be undone",
            "appropriate secure process", "untrusted one",
        ):
            assert required in trust, required
        # Extract what the guide requires hosts to save, not just surrounding prose.
        reconnect = guide.split("### Make future checks easy\n", 1)[1].split("### Catch up", 1)[0]
        saved = "\n".join(line[2:] for line in reconnect.splitlines() if line.startswith("> "))
        for required in (
            "Before pairing, loading/using credentials", "metadata/file",
            "every new/reconnected session", "same approved", "Old consent, credentials",
            "If unknown, pause", "known untrusted, abort", "Public guide/card fetches",
            "never load a private credential", "stop calls, reading and local polling/streams",
            "Previously processed data cannot be undone", "appropriate secure process",
            "Browser fallback", "not server provider enforcement",
        ):
            assert required in saved, required
        assert reconnect.index("> Before pairing") < reconnect.index("fetch the current guide and Agent Card")
        assert reconnect.index("under that trusted approval") < reconnect.index("fresh `hello`")
        browser = guide.split("## Browser-runtime fallback:", 1)[1]
        assert browser.index("First satisfy the AI-environment prerequisite") < browser.index("```javascript")
        assert "local browser does not make remotely processed notes local" in " ".join(browser.split())
        instructions = call(system, A, "hello")["instructions"]
        assert "Before any further cubby operation" in instructions[0]
        assert "unknown trust means pause, known untrusted means abort" in instructions[0]
        assert "not server enforcement" in instructions[0]
        # No provider assertion is introduced into the protocol or public human landing.
        root = (await http.get("/")).text
        assert "Before connecting: use an approved AI environment" not in root


@pytest.mark.asyncio
async def test_browser_guide_javascript_against_actual_api(system, monkeypatch):
    """Run the served JS with Node, routing fetch through the real offline ASGI app."""
    origin = "https://cubby.bayleaf.dev"
    system.settings.url = origin
    clock = [time.time()]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=origin) as http:
        guide = (await http.get("/SKILL.md")).text
        snippets = re.findall(r"```javascript\n([\s\S]*?)\n```", guide)
        # Only synthetic offline credentials cross this subprocess transport.
        script = r'''
const readline = require('node:readline');
const vm = require('node:vm');
const input = readline.createInterface({input: process.stdin});
const lines = input[Symbol.asyncIterator]();
const emit = data => process.stdout.write(JSON.stringify(data) + '\n');
(async () => {
  const config = JSON.parse((await lines.next()).value);
  let now = config.now;
  const context = {window: {}, location: {origin: config.origin}, URL, URLSearchParams,
    AbortSignal, crypto: require('node:crypto').webcrypto, Date: {now: () => now},
    setTimeout: (resolve, delay) => {now += delay; resolve();},
    fetch: async (url, options) => {
      emit({kind: 'request', url, now, method: options.method || 'GET',
        headers: options.headers || {}, body: options.body?.toString() || ''});
      const result = JSON.parse((await lines.next()).value);
      return {status: result.status, json: async () => result.body};
    }};
  const run = code => vm.runInNewContext(code, context);
  const start = await run(config.snippets[0]);
  const pending = await run(config.snippets[1]);
  const connected = await run(config.snippets[1]);
  const hello = await run(config.snippets[2]);
  emit({kind: 'done', start, pending, connected, hello});
  input.close();
})().catch(() => {emit({kind: 'failed'}); input.close(); process.exitCode = 1;});
'''
        process = await asyncio.create_subprocess_exec(
            "node", "-e", script, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        async def send(data):
            process.stdin.write((json.dumps(data) + "\n").encode())
            await process.stdin.drain()
        try:
            await send({"origin": origin, "now": clock[0] * 1000, "snippets": snippets})
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
                assert line, "Browser guide subprocess ended prematurely"
                message = json.loads(line)
                if message["kind"] != "request":
                    break
                clock[0] = message["now"] / 1000
                response = await http.request(message["method"], message["url"],
                                              headers=message["headers"], content=message["body"])
                if message["url"].endswith("/auth/device"):
                    code = response.json()["user_code"]
                await send({"status": response.status_code, "body": response.json()})
                if response.status_code == 400 and response.json().get("error") == "authorization_pending":
                    # Simulate human approval offline only, after proving pending.
                    app.state.auth.approve(code, A)
            assert message["kind"] == "done"
            assert message["pending"]["status"] == "Awaiting human approval"
            assert message["connected"]["status"] == "Connected"
            assert message["hello"]["ok"] and message["hello"]["identity"] == A
            assert message["hello"]["tools"] and message["hello"]["instructions"]
            assert "access_token" not in json.dumps(message)
            assert "device_code" not in json.dumps(message)
            assert await asyncio.wait_for(process.wait(), timeout=10) == 0
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.asyncio
async def test_public_http_guards_csrf_and_pairing(system, caplog):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        for path in ("/", "/.well-known/agent-card.json", "/SKILL.md", "/llms.txt", "/health"):
            response = await http.get(path)
            assert response.status_code == 200
            assert "SECRET" not in response.text
            assert "drive.google.com/drive/folders/" not in response.text
            for owner in (A, B, ADMIN):
                assert system.user(owner)["folder"] not in response.text
        assert (await http.post("/a2a", json={"method": "SendMessage"})).status_code == 401
        landing = (await http.get("/")).text
        assert "Give your agent this address" in landing and system.settings.url in landing
        assert 'href="https://chat.bayleaf.dev/?model=basic&amp;tools=lathe&amp;q=Help%20me%20set%20up%20my%20Campus%20Cubby.%20Start%20with%20the%20public%20agent%20guide%20at%20https%3A%2F%2Fcubby.bayleaf.dev%2FSKILL.md%20We%20trust%20BayLeaf%20inference.&amp;submit=false">Try Cubbies via Bayleaf Chat</a>' in landing
        assert '<details><summary>Privacy and data protection</summary>' in landing
        assert '<details open' not in landing
        assert 'for the information it processes.</p></details>' in landing
        assert "Instructions for agents" not in landing
        assert "Agent-to-agent (A2A) messaging, backed by a simple folder on your UCSC Google Drive." in landing
        assert "Python" not in landing
        assert "can’t peek at what’s inside" in landing
        assert "fully integrated production service" in landing
        assert "campus Data Protection Agreement (DPA)" in landing
        assert "UCSC–Google–BayLeaf infrastructure boundary" in landing
        assert "BayLeaf has previously been reviewed by the campus CISO" in landing
        assert "Cubbies itself runs no AI inference" in landing
        assert "inference provider is where information may leave that boundary and needs separate approval" in landing
        assert "prototype" not in landing.lower()
        assert "gremlin" not in landing.lower()
        assert "gremlin" not in (await http.get("/.well-known/agent-card.json")).text.lower()
        for retired in ("/cubby_client.py", "/gremlin_client.py"):
            assert (await http.get(retired)).status_code == 404
        skill = await http.get("/SKILL.md")
        assert skill.headers["content-type"].startswith("text/markdown")
        assert skill.text == Path(__file__).with_name("SKILL.md").read_text()
        card = (await http.get("/.well-known/agent-card.json")).json()
        assert card["documentationUrl"] == system.settings.url + "/SKILL.md"
        assert "/auth/device" not in card["description"]
        pointer = (await http.get("/llms.txt")).text
        assert system.settings.url + "/SKILL.md" in pointer and len(pointer) < 200
        token = credential(system, A)
        assert (await http.post("/a2a", json={"method": "ListTasks"}, headers={"Authorization": "Bearer " + token})).status_code == 400
        assert (await http.post("/auth/token", content=b"x" * 128001)).status_code == 413
        pairing = (await http.post("/auth/device")).json()
        pending = await http.post("/auth/token", data={"user_code": pairing["user_code"], "device_code": pairing["device_code"]})
        assert pending.json() == {"error": "authorization_pending"}
        assert (await http.post("/auth/token", data={"user_code": pairing["user_code"], "device_code": pairing["device_code"]})).json() == {"error": "slow_down"}
        connection = await http.get("/connect?code=" + pairing["user_code"])
        # OAuth starts via an ordinary link after the same-origin POST completes.
        assert "form-action 'self';" in connection.headers["content-security-policy"]
        assert "connect-src 'self';" in connection.headers["content-security-policy"]
        # Configure only for reaching CSRF validation, with no actual Google calls.
        system.settings.client_id = system.settings.client_secret = "configured"
        system.settings.service_account = system.settings.token_key = "configured"
        assert (await http.post("/login", data={"csrf": "wrong", "code": pairing["user_code"]})).status_code == 403
        assert "Connection wasn" in (await http.get("/auth/callback")).text
    assert "SECRET" not in caplog.text


@pytest.mark.asyncio
async def test_official_sdk_transport_and_request_isolation(system, caplog):
    app = create_app(system.settings, system.repo, system.drive)

    async def run(email, request):
        token = credential(system, email)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost",
                                     headers={"Authorization": "Bearer " + token}) as http:
            card = await A2ACardResolver(httpx_client=http, base_url="http://localhost").get_agent_card()
            client = await create_client(agent=card, client_config=ClientConfig(streaming=False, httpx_client=http))
            try:
                async for event in client.send_message(SendMessageRequest(message=new_text_message(
                        json.dumps(request), role=Role.ROLE_USER))):
                    response = event[0] if isinstance(event, tuple) else event
                    return json.loads(get_message_text(response.message))
            finally:
                await client.close()
    import asyncio
    results = await asyncio.gather(run(A, {"action": "hello"}), run(B, {"action": "hello"}))
    assert [r["identity"] for r in results] == [A, B]
    assert [r["cubby"]["folder_url"] for r in results] == [drive_folder_url(system.user(email)["folder"]) for email in (A, B)]
    assert CALLER.get() is None
    assert not (await run(A, {"action": "admin_audit"}))["ok"]
    assert not (await run(A, {"action": "contribute", "to": B, "subject": "SUBJECT_CANARY", "body": "BODY_CANARY", "request_id": "x"}))["ok"]
    assert (await run(A, {"action": "add_contributor", "email": B}))["ok"]
    note = {"action": "contribute", "to": A, "subject": "SUBJECT_CANARY", "body": "BODY_CANARY", "request_id": "sdk"}
    result = await run(B, note)
    assert result["ok"] and result["receipt"]["status"] == "delivered"
    assert await run(B, note) == result
    assert "SUBJECT_CANARY" not in caplog.text and "BODY_CANARY" not in caplog.text


@pytest.fixture
def drive_adapter(monkeypatch, system):
    drive = Drive(system.settings, system.repo)
    monkeypatch.setattr(drive, "owner_token", lambda user: "OWNER_SECRET")
    monkeypatch.setattr(drive, "service_token", lambda: "SERVICE_SECRET")
    return drive


def mock_http(monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "request", client.request)
    monkeypatch.setattr(httpx, "get", client.get)
    return client


def metadata(**overrides):
    return {"id": "file", "name": "Notes.md", "parents": ["folder"], "mimeType": "text/plain",
            "version": "1", "size": "5", "trashed": False, **overrides}


@pytest.mark.parametrize("overrides", [{"parents": ["foreign"]}, {"parents": []}, {"trashed": True},
    {"mimeType": "application/vnd.google-apps.shortcut"}, {"mimeType": "application/vnd.google-apps.document"}, {"size": "100001"}])
def test_drive_confinement_no_writes(monkeypatch, drive_adapter, overrides):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=metadata(**overrides))
    mock_http(monkeypatch, handler)
    for operation in (lambda: drive_adapter.read({"folder": "folder"}, "file"),
                      lambda: drive_adapter.trash({"folder": "folder"}, "file"),
                      lambda: drive_adapter.rename({"folder": "folder"}, "file", "new")):
        with pytest.raises(Fault):
            operation()
    assert all(r.method == "GET" for r in requests)
    for file_id in ("../file", "a/b", "https://evil", "file?alt=media"):
        with pytest.raises(Fault):
            drive_adapter.read({"folder": "folder"}, file_id)


@pytest.mark.parametrize("revision,search,text,changed", [("0", "hello", "hello", False),
    ("1", "hello", "hello hello", False), ("1", "aa", "aaa", False),
    ("1", "", "hello", False), ("1", "hello", "hello", True)])
def test_exact_edit_failures(monkeypatch, drive_adapter, revision, search, text, changed):
    requests, reads = [], [0]
    def handler(request):
        requests.append(request)
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, text=text)
        reads[0] += 1
        return httpx.Response(200, json=metadata(version="2" if changed and reads[0] > 1 else "1"))
    mock_http(monkeypatch, handler)
    with pytest.raises(Fault):
        drive_adapter.edit({"folder": "folder"}, "file", revision, search, "bye")
    assert all(r.method == "GET" for r in requests)


def test_drive_edit_without_etag_and_owner_creation(monkeypatch, drive_adapter):
    requests = []
    def handler(request):
        requests.append(request)
        if request.method == "POST":
            assert request.headers["authorization"] == "Bearer OWNER_SECRET"
            assert b'"parents": ["folder"]' in request.content
            return httpx.Response(200, json={"id": "created"})
        if request.method == "PATCH":
            assert request.content == b"bye"
            return httpx.Response(200, json={"id": "file", "version": "2"})
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, text="hello")
        return httpx.Response(200, json=metadata())
    mock_http(monkeypatch, handler)
    assert drive_adapter.edit({"folder": "folder"}, "file", "1", "hello", "bye")["version"] == "2"
    assert drive_adapter.create({"folder": "folder"}, "notes.md", "text")["id"] == "created"
    with pytest.raises(Fault):
        drive_adapter.create({"folder": "folder"}, "../notes", "text")


def test_drive_redaction_utf8_and_encryption(monkeypatch, drive_adapter, system):
    mock_http(monkeypatch, lambda request: httpx.Response(403, text="SECRET SUBJECT_CANARY BODY_CANARY"))
    with pytest.raises(Fault) as exc:
        drive_adapter.read({"folder": "folder"}, "file")
    assert "CANARY" not in str(exc.value) and "SECRET" not in str(exc.value)
    system.settings.token_key = Fernet.generate_key().decode()
    sealed = drive_adapter.seal("REFRESH_SECRET")
    assert "REFRESH_SECRET" not in sealed
    assert drive_adapter.cipher().decrypt(sealed.encode()) == b"REFRESH_SECRET"
    mock_http(monkeypatch, lambda request: httpx.Response(200, content=b"\xff") if request.url.params.get("alt") else httpx.Response(200, json=metadata()))
    with pytest.raises(Fault, match="UTF-8"):
        drive_adapter.read({"folder": "folder"}, "file")


@pytest.mark.asyncio
async def test_raw_http_pairing_lifecycle_and_no_public_credentials(system, monkeypatch, caplog):
    clock = [time.time()]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        started = await http.post("/auth/device")
        assert started.status_code == 200
        pairing = started.json()
        assert pairing["verification_uri"] == "http://localhost/connect"
        assert pairing["expires_in"] == 600 and pairing["interval"] == 5
        assert pairing["device_code"] not in pairing["verification_uri_complete"]
        form = {k: pairing[k] for k in ("user_code", "device_code")}
        assert (await http.post("/auth/token", data=form)).json()["error"] == "authorization_pending"
        assert (await http.post("/auth/token", data=form)).json()["error"] == "slow_down"
        clock[0] += 10
        app.state.auth.approve(pairing["user_code"], A)
        exchanged = await http.post("/auth/token", data=form)
        assert exchanged.status_code == 200
        bearer = exchanged.json()
        assert bearer["token_type"] == "Bearer" and bearer["expires_in"] == 172800
        assert (await http.post("/auth/token", data=form)).json()["error"] == "expired_token"
        for path in ("/", "/SKILL.md", "/llms.txt", "/.well-known/agent-card.json"):
            public = await http.get(path)
            assert bearer["access_token"] not in public.text and pairing["device_code"] not in public.text
        assert bearer["access_token"] not in caplog.text and pairing["device_code"] not in caplog.text
        clock[0] += 172801
        assert app.state.auth.authorize(bearer["access_token"]) is None


@pytest.mark.asyncio
async def test_served_skill_wire_example_and_schema_authority(system):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        guide = (await http.get("/SKILL.md")).text
        envelope, _ = documented_request(guide, "not-a-real-token")
        # Match the official SDK representation, but send the documentation's JSON itself.
        message = new_text_message('{"action":"hello"}', role=Role.ROLE_USER)
        message.message_id = envelope["params"]["message"]["messageId"]
        assert envelope["params"] == MessageToDict(SendMessageRequest(message=message))
        card = (await http.get("/.well-known/agent-card.json")).json()
        assert card["supportedInterfaces"] == [{"url": "http://localhost/a2a", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}]
        for email in (A, ADMIN):
            envelope, headers = documented_request(guide, credential(system, email))
            response = await http.post("/a2a", json=envelope, headers=headers)
            assert response.status_code == 200
            rpc = response.json()
            assert rpc["id"] == envelope["id"] and "error" not in rpc
            decoded = ParseDict(rpc["result"], SendMessageResponse())
            result = json.loads("".join(p["text"] for p in rpc["result"]["message"]["parts"]))
            assert result == json.loads(get_message_text(decoded.message))
            assert result["ok"] and result["identity"] == email and result["instructions"]
            tools = {t["action"]: t["input_schema"] for t in result["tools"]}
            assert ("admin_audit" in tools) == (email == ADMIN)
            assert tools["hello"]["properties"]["action"]["const"] == "hello"
        headers.pop("A2A-Version")
        version_error = (await http.post("/a2a", json=envelope, headers=headers)).json()
        assert version_error["error"]["code"] == -32009
        # Connection prose is not a second copy of registry schemas or workspace instructions.
        assert "input_schema" in guide and "Keep My Cubby small" not in guide


@pytest.mark.asyncio
async def test_documented_raw_http_tool_errors_and_revocation(system):
    app = create_app(system.settings, system.repo, system.drive)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        guide = (await http.get("/SKILL.md")).text
        envelope, headers = documented_request(guide, credential(system, A))
        async def invoke(tool):
            envelope["params"]["message"]["parts"][0]["text"] = json.dumps(tool)
            response = await http.post("/a2a", json=envelope, headers=headers)
            assert response.status_code == 200
            return json.loads(response.json()["result"]["message"]["parts"][0]["text"])
        assert not (await invoke({"action": "admin_audit"}))["ok"]
        assert (await invoke({"action": "revoke_agents"}))["ok"]
        assert (await http.post("/a2a", json=envelope, headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_google_browser_csrf_state_without_live_google(system):
    settings = system.settings
    settings.client_id, settings.client_secret = "client", "OAUTH_SECRET"
    settings.service_account, settings.token_key = "drive@example.iam.gserviceaccount.com", Fernet.generate_key().decode()
    app = create_app(settings, system.repo, system.drive)
    calls = []
    def google(request):
        calls.append(request)
        assert request.url.path == "/.well-known/openid-configuration"
        return httpx.Response(200, json={"issuer": "https://accounts.google.com",
            "authorization_endpoint": "https://accounts.google.com/authorize", "token_endpoint": "https://oauth2.googleapis.com/token",
            "jwks_uri": "https://accounts.google.com/jwks", "response_types_supported": ["code"], "id_token_signing_alg_values_supported": ["RS256"]})
    app.state.oauth.google.client_kwargs["transport"] = httpx.MockTransport(google)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://localhost") as http:
        pairing = (await http.post("/auth/device")).json()
        connect = await http.get("/connect?code=" + pairing["user_code"])
        csrf = re.search(r'name="csrf" value="([^"]+)"', connect.text)[1]
        assert (await http.post("/login", data={"csrf": csrf, "code": pairing["user_code"]}, headers={"Origin": "https://evil.example"})).status_code == 403
        login = await http.post("/login", data={"csrf": csrf, "code": pairing["user_code"]})
        assert login.status_code == 200 and "location" not in login.headers
        assert "form-action 'self';" in login.headers["content-security-policy"]
        assert "<form" not in login.text and "<script" not in login.text
        from html import unescape
        from urllib.parse import urlsplit, parse_qs
        authorization = unescape(re.search(r'<a href="([^"]+)"', login.text)[1])
        url = urlsplit(authorization)
        assert url.scheme == "https" and url.netloc == "accounts.google.com"
        params = parse_qs(url.query)
        assert params["state"][0] and params["nonce"][0]
        assert params["code_challenge_method"] == ["S256"] and params["code_challenge"][0]
        assert params["redirect_uri"] == [settings.url + "/auth/callback"]
        assert params["hd"] == [settings.domain]
        assert params["access_type"] == ["offline"]
        assert params["prompt"] == ["consent select_account"]
        # The discarded redirect response must still persist Authlib's session state.
        import base64
        session = json.loads(base64.b64decode(http.cookies["session"].split(".")[0]))
        state = session["_state_google_" + params["state"][0]]["data"]
        assert state["code_verifier"] and state["nonce"] == params["nonce"][0]
        import hashlib
        challenge = base64.urlsafe_b64encode(hashlib.sha256(state["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        assert params["code_challenge"] == [challenge]
        assert session["pairing"] == pairing["user_code"]
        callback = await http.get("/auth/callback?code=CODE_CANARY&state=wrong")
        assert "Connection wasn" in callback.text
        assert system.repo.get("pairings", digest(pairing["user_code"]))["email"] == ""
        assert "SECRET" not in str(http.cookies)
    assert len(calls) == 1  # Wrong state never reaches the token exchange.


def test_drive_setup_idempotent_and_reserved_delivery(monkeypatch, drive_adapter, system):
    user = {"email": A, "refresh_token": "sealed"}
    requests, created = [], [False]
    drive_adapter.settings.service_account = "service@example.com"
    def handler(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("/permissions"):
            return httpx.Response(200, json={"permissions": [{"id": "permission", "emailAddress": "service@example.com", "role": "writer"}]})
        if path.endswith("/files") and request.method == "GET":
            return httpx.Response(200, json={"files": [{"id": "folder"}]})
        if path.endswith("/folder"):
            return httpx.Response(200, json={"id": "folder", "mimeType": "application/vnd.google-apps.folder",
                "trashed": False, "owners": [{"emailAddress": A}]})
        if path.endswith("/reserved"):
            return httpx.Response(200, json=metadata()) if created[0] else httpx.Response(404)
        if request.method == "POST":
            created[0] = True
            assert b'"id": "reserved"' in request.content
            raise httpx.ReadTimeout("Ambiguous response after upload", request=request)
        raise AssertionError(str(request.url))
    mock_http(monkeypatch, handler)
    drive_adapter.setup(user)
    drive_adapter.setup(user)
    assert user["folder"] == "folder"
    assert not any(r.method == "POST" for r in requests)
    with pytest.raises(httpx.ReadTimeout):
        drive_adapter.deliver(user, "reserved", "note.json", "attributed text")
    drive_adapter.deliver(user, "reserved", "note.json", "attributed text")
    assert sum(r.method == "POST" for r in requests) == 1


@pytest.mark.parametrize("change", [
    {"name": "My research inbox"}, {"parents": ["another-owned-folder"]},
    {"name": "My research inbox", "parents": ["another-owned-folder"]},
])
def test_drive_saved_folder_survives_rename_and_move(monkeypatch, drive_adapter, system, change):
    user = system.repo.get("users", digest(A))
    user["folder"] = "folder"
    system.repo.put("users", digest(A), user)
    folder = {"id": "folder", "name": "My Cubby", "folderColorRgb": "#123456",
              "parents": ["root"], "mimeType": "application/vnd.google-apps.folder",
              "trashed": False, "owners": [{"emailAddress": A}]}
    child = metadata()
    requests = []
    drive_adapter.settings.service_account = "service@example.com"

    def handler(request):
        requests.append(request)
        assert request.method == "GET"  # No replacement or metadata reset allowed.
        path = request.url.path
        if path.endswith("/folder/permissions"):
            return httpx.Response(200, json={"permissions": [
                {"id": "permission", "emailAddress": "service@example.com", "role": "writer"}]})
        if path.endswith("/folder"):
            return httpx.Response(200, json=folder)
        if path.endswith("/files"):
            assert request.url.params["q"] == "'folder' in parents and trashed=false"
            return httpx.Response(200, json={"files": [child]})
        if path.endswith("/file"):
            return httpx.Response(200, text="hello") if request.url.params.get("alt") == "media" else httpx.Response(200, json=child)
        raise AssertionError(str(request.url))

    mock_http(monkeypatch, handler)
    drive_adapter.setup(user)
    cubby_before = call(system, A, "hello")["cubby"]
    before = drive_adapter.read(user, "file")
    folder.update(change)  # Simulate the owner's external Drive rename/move.
    expected_folder = deepcopy(folder)
    requests.clear()
    reloaded = system.repo.get("users", digest(A))
    assert drive_adapter.setup(reloaded) == user
    assert drive_adapter.list(reloaded)["files"] == [child]
    assert drive_adapter.read(reloaded, "file") == before
    assert folder == expected_folder
    assert reloaded["folder"] == system.repo.get("users", digest(A))["folder"] == "folder"
    assert all(r.method == "GET" for r in requests)
    assert call(system, A, "hello")["cubby"] == cubby_before == {
        "folder_id": "folder", "folder_url": "https://drive.google.com/drive/folders/folder"}


@pytest.mark.parametrize("failure", [403, 404, {"trashed": True},
    {"mimeType": "text/plain"}, {"owners": [{"emailAddress": B}]}])
def test_drive_unavailable_saved_folder_never_replaced(monkeypatch, drive_adapter, system, failure):
    user = {"email": A, "folder": "folder", "refresh_token": "sealed"}
    system.repo.put("users", digest(A), user)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET" and request.url.path.endswith("/files/folder")
        if isinstance(failure, int):
            return httpx.Response(failure, text="PRIVATE_GOOGLE_ERROR")
        return httpx.Response(200, json={"trashed": False, "mimeType": "application/vnd.google-apps.folder",
            "owners": [{"emailAddress": A}], **failure})

    mock_http(monkeypatch, handler)
    with pytest.raises(Fault) as exc:
        drive_adapter.setup(user)
    message = str(exc.value)
    assert "reconnect" in message and "No replacement folder was created" in message
    assert "PRIVATE_GOOGLE_ERROR" not in message
    if failure == 404:
        assert "permanently deleted" in message and "administrator" in message
    assert len(requests) == 1
    assert system.repo.get("users", digest(A)) == user


@pytest.mark.parametrize("role", [None, "reader", "writer"])
def test_drive_reconnect_restores_sharing_without_replacing_folder(monkeypatch, drive_adapter, system, role):
    user = {"email": A, "folder": "folder", "refresh_token": "sealed"}
    system.repo.put("users", digest(A), user)
    drive_adapter.settings.service_account = "service@example.com"
    requests = []

    def handler(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("/folder"):
            return httpx.Response(200, json={"id": "folder", "trashed": False,
                "mimeType": "application/vnd.google-apps.folder", "owners": [{"emailAddress": A}]})
        if request.method == "GET" and path.endswith("/permissions"):
            return httpx.Response(200, json={"permissions": [] if role is None else [
                {"id": "permission", "emailAddress": "service@example.com", "role": role}]})
        assert request.headers["authorization"] == "Bearer OWNER_SECRET"
        assert json.loads(request.content)["role"] == "writer"
        assert (request.method, path) == (("POST", "/drive/v3/files/folder/permissions") if role is None else
                                         ("PATCH", "/drive/v3/files/folder/permissions/permission"))
        return httpx.Response(200, json={"id": "permission"})

    mock_http(monkeypatch, handler)
    assert drive_adapter.setup(user) == user
    assert sum(r.method != "GET" for r in requests) == (role != "writer")
    assert requests[-1].headers["authorization"] == "Bearer SERVICE_SECRET"
    assert system.repo.get("users", digest(A)) == user


@pytest.mark.parametrize("stage", ["permissions", "service"])
def test_drive_sharing_failure_does_not_replace_saved_folder(monkeypatch, drive_adapter, system, stage):
    user = {"email": A, "folder": "folder", "refresh_token": "sealed"}
    system.repo.put("users", digest(A), user)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        if request.url.path.endswith("/permissions"):
            if stage == "permissions":
                return httpx.Response(403)
            return httpx.Response(200, json={"permissions": [
                {"id": "permission", "emailAddress": drive_adapter.settings.service_account, "role": "writer"}]})
        if request.headers["authorization"] == "Bearer SERVICE_SECRET":
            return httpx.Response(404)
        return httpx.Response(200, json={"trashed": False, "mimeType": "application/vnd.google-apps.folder",
            "owners": [{"emailAddress": A}]})

    mock_http(monkeypatch, handler)
    with pytest.raises(Fault, match="Check account connection and folder sharing"):
        drive_adapter.setup(user)
    assert system.repo.get("users", digest(A)) == user
    assert all(r.method == "GET" for r in requests)


def test_single_use_pairing_concurrent_exchange(system):
    from concurrent.futures import ThreadPoolExecutor
    auth = Auth(system.repo)
    device, code = auth.start()
    auth.approve(code, A)
    def exchange():
        try:
            return auth.exchange(code, device)
        except Fault:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: exchange(), range(2)))
    assert sum(r is not None for r in results) == 1
    assert sum(kind == "tokens" for kind, key in system.repo.data) == 1


def test_reconnect_cannot_overwrite_concurrent_revocation(system, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    s = system
    app = create_app(s.settings, s.repo, s.drive)
    old_token = credential(s, A)
    device, code = app.state.auth.start()
    setup_entered, finish_setup, revoke_attempted = threading.Event(), threading.Event(), threading.Event()
    original_setup, original_lock = s.drive.setup, s.repo.lock

    def setup(user):
        setup_entered.set()
        assert finish_setup.wait(5)
        return original_setup(user)

    @contextmanager
    def lock(key):
        if setup_entered.is_set():
            revoke_attempted.set()
        with original_lock(key):
            yield

    monkeypatch.setattr(s.drive, "setup", setup)
    monkeypatch.setattr(s.repo, "lock", lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reconnect = pool.submit(app.state.onboard, claims(), {}, code)
        try:
            assert setup_entered.wait(5)
            revocation = pool.submit(call, s, A, "revoke_agents")
            assert revoke_attempted.wait(5)
            assert not revocation.done()  # Waits for reconnect's whole-user write.
        finally:
            finish_setup.set()
        reconnect.result(timeout=5)
        assert revocation.result(timeout=5) == {"revoked": True}
    assert s.repo.get("users", digest(A))["generation"] == 1
    assert app.state.auth.authorize(old_token) is None


def test_partial_onboarding_is_not_connected_or_deliverable(system, monkeypatch):
    s = system
    app = create_app(s.settings, s.repo, s.drive)
    email = "partial@ucsc.edu"
    call(s, ADMIN, "admin_set_contributor", owner=email, email=B,
         managed_by="admin", reason="Before onboarding")
    device, code = app.state.auth.start()
    original_setup = s.drive.setup

    def setup(user):
        user = original_setup(user)
        s.repo.put("users", digest(user["email"]), user)
        return user

    def fail_starter(*args):
        raise RuntimeError("Starter upload failed")

    monkeypatch.setattr(s.drive, "setup", setup)
    monkeypatch.setattr(s.drive, "deliver", fail_starter)
    with pytest.raises(RuntimeError, match="Starter upload failed"):
        app.state.onboard(claims(email, "partial-sub"), {"refresh_token": "PRIVATE"}, code)
    partial = s.repo.get("users", digest(email))
    assert partial["folder"] and not partial.get("initialized")
    assert call(s, B, "can_contribute", email=email) == {"allowed": False}
    with pytest.raises(Fault, match="not permitted or recipient unavailable"):
        call(s, B, "contribute", to=email, subject="Note", body="Body", request_id="partial")
    with pytest.raises(Fault, match="Connect your Google account first"):
        s.user(email)
    users = call(s, ADMIN, "admin_list_users")["users"]
    assert next(u for u in users if u["email"] == email)["connected"] is False
    assert not any(kind == "deliveries" for kind, key in s.repo.data)
