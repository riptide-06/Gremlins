"""Department gremlin: box-only prompts, cite filtering, code-decided escalation, pointer logs."""
import json

import httpx

from brain import ScriptedBrain
from conftest import good_answer
from dept_gremlin import ANSWER_KEYS, DeptGremlin, ask_dept, build_app, empty_answer, validate_answer


def test_answer_contract_and_cite_filtering(store):
    brain = ScriptedBrain([good_answer()])
    g = DeptGremlin("iso", store=store, brain=brain)
    out = g.answer("s-1", "Can I drop to 8 units?", {"units": "16", "final_quarter": "no", "rcl_on_file": "no"})
    assert tuple(out) == ANSWER_KEYS
    assert out["cites"] == ["F-01", "F-02", "Q-01"]          # F-99 does not exist
    assert out["escalate"] is False and out["authority"] == "federal"
    assert [o["cites"] for o in out["options"]] == [["F-04"], ["F-01"], []]  # F-77 dropped, option kept for the wall to count
    assert out["confidence"] == 0.8 and out["scope"] == "in_scope"


def test_escalation_is_decided_by_code_from_triggers(store):
    g = DeptGremlin("iso", store=store, brain=ScriptedBrain(default=good_answer(cites=["F-07"])))
    calm = g.answer("s-2", "Can I drop a class?", {"units": "16", "final_quarter": "no", "rcl_on_file": "no"})
    assert calm["escalate"] is False and calm["authority"] == "department"
    hot = g.answer("s-3", "Can I drop a class?", {"units": "9", "final_quarter": "yes", "rcl_on_file": "no"})
    assert hot["escalate"] is True and set(hot["cites"]) >= {"E-02", "E-03", "F-07"}
    medical = g.answer("s-4", "I have a medical condition and need fewer units", {"units": "16"})
    assert medical["escalate"] is True and "E-01" in medical["cites"]


def test_prompt_is_built_from_the_box_only_and_never_from_history(store):
    brain = ScriptedBrain(default=good_answer())
    g = DeptGremlin("iso", store=store, brain=brain)
    g.answer("s-1", "FIRST QUESTION", {"units": "16"})
    g.answer("s-2", "SECOND QUESTION", {"units": "16"})
    first, second = brain.calls
    assert "F-01" in first["system"] and "8 CFR" in first["system"]
    assert "FIRST QUESTION" in first["user"] and "FIRST QUESTION" not in second["user"]
    assert "FIRST QUESTION" not in second["system"]
    assert first["system"] == second["system"]  # same box, same system prompt, no state


def test_box_is_reloaded_fresh_each_session(store):
    brain = ScriptedBrain(default=good_answer())
    g = DeptGremlin("iso", store=store, brain=brain)
    g.answer("s-1", "q", {})
    store.write("iso", store.load("iso").text.replace("F-01 | F-1 undergraduates", "F-01 | CHANGED RULE"))
    g.answer("s-2", "q", {})
    assert "CHANGED RULE" not in brain.calls[0]["system"] and "CHANGED RULE" in brain.calls[1]["system"]


def test_session_log_holds_pointers_only(store):
    g = DeptGremlin("iso", store=store, brain=ScriptedBrain(default=good_answer(needs=["hours"])))
    g.answer("sess-42", "My name is Riya and I want to drop to 9 units", {"units": "9", "rcl_on_file": "no"})
    lines = [l for l in store.load("iso").section(5).lines if l.strip()]
    assert len(lines) == 1
    cells = lines[0].split(" | ")
    assert cells[1] == "SESSION" and cells[2] == "sess-42" and cells[3] == "in_scope"
    assert "F-01" in cells[4] and "E-03" in cells[4] and cells[5] == "hours" and cells[6] == "escalate"
    assert "Riya" not in lines[0] and "drop" not in lines[0]


def test_brain_failure_gives_safe_empty_answer_but_still_escalates(store):
    g = DeptGremlin("iso", store=store, brain=ScriptedBrain(default=None))
    out = g.answer("s-1", "q", {"units": "6", "rcl_on_file": "no"})
    assert out["answer"] == "" and out["options"] == [] and out["confidence"] == 0.0
    assert out["escalate"] is True and out["cites"] == ["E-03"] and out["authority"] == ""
    assert "brain_failed" in [l for l in store.load("iso").section(5).lines if l.strip()][0]
    assert tuple(empty_answer()) == ANSWER_KEYS


def test_malformed_model_output_is_clamped(store):
    raw = good_answer(confidence=7, options=[{"option": "x", "conditions": [], "cites": ["F-01"], "units": "12"}, "junk"],
                      needs=["a", "a", "", 3], scope="weird")
    out = validate_answer(raw, store.load("iso"), [])
    assert out["confidence"] == 1.0 and out["needs"] == ["a"] and out["scope"] == "out_of_scope"
    assert len(out["options"]) == 1 and out["options"][0]["units"] is None


async def test_a2a_round_trip_and_hello_guide(store):
    g = DeptGremlin("iso", store=store, brain=ScriptedBrain(default=good_answer()))
    app = build_app(g, "http://test")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        card = (await http.get("/.well-known/agent-card.json")).json()
        assert card["skills"][0]["id"] == "answer" and "identity" in card["description"]
        out = await ask_dept("http://test", "s-a2a", "Can I drop to 8?", {"units": "8", "rcl_on_file": "no"}, http=http)
        assert out["ok"] and out["escalate"] is True and out["cites"][:2] == ["F-01", "F-02"]
        assert set(ANSWER_KEYS) <= set(out)
        hello = await ask_dept("http://test", "s", "", {}, http=http)  # no question -> guide
        assert hello["guide"]["skill"] == "answer"
    logged = [l for l in store.load("iso").section(5).lines if l.strip()]
    assert any("s-a2a" in l for l in logged)
