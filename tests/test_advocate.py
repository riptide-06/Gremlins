"""Advocate: minimal sharing, resend round, verdicts, preference scoring, writes to the student box."""
import asyncio

import pytest

from advocate import Advocate, DeptGremlin, default_advocate, in_process, score_options
from brain import ScriptedBrain
from conftest import good_answer
from wall import approve


def answer(**over):
    a = good_answer(cites=["F-01", "F-02"], options=[
        {"option": "Academic-difficulty RCL to 6 units", "conditions": ["once per level"], "cites": ["F-04"], "units": 6, "hours": None, "weeks": 1},
        {"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(over)
    return a


_DEFAULT = object()


def advocate_with(store, *answers, default=_DEFAULT):
    brain = ScriptedBrain(list(answers), default=answer() if default is _DEFAULT else default)
    return Advocate(store=store, depts={"iso": in_process(DeptGremlin("iso", store=store, brain=brain))}), brain


def context_of(brain, i=0):
    import json
    user = brain.calls[i]["user"]
    return json.loads(user[user.index("{"):])


def test_converged_round_one_shares_only_relevant_yes_fields(store):
    adv, brain = advocate_with(store)
    v = adv.ask_sync("Can I drop from 16 to 9 units?", "s1")
    assert v.kind == "CONVERGED" and len(brain.calls) == 1
    ctx = context_of(brain)
    assert ctx["units"] == "16" and ctx["final_quarter"] == "no" and ctx["rcl_on_file"] == "no"
    assert "visa" not in ctx and "major" not in ctx                       # yes, but not mentioned by the ISO box
    assert "name" not in ctx and "email" not in ctx and ctx["gpa"] == "not shared"
    assert "hours" not in ctx                                              # ask, not approved
    assert v.shared == {"iso": ["level", "units", "final_quarter", "rcl_on_file"]}  # the ISO box mentions "program level"
    assert v.best["option"] == "Academic-difficulty RCL to 6 units"       # fewer units wins
    assert v.authority == "federal" and v.dropped == 0
    student = store.load("student")
    five = [l for l in student.section(5).lines if "CONVERGED" in l]
    assert len(five) == 1 and "s1" in five[0] and "Academic-difficulty" in five[0] and "F-04" in five[0]
    assert any("SESSION | s1 | CONVERGED" in l for l in student.section(4).lines)
    assert any("SHARED | iso | level,units,final_quarter,rcl_on_file | s1" in l for l in student.section(7).lines)
    assert [s for s, _ in v.written] == [5, 4]


def test_resend_round_adds_allowed_needs_once(store):
    adv, brain = advocate_with(store, answer(needs=["visa", "major"], options=[]), answer())
    v = adv.ask_sync("q", "s2")
    assert v.kind == "CONVERGED" and len(brain.calls) == 2
    assert "visa" not in context_of(brain, 0) and context_of(brain, 1)["visa"] == "F-1" and context_of(brain, 1)["major"] == "Computer Science"
    assert v.shared["iso"] == ["level", "units", "final_quarter", "rcl_on_file", "visa", "major"]
    shared_lines = [l for l in store.load("student").section(7).lines if "SHARED" in l]
    assert len(shared_lines) == 2


def test_needs_that_keep_coming_stop_after_one_resend(store):
    adv, brain = advocate_with(store, default=answer(needs=["visa"]))
    v = adv.ask_sync("q", "s3")
    assert len(brain.calls) == 2 and v.kind == "CONVERGED"


def test_ask_student_when_need_is_an_ask_field(store):
    adv, brain = advocate_with(store, answer(needs=["hours"], options=[]))
    v = adv.ask_sync("Can I work more and study less?", "s4")
    assert v.kind == "ASK_STUDENT" and v.ask == ["hours"] and len(brain.calls) == 1
    items = adv.open_items()
    assert items == [{"time": items[0]["time"], "session_id": "s4", "question": "Can I work more and study less?",
                      "fields": ["hours"], "dept": "iso"}]
    assert not [l for l in store.load("student").section(5).lines if l.strip()]


def test_ask_student_when_box_lacks_the_field(store):
    adv, _ = advocate_with(store, answer(needs=["days_to_deadline"], options=[]))   # a vocabulary field this box lacks
    v = adv.ask_sync("q", "s5")
    assert v.kind == "ASK_STUDENT" and v.ask == ["days_to_deadline"]


def test_approval_unblocks_and_is_read_fresh(store):
    adv, brain = advocate_with(store, answer(needs=["hours"], options=[]), answer())
    assert adv.ask_sync("q", "s6").kind == "ASK_STUDENT"
    approve(store, "student", "hours", "iso")
    v = adv.ask_sync("q", "s7")
    assert v.kind == "CONVERGED" and context_of(brain, 1)["hours"] == "10" and "hours" in v.shared["iso"]


def test_blocked_needs_do_not_block_the_verdict(store):
    adv, brain = advocate_with(store, answer(needs=["gpa", "name"]))
    v = adv.ask_sync("q", "s8")
    assert v.kind == "CONVERGED" and v.depts[0].blocked == ["gpa", "name"] and len(brain.calls) == 1


def test_escalated_brief_and_verdict_change_after_box_flip(store):
    adv, _ = advocate_with(store, default=answer())
    before = adv.ask_sync("Can I take 9 units?", "s9")
    assert before.kind == "CONVERGED"
    store.set_field("student", "final_quarter", "yes")
    store.set_field("student", "units", "9")
    after = adv.ask_sync("Can I take 9 units?", "s10")
    assert after.kind == "ESCALATED" and after.escalations == ["E-02", "E-03"]
    assert after.brief["decides"] == ["ISO"] and any("degree audit" in r for r in after.brief["resolve"])
    assert after.brief["agreed"] == ["ISO is the only department in scope"]
    six = [l for l in store.load("student").section(6).lines if "ESCALATED" in l]
    assert len(six) == 1 and "triggers=E-02,E-03" in six[0] and "decides=ISO" in six[0]
    assert [s for s, _ in after.written] == [6, 4]


def test_unanswered_when_brain_fails(store):
    adv, _ = advocate_with(store, default=None)
    v = adv.ask_sync("q", "s11")
    assert v.kind == "UNANSWERED" and v.written and v.written[0][0] == 4
    assert v.answer == "" and v.best is None


def test_rejected_leak_yields_unanswered(store):
    adv, _ = advocate_with(store, answer(answer="Riya Example, no [F-02].", options=[]))
    v = adv.ask_sync("q", "s12")
    assert v.kind == "UNANSWERED" and v.depts[0].inbound.rejected


def test_score_options_follows_preferences():
    opts = [{"option": "a", "units": 12, "hours": 20, "weeks": 1}, {"option": "b", "units": 6, "hours": 10, "weeks": 3},
            {"option": "c", "units": 6, "hours": 20, "weeks": 3}, {"option": "d", "units": None, "hours": None, "weeks": None}]
    assert [o["option"] for o in score_options(opts, ["fewer units", "more hours", "sooner"])] == ["c", "b", "a", "d"]
    assert [o["option"] for o in score_options(opts, ["sooner", "more units"])] == ["a", "b", "c", "d"]  # b and c tie
    assert [o["rank"] for o in score_options(opts, [])] == [1, 2, 3, 4]


def fake_dept(units, authority, cites=("F-01",), escalate=False):
    async def call(session_id, question, context):
        return {"scope": "in_scope", "answer": f"Take {units} units [F-01].", "cites": list(cites), "needs": [],
                "options": [{"option": f"{units} units", "conditions": [], "cites": list(cites), "units": units, "hours": None, "weeks": 0}],
                "escalate": escalate, "authority": authority, "confidence": 0.9}
    return call


def test_disputed_at_equal_authority_and_precedence_otherwise(store, tmp_path):
    # a second department whose box is the ISO box under another name
    store.write("registrar", store.load("iso").text)
    # the authority behind a position is that of the facts its best option cites (F-07 is department level, F-01 federal)
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "campus", cites=("F-07",)), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    v = adv.ask_sync("How few units can I take?", "s13")
    assert v.kind == "DISPUTED" and v.brief["disputed"] and v.brief["decides"] == ["ISO", "REGISTRAR"]
    assert v.best["units"] == 6  # preferences still rank the pooled options
    assert any("DISPUTED" in l for l in store.load("student").section(6).lines)
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01",)), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    v = adv.ask_sync("How few units can I take?", "s14")
    assert v.kind == "CONVERGED" and v.brief["precedence"] == ["ISO wins by authority_order (federal)"]
    # quoting a federal rule in passing does not lift a department-level recommendation
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01",)), "registrar": fake_dept(6, "federal", cites=("F-07",))})
    assert adv.ask_sync("How few units can I take?", "s15").kind == "CONVERGED"


def test_default_advocate_builds_iso_in_process(store):
    adv = default_advocate(store=store, brain=ScriptedBrain(default=answer()))
    assert list(adv.depts) == ["iso"] and adv.ask_sync("q").kind == "CONVERGED"
