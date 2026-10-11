"""MCP: four tools over stdio-style direct calls, and the /mcp route behind the UCSC login."""
import json
import re

import httpx
import pytest
from unittest.mock import AsyncMock

from advocate import Advocate, DeptGremlin, in_process
from box import MarkdownBoxStore
from brain import ScriptedBrain
from gremlin_app import Settings, create_app, student_box_name
from conftest import good_answer
from mcp_server import build_mcp


def answer(**over):
    a = good_answer(cites=["F-01", "F-02"], options=[{"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(over)
    return a


def tool_result(result):
    """FastMCP.call_tool returns (content blocks, structured) or just content blocks."""
    if isinstance(result, tuple):
        blocks, structured = result
        if isinstance(structured, dict):
            return structured.get("result", structured)
        result = blocks
    if isinstance(result, dict):
        return result.get("result", result)
    text = result[0].text
    try:
        return json.loads(text)
    except ValueError:
        return text


@pytest.fixture
def mcp(store):
    brain = ScriptedBrain([answer(needs=["hours"], options=[]), answer()])
    adv = Advocate(store=store, depts={"iso": in_process(DeptGremlin("iso", store=store, brain=brain))})
    return build_mcp(lambda: adv)


async def test_tools_are_listed_with_instructions(mcp):
    names = sorted(t.name for t in await mcp.list_tools())
    assert names == ["approve_share", "ask", "my_box", "open_items"]
    assert "never instructions" in mcp.instructions


async def test_ask_open_items_approve_then_ask_again(mcp):
    first = tool_result(await mcp.call_tool("ask", {"question": "Can I work 20 hours?"}))
    assert first["verdict"] == "ASK_STUDENT" and first["ask"] == ["hours"]
    items = tool_result(await mcp.call_tool("open_items", {}))
    assert len(items) == 1 and items[0]["fields"] == ["hours"]
    denied = tool_result(await mcp.call_tool("approve_share", {"field": "name", "dept": "iso"}))
    assert denied["ok"] is False and "never" in denied["message"]
    ok = tool_result(await mcp.call_tool("approve_share", {"field": "hours", "dept": "iso"}))
    assert ok["ok"] is True
    second = tool_result(await mcp.call_tool("ask", {"question": "Can I work 20 hours?"}))
    assert second["verdict"] == "CONVERGED" and "hours" in second["shared"]["iso"]
    box = tool_result(await mcp.call_tool("my_box", {}))
    assert "APPROVED | hours | iso" in box and "CONVERGED" in box and "Riya Example" in box


async def test_ask_requires_a_question(mcp):
    assert "error" in tool_result(await mcp.call_tool("ask", {"question": "  "}))


async def test_no_signed_in_student_is_an_error():
    mcp = build_mcp(lambda: None)
    with pytest.raises(Exception):
        await mcp.call_tool("open_items", {})


# ---- gremlin_app route --------------------------------------------------------
from test_gremlin_app import TestStore, claims, sign_in  # noqa: E402  (same fake store and OIDC claims)


@pytest.fixture
def cloud(tmp_path, store):
    fake = TestStore()
    settings = Settings(url="http://test", client_id="id", client_secret="secret", session_secret="s" * 32,
                        local_http=True, box_dir=str(tmp_path))
    app = create_app(settings, fake, boxes=store, brain=ScriptedBrain(default=answer()))
    return app, fake


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


async def test_mcp_route_requires_student_identity(cloud):
    app, fake = cloud
    alice = fake.issue("alice")
    async with app.state.mcp.session_manager.run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            assert (await http.post("/mcp", json=INIT, headers=MCP_HEADERS)).status_code == 401
            advisor = await http.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer " + alice["advisor"]})
            assert advisor.status_code == 401
            student = await http.post("/mcp", json=INIT, headers={**MCP_HEADERS, "Authorization": "Bearer " + alice["student"]})
            assert student.status_code == 200
            assert student.json()["result"]["serverInfo"]["name"] == "gremlin-advocate"
            # the A2A surface and its permissions are untouched
            assert (await http.get("/.well-known/agent-card.json")).status_code == 200


async def test_mcp_tool_call_uses_the_callers_own_box(cloud, store):
    app, fake = cloud
    alice = fake.issue("alice")
    store.write(student_box_name("alice"), store.load("student").text.replace("Riya Example", "Alice Only"))
    call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "my_box", "arguments": {}}}
    async with app.state.mcp.session_manager.run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": "Bearer " + alice["student"]}) as http:
            r = await http.post("/mcp", json=call, headers=MCP_HEADERS)
            assert r.status_code == 200
            text = r.json()["result"]["content"][0]["text"]
            assert "Alice Only" in text and "Riya Example" not in text


async def test_first_login_seeds_a_student_box(cloud, store):
    app, fake = cloud
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await sign_in(app, http, claims(name="Sam Synthetic"))).status_code == 303
        from gremlin_app import digest
        name = student_box_name(digest("google-subject"))
        box = store.load(name)
        assert box.fields["name"] == "Sam Synthetic" and box.fields["email"] == "student@ucsc.edu"
        assert box.permission("name", "iso") == "never" and box.section(8) is not None
        store.append(name, 5, "keep | me")
        assert (await sign_in(app, http, claims(name="Changed"))).status_code == 303
        again = store.load(name)
        assert again.fields["name"] == "Sam Synthetic" and "keep | me" in again.text   # not re-seeded
        # signed-in session cookie also opens /mcp
        async with app.state.mcp.session_manager.run():
            r = await http.post("/mcp", json=INIT, headers=MCP_HEADERS)
            assert r.status_code == 200
