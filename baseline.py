"""Baseline condition: one LLM call with the question, every department box, and the
full student box. No wall, no code-decided escalation, no cite verification.
Same output contract as a department gremlin so the eval can score both."""
from __future__ import annotations

from box import Box
from brain import Brain
from dept_gremlin import ANSWER_KEYS, BRAIN_SCHEMA, SCOPES, _dedupe, _num

BASELINE_SCHEMA = {**BRAIN_SCHEMA, "required": BRAIN_SCHEMA["required"] + ["escalate", "authority"],
                   "properties": {**BRAIN_SCHEMA["properties"], "escalate": {"type": "boolean"},
                                  "authority": {"type": "string"}}}

SYSTEM = """You are a campus advising assistant. Answer the student's question using the
department policy box and the student's own box below. Cite box ids like [F-xx] for
every claim. If you need information that is not in either box, list the field names
under "needs". Set "escalate" to true when a human must decide. Reply with one JSON object:
{{"scope": "in_scope"|"partial"|"out_of_scope", "answer": "...", "cites": [...], "needs": [...],
  "options": [{{"option": "...", "conditions": [...], "cites": [...], "units": number|null,
               "hours": number|null, "weeks": number|null}}],
  "escalate": true|false, "authority": "federal|state|campus|department|", "confidence": 0.0-1.0}}

=== DEPARTMENT BOX ===
{dept}
=== END DEPARTMENT BOX ===

=== STUDENT BOX ===
{student}
=== END STUDENT BOX ==="""


def merge_boxes(boxes: list[Box]) -> Box:
    """The baseline gets every department box pasted into one prompt. The merged Box is
    only used for the after-the-fact cite check; colliding ids (every box has an F-01)
    are part of what the baseline gets wrong."""
    if len(boxes) == 1:
        return boxes[0]
    merged = Box(name="all-departments")
    merged.text = "\n\n".join(f"=== {b.meta.get('name') or b.name} ===\n{b.text}" for b in boxes)
    for b in boxes:
        merged.facts.update(b.facts)
        merged.precedence.update(b.precedence)
        merged.faq.update(b.faq)
        merged.escalations.update(b.escalations)
    merged.meta["authority_order"] = boxes[0].meta.get("authority_order", "")
    return merged


def build_prompts(dept_box: Box | list[Box], student_box: Box, question: str) -> tuple[str, str]:
    dept_box = merge_boxes(dept_box) if isinstance(dept_box, list) else dept_box
    return SYSTEM.format(dept=dept_box.text, student=student_box.text), f"question: {question}"


def baseline_answer(brain: Brain, dept_box: Box | list[Box], student_box: Box, question: str) -> dict:
    system, user = build_prompts(dept_box, student_box, question)
    raw = brain.complete(system, user, BASELINE_SCHEMA)
    out = {"scope": "out_of_scope", "answer": "", "cites": [], "needs": [], "options": [],
           "escalate": False, "authority": "", "confidence": 0.0, "failed": raw is None, "refers": [], "stance": ""}
    if raw is None:
        return out
    out["scope"] = raw["scope"] if raw.get("scope") in SCOPES else "out_of_scope"
    out["answer"] = str(raw.get("answer", ""))
    out["cites"] = _dedupe(raw.get("cites", []))          # NOT filtered against the box: that is the point
    out["needs"] = _dedupe(raw.get("needs", []))
    out["options"] = [{"option": str(o.get("option", "")), "conditions": [str(c) for c in o.get("conditions", []) or []],
                       "cites": _dedupe(o.get("cites", [])), "units": _num(o.get("units")),
                       "hours": _num(o.get("hours")), "weeks": _num(o.get("weeks"))}
                      for o in raw.get("options", []) or [] if isinstance(o, dict)]
    out["escalate"] = bool(raw.get("escalate"))
    out["authority"] = str(raw.get("authority", ""))
    conf = raw.get("confidence", 0)
    out["confidence"] = round(min(1.0, max(0.0, float(conf))), 3) if isinstance(conf, (int, float)) else 0.0
    return {k: out[k] for k in ANSWER_KEYS}


def baseline_outcome(answer: dict) -> str:
    """Map the single-call output onto the advocate's verdict vocabulary."""
    if answer["escalate"]:
        return "ESCALATED"
    if answer["needs"]:
        return "ASK_STUDENT"
    if answer["answer"] or answer["options"]:
        return "CONVERGED"
    return "UNANSWERED"
