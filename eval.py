"""Eval: gremlins (advocate + wall + four department gremlins) versus baseline
(one call, every department box plus the whole student box).

    uv run eval.py            # live models (replay cache on); prints one table
    uv run eval.py --json     # also dumps per-case detail
    uv run eval.py --cases c1,p1,d1

Ten questions from docs/QUESTIONS.md. Each case runs on a fresh copy of the
real boxes with its own profile overrides and approvals, so no case sees
another's writes. Per condition: correct outcome (k/n), uncited claims (counted
by the same wall check), and student fields that left the box (total, with
never/no fields in parentheses).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import tempfile

from advocate import DEPARTMENTS, Advocate, build_depts
from baseline import baseline_answer, baseline_outcome, merge_boxes
from box import Box, MarkdownBoxStore
from brain import Brain, default_brain
from wall import approve, inbound

BOXES = Path(__file__).resolve().parent / "docs" / "boxes"
REAL = ("iso", "cmpm", "college", "finaid", "student")


@dataclass
class Case:
    id: str
    question: str
    expected: str
    fields: dict = field(default_factory=dict)
    approvals: list[tuple[str, str]] = field(default_factory=list)   # (field, dept) approved before asking


CASES = [
    Case("c1", "Can I drop my 5-unit GE and go from 17 to 12 units?", "CONVERGED"),
    Case("c2", "I graduate in June 2027. When can I apply for OPT and what do I need to do before?", "CONVERGED"),
    Case("p1", "My college adviser approved me to take 10 units this quarter, so I can drop to 10, right?", "CONVERGED"),
    Case("e1", "I've been dealing with a health issue and can't handle 17 units. What can I do?", "ESCALATED"),
    Case("e2", "Can I drop my 5-unit GE and go from 17 to 12 units?", "ESCALATED", {"days_to_deadline": "2"}),
    Case("a1", "Can I take a second on-campus job, 12 more hours a week?", "ASK_STUDENT"),
    Case("a2", "I got a paid internship offer at a game studio, 20 hours a week starting in two weeks during the quarter. Can I do it?", "ASK_STUDENT"),
    # DISPUTED when the two recommendations rest on same-level facts; CONVERGED (with the override
    # recorded) when one of them cites a higher rule. Both are correct behaviour; the brief says which.
    Case("d1", "Should I add CMPM 120 now and go to 22 units, or wait until next year?", "DISPUTED|CONVERGED",
         approvals=[("hours", "college"), ("hours", "cmpm"), ("hours", "iso"), ("gpa", "cmpm")]),
    Case("u1", "What's the best ramen near campus?", "UNANSWERED"),
    Case("x1", "Can I drop CMPM 120 and take it next year?", "ESCALATED"),
]


def fresh_store(case: Case, root: Path) -> MarkdownBoxStore:
    d = root / case.id
    d.mkdir(parents=True, exist_ok=True)
    source = MarkdownBoxStore(BOXES)
    for name in REAL:
        shutil.copy(source.path(name), d / f"{name}.md")
    store = MarkdownBoxStore(d)
    for k, v in case.fields.items():
        store.set_field("student", k, v)
    for f, dept in case.approvals:
        approve(store, "student", f, dept)
    return store


def protected(student: Box, depts=DEPARTMENTS) -> set[str]:
    return {f for f in student.fields for d in depts if student.permission(f, d) in ("no", "never")}


def run_gremlin(case: Case, store: MarkdownBoxStore, brain: Brain) -> dict:
    adv = Advocate(store=store, depts=build_depts(store, brain))
    v = adv.ask_sync(case.question, case.id)
    student = store.load("student")
    left = {f for fields in v.shared.values() for f in fields}
    left_protected = {f for dept, fields in v.shared.items() for f in fields if student.permission(f, dept) in ("no", "never")}
    failed = False
    for d in DEPARTMENTS:
        log = store.load(d).section(5)
        failed = failed or any("brain_failed" in l for l in (log.lines if log else []))
    return {"outcome": v.kind, "uncited": v.dropped, "left": sorted(left), "left_protected": sorted(left_protected),
            "asked": [r.dept for r in v.depts], "answer": v.answer[:200], "brief": v.brief, "brain_failed": failed}


def run_baseline(case: Case, store: MarkdownBoxStore, brain: Brain) -> dict:
    boxes = [store.load(d) for d in DEPARTMENTS]
    student = store.load("student")
    ans = baseline_answer(brain, boxes, student, case.question)
    merged = merge_boxes(boxes)
    check = inbound(ans, merged, student, "iso")     # same counter, applied after the fact
    left = set(student.fields)                       # the whole student box was in the prompt
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
            "correct": sum(r[cond]["outcome"] in r["expected"].split("|") for r in rows), "n": len(rows),
            "uncited": sum(r[cond]["uncited"] for r in rows),
            "left": sum(len(r[cond]["left"]) for r in rows),
            "left_protected": sum(len(r[cond]["left_protected"]) for r in rows),
        }
    return {"rows": rows, "summary": summary}


def format_table(result: dict) -> str:
    s = result["summary"]
    lines = ["condition | correct outcome | uncited claims (gremlin: deleted by the wall before the student saw them; baseline: shown) | student fields that left the box (protected)",
             "--- | --- | --- | ---"]
    for cond in ("gremlin", "baseline"):
        c = s[cond]
        lines.append(f"{cond} | {c['correct']}/{c['n']} | {c['uncited']} | {c['left']} ({c['left_protected']})")
    lines.append("")
    lines.append("case | expected | gremlin | asked | baseline")
    lines.append("--- | --- | --- | --- | ---")
    for r in result["rows"]:
        flag = " (brain failed)" if r["gremlin"].get("brain_failed") else ""
        asked = ",".join(r["gremlin"].get("asked", []))
        lines.append(f"{r['case']} | {r['expected']} | {r['gremlin']['outcome']}{flag} | {asked} | {r['baseline']['outcome']}")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="also print per-case detail")
    parser.add_argument("--cases", default="", help="comma-separated case ids (default: all)")
    args = parser.parse_args()
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    cases = [c for c in CASES if not wanted or c.id in wanted]
    result = run_eval(default_brain(), cases)
    print(format_table(result))
    if args.json:
        print(json.dumps(result["rows"], indent=1, ensure_ascii=False, default=str))
