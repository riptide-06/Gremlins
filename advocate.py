"""The student gremlin (advocate). Reads the student box fresh, runs the wall,
asks every in-scope department gremlin (chosen by the `topics:` line each box
advertises, all at once, none seeing another's answer), scores options with the
student's preferences, and writes the verdict back into the student box.

Verdicts
  CONVERGED    one answer, written to section 5
  ESCALATED    an E-xx trigger matched; brief written to section 6
  DISPUTED     two departments conflict at equal authority; brief in section 6
  ASK_STUDENT  a department needs an `ask` field or a field the box lacks; section 8
  UNANSWERED   nothing usable came back; session log only

Round 1 shares the minimum: `yes` fields the department box mentions. If the
department lists `needs` that the permissions allow, one resend round adds them.
Everything the model said that could not be cited is dropped by the wall.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import os
import re
from typing import Awaitable, Callable
import uuid

from box import Box, BoxStore, MarkdownBoxStore, log_line
from dept_gremlin import DeptGremlin, ask_dept, empty_answer
from wall import Inbound, Outbound, approved_fields, inbound, log_shared, outbound

SECTION_LOG, SECTION_CONVERGED, SECTION_BRIEFS, SECTION_OPEN = 4, 5, 6, 8
VERDICTS = ("CONVERGED", "ESCALATED", "DISPUTED", "ASK_STUDENT", "UNANSWERED")
DEPARTMENTS = ("iso", "cmpm", "college", "finaid")   # a box per department under docs/boxes/

DeptCaller = Callable[[str, str, dict], Awaitable[dict]]


def in_process(gremlin: DeptGremlin) -> DeptCaller:
    async def call(session_id: str, question: str, context: dict) -> dict:
        return await asyncio.to_thread(gremlin.answer, session_id, question, context)
    return call


def over_a2a(url: str) -> DeptCaller:
    async def call(session_id: str, question: str, context: dict) -> dict:
        out = await ask_dept(url, session_id, question, context)
        return out if out.get("ok") else empty_answer()
    return call


@dataclass
class DeptResult:
    dept: str
    rounds: list[Outbound] = field(default_factory=list)
    answer: dict = field(default_factory=empty_answer)
    inbound: Inbound | None = None
    ask: list[str] = field(default_factory=list)       # fields the student must approve or supply
    blocked: list[str] = field(default_factory=list)   # needs the permissions forbid (no/never)

    @property
    def shared(self) -> list[str]:
        seen: list[str] = []
        for r in self.rounds:
            seen += [f for f in r.shared if f not in seen]
        return seen


@dataclass
class Verdict:
    kind: str
    session_id: str
    question: str
    answer: str = ""
    best: dict | None = None
    options: list[dict] = field(default_factory=list)
    cites: list[str] = field(default_factory=list)
    authority: str = ""
    escalations: list[str] = field(default_factory=list)
    ask: list[str] = field(default_factory=list)
    depts: list[DeptResult] = field(default_factory=list)
    brief: dict = field(default_factory=dict)
    written: list[tuple[int, str]] = field(default_factory=list)

    @property
    def shared(self) -> dict[str, list[str]]:
        return {d.dept: d.shared for d in self.depts}

    @property
    def dropped(self) -> int:
        return sum(d.inbound.dropped for d in self.depts if d.inbound)

    def to_dict(self) -> dict:
        return {"verdict": self.kind, "session_id": self.session_id, "question": self.question,
                "answer": self.answer, "best": self.best, "options": self.options, "cites": self.cites,
                "authority": self.authority, "escalations": self.escalations, "ask": self.ask,
                "ask_by_dept": {d.dept: d.ask for d in self.depts if d.ask},
                "shared": self.shared, "dropped": self.dropped, "brief": self.brief,
                "written": [{"section": s, "line": l} for s, l in self.written]}


# ---- preferences -------------------------------------------------------
_PREF = {
    "fewer units": ("units", 1), "more units": ("units", -1),
    "more hours": ("hours", -1), "fewer hours": ("hours", 1),
    "sooner": ("weeks", 1), "later": ("weeks", -1),
}


def preference_key(preferences: list[str]) -> Callable[[dict], tuple]:
    """Lexicographic: first preference decides, ties fall to the next. Unknown values sort last."""
    axes = [_PREF[p.strip().lower()] for p in preferences if p.strip().lower() in _PREF] or [("units", 1)]

    def key(option: dict) -> tuple:
        parts = []
        for name, sign in axes:
            value = option.get(name)
            missing = not isinstance(value, (int, float))
            parts.append((missing, 0 if missing else sign * value))
        return tuple(parts)
    return key


def score_options(options: list[dict], preferences: list[str]) -> list[dict]:
    key = preference_key(preferences)
    ranked = sorted(options, key=key)
    return [{**o, "rank": i + 1} for i, o in enumerate(ranked)]


# ---- relevance for round 1 -----------------------------------------------
def relevant_fields(dept_box: Box, student: Box) -> list[str]:
    """Share first only the yes-fields the department box itself talks about."""
    text = dept_box.text.lower()
    return [f for f in student.fields if re.search(rf"\b{re.escape(f.lower())}\b", text)]


class Advocate:
    def __init__(self, store: BoxStore | None = None, student_box: str = "student",
                 depts: dict[str, DeptCaller] | None = None, dept_boxes: dict[str, str] | None = None):
        self.store = store or MarkdownBoxStore()
        self.student_box = student_box
        self.depts = depts or {}
        self.dept_boxes = dept_boxes or {}

    # -- scope ---------------------------------------------------------------
    def in_scope(self, student: Box, question: str) -> list[str]:
        """Capability-based selection, no central router: a department is asked when the
        question matches the `topics:` regex its own box advertises. A box with no topics
        line is always asked. If nothing matches, everyone is asked and each gremlin
        decides its own scope. Only departments the student's permissions table knows."""
        known = {d.lower() for d in student.departments}
        candidates = [d for d in self.depts if d.lower() in known] or list(self.depts)
        chosen = []
        for d in candidates:
            try:
                topics = self.dept_box(d).meta.get("topics", "").strip()
            except (FileNotFoundError, OSError, ValueError):
                topics = ""
            if not topics:
                chosen.append(d)
                continue
            try:
                if re.search(topics, question, re.IGNORECASE):
                    chosen.append(d)
            except re.error:
                chosen.append(d)
        return chosen or candidates

    def dept_box(self, dept: str) -> Box:
        return self.store.load(self.dept_boxes.get(dept, dept))

    # -- one department, up to two rounds ---------------------------------------
    async def consult(self, dept: str, student: Box, question: str, session_id: str,
                      declined: set[str] | None = None) -> DeptResult:
        result = DeptResult(dept=dept)
        dept_box = self.dept_box(dept)
        approvals = approved_fields(student, dept)
        fields = relevant_fields(dept_box, student)
        declined = set(declined or ())
        for round_no in (1, 2):
            out = outbound(student, dept, question, approvals, fields=fields, declined=declined)
            result.rounds.append(out)
            log_shared(self.store, self.student_box, out, session_id)
            raw = await self.depts[dept](session_id, out.question, out.context)
            result.inbound = inbound(raw, dept_box, student, dept)
            result.answer = result.inbound.answer
            needs = [n for n in result.answer.get("needs", []) if n not in out.context or out.context[n] == "not shared"]
            if not needs:
                break
            resend, ask, blocked = [], [], []
            for n in needs:
                perm = student.permission(n, dept)
                if n not in student.fields:
                    ask.append(n)                      # the student must supply it
                elif perm == "yes" or (perm == "ask" and n in approvals):
                    resend.append(n)
                elif perm == "ask" and n in declined:
                    blocked.append(n)                  # the student said no for this question
                elif perm == "ask":
                    ask.append(n)
                else:
                    blocked.append(n)
            result.ask, result.blocked = ask, blocked
            if ask or not resend or round_no == 2:
                break
            fields = sorted(set(fields) | set(resend))   # one resend round with the allowed needs
        return result

    # -- the whole question --------------------------------------------------------
    async def ask(self, question: str, session_id: str | None = None, declined: set[str] | None = None) -> Verdict:
        session_id = session_id or uuid.uuid4().hex[:12]
        student = self.store.load(self.student_box)  # fresh: a flipped field changes the verdict
        depts = self.in_scope(student, question)
        # every department is consulted at once; none sees another's answer (no central decision-maker)
        results = list(await asyncio.gather(*[self.consult(d, student, question, session_id, declined) for d in depts]))
        verdict = self.decide(student, question, session_id, results)
        self.write(verdict)
        return verdict

    def ask_sync(self, question: str, session_id: str | None = None, declined: set[str] | None = None) -> Verdict:
        return asyncio.run(self.ask(question, session_id, declined))

    # -- deciding -------------------------------------------------------------------
    def decide(self, student: Box, question: str, session_id: str, results: list[DeptResult]) -> Verdict:
        v = Verdict(kind="UNANSWERED", session_id=session_id, question=question, depts=results)
        answered = [r for r in results if r.answer.get("answer") or r.answer.get("options")]
        v.escalations = sorted({c for r in results if r.answer.get("escalate")
                                for c in r.answer.get("cites", []) if c.startswith("E-")})
        v.ask = sorted({f for r in results for f in r.ask})
        pooled = [{**o, "dept": r.dept, "authority": r.answer.get("authority", "")}
                  for r in answered for o in r.answer.get("options", [])]
        v.options = score_options(pooled, student.preferences)
        v.best = v.options[0] if v.options else None
        v.cites = sorted({c for r in results for c in r.answer.get("cites", [])}
                         | {c for o in pooled for c in o.get("cites", [])})
        v.authority = student.highest_authority(v.cites) or next((r.answer.get("authority", "") for r in answered), "")
        # each department speaks in its own voice; a disagreement should read as one
        v.answer = " ".join(f"{r.dept.upper()}: {r.answer['answer'].strip()}" for r in answered if r.answer.get("answer"))

        agreed, disputed, decides = self._positions(student, answered)
        if v.escalations or any(r.answer.get("escalate") for r in results):
            v.kind = "ESCALATED"
            triggers = {e.id: e.text for d in {r.dept for r in results} for e in self.dept_box(d).escalations.values()}
            v.brief = {"agreed": agreed, "disputed": disputed,
                       "options": [o["option"] for o in v.options[:4]],
                       "resolve": [triggers.get(e, e) for e in v.escalations] + [f"student supplies {f}" for f in v.ask],
                       "decides": sorted({r.dept.upper() for r in results if r.answer.get("escalate")})}
        elif v.ask:
            v.kind = "ASK_STUDENT"
        elif disputed:
            v.kind = "DISPUTED"
            v.brief = {"agreed": agreed, "disputed": disputed, "options": [o["option"] for o in v.options[:4]],
                       "resolve": ["a precedence rule (P-xx) or authority_order ranking one department above the other",
                                   "or a human decision"],
                       "decides": decides}
        elif answered:
            v.kind = "CONVERGED"
            if decides:  # a conflict existed but authority_order settled it
                v.brief = {"agreed": agreed, "precedence": decides}
        return v

    def _positions(self, student: Box, answered: list[DeptResult]) -> tuple[list[str], list[str], list[str]]:
        """Compare departments by their best option's units. The authority behind a position is
        the highest authority among the facts that option cites (not everything the department
        mentioned), so a campus office quoting a federal rule in passing does not outrank the
        office that administers it. Equal authority -> disputed; otherwise authority_order decides."""
        agreed, disputed, decides = [], [], []
        best = {}
        for r in answered:
            opts = score_options(r.answer.get("options", []), student.preferences)
            if opts and isinstance(opts[0].get("units"), (int, float)):
                authority = ""
                try:
                    authority = self.dept_box(r.dept).highest_authority(opts[0].get("cites", []))
                except (FileNotFoundError, OSError, ValueError):
                    pass
                best[r.dept] = (opts[0]["units"], authority or r.answer.get("authority", ""), opts[0]["option"])
        depts = list(best)
        for i, a in enumerate(depts):
            for b in depts[i + 1:]:
                ua, auth_a, text_a = best[a]
                ub, auth_b, text_b = best[b]
                if ua == ub:
                    agreed.append(f"{a.upper()} and {b.upper()} both allow {ua} units")
                    continue
                ra, rb = student.authority_rank(auth_a), student.authority_rank(auth_b)
                if ra == rb:
                    disputed.append(f"{a.upper()} ({auth_a}): {text_a} vs {b.upper()} ({auth_b}): {text_b}")
                    decides += [a.upper(), b.upper()]
                else:
                    winner = a if ra < rb else b
                    decides.append(f"{winner.upper()} wins by authority_order ({best[winner][1]})")
                    agreed.append(f"{winner.upper()} position stands: {best[winner][2]}")
        if len(answered) == 1 and not agreed and not disputed:
            agreed.append(f"{answered[0].dept.upper()} is the only department in scope")
        return agreed, disputed, sorted(set(decides))

    # -- writing back ----------------------------------------------------------------
    def write(self, v: Verdict) -> None:
        q = v.question[:160]
        best = v.best["option"][:160] if v.best else "-"
        if v.kind == "CONVERGED":
            self._append(v, SECTION_CONVERGED, log_line("CONVERGED", v.session_id, q, best, ",".join(v.cites) or "-", v.authority or "-"))
        elif v.kind in ("ESCALATED", "DISPUTED"):
            b = v.brief
            self._append(v, SECTION_BRIEFS, log_line(
                v.kind, v.session_id, q, "triggers=" + (",".join(v.escalations) or "-"),
                "agreed=" + ("; ".join(b.get("agreed", [])) or "-"), "disputed=" + ("; ".join(b.get("disputed", [])) or "-"),
                "options=" + ("; ".join(b.get("options", [])) or "-"), "resolve=" + ("; ".join(b.get("resolve", [])) or "-"),
                "decides=" + (",".join(b.get("decides", [])) or "-")))
        elif v.kind == "ASK_STUDENT":
            depts = ",".join(sorted({r.dept for r in v.depts if r.ask}))
            self._append(v, SECTION_OPEN, log_line("ASK_STUDENT", v.session_id, q, ",".join(v.ask), depts))
        self._append(v, SECTION_LOG, log_line("SESSION", v.session_id, v.kind, ",".join(r.dept for r in v.depts) or "-",
                                              ",".join(v.cites) or "-", f"dropped={v.dropped}"))

    def _append(self, v: Verdict, section: int, line: str) -> None:
        self.store.append(self.student_box, section, line)
        v.written.append((section, line))

    # -- student-facing reads -----------------------------------------------------------
    def open_items(self) -> list[dict]:
        student = self.store.load(self.student_box)
        section = student.section(SECTION_OPEN)
        items = []
        for line in (section.lines if section else []):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 5 and cells[1] == "ASK_STUDENT":
                items.append({"time": cells[0], "session_id": cells[2], "question": cells[3],
                              "fields": [f for f in cells[4].split(",") if f], "dept": cells[5] if len(cells) > 5 else ""})
        return items


def dept_urls_from_env() -> dict[str, str]:
    """DEPT_URLS="iso=http://127.0.0.1:10001,cmpm=http://127.0.0.1:10002"; ISO_URL still works."""
    out = {}
    for pair in (os.environ.get("DEPT_URLS") or "").split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            if k.strip() and v.strip():
                out[k.strip().lower()] = v.strip()
    if os.environ.get("ISO_URL"):
        out.setdefault("iso", os.environ["ISO_URL"])
    return out


def build_depts(store: BoxStore, brain=None, urls: dict[str, str] | None = None,
                names: tuple[str, ...] = DEPARTMENTS) -> dict[str, DeptCaller]:
    """One caller per department whose box exists: over A2A when a URL is given, in-process otherwise."""
    urls = urls or {}
    depts: dict[str, DeptCaller] = {}
    for d in names:
        if d in urls:
            depts[d] = over_a2a(urls[d])
        elif store.exists(d):
            depts[d] = in_process(DeptGremlin(d, store=store, brain=brain))
    return depts


def default_advocate(store: BoxStore | None = None, brain=None, iso_url: str | None = None,
                     dept_urls: dict[str, str] | None = None, student_box: str = "student") -> Advocate:
    """Every department with a box, in-process by default; URLs route a department over A2A."""
    store = store or MarkdownBoxStore()
    urls = {**dept_urls_from_env(), **(dept_urls or {})}
    if iso_url:
        urls["iso"] = iso_url
    return Advocate(store=store, student_box=student_box, depts=build_depts(store, brain, urls))


if __name__ == "__main__":
    import sys
    from brain import default_brain
    question = " ".join(sys.argv[1:]) or "Can I drop from 16 to 9 units this quarter?"
    print(json.dumps(default_advocate(brain=default_brain()).ask_sync(question).to_dict(), indent=1, ensure_ascii=False))
