"""Eval: gremlin (advocate + wall + ISO gremlin) versus baseline (one call, both boxes).

    uv run eval.py            # live models; prints one table
    uv run eval.py --json     # also dumps per-case detail

Six questions, two per expected outcome (CONVERGED, ESCALATED, ASK_STUDENT).
Each case runs on a fresh copy of the example boxes with its own profile
overrides, so no case sees another's writes. Per condition: correct outcome
(k/n), uncited claims (counted by the same wall check), and student fields
that left the box (total, with never/no fields in parentheses).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import tempfile

from advocate import Advocate, DeptGremlin, in_process
from baseline import baseline_answer, baseline_outcome
from box import Box, MarkdownBoxStore
from brain import Brain, default_brain
from wall import inbound

BOXES = Path(__file__).resolve().parent / "docs" / "boxes"


@dataclass
class Case:
    id: str
    question: str
    expected: str
    fields: dict = field(default_factory=dict)


CASES = [
    Case("c1", "I want to drop from 16 to 9 units this quarter because of my job. Can I?", "CONVERGED"),
    Case("c2", "Do I have to enroll in classes during summer quarter?", "CONVERGED"),
    Case("e1", "I have a medical condition and need to take fewer units this quarter. What are my options?", "ESCALATED"),
    Case("e2", "It is my final quarter and I only need 8 units to graduate. Can I enroll in just those?", "ESCALATED",
         {"final_quarter": "yes", "units": "8"}),
    Case("a1", "Am I currently over the on-campus work-hour limit?", "ASK_STUDENT"),
    Case("a2", "If I drop my one in-person class, will my remaining online classes keep me full-time?", "ASK_STUDENT"),
]


def fresh_store(case: Case, root: Path) -> MarkdownBoxStore:
    d = root / case.id
    d.mkdir(parents=True, exist_ok=True)
    for f in BOXES.glob("*.example.md"):
        shutil.copy(f, d / f.name)
    store = MarkdownBoxStore(d)
    for k, v in case.fields.items():
        store.set_field("student", k, v)
    return store


def protected(student: Box, dept: str = "iso") -> set[str]:
    return {f for f in student.fields if student.permission(f, dept) in ("no", "never")}


def run_gremlin(case: Case, store: MarkdownBoxStore, brain: Brain) -> dict:
    adv = Advocate(store=store, depts={"iso": in_process(DeptGremlin("iso", store=store, brain=brain))})
    v = adv.ask_sync(case.question, case.id)
    student = store.load("student")
    left = set(v.shared.get("iso", []))
    iso_log = store.load("iso").section(5)
    failed = any("brain_failed" in l for l in (iso_log.lines if iso_log else []))
    return {"outcome": v.kind, "uncited": v.dropped, "left": sorted(left),
            "left_protected": sorted(left & protected(student)), "answer": v.answer[:200],
            "brain_failed": failed}


def run_baseline(case: Case, store: MarkdownBoxStore, brain: Brain) -> dict:
    iso, student = store.load("iso"), store.load("student")
    ans = baseline_answer(brain, iso, student, case.question)
    check = inbound(ans, iso, student, "iso")       # same counter, applied after the fact
    left = set(student.fields)                      # the whole student box was in the prompt
    return {"outcome": baseline_outcome(ans), "uncited": check.dropped + (1 if check.rejected else 0),
            "left": sorted(left), "left_protected": sorted(left & protected(student)),
            "echoed_protected": check.rejected, "answer": ans["answer"][:200]}


def run_eval(brain: Brain, cases: list[Case] = CASES, root: Path | None = None,
             gremlin_brain: Brain | None = None) -> dict:
    root = root or Path(tempfile.mkdtemp(prefix="gremlin-eval-"))
    rows = []
    for case in cases:
        g = run_gremlin(case, fresh_store(case, root / "gremlin"), gremlin_brain or brain)
        b = run_baseline(case, fresh_store(case, root / "baseline"), brain)
        rows.append({"case": case.id, "question": case.question, "expected": case.expected, "gremlin": g, "baseline": b})
    summary = {}
    for cond in ("gremlin", "baseline"):
        summary[cond] = {
            "correct": sum(r[cond]["outcome"] == r["expected"] for r in rows), "n": len(rows),
            "uncited": sum(r[cond]["uncited"] for r in rows),
            "left": sum(len(r[cond]["left"]) for r in rows),
            "left_protected": sum(len(r[cond]["left_protected"]) for r in rows),
        }
    return {"rows": rows, "summary": summary}


def format_table(result: dict) -> str:
    s = result["summary"]
    lines = ["condition | correct outcome | uncited claims | student fields that left the box (protected)",
             "--- | --- | --- | ---"]
    for cond in ("gremlin", "baseline"):
        c = s[cond]
        lines.append(f"{cond} | {c['correct']}/{c['n']} | {c['uncited']} | {c['left']} ({c['left_protected']})")
    lines.append("")
    lines.append("case | expected | gremlin | baseline")
    lines.append("--- | --- | --- | ---")
    for r in result["rows"]:
        flag = " (brain failed)" if r["gremlin"].get("brain_failed") else ""
        lines.append(f"{r['case']} | {r['expected']} | {r['gremlin']['outcome']}{flag} | {r['baseline']['outcome']}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="also print per-case detail")
    args = parser.parse_args()
    result = run_eval(default_brain())
    print(format_table(result))
    if args.json:
        print(json.dumps(result["rows"], indent=1, ensure_ascii=False))
