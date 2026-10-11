"""Advocate: minimal sharing, resend round, verdicts, preference scoring, writes to the student box."""
import asyncio
import re

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
    # each trigger is named with its department: college E-02 is not ISO's E-02
    assert [t.split(":")[0] for t in after.brief["triggers"]] == ["ISO E-02", "ISO E-03"]
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


def fake_dept(units, authority, cites=("F-01",), escalate=False, basis=None, more=()):
    """A department recommending `units` first; `more` adds further (units) options after it."""
    async def call(session_id, question, context):
        first = {"option": f"{units} units", "conditions": [], "cites": list(cites), "units": units, "hours": None, "weeks": 0}
        if basis:
            first["basis"] = basis
        rest = [{"option": f"{u} units", "conditions": [], "cites": list(cites), "units": u, "hours": None, "weeks": 0} for u in more]
        return {"scope": "in_scope", "answer": f"Take {units} units [F-01].", "cites": list(cites), "needs": [],
                "options": [first] + rest, "escalate": escalate, "authority": authority, "confidence": 0.9}
    return call


def test_disputed_at_equal_authority_and_precedence_otherwise(store, tmp_path):
    # a second department whose box is the ISO box under another name
    store.write("registrar", store.load("iso").text)
    # the authority behind a position is that of the facts its recommended option cites (F-07 is department level, F-01 federal)
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "campus", cites=("F-07",)), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    v = adv.ask_sync("How few units can I take?", "s13")
    assert v.kind == "DISPUTED" and v.brief["disputed"] and v.brief["decides"] == ["ISO", "REGISTRAR"]
    assert v.best["units"] == 6  # preferences still rank the pooled options
    assert any("DISPUTED" in l for l in store.load("student").section(6).lines)
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01",)), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    v = adv.ask_sync("How few units can I take?", "s14")
    assert v.kind == "CONVERGED" and v.brief["precedence"] == ["ISO wins by authority_order (federal) over REGISTRAR (department)"]
    # the recorded best option comes from the office whose position stands, even though the student
    # prefers fewer units: the overruled office's menu cannot win what its position lost
    assert v.best["units"] == 12 and [o["dept"] for o in v.options] == ["iso"]
    assert "| 12 units |" in [l for l in store.load("student").section(5).lines if "s14" in l][0]
    # quoting a federal rule in passing does not lift a department-level recommendation
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01",)), "registrar": fake_dept(6, "federal", cites=("F-07",))})
    assert adv.ask_sync("How few units can I take?", "s15").kind == "CONVERGED"


def test_position_is_the_recommendation_and_basis_sets_its_authority(store):
    store.write("registrar", store.load("iso").text)
    # Both offices list a 6-unit option too, which the student's preferences (fewer units) would rank
    # first; the positions compared are still what each office recommends (12 vs 6): a dispute.
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "campus", cites=("F-07",), more=(6,)), "registrar": fake_dept(6, "campus", cites=("F-07",), more=(12,))})
    v = adv.ask_sync("How few units can I take?", "s16")
    assert v.kind == "DISPUTED" and v.best["units"] == 6
    # A recommendation that cites a federal rule in passing but rests on department practice (basis F-07)
    # stays department level: equal to the other office, so disputed rather than a win by authority.
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01", "F-07"), basis="F-07"), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    assert adv.ask_sync("How few units can I take?", "s17").kind == "DISPUTED"
    # The same cites with the federal rule as the basis: ISO wins.
    adv = Advocate(store=store, depts={"iso": fake_dept(12, "federal", cites=("F-01", "F-07"), basis="F-01"), "registrar": fake_dept(6, "campus", cites=("F-07",))})
    v = adv.ask_sync("How few units can I take?", "s18")
    assert v.kind == "CONVERGED" and v.brief["precedence"][0].startswith("ISO wins by authority_order (federal)")


def test_default_advocate_builds_iso_in_process(store):
    adv = default_advocate(store=store, brain=ScriptedBrain(default=answer()))
    assert list(adv.depts) == ["iso"] and adv.ask_sync("q").kind == "CONVERGED"


def test_declined_ask_field_is_sent_as_not_shared_and_does_not_stall(store):
    adv, brain = advocate_with(store, answer(needs=["hours"], options=[]), answer())
    v = adv.ask_sync("Can I add 12 hours?", "s16", declined={"hours"})
    assert v.kind == "CONVERGED" and v.ask == []            # no ASK_STUDENT: the student already said no
    assert context_of(brain, 0)["hours"] == "not shared"    # the department was told it was withheld
    assert v.depts[0].blocked == ["hours"]


def scripted_dept(dept, store, answers):
    """A department gremlin that returns the given answers in order (each a dict for one call)."""
    brain = ScriptedBrain(list(answers), default=answers[-1])
    return in_process(DeptGremlin(dept, store=store, brain=brain)), brain


def position(units, text, cites=("F-01",), **extra):
    a = {"scope": "in_scope", "answer": text, "cites": list(cites), "needs": [],
         "options": [{"option": f"{units} units", "conditions": [], "cites": list(cites), "units": units, "hours": None, "weeks": 0}],
         "confidence": 0.9}
    a.update(extra)
    return a


def test_referral_pulls_a_named_office_into_round_two(store):
    # ISO's box names financial aid as the office that decides the money side: with `deliberate`
    # the finaid gremlin joins round 2 and sees ISO's cited position, but not ISO's student fields.
    # the registrar's box advertises topics nothing here matches, so it is never in scope by itself
    text = store.load("iso").text
    text = re.sub(r"^topics: .*$", "topics: zzz-never-asked", text, flags=re.M) if "\ntopics:" in text else text.replace("\n", "\ntopics: zzz-never-asked\n", 1)
    store.write("registrar", text)
    iso, iso_brain = scripted_dept("iso", store, [position(12, "Stay at 12 [F-01].", refers=["registrar", "finaid"])])
    reg, reg_brain = scripted_dept("registrar", store, [position(12, "Fine at 12 [F-01].")])
    adv = Advocate(store=store, depts={"iso": iso, "registrar": reg})
    plain = adv.ask_sync("How few units can I take?", "s20")
    assert [r.dept for r in plain.depts] == ["iso"] and not plain.transcript      # no deliberation: registrar out of scope
    adv = Advocate(store=store, depts={"iso": scripted_dept("iso", store, [position(12, "Stay at 12 [F-01].", refers=["registrar", "finaid"])])[0], "registrar": reg})
    v = adv.ask_sync("How few units can I take?", "s21", deliberate=True)
    # finaid is not an office this student's permissions table knows (nor one this advocate runs): ignored
    assert [r.dept for r in v.depts] == ["iso", "registrar"] and v.kind == "CONVERGED"
    # round 1, the referral, then both answer each other (they agree, and say so)
    assert [(t["dept"], t["round"], t["kind"]) for t in v.transcript] == [("iso", 1, "position"), ("registrar", 2, "referral"), ("iso", 3, "reconsider"), ("registrar", 3, "reconsider")]
    assert v.transcript[1]["invited_by"] == ["iso"] and v.brief["deliberation"][0] == "REGISTRAR joined at ISO's request"
    assert v.transcript[2]["heard"] == ["registrar"] and v.transcript[3]["heard"] == ["iso"]
    prompt = reg_brain.calls[0]["user"]
    assert "other offices' positions" in prompt and "ISO (federal): 12 units [F-01]" in prompt and "reconsider" not in prompt
    assert "Riya" not in prompt and "Asha" not in prompt
    assert any("DELIBERATION" in l and "registrar:referral" in l for l in store.load("student").section(4).lines)


def test_reconsider_round_converges_or_keeps_the_dispute(store):
    store.write("registrar", store.load("iso").text)
    # round 1: ISO 12 vs REGISTRAR 6 at equal (department) authority; round 3: the registrar revises to 12
    def pair():
        iso, _ = scripted_dept("iso", store, [position(12, "Twelve [F-07].", cites=("F-07",)), position(12, "Holding: twelve [F-07].", cites=("F-07",), stance="hold")])
        reg, reg_brain = scripted_dept("registrar", store, [position(6, "Six [F-07].", cites=("F-07",)), position(12, "Agreed, twelve [F-07].", cites=("F-07",), stance="revise")])
        return Advocate(store=store, depts={"iso": iso, "registrar": reg}), reg_brain
    adv, _ = pair()
    assert adv.ask_sync("How few units can I take?", "s22").kind == "DISPUTED"          # without deliberation
    adv, reg_brain = pair()
    turns = []
    v = asyncio.run(adv.ask("How few units can I take?", "s23", deliberate=True, on_turn=turns.append))
    assert v.kind == "CONVERGED" and v.best["units"] == 12
    assert [(t["dept"], t["round"], t["kind"], t.get("stance")) for t in v.transcript] == [
        ("iso", 1, "position", None), ("registrar", 1, "position", None), ("iso", 3, "reconsider", "hold"), ("registrar", 3, "reconsider", "revise")]
    assert turns == v.transcript and v.brief["deliberation"] == ["ISO hold", "REGISTRAR revise"]
    reconsider_prompt = reg_brain.calls[1]["user"]
    assert "reconsider:" in reconsider_prompt and "ISO (department): 12 units [F-07]" in reconsider_prompt
    # both hold: the dispute is kept, with the stances recorded
    iso, _ = scripted_dept("iso", store, [position(12, "Twelve [F-07].", cites=("F-07",)), position(12, "Twelve [F-07].", cites=("F-07",), stance="hold")])
    reg, _ = scripted_dept("registrar", store, [position(6, "Six [F-07].", cites=("F-07",)), position(6, "Six [F-07].", cites=("F-07",), stance="hold")])
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("How few units can I take?", "s24", deliberate=True)
    assert v.kind == "DISPUTED" and v.brief["deliberation"] == ["ISO hold", "REGISTRAR hold"] and v.brief["decides"] == ["ISO", "REGISTRAR"]


def test_outranked_office_gets_a_reconsider_turn_too(store):
    store.write("registrar", store.load("iso").text)
    # ISO (federal) outranks the registrar (department) in round 1; in round 3 the registrar agrees
    iso, _ = scripted_dept("iso", store, [position(12, "Twelve [F-01].", cites=("F-01",)), position(12, "Twelve [F-01].", cites=("F-01",), stance="hold")])
    reg, _ = scripted_dept("registrar", store, [position(6, "Six [F-07].", cites=("F-07",)), position(12, "Agreed, twelve [F-01].", cites=("F-01",), stance="agree")])
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("How few units can I take?", "s25", deliberate=True)
    assert v.kind == "CONVERGED" and v.best["units"] == 12 and "precedence" not in v.brief   # they now agree outright
    assert [(t["dept"], t["round"], t.get("stance")) for t in v.transcript][2:] == [("iso", 3, "hold"), ("registrar", 3, "agree")]
    assert v.brief["deliberation"] == ["ISO hold", "REGISTRAR agree"]


def test_serves_keeps_a_major_office_out_of_another_majors_question(store):
    from advocate import serves
    from box import parse_box
    # the registrar box serves game-design majors only; this student's major is TIM
    text = store.load("iso").text.replace("\n", "\nserves: major ~ game design|computational media\n", 1)
    store.write("registrar", text)
    store.set_field("student", "major", "Technology and Information Management")
    student = store.load("student")
    assert serves("major ~ game design|computational media", student) is False
    assert serves("", student) is True
    assert serves("quarters_to_graduation <= 2", student) is True     # field not filled in: cannot tell, so consulted
    iso, _ = scripted_dept("iso", store, [position(12, "Twelve [F-01].")])
    reg, _ = scripted_dept("registrar", store, [position(6, "Six [F-07].", cites=("F-07",))])
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("How few units can I take?", "s26")
    assert [r.dept for r in v.depts] == ["iso"]
    store.set_field("student", "major", "Computer Science: Computer Game Design")
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("How few units can I take?", "s27")
    assert [r.dept for r in v.depts] == ["iso", "registrar"]
    # a TIM major asking about one of the office's courses is served too (department to department, class to class)
    store.set_field("student", "major", "Technology and Information Management")
    text = store.load("registrar").text.replace("serves: major ~ game design|computational media", "serves: major ~ game design|computational media or question ~ \\bCMPM\\b")
    store.write("registrar", text)
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("Can I add CMPM 120 and still take few units?", "s28")
    assert [r.dept for r in v.depts] == ["iso", "registrar"]
    v = Advocate(store=store, depts={"iso": iso, "registrar": reg}).ask_sync("How few units can I take?", "s29")
    assert [r.dept for r in v.depts] == ["iso"]
