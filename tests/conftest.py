import shutil
from pathlib import Path

import pytest

from box import MarkdownBoxStore

ROOT = Path(__file__).resolve().parent.parent / "docs" / "boxes"


@pytest.fixture
def store(tmp_path):
    for f in ROOT.glob("*.example.md"):
        shutil.copy(f, tmp_path / f.name)
    return MarkdownBoxStore(tmp_path)


def good_answer(**over):
    base = {"scope": "in_scope",
            "answer": "You need an approved RCL before dropping below 12 units [F-02].",
            "cites": ["F-01", "F-02", "F-99", "Q-01"],
            "needs": [],
            "options": [{"option": "Academic-difficulty RCL to 6 units", "conditions": ["once per program level"],
                         "cites": ["F-04"], "units": 6, "hours": None, "weeks": 1},
                        {"option": "Stay at 12 units", "conditions": [], "cites": ["F-01"], "units": 12,
                         "hours": None, "weeks": 0},
                        {"option": "Invented loophole", "conditions": [], "cites": ["F-77"], "units": 0,
                         "hours": None, "weeks": 0}],
            "confidence": 0.8}
    base.update(over)
    return base
