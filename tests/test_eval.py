"""Baseline mapping and eval bookkeeping with scripted brains (no network)."""
from baseline import baseline_answer, baseline_outcome
from brain import ScriptedBrain
from conftest import good_answer
from eval import CASES, Case, format_table, run_eval


def scripted(escalate=False, **over):
    a = good_answer(cites=["F-01", "F-02"], options=[{"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(escalate=escalate, authority="federal", **over)
    return a


def test_baseline_sees_both_boxes_and_keeps_unverified_cites(store):
    brain = ScriptedBrain([scripted(cites=["F-01", "F-99"], answer="Riya, stay at 12 [F-99].")])
    out = baseline_answer(brain, store.load("iso"), store.load("student"), "q")
    system = brain.calls[0]["system"]
    assert "Riya Example" in system and "rexample@ucsc.edu" in system and "8 CFR" in system
    assert out["cites"] == ["F-01", "F-99"] and out["authority"] == "federal"
    assert baseline_outcome(out) == "CONVERGED"
    assert baseline_outcome({**out, "escalate": True}) == "ESCALATED"
    assert baseline_outcome({**out, "needs": ["hours"]}) == "ASK_STUDENT"
    assert baseline_outcome({**out, "answer": "", "options": []}) == "UNANSWERED"
    assert baseline_outcome(baseline_answer(ScriptedBrain(default=None), store.load("iso"), store.load("student"), "q")) == "UNANSWERED"


def test_eval_counts_outcomes_uncited_and_fields_left(tmp_path):
    cases = [Case("x1", "q1", "CONVERGED"), Case("x2", "q2", "ESCALATED", {"final_quarter": "yes", "units": "8"})]
    # gremlin brain: two good answers (escalation comes from code on x2)
    gremlin = ScriptedBrain(default=scripted())
    # baseline brain: first echoes the name with a bad cite, second forgets to escalate
    baseline = ScriptedBrain([scripted(answer="Riya Example, stay [F-99].", cites=["F-99"]), scripted(escalate=False)])
    result = run_eval(baseline, cases, root=tmp_path, gremlin_brain=gremlin)
    s = result["summary"]
    assert s["gremlin"] == {"correct": 2, "n": 2, "uncited": 0, "left": 8, "left_protected": 0}
    assert s["baseline"]["correct"] == 1 and s["baseline"]["left"] == 24 and s["baseline"]["left_protected"] == 6
    assert s["baseline"]["uncited"] >= 2 and result["rows"][0]["baseline"]["echoed_protected"] is True
    table = format_table(result)
    assert "gremlin | 2/2 | 0 | 8 (0)" in table and "baseline | 1/2" in table
    assert "x2 | ESCALATED | ESCALATED | CONVERGED" in table
    # each case ran on its own copy: the example boxes in the repo are untouched
    assert (tmp_path / "gremlin" / "x1" / "student.example.md").exists()


def test_cases_cover_two_per_outcome():
    from collections import Counter
    assert Counter(c.expected for c in CASES) == {"CONVERGED": 2, "ESCALATED": 2, "ASK_STUDENT": 2}
