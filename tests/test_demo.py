"""The demo runs end to end in-process with a scripted brain and prints every step."""
import io

from brain import ScriptedBrain
from conftest import good_answer
from demo import run


def answer(**over):
    a = good_answer(cites=["F-01", "F-02"], options=[
        {"option": "Academic-difficulty RCL to 6 units", "conditions": ["once per level"], "cites": ["F-04"], "units": 6, "hours": None, "weeks": 1},
        {"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(over)
    return a


def test_demo_prints_steps_and_the_verdict_change(store):
    brain = ScriptedBrain([
        answer(),                                   # Q1 converged
        answer(needs=["hours"], options=[], answer=""),  # Q2 ask student
        answer(answer="You are under the 20-hour limit [F-06].", cites=["F-06"], options=[]),  # Q2 after approval
        answer(),                                   # Q3 before the flip
        answer(),                                   # Q3 after the flip: escalation comes from code
    ])
    out = io.StringIO()
    verdicts = run(store, brain=brain, transport="inprocess", log=lambda s="": out.write(str(s) + "\n"))
    text = out.getvalue()
    assert [v.kind for v in verdicts] == ["CONVERGED", "ASK_STUDENT", "CONVERGED", "CONVERGED", "ESCALATED"]
    assert "transport: in-process" in text
    assert "round 1 -> ISO: shared ['level', 'units', 'final_quarter', 'rcl_on_file']" in text
    assert "awaiting approval ['hours']" in text and "student approves sharing 'hours'" in text
    assert "shared ['level', 'units', 'hours', 'final_quarter', 'rcl_on_file']" in text   # approved: now a yes field
    assert "1. Academic-difficulty RCL to 6 units  [F-04]  (units=6, weeks=1)" in text
    assert "VERDICT: ESCALATED  authority=federal  triggers=['E-02', 'E-03']" in text
    assert "verdict change: CONVERGED -> ESCALATED" in text
    assert "wrote section 5:" in text and "wrote section 6:" in text and "wrote section 8:" in text
    assert "Riya" not in text  # identity never leaves the box, not even into the demo output
    student = store.load("student")
    assert student.fields["final_quarter"] == "yes"
    assert len([l for l in student.section(5).lines if "CONVERGED" in l]) == 3
    assert len([l for l in student.section(6).lines if "ESCALATED" in l]) == 1
    assert len(brain.calls) == 5
