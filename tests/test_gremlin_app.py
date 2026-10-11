"""gremlin_app: the site, Campus Cubbies pairing, the student's box in their cubby, judge mode, MCP."""
import json
import shutil
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from brain import ScriptedBrain
from conftest import good_answer
from gremlin_app import Settings, create_app
from test_cubby_store import FakeCubbies

BOXES = Path(__file__).resolve().parent.parent / "docs" / "boxes"
API = {"X-Gremlin": "1", "Origin": "http://test"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


class FakeCampus(FakeCubbies):
    """FakeCubbies plus the pairing endpoints of prototypes/cubbies (device code, polled exchange)."""

    def __init__(self):
        super().__init__(token="cubby-" + "t" * 40)
        self.pending = {}
        self.approved = set()
        self.exchanged = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/auth/device":
            self.pending["DEV" + str(len(self.pending))] = "CODE1"
            return httpx.Response(200, json={"device_code": "DEV0", "user_code": "CODE1", "verification_uri": "https://cubby.test/connect",
                                             "verification_uri_complete": "https://cubby.test/connect?code=CODE1", "expires_in": 600, "interval": 1})
        if path == "/auth/token":
            form = parse_qs(request.content.decode())
            code, dev = form.get("user_code", [""])[0], form.get("device_code", [""])[0]
            if dev not in self.pending or self.pending[dev] != code:
                return httpx.Response(400, json={"error": "expired_token"})
            if code not in self.approved:
                return httpx.Response(400, json={"error": "authorization_pending"})
            if code in self.exchanged:
                return httpx.Response(400, json={"error": "expired_token"})
            self.exchanged.add(code)
            return httpx.Response(200, json={"access_token": self.token, "token_type": "Bearer", "expires_in": 172800})
        return super().handler(request)


def answer(**over):
    a = good_answer(cites=["F-01"], options=[{"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(over)
    return a


@pytest.fixture
def campus(tmp_path):
    for name in ("iso", "cmpm", "college", "finaid", "student", "student.template"):
        shutil.copy(BOXES / f"{name}.md", tmp_path / f"{name}.md")
    fake = FakeCampus()
    settings = Settings(url="http://test", cubby_url="https://cubby.test", session_secret="s" * 32, local_http=True,
                        box_dir=str(tmp_path), demo_token="judge-token-123")
    app = create_app(settings, brain=ScriptedBrain(default=answer()), cubby_http=httpx.Client(transport=httpx.MockTransport(fake.handler)))
    return app, fake, tmp_path


async def test_site_and_public_me(campus):
    app, fake, _ = campus
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        r = await http.get("/")
        assert r.status_code == 200 and "gremlin labs" in r.text and "script-src 'unsafe-inline'" in r.headers["content-security-policy"]
        me = (await http.get("/api/me")).json()
        assert me["connected"] is False and set(me["departments"]) == {"iso", "cmpm", "college", "finaid"} and me["demo_available"] is True
        assert (await http.post("/api/ask", json={"question": "q"}, headers=API)).status_code == 401
        assert (await http.get("/chat")).status_code == 303


async def test_pairing_flow_puts_the_box_in_the_cubby(campus):
    app, fake, _ = campus
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.post("/api/connect/start", json={})).status_code == 401       # needs the marker header
        start = (await http.post("/api/connect/start", json={}, headers=API)).json()
        assert start["user_code"] == "CODE1" and start["verification_uri_complete"] == "https://cubby.test/connect?code=CODE1"
        pending = (await http.post("/api/connect/poll", json={}, headers=API)).json()
        assert pending["status"] == "authorization_pending"
        fake.approved.add("CODE1")                                                      # the human approves on Campus Cubbies
        # the server respects the interval: an immediate second poll is answered locally as pending
        assert (await http.post("/api/connect/poll", json={}, headers=API)).json()["status"] == "authorization_pending"
        import asyncio
        await asyncio.sleep(1.5)                                                        # past the one-second interval, with slack
        done = (await http.post("/api/connect/poll", json={}, headers=API)).json()
        assert done["status"] == "connected" and done["identity"] == "demo@ucsc.edu" and done["created"] is True
        me = (await http.get("/api/me")).json()
        assert me["connected"] is True and me["demo"] is False and me["identity"] == "demo@ucsc.edu" and "drive.google.com" in me["folder_url"]
        # the student box is a file in the cubby, seeded from the template
        assert [f["name"] for f in fake.files.values()] == ["gremlin-student.md"]
        box = (await http.get("/api/box", headers=API)).json()
        assert box["location"] == "cubby:gremlin-student.md" and box["fields"]["email"] == "demo@ucsc.edu" and box["departments"] == ["ISO", "CMPM", "College", "FinAid"]
        # fill in a field, change a permission, ask: the verdict lands in the cubby file
        assert (await http.post("/api/set", json={"field": "units", "value": "17"}, headers=API)).json()["ok"] is True
        assert (await http.post("/api/permission", json={"field": "units", "dept": "ISO", "value": "yes"}, headers=API)).json()["ok"] is True
        assert (await http.post("/api/permission", json={"field": "name", "dept": "ISO", "value": "yes"}, headers=API)).status_code == 400
        v = (await http.post("/api/ask", json={"question": "Can I drop to 12 units?"}, headers=API)).json()
        assert v["verdict"] == "CONVERGED" and "units" in v["shared"]["iso"]
        text = list(fake.files.values())[0]["text"]
        assert "SESSION" in text and "CONVERGED" in text and "units: 17" in text
        assert "demo@ucsc.edu" not in json.dumps(v)
        # a declined ask-field is sent as not shared and never stalls the question
        v2 = (await http.post("/api/ask", json={"question": "Can I add 12 hours?", "declined": ["hours"]}, headers=API)).json()
        assert v2["verdict"] in ("CONVERGED", "UNANSWERED")
        # reset is not for real students
        assert (await http.post("/api/reset", json={}, headers=API)).status_code == 400
        assert (await http.post("/api/logout", json={}, headers=API)).json()["ok"] is True
        assert (await http.get("/api/me")).json()["connected"] is False


async def test_judge_mode(campus):
    app, fake, tmp_path = campus
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/demo?token=wrong")).headers["location"] == "/#nojudge"
        r = await http.get("/demo?token=judge-token-123")
        assert r.status_code == 303 and r.headers["location"] == "/#chat"
        me = (await http.get("/api/me")).json()
        assert me["connected"] is True and me["demo"] is True
        box = (await http.get("/api/box", headers=API)).json()
        assert "Asha Rao" in box["box"] and box["location"].endswith("student.md") and not box["location"].startswith("cubby:")
        v = (await http.post("/api/ask", json={"question": "Can I drop my 5-unit GE and go from 17 to 12 units?"}, headers=API)).json()
        assert v["verdict"] == "CONVERGED" and "Asha" not in json.dumps(v)
        assert (await http.post("/api/set", json={"field": "days_to_deadline", "value": "2"}, headers=API)).json()["ok"] is True
        v2 = (await http.post("/api/ask", json={"question": "Can I drop my 5-unit GE and go from 17 to 12 units?"}, headers=API)).json()
        assert v2["verdict"] == "ESCALATED" and "E-02" in v2["escalations"]
        reset = (await http.post("/api/reset", json={}, headers=API)).json()
        assert reset["ok"] is True and "student" in reset["restored"]
        after = (await http.get("/api/box", headers=API)).json()["box"]
        assert "SESSION" not in after and "days_to_deadline: 9" in after
        assert not fake.calls                                                 # judge mode never touches Campus Cubbies


async def test_mcp_with_a_campus_cubbies_bearer(campus):
    app, fake, _ = campus
    fake.files["id1"] = {"name": "gremlin-student.md", "text": (BOXES / "student.md").read_text(), "version": 1}
    async with app.state.mcp.session_manager.run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            assert (await http.post("/mcp", json=INIT, headers=MCP_HEADERS)).status_code == 401
            bad = await http.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer " + "x" * 40})
            assert bad.status_code == 401
            ok = await http.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer " + fake.token})
            assert ok.status_code == 200 and ok.json()["result"]["serverInfo"]["name"] == "gremlin-advocate"
            call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "my_box", "arguments": {}}}
            r = await http.post("/mcp", json=call, headers={**MCP_HEADERS, "Authorization": "Bearer " + fake.token})
            assert r.status_code == 200 and "Asha Rao" in r.json()["result"]["content"][0]["text"]
            assert "hello" in fake.calls and "read_file" in fake.calls


async def test_demo_word_streams_the_offices_turns(campus):
    app, fake, tmp_path = campus
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        await http.get("/demo?token=judge-token-123")
        # the word demo turns deliberation on and is dropped from the question
        v = (await http.post("/api/ask", json={"question": "demo: can I drop to 12 units?"}, headers=API)).json()
        assert v["deliberated"] is True and v["question"] == "can I drop to 12 units?"
        assert [t["kind"] for t in v["transcript"]] and all(t["round"] == 1 for t in v["transcript"])
        # the same over server-sent events: turns as they happen, then the verdict
        async with http.stream("POST", "/api/ask_stream", json={"question": "Can I drop to 12 units?"}, headers=API) as r:
            assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
            body = (await r.aread()).decode()
        events = [blk.split("\n", 1) for blk in body.strip().split("\n\n")]
        kinds = [e[0].removeprefix("event: ") for e in events]
        assert kinds[0] == "open" and kinds[-1] == "verdict" and "turn" in kinds
        verdict = json.loads(events[-1][1].removeprefix("data: "))
        assert verdict["deliberated"] is True and verdict["verdict"] in ("CONVERGED", "DISPUTED", "ESCALATED", "ASK_STUDENT", "UNANSWERED")
        turn = json.loads(next(e for e in events if e[0] == "event: turn")[1].removeprefix("data: "))
        assert {"dept", "round", "kind", "position", "cites", "authority", "text"} <= set(turn)
        assert (await http.post("/api/ask_stream", json={"question": ""}, headers=API)).status_code == 400
    # nobody signed in: denied
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.post("/api/ask_stream", json={"question": "x"}, headers=API)).status_code == 401
