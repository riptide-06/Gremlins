"""MCP: four tools over stdio-style direct calls, and the /mcp route behind the UCSC login."""
import json
import re

import httpx
import pytest
from unittest.mock import AsyncMock

from advocate import Advocate, DeptGremlin, in_process
from box import MarkdownBoxStore
from brain import ScriptedBrain
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


# The /mcp route of gremlin_app (session cookie, Campus Cubbies bearer, judge mode) is covered in test_gremlin_app.py.
