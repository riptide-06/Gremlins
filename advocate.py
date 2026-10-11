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

from box import Box, BoxStore, MarkdownBoxStore, log_line, match_condition
from dept_gremlin import DeptGremlin, ask_dept, empty_answer
from wall import SHARED_SECTION, Inbound, Outbound, approved_fields, inbound, outbound, shared_line

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
    pending: list[tuple[int, str]] = field(default_factory=list)   # SHARED lines, written with the verdict in one edit
    invited_by: list[str] = field(default_factory=list)            # departments whose referral pulled this one in
    stance: str = ""                                               # hold | revise | agree after a reconsider round

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
    transcript: list[dict] = field(default_factory=list)   # every department turn, in order (deliberation mode)
    deliberated: bool = False

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
                "failed": [d.dept for d in self.depts if d.answer.get("failed")],
                "deliberated": self.deliberated, "transcript": self.transcript,
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


_COND_KEYS = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*)\s*(?:==|!=|<=|>=|<|>|~)")


def serves(when: str, student: Box, question: str = "") -> bool:
    """A box's `serves:` line says who the office is for, in the escalation condition grammar
    over the student's own fields plus the question (`major ~ game design or question ~ CMPM`):
    a major office serves its majors, and anyone asking about one of its courses. The advocate
    reads the student's box for this; nothing is shared. No line, or a condition on a field
    the student has not filled in, means the office is consulted."""
    when = (when or "").strip()
    if not when:
        return True
    scope = {**student.fields, "question": question}
    if any(k not in scope for k in _COND_KEYS.findall(when)):
        return True
    return match_condition(when, scope)


def append_many(store: BoxStore, name: str, items: list[tuple[int, str]]) -> None:
    """One edit when the store can batch (the cubby), one append per line otherwise."""
    if not items:
        return
    batch = getattr(store, "append_many", None)
    if batch is not None:
        batch(name, list(items))
    else:
        for section, line in items:
            store.append(name, section, line)


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
                meta = self.dept_box(d).meta
            except (FileNotFoundError, OSError, ValueError):
                meta = {}
            if not serves(meta.get("serves", ""), student, question):
                continue          # not this student's office, and the question is not about its courses
            topics = meta.get("topics", "").strip()
            if not topics:
                chosen.append(d)
                continue
            try:
                if re.search(topics, question, re.IGNORECASE):
                    chosen.append(d)
            except re.error:
                chosen.append(d)
        return chosen or [d for d in candidates if serves(self._meta(d).get("serves", ""), student, question)] or candidates

    def _meta(self, dept: str) -> dict:
        try:
            return self.dept_box(dept).meta
        except (FileNotFoundError, OSError, ValueError):
            return {}

    def dept_box(self, dept: str) -> Box:
        return self.store.load(self.dept_boxes.get(dept, dept))

    # -- one department, up to two rounds ---------------------------------------
    async def consult(self, dept: str, student: Box, question: str, session_id: str,
                      declined: set[str] | None = None, peers: list[dict] | None = None,
                      reconsider: bool = False) -> DeptResult:
        """One department, through the wall. `peers` are other offices' cited positions (a
        referral or a reconsider round): they ride in the context as `other_offices`, policy
        text only, never another office's student fields."""
        result = DeptResult(dept=dept)
        dept_box = self.dept_box(dept)
        approvals = approved_fields(student, dept)
        fields = relevant_fields(dept_box, student)
        declined = set(declined or ())
        for round_no in (1, 2):
            out = outbound(student, dept, question, approvals, fields=fields, declined=declined)
            if peers:
                out.context["other_offices"] = [dict(p) for p in peers]
                if reconsider:
                    out.context["reconsider"] = True
            result.rounds.append(out)
            if (line := shared_line(out, session_id)):
                result.pending.append((SHARED_SECTION, line))
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
    async def ask(self, question: str, session_id: str | None = None, declined: set[str] | None = None,
                  deliberate: bool = False, on_turn=None) -> Verdict:
        """Round 1: every department in scope at once, none sees another (no central decision-maker).
        With `deliberate`: a department that says another office must weigh in (`refers`) pulls it
        into round 2 with the referring office's cited position; and when two offices still differ
        at equal authority, round 3 gives each the other's position once and asks whether its own
        box changes its recommendation. Agreement after that is CONVERGED with the exchange
        recorded; disagreement stays DISPUTED, kept rather than averaged. `on_turn(turn)` is
        called as each department speaks."""
        session_id = session_id or uuid.uuid4().hex[:12]
        student = self.store.load(self.student_box)  # fresh: a flipped field changes the verdict
        depts = self.in_scope(student, question)
        transcript: list[dict] = []

        def say(r: DeptResult, round_no: int, kind: str, **extra) -> None:
            turn = {"round": round_no, "kind": kind, **self._position_of(r.dept, r.answer), **extra}
            transcript.append(turn)
            if on_turn is not None:
                on_turn(turn)

        results = list(await asyncio.gather(*[self.consult(d, student, question, session_id, declined) for d in depts]))
        if deliberate:
            for r in results:
                say(r, 1, "position", refers=list(r.answer.get("refers") or []))
            # round 2: referrals. An office named by another office's box joins, with that position in view.
            known = {d.lower() for d in student.departments} or set(self.depts)
            consulted = {r.dept for r in results}
            invited: dict[str, list[str]] = {}
            for r in results:
                for d in r.answer.get("refers") or []:
                    if d in self.depts and d in known and d not in consulted:
                        invited.setdefault(d, []).append(r.dept)
            if invited:
                joined = list(await asyncio.gather(*[
                    self.consult(d, student, question, session_id, declined,
                                 peers=[self._position_of(b, next(x for x in results if x.dept == b).answer) for b in by])
                    for d, by in invited.items()]))
                for r, (d, by) in zip(joined, invited.items()):
                    r.invited_by = by
                    say(r, 2, "referral", invited_by=by)
                results += joined
            # round 3: the discussion. Every office that took a position hears the others' cited
            # positions once and answers them: hold, revise, or agree, with its own box as the reason.
            # Nobody is asked to reconsider when the student still has to supply a field (the verdict
            # would be ASK_STUDENT either way) or when only one office had anything to say.
            spoke = [r for r in results if (r.answer.get("answer") or r.answer.get("options")) and not r.ask and r.dept in self.depts]
            parties = [r.dept for r in spoke]
            if len(parties) >= 2 and not any(r.ask for r in results):
                before = {r.dept: r for r in results}
                revised = list(await asyncio.gather(*[
                    self.consult(d, student, question, session_id, declined, reconsider=True,
                                 peers=[self._position_of(o, before[o].answer) for o in parties if o != d])
                    for d in parties]))
                for r in revised:
                    old = before[r.dept]
                    r.invited_by = old.invited_by
                    if r.answer.get("answer") or r.answer.get("options"):    # a failed reconsider keeps the first answer
                        r.stance = r.answer.get("stance") or ("hold" if self._same_position(old.answer, r.answer) else "revise")
                        results[results.index(old)] = r
                    else:
                        r = old
                        r.stance = "hold"
                    say(r, 3, "reconsider", stance=r.stance, heard=[o for o in parties if o != r.dept])
        verdict = self.decide(student, question, session_id, results)
        verdict.transcript, verdict.deliberated = transcript, deliberate
        if deliberate:
            stances = [f"{r.dept.upper()} {r.stance}" for r in results if r.stance]
            joined_names = [f"{r.dept.upper()} joined at {','.join(b.upper() for b in r.invited_by)}'s request" for r in results if r.invited_by]
            verdict.brief["deliberation"] = joined_names + stances
        self.write(verdict)
        return verdict

    def ask_sync(self, question: str, session_id: str | None = None, declined: set[str] | None = None,
                 deliberate: bool = False) -> Verdict:
        return asyncio.run(self.ask(question, session_id, declined, deliberate=deliberate))

    def _position_of(self, dept: str, answer: dict) -> dict:
        """What one office says, as the other offices may see it: its recommended option, the
        cites behind it, its authority level, and the cited answer text. No student fields."""
        opts = answer.get("options") or []
        first = opts[0] if opts else {}
        return {"dept": dept, "position": str(first.get("option", "") or "")[:300],
                "units": first.get("units"), "hours": first.get("hours"),
                "cites": list(first.get("cites") or answer.get("cites") or [])[:8],
                "authority": self.position_authority(dept, first) if first else answer.get("authority", ""),
                "text": str(answer.get("answer", ""))[:600], "failed": bool(answer.get("failed"))}

    @staticmethod
    def _same_position(a: dict, b: dict) -> bool:
        fa, fb = (a.get("options") or [{}])[0], (b.get("options") or [{}])[0]
        return fa.get("units") == fb.get("units") and fa.get("option", "").strip().lower() == fb.get("option", "").strip().lower()

    # -- deciding -------------------------------------------------------------------
    def decide(self, student: Box, question: str, session_id: str, results: list[DeptResult]) -> Verdict:
        v = Verdict(kind="UNANSWERED", session_id=session_id, question=question, depts=results)
        answered = [r for r in results if r.answer.get("answer") or r.answer.get("options")]
        v.escalations = sorted({c for r in results if r.answer.get("escalate")
                                for c in r.answer.get("cites", []) if c.startswith("E-")})
        v.ask = sorted({f for r in results for f in r.ask})
        agreed, disputed, decides, precedence, outranked = self._positions(student, answered)
        pooled = [{**o, "dept": r.dept, "authority": r.answer.get("authority", "")}
                  for r in answered for o in r.answer.get("options", [])]
        v.cites = sorted({c for r in results for c in r.answer.get("cites", [])}
                         | {c for o in pooled for c in o.get("cites", [])})
        # The menu the student ranks is what the offices whose position stands offered. An office
        # outranked by precedence keeps its voice in the answer text and the brief, but its options
        # cannot come out on top of the office that overruled it. A dispute keeps everything.
        menu = pooled if disputed else [o for o in pooled if o["dept"] not in outranked]
        v.options = score_options(menu, student.preferences)
        v.best = v.options[0] if v.options else None
        v.authority = student.highest_authority(v.cites) or next((r.answer.get("authority", "") for r in answered), "")
        # each department speaks in its own voice; a disagreement should read as one
        v.answer = " ".join(f"{r.dept.upper()}: {r.answer['answer'].strip()}" for r in answered if r.answer.get("answer"))

        if v.escalations or any(r.answer.get("escalate") for r in results):
            v.kind = "ESCALATED"
            # E-xx ids are per box (college E-02 is not ISO's E-02): read each trigger's text from the
            # box of the department whose answer fired it.
            fired: list[str] = []
            for r in results:
                if not r.answer.get("escalate"):
                    continue
                try:
                    rules = self.dept_box(r.dept).escalations
                except (FileNotFoundError, OSError, ValueError):
                    rules = {}
                for c in r.answer.get("cites", []):
                    if c.startswith("E-"):
                        fired.append(f"{r.dept.upper()} {c}: {rules[c].text if c in rules else 'a trigger in its box matched'}")
            v.brief = {"agreed": agreed, "disputed": disputed, "precedence": precedence,
                       "options": [o["option"] for o in v.options[:4]],
                       "triggers": fired,
                       "resolve": fired + [f"student supplies {f}" for f in v.ask],
                       "decides": sorted({r.dept.upper() for r in results if r.answer.get("escalate")})}
        elif v.ask:
            v.kind = "ASK_STUDENT"
        elif disputed:
            v.kind = "DISPUTED"
            v.brief = {"agreed": agreed, "disputed": disputed, "precedence": precedence,
                       "options": [o["option"] for o in v.options[:4]],
                       "resolve": ["a precedence rule (P-xx) or authority_order ranking one department above the other",
                                   "or a human decision"],
                       "decides": decides}
        elif answered:
            v.kind = "CONVERGED"
            if precedence:  # a conflict existed but authority_order settled it
                v.brief = {"agreed": agreed, "precedence": precedence}
        return v

    def position_authority(self, dept: str, option: dict) -> str:
        """The authority level behind one option: the box's level for the rule the option rests on
        (`basis`, a fact it cites), else the highest level among its cites. Read from the box, never
        from the model's own claim."""
        try:
            box = self.dept_box(dept)
        except (FileNotFoundError, OSError, ValueError):
            return ""
        basis = option.get("basis")
        if basis in box.facts:
            return box.facts[basis].authority
        return box.highest_authority(option.get("cites", []))

    def _positions(self, student: Box, answered: list[DeptResult]) -> tuple[list[str], list[str], list[str], list[str], set[str]]:
        """Compare departments by the option each one recommends (its first), by `units`. The
        student's preferences rank the pooled menu later; they do not decide whether two offices
        disagree. The authority behind a position is the level of the rule it rests on, so a campus
        office quoting a federal rule in passing does not outrank the office that administers it.
        Equal authority -> disputed; otherwise authority_order decides. Returns (agreed, disputed,
        decides: the departments in a dispute, precedence: who outranked whom, outranked: the
        departments whose position lost to a higher authority)."""
        agreed, disputed, decides, precedence = [], [], [], []
        outranked: set[str] = set()
        best = {}
        for r in answered:
            opts = [o for o in r.answer.get("options", []) if isinstance(o.get("units"), (int, float))]
            if opts:
                best[r.dept] = (opts[0]["units"], self.position_authority(r.dept, opts[0]) or r.answer.get("authority", ""), opts[0]["option"])
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
                    winner, loser = (a, b) if ra < rb else (b, a)
                    outranked.add(loser)
                    precedence.append(f"{winner.upper()} wins by authority_order ({best[winner][1]}) over {loser.upper()} ({best[loser][1]})")
                    agreed.append(f"{winner.upper()} position stands: {best[winner][2]}")
        if len(answered) == 1 and not agreed and not disputed:
            agreed.append(f"{answered[0].dept.upper()} is the only department in scope")
        return agreed, disputed, sorted(set(decides)), precedence, outranked

    # -- writing back ----------------------------------------------------------------
    def write(self, v: Verdict) -> None:
        """Everything a question leaves in the student box (what was shared per department, the
        verdict line, the session line) goes in one edit: one round trip to the cubby instead of
        one per department, and no chance of racing our own previous write."""
        q = v.question[:160]
        best = v.best["option"][:160] if v.best else "-"
        if v.kind == "CONVERGED":
            v.written.append((SECTION_CONVERGED, log_line("CONVERGED", v.session_id, q, best, ",".join(v.cites) or "-", v.authority or "-")))
        elif v.kind in ("ESCALATED", "DISPUTED"):
            b = v.brief
            v.written.append((SECTION_BRIEFS, log_line(
                v.kind, v.session_id, q, "triggers=" + (",".join(v.escalations) or "-"),
                "agreed=" + ("; ".join(b.get("agreed", [])) or "-"), "disputed=" + ("; ".join(b.get("disputed", [])) or "-"),
                "options=" + ("; ".join(b.get("options", [])) or "-"), "resolve=" + ("; ".join(b.get("resolve", [])) or "-"),
                "decides=" + (",".join(b.get("decides", [])) or "-"))))
        elif v.kind == "ASK_STUDENT":
            depts = ",".join(sorted({r.dept for r in v.depts if r.ask}))
            v.written.append((SECTION_OPEN, log_line("ASK_STUDENT", v.session_id, q, ",".join(v.ask), depts)))
        v.written.append((SECTION_LOG, log_line("SESSION", v.session_id, v.kind, ",".join(r.dept for r in v.depts) or "-",
                                                ",".join(v.cites) or "-", f"dropped={v.dropped}")))
        if v.deliberated:
            v.written.append((SECTION_LOG, log_line("DELIBERATION", v.session_id,
                                                    ",".join(f"{t['dept']}:{t['kind']}" + (f"={t['stance']}" if t.get("stance") else "") for t in v.transcript) or "-",
                                                    "; ".join(v.brief.get("deliberation", [])) or "-")))
        shared = [item for r in v.depts for item in r.pending]
        append_many(self.store, self.student_box, shared + v.written)

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
