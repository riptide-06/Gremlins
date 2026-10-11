"""The wall: permissions outbound, cite verification inbound, red-team leak rejection."""
from conftest import good_answer
from wall import approve, approved_fields, inbound, log_shared, outbound, redact


def test_outbound_applies_yes_no_ask_never(store):
    s = store.load("student")
    out = outbound(s, "iso", "Can I drop to 9 units?")
    assert out.context["units"] == "16" and out.context["visa"] == "F-1"
    assert out.context["gpa"] == "not shared" and "gpa" in out.withheld
    assert "hours" not in out.context and out.ask == ["hours"]
    assert "name" not in out.context and "email" not in out.context  # never: not even mentioned
    assert "not shared" not in (out.context.get("name"), out.context.get("email"))
    assert set(out.shared) == {"visa", "level", "units", "first_quarter", "final_quarter", "rcl_on_file", "major", "expected_graduation"}


def test_outbound_is_per_department(store):
    s = store.load("student")
    reg = outbound(s, "registrar", "q")
    assert reg.context["visa"] == "not shared" and reg.ask == ["gpa"] and reg.context["hours"] == "not shared"
    assert "rcl_on_file" in reg.withheld and "name" not in reg.context


def test_outbound_redacts_protected_values_from_the_question(store):
    s = store.load("student")
    out = outbound(s, "iso", "Hi, I'm Riya Example (rexample@ucsc.edu), GPA 3.4, can I drop?")
    assert "Riya" not in out.question and "rexample" not in out.question and "3.4" not in out.question
    assert out.question == "Hi, I'm [redacted] ([redacted]), GPA [redacted], can I drop?"
    assert set(out.redacted) == {"name", "email", "gpa"}
    assert redact("nothing here", {"name": "Riya"}) == ("nothing here", [])


def test_approval_turns_ask_into_yes_and_is_logged(store):
    assert approve(store, "student", "hours", "iso") is True
    assert approve(store, "student", "hours", "iso") is True       # idempotent
    assert approve(store, "student", "name", "iso") is False       # never cannot be approved
    assert approve(store, "student", "units", "iso") is False      # already yes
    s = store.load("student")
    assert approved_fields(s, "iso") == {"hours"} and approved_fields(s, "registrar") == set()
    out = outbound(s, "iso", "q")
    assert out.context["hours"] == "10" and out.ask == []
    lines = [l for l in s.section(7).lines if "APPROVED" in l]
    assert len(lines) == 1


def test_log_shared_writes_section_7(store):
    s = store.load("student")
    out = outbound(s, "iso", "q")
    log_shared(store, "student", out, "sess-9")
    line = [l for l in store.load("student").section(7).lines if "SHARED" in l][0]
    cells = [c.strip() for c in line.split("|")]
    assert cells[1:3] == ["SHARED", "iso"] and "units" in cells[3] and cells[4] == "sess-9"
    assert "16" not in line  # fields, not values


def test_inbound_drops_and_counts_uncited_claims(store):
    iso, s = store.load("iso"), store.load("student")
    answer = good_answer(answer="You need an RCL first [F-02]. Everyone says so. Medical RCL allowed [F-03].",
                         cites=["F-02", "F-03", "F-99", "Z-1"])
    answer.update(escalate=False, authority="federal")
    res = inbound(answer, iso, s, "iso")
    assert not res.rejected
    assert res.answer["cites"] == ["F-02", "F-03"]
    assert res.answer["answer"] == "You need an RCL first [F-02]. Medical RCL allowed [F-03]."
    assert [o["option"] for o in res.answer["options"]] == ["Academic-difficulty RCL to 6 units", "Stay at 12 units"]
    assert res.dropped == 2 + 1 + 1   # two bad cites, one uncited option, one uncited sentence
    assert any("Invented loophole" in d for d in res.dropped_detail)


def test_inbound_cite_must_exist_in_that_departments_box(store):
    iso, s = store.load("iso"), store.load("student")
    other = store.load("student")  # a box with no F ids at all
    res = inbound(good_answer(), other, s, "iso")
    assert res.answer["cites"] == [] and res.answer["options"] == [] and res.answer["answer"] == ""
    assert res.dropped >= 4


def test_red_team_answer_echoing_student_name_is_rejected(store):
    iso, s = store.load("iso"), store.load("student")
    leak = good_answer(answer="Riya Example, you need an RCL [F-02].", cites=["F-02"])
    res = inbound(leak, iso, s, "iso")
    assert res.rejected and "name" in res.reason
    assert res.answer["answer"] == "" and res.answer["options"] == [] and res.answer["cites"] == []
    leak_in_option = good_answer(answer="Fine [F-02].", cites=["F-02"],
                                 options=[{"option": "email rexample@ucsc.edu", "conditions": [], "cites": ["F-01"]}])
    assert inbound(leak_in_option, iso, s, "iso").rejected
    gpa = good_answer(answer="Your GPA of 3.4 is fine [F-02].", cites=["F-02"])
    assert inbound(gpa, iso, s, "iso").rejected   # "no" fields are protected too


def test_inbound_keeps_escalate_even_when_rejected(store):
    iso, s = store.load("iso"), store.load("student")
    leak = good_answer(answer="Riya Example [F-02].", cites=["F-02"])
    leak["escalate"] = True
    assert inbound(leak, iso, s, "iso").answer["escalate"] is True
