"""The wall between the student box and department gremlins. Pure code, no model.

Outbound: build the context a department may see from the student's sharing
permissions table.  yes -> value sent, no -> "not shared", never -> omitted
entirely, ask -> listed for the student to approve (sent only once approved).
Protected values are also redacted from the question text. Fields actually
sent are logged to student section 7.

Inbound: every cite must exist in that department's box. Cites that do not,
options without a valid cite, and answer sentences without a valid [id]
marker are dropped and counted. An answer that echoes a protected field
value (the student's name, for instance) is rejected outright.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from box import Box, BoxStore, log_line

SHARED_SECTION = 7
_CITE = re.compile(r"\[([FPQE]-\d+[A-Za-z0-9]*)\]")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Outbound:
    dept: str
    question: str
    context: dict = field(default_factory=dict)
    shared: list[str] = field(default_factory=list)     # fields sent with values
    withheld: list[str] = field(default_factory=list)   # "no" fields, sent as "not shared"
    ask: list[str] = field(default_factory=list)        # "ask" fields awaiting approval
    redacted: list[str] = field(default_factory=list)   # fields whose values were scrubbed from the question
    held: list[str] = field(default_factory=list)       # "yes" fields not sent yet (round 1 shares the minimum)


@dataclass
class Inbound:
    answer: dict
    dropped: int = 0
    rejected: bool = False
    reason: str = ""
    dropped_detail: list[str] = field(default_factory=list)


def approved_fields(student: Box, dept: str) -> set[str]:
    """`ts | APPROVED | field | dept` lines in section 7 turn an ask into a yes."""
    section = student.section(SHARED_SECTION)
    out: set[str] = set()
    for line in (section.lines if section else []):
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 4 and cells[1] == "APPROVED" and cells[3].lower() == dept.lower():
            out.add(cells[2])
    return out


_LOW_SIGNAL = {"yes", "no", "true", "false", "none", "n/a", "na", "-"}


def _identifying(value: str) -> bool:
    """A value worth redacting: not a yes/no token and not a bare small integer such as
    a unit count (a GPA like 3.4 or a date still counts; a `no` field is still protected)."""
    v = value.strip()
    if len(v) < 3 or v.lower() in _LOW_SIGNAL:
        return False
    return not (len(v) < 4 and v.isdigit())


def protected_values(student: Box, dept: str, policy_text: str = "") -> dict[str, str]:
    """Field values that must not travel to or come back from this department.
    A value that appears verbatim in the department's own policy text (say `F-1`)
    is policy, not a leak, and is not treated as this student's secret."""
    out = {}
    policy = policy_text.lower()
    for name, value in student.fields.items():
        perm = student.permission(name, dept)
        if perm in ("never", "no") and _identifying(value) and not (policy and value.strip().lower() in policy):
            out[name] = value.strip()
    return out


def redact(text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    hit: list[str] = []
    for name, value in sorted(values.items(), key=lambda kv: -len(kv[1])):
        pattern = re.compile(re.escape(value), re.IGNORECASE)
        if pattern.search(text):
            text = pattern.sub("[redacted]", text)
            hit.append(name)
    return text, hit


def outbound(student: Box, dept: str, question: str, approvals: set[str] | None = None,
             fields: list[str] | None = None, declined: set[str] | None = None) -> Outbound:
    """`fields` limits which permitted fields are sent this round (None sends every permitted one).
    `declined` are ask-fields the student chose not to share for this question: sent as "not shared"."""
    approvals = approved_fields(student, dept) | (approvals or set())
    out = Outbound(dept=dept, question=question)
    for name, value in student.fields.items():
        perm = student.permission(name, dept)
        if perm == "ask" and name in approvals:
            perm = "yes"
        elif perm == "ask" and declined and name in declined:
            perm = "no"
        if perm == "yes" and fields is not None and name not in fields:
            out.held.append(name)
        elif perm == "yes":
            out.context[name] = value
            out.shared.append(name)
        elif perm == "no":
            out.context[name] = "not shared"
            out.withheld.append(name)
        elif perm == "ask":
            out.ask.append(name)
        # never: not mentioned at all
    out.question, out.redacted = redact(question, protected_values(student, dept))
    return out


def log_shared(store: BoxStore, name: str, out: Outbound, session_id: str) -> None:
    if out.shared:
        store.append(name, SHARED_SECTION, log_line("SHARED", out.dept, ",".join(out.shared), session_id))


def approve(store: BoxStore, name: str, field_name: str, dept: str) -> bool:
    """Record the student's approval of one ask field for one department."""
    student = store.load(name)
    if student.permission(field_name, dept) != "ask":
        return False
    if field_name in approved_fields(student, dept):
        return True
    store.append(name, SHARED_SECTION, log_line("APPROVED", field_name, dept))
    return True


def _valid_cites(cites, dept_box: Box) -> tuple[list[str], list[str]]:
    good, bad = [], []
    for c in cites or []:
        (good if isinstance(c, str) and dept_box.has(c) and c not in good else bad).append(c)
    return good, bad


def inbound(answer: dict, dept_box: Box, student: Box, dept: str) -> Inbound:
    from dept_gremlin import empty_answer  # local import keeps wall.py model-free and import-light

    result = Inbound(answer=dict(answer))
    a = result.answer
    cites, bad = _valid_cites(a.get("cites"), dept_box)
    result.dropped += len(bad)
    result.dropped_detail += [f"cite {c}" for c in bad]
    a["cites"] = cites

    kept = []
    for opt in a.get("options") or []:
        good, bad = _valid_cites(opt.get("cites") if isinstance(opt, dict) else None, dept_box)
        if good:
            kept.append({**opt, "cites": good})
        else:
            result.dropped += 1
            result.dropped_detail.append(f"option without cite: {str(opt.get('option', opt))[:60]}")
    a["options"] = kept

    text = str(a.get("answer", "")).strip()
    if text:
        sentences = [s for s in _SENTENCE.split(text) if s.strip()]
        cited = [s for s in sentences if any(dept_box.has(m) for m in _CITE.findall(s))]
        uncited = len(sentences) - len(cited)
        result.dropped += uncited
        result.dropped_detail += [f"uncited sentence: {s[:60]}" for s in sentences if s not in cited]
        a["answer"] = " ".join(cited)

    # leak check on the ORIGINAL answer: a department answer must never echo protected
    # student values, even in a sentence that was already dropped as uncited
    original = answer.get("options") or []
    blob = " ".join([str(answer.get("answer", "")),
                     *[str(o.get("option", "")) + " " + " ".join(str(c) for c in (o.get("conditions") or []))
                       for o in original if isinstance(o, dict)]])
    for name, value in protected_values(student, dept, dept_box.text).items():
        if re.search(re.escape(value), blob, re.IGNORECASE):
            result.rejected, result.reason = True, f"answer echoed protected field {name}"
            result.answer = {**empty_answer(), "escalate": bool(a.get("escalate"))}
            break
    return result
