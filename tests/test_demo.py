"""The demo runs end to end in-process against the real boxes with a scripted brain."""
import io
import json
import shutil
from pathlib import Path

from box import MarkdownBoxStore
from brain import conforms
from conftest import good_answer
from demo import QUESTIONS, REAL, run

BOXES = Path(__file__).resolve().parent.parent / "docs" / "boxes"


def answer(**over):
    a = good_answer(cites=["F-01", "F-02"], options=[
        {"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12, "hours": None, "weeks": 0}])
    a.update(over)
    return a


class RoutingBrain:
    """Deterministic under parallel calls: the reply depends on the prompt, not on call order."""

    def __init__(self):
        self.calls = []

    def complete(self, system, user, schema):
        self.calls.append(user)
        context = json.loads(user[user.index("{"):])
        if "second on-campus job" in user and "hours" not in context:
            out = answer(needs=["hours"], options=[], answer="")
        elif "second on-campus job" in user:
            out = answer(answer="Ten more hours keeps you at the 20-hour limit [F-10].", cites=["F-10"], options=[])
        else:
            out = answer()
        assert conforms(out, schema)
        return out


def real_store(tmp_path):
    source = MarkdownBoxStore(BOXES)
    for name in REAL:
        shutil.copy(source.path(name), tmp_path / f"{name}.md")
    return MarkdownBoxStore(tmp_path)


def test_demo_runs_the_six_questions_with_four_departments(tmp_path):
    store = real_store(tmp_path)
    brain = RoutingBrain()
    out = io.StringIO()
    verdicts = run(store, brain=brain, transport="inprocess", log=lambda s="": out.write(str(s) + "\n"))
    text = out.getvalue()
    kinds = [v.kind for v in verdicts]
    assert kinds[0] == "CONVERGED"                       # c1
    assert "ESCALATED" in kinds                          # e1: health -> iso E-01 and college E-04 in code
    assert kinds[-1] == "ESCALATED"                      # e2: deadline moved to 2 days -> college E-02
    assert "ASK_STUDENT" in kinds and kinds[kinds.index("ASK_STUDENT") + 1] == "CONVERGED"   # a1 then the approval
    assert "departments: iso, cmpm, college, finaid" in text
    assert "in scope: ['iso', 'college']" in text         # a1 is routed by the topics lines, not to everyone
    assert "awaiting approval ['hours']" in text and "student approves sharing 'hours' with ISO" in text
    assert "verdict change on new information: CONVERGED (c1) -> ESCALATED (e2)" in text
    assert "wrote section 5:" in text and "wrote section 6:" in text and "wrote section 8:" in text
    assert "Asha" not in text and "arao@" not in text    # identity never leaves the box, not even into the demo output
    student = store.load("student")
    assert student.fields["days_to_deadline"] == "2"
    assert any("SHARED | iso" in l for l in student.section(7).lines)
    assert len(QUESTIONS) == 6
