"""Baseline mapping and eval bookkeeping with scripted brains (no network)."""
from collections import Counter

from baseline import baseline_answer, baseline_outcome, merge_boxes
from box import MarkdownBoxStore
from brain import ScriptedBrain
from conftest import good_answer
from eval import CASES, DEPARTMENTS, Case, format_table, protected, run_eval


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


def test_baseline_gets_every_department_box_in_one_prompt():
    real = MarkdownBoxStore()
    boxes = [real.load(d) for d in DEPARTMENTS]
    brain = ScriptedBrain([scripted()])
    baseline_answer(brain, boxes, real.load("student"), "q")
    system = brain.calls[0]["system"]
    for b in boxes:
        assert b.meta["name"] in system
    merged = merge_boxes(boxes)
    assert merged.has("F-01") and merged.has("E-07") and merged.text.count("## 1. Facts") == len(boxes)


def test_eval_counts_outcomes_uncited_and_fields_left(tmp_path):
    cases = [Case("x1", "q1", "CONVERGED"), Case("x2", "q2", "ESCALATED", {"final_quarter": "yes", "units": "8"})]
    # gremlin brain: good answers for every department (escalation comes from code on x2)
    gremlin = ScriptedBrain(default=scripted())
    # baseline brain: first echoes the name with a bad cite, second forgets to escalate
    baseline = ScriptedBrain([scripted(answer="Asha Rao, stay [F-99].", cites=["F-99"]), scripted(escalate=False)])
    result = run_eval(baseline, cases, root=tmp_path, gremlin_brain=gremlin)
    s = result["summary"]
    student = MarkdownBoxStore(tmp_path / "gremlin" / "x1").load("student")
    assert s["gremlin"]["correct"] == 2 and s["gremlin"]["n"] == 2
    assert s["gremlin"]["uncited"] == 0 and s["gremlin"]["left_protected"] == 0
    assert 0 < s["gremlin"]["left"] < s["baseline"]["left"]
    assert s["baseline"]["correct"] == 1
    assert s["baseline"]["left"] == 2 * len(student.fields)
    assert s["baseline"]["left_protected"] == 2 * len(protected(student))
    assert s["baseline"]["uncited"] >= 2 and result["rows"][0]["baseline"]["echoed_protected"] is True
    assert result["rows"][0]["gremlin"]["asked"] == list(DEPARTMENTS)   # "q1" matches no topics: everyone is asked
    table = format_table(result)
    assert "gremlin | 2/2 | 0 |" in table and "baseline | 1/2" in table
    assert "x2 | ESCALATED | ESCALATED | iso,cmpm,college,finaid | CONVERGED" in table
    # each case ran on its own copy: the real boxes in the repo are untouched
    assert (tmp_path / "gremlin" / "x1" / "student.md").exists()
    assert "SESSION" not in MarkdownBoxStore().load("student").text


def test_cases_cover_every_verdict():
    assert Counter(c.expected for c in CASES) == {"CONVERGED": 3, "ESCALATED": 3, "ASK_STUDENT": 2, "DISPUTED": 1, "UNANSWERED": 1}
    assert len({c.id for c in CASES}) == len(CASES)
