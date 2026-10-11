"""Our service against Adam's actual Campus Cubbies code (prototypes/cubbies/cloud_app.py),
served offline on a local port with his test fakes for Firestore and Drive: the device
pairing, hello, the student box created and edited in the cubby through his A2A tools,
an advocate answer logged there, and MCP with the same bearer. No network, no Google."""
import json
import shutil
import socket
import threading
import time
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
import uvicorn

import cloud_app as campus                       # prototypes/cubbies, on the pytest pythonpath
from cubbies import Fault, digest, drive_folder_url
from test_cubbies import A, ADMIN, FakeDrive, MemoryRepo, claims   # Adam's offline fakes

from brain import ScriptedBrain
from conftest import good_answer
from gremlin_app import Settings, create_app

BOXES = Path(__file__).resolve().parent.parent / "docs" / "boxes"
API = {"X-Gremlin": "1", "Origin": "http://test"}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
REAL_TIME = time.time


class DriveLikeFake(FakeDrive):
    """Adam's FakeDrive with the wire shapes of his real cubby_drive.Drive (list entries,
    create result, revision-checked exact edits), which our box store relies on."""

    def create(self, user, name, text, file_id=None):
        if len(text.encode()) > 100000:
            raise Fault("File size limit is 100000 UTF-8 bytes.")
        file_id = file_id or self.allocate(user)
        self.deliver(user, file_id, name, text)
        return {"id": file_id, "name": name, "version": "1"}

    def list(self, user, cursor=""):
        return {"files": [{"id": k, "name": v["name"], "mimeType": "text/plain", "version": v["revision"]}
                          for k, v in self.files.items() if v["owner"] == user["email"] and not v.get("trashed")], "cursor": ""}

    def read(self, user, file_id):
        data = super().read(user, file_id)
        return {"file_id": file_id, "name": data["name"], "text": data["text"], "revision": data["revision"]}

    def edit(self, user, file_id, revision, search, replacement):
        data = self.files.get(file_id)
        if not data or data["owner"] != user["email"]:
            raise Fault("Only direct text-file children of your cubby are accessible.")
        if data["revision"] != revision:
            raise Fault("File changed. Read again before editing.")
        text = data["text"]
        first = text.find(search) if search else -1
        if first < 0 or text.find(search, first + 1) >= 0:
            raise Fault("Search text must match exactly once.")
        updated = text.replace(search, replacement, 1)
        if len(updated.encode()) > 100000:
            raise Fault("File size limit is 100000 UTF-8 bytes.")
        data["text"], data["revision"] = updated, str(int(revision) + 1)
        return {"id": file_id, "version": data["revision"]}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def clock(monkeypatch):
    """A clock that only moves forward from real time: safe for signed session cookies on both apps."""
    offset = {"s": 0.0}
    monkeypatch.setattr(time, "time", lambda: REAL_TIME() + offset["s"])
    return offset


@pytest.fixture
def campus_server(clock):
    repo, drive = MemoryRepo(), DriveLikeFake()
    port = free_port()
    origin = f"http://127.0.0.1:{port}"
    settings = campus.Settings(url=origin, project="test", session_secret="campus-secret-" + "x" * 20, local_http=True, admins=(ADMIN,))
    app = campus.create_app(settings, repo, drive)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "Campus Cubbies did not start"
    yield origin, app, repo, drive
    server.should_exit = True
    thread.join(5)


@pytest.fixture
def gremlins(campus_server, tmp_path):
    origin, campus_app, repo, drive = campus_server
    for name in ("iso", "cmpm", "college", "finaid", "student", "student.template"):
        shutil.copy(BOXES / f"{name}.md", tmp_path / f"{name}.md")
    answer = good_answer(cites=["F-01"], options=[{"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    settings = Settings(url="http://test", cubby_url=origin, session_secret="gremlin-secret-" + "y" * 20, local_http=True,
                        box_dir=str(tmp_path), demo_token="judge-token-123")
    app = create_app(settings, brain=ScriptedBrain(default=answer), cubby_http=httpx.Client(timeout=10))
    return app, campus_app, repo, drive


def a2a(http: httpx.Client, origin: str, token: str, request: dict) -> dict:
    """The documented raw Campus Cubbies call, independent of our client code."""
    body = {"jsonrpc": "2.0", "id": "t1", "method": "SendMessage",
            "params": {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": json.dumps(request)}]}}}
    r = http.post(origin + "/a2a", json=body, headers={"Authorization": "Bearer " + token, "A2A-Version": "1.0", "Accept": "application/json"})
    assert r.status_code == 200, r.text
    return json.loads("".join(p["text"] for p in r.json()["result"]["message"]["parts"]))


async def test_pairing_box_and_edits_against_campus_cubbies(gremlins, campus_server, clock):
    origin, campus_app, repo, drive = campus_server
    app = gremlins[0]
    async with app.state.mcp.session_manager.run(), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        # 1. pairing starts on Adam's real /auth/device and the approval page is on his origin
        started = (await http.post("/api/connect/start", headers=API)).json()
        assert started["verification_uri_complete"].startswith(origin + "/connect?code=") and started["interval"] == 5
        code = started["verification_uri_complete"].rsplit("code=", 1)[1]
        assert "device_code" not in started and started.get("user_code") in (None, code)   # the secret never reaches the browser
        # his /connect page really serves that code
        page = httpx.get(started["verification_uri_complete"])
        assert page.status_code == 200 and 'value="' + code + '"' in page.text
        # 2. before approval his server says authorization_pending (first poll goes through)
        assert (await http.post("/api/connect/poll", headers=API)).json()["status"] == "authorization_pending"
        # 3. the human approves: Adam's onboarding fixture (new UCSC user, cubby initialised with his two files)
        campus_app.state.onboard(claims(A), {"refresh_token": "PRIVATE"}, code)
        assert sorted(v["name"] for v in drive.files.values()) == ["Notes.md", "Start here.md"]
        clock["s"] += 5.5                                                    # past both poll intervals
        done = (await http.post("/api/connect/poll", headers=API)).json()
        assert done["status"] == "connected" and done["identity"] == A
        me = (await http.get("/api/me")).json()
        folder = repo.get("users", digest(A))["folder"]
        assert me["connected"] is True and me["demo"] is False and me["identity"] == A
        assert me["folder_url"] == drive_folder_url(folder)
        # 4. the student box was created in the cubby by his create_file tool, with the right header and no secrets
        names = {v["name"]: k for k, v in drive.files.items()}
        assert "gremlin-student.md" in names
        box_text = drive.files[names["gremlin-student.md"]]["text"]
        assert box_text.startswith("# Student box") or "department: student" in box_text
        assert "email: " + A in box_text and "PRIVATE" not in box_text and "sealed" not in box_text
        box = (await http.get("/api/box", headers=API)).json()
        assert box["location"] == "cubby:gremlin-student.md" and box["fields"]["email"] == A
        assert box["departments"] == ["ISO", "CMPM", "College", "FinAid"]
        # 5. a field change and a permission change are exact single-match edits through his edit_file
        r = (await http.post("/api/set", json={"field": "units", "value": "13"}, headers=API)).json()
        assert r.get("ok") is True, r
        r = (await http.post("/api/permission", json={"field": "gpa", "dept": "FinAid", "value": "no"}, headers=API)).json()
        assert r.get("ok") is True, r
        box = (await http.get("/api/box", headers=API)).json()
        assert box["fields"]["units"] == "13" and box["permissions"]["gpa"]["FinAid"] == "no"
        text = drive.files[names["gremlin-student.md"]]["text"]
        assert [l for l in text.splitlines() if l.startswith("units:")] == ["units: 13"]
        # 6. an answer: departments consulted, the session logged into the cubby file (his revision check passes)
        v = (await http.post("/api/ask", json={"question": "Can I drop to 12 units?"}, headers=API)).json()
        assert v["verdict"] in ("CONVERGED", "DISPUTED", "ESCALATED") and v["written"], v
        text = drive.files[names["gremlin-student.md"]]["text"]
        assert "| SESSION |" in text and "| SHARED |" in text and A not in text.split("## 4.")[1]   # logs never carry the identity
        assert int(drive.files[names["gremlin-student.md"]]["revision"]) >= 4   # seed + set + permission + log lines
        # 7. an approval is logged too, and shows up as an APPROVED line
        r = (await http.post("/api/approve", json={"field": "gpa", "dept": "cmpm"}, headers=API)).json()
        assert r["ok"] is True
        assert "| APPROVED | gpa | cmpm" in drive.files[names["gremlin-student.md"]]["text"]
        # 8. our MCP server accepts a Campus Cubbies bearer, validated by his hello. The session's
        # own token never leaves the server, so pair a second agent the documented way.
        device_code, user_code = campus_app.state.auth.start()
        campus_app.state.auth.approve(user_code, A)
        clock["s"] += 5.5
        bearer = campus_app.state.auth.exchange(user_code, device_code)["access_token"]
        hello = a2a(httpx.Client(timeout=10), origin, bearer, {"action": "hello"})
        assert hello["ok"] and hello["identity"] == A
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        mcp = await http.post("/mcp", json=init, headers={**MCP_HEADERS, "Authorization": "Bearer " + bearer})
        assert mcp.status_code == 200 and mcp.json()["result"]["serverInfo"]["name"] == "gremlin-advocate", mcp.text
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "my_box", "arguments": {}}}
        r = await http.post("/mcp", json=call, headers={**MCP_HEADERS, "Authorization": "Bearer " + bearer})
        assert r.status_code == 200 and "units: 13" in r.json()["result"]["content"][0]["text"]   # read from the cubby, not this server
        assert (await http.post("/mcp", json=init, headers={**MCP_HEADERS, "Authorization": "Bearer " + "z" * 43})).status_code == 401
        # 9. his revoke_agents kills the session token: the next call fails cleanly, not with a crash
        a2a(httpx.Client(timeout=10), origin, bearer, {"action": "revoke_agents"})
        r = await http.get("/api/box", headers=API)
        assert r.status_code == 401 and r.json()["reconnect"] is True
        assert (await http.get("/api/me")).json()["connected"] is False       # the session is gone: sign in again


async def test_cubby_unreachable_is_an_error_not_a_crash(tmp_path, clock):
    """Campus Cubbies down: pairing start and polls report it, the site still serves."""
    for name in ("iso", "cmpm", "college", "finaid", "student", "student.template"):
        shutil.copy(BOXES / f"{name}.md", tmp_path / f"{name}.md")
    dead = f"http://127.0.0.1:{free_port()}"
    settings = Settings(url="http://test", cubby_url=dead, session_secret="s" * 32, local_http=True, box_dir=str(tmp_path))
    app = create_app(settings, brain=ScriptedBrain(), cubby_http=httpx.Client(timeout=2))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/")).status_code == 200
        r = await http.post("/api/connect/start", headers=API)
        assert r.status_code == 503 and "error" in r.json()
        me = (await http.get("/api/me")).json()
        assert me["connected"] is False
