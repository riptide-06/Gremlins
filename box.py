"""Boxes: the Markdown documents gremlins reason from. See docs/boxes/README.md.

A box is parsed fresh on every load. Nothing here calls a model. The only
writes are appends to numbered sections (student sections 4 to 8, department
session log), and every appended line is timestamped.

BoxStore is the interface. MarkdownBoxStore reads files under a directory.
GoogleDocBoxStore is a stub for the Docs API (scope documents.readonly).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Protocol

BASE = Path(__file__).resolve().parent
DEFAULT_ROOT = BASE / "docs" / "boxes"
PERMISSION_VALUES = {"yes", "no", "ask", "never"}

# The student profile vocabulary (docs/boxes/student.template.md, docs/CUBBY.md). A department
# may only ask for these; anything else a model invents is dropped before it can stall a question.
STUDENT_FIELDS = (
    "name", "email", "college", "level", "major", "major_declared", "quarter_number", "units", "hours",
    "gpa", "visa", "rcl_on_file", "first_quarter", "final_quarter", "expected_graduation",
    "quarters_to_graduation", "days_to_deadline", "days_to_i20_end", "aid", "aid_type", "part_time_program",
)
_FIELD_SYNONYMS = {
    "units": ("credits", "current_units", "enrolled_units", "units_this_quarter", "current_credits", "enrollment", "course_load", "unit_count", "credit_count"),
    "hours": ("work_hours", "weekly_hours", "on_campus_hours", "current_on_campus_hours", "current_hours", "hours_per_week", "job_hours", "employment_hours", "current_work_hours"),
    "visa": ("visa_status", "visa_type", "immigration_status", "f1_status", "f_1_status", "status", "international"),
    "gpa": ("cumulative_gpa", "ucsc_gpa", "term_gpa", "grade_point_average"),
    "major_declared": ("declared", "declared_major", "declaration_status", "major_declaration", "is_declared"),
    "rcl_on_file": ("rcl", "rcl_status", "rcl_approved", "reduced_course_load", "rcl_authorization", "issp_approval", "issp_rcl_approval"),
    "part_time_program": ("part_time", "part_time_status", "part_time_program_approved", "part_time_approval", "official_part_time_program"),
    "final_quarter": ("last_quarter", "final_term", "graduating_this_quarter", "is_final_quarter"),
    "first_quarter": ("first_term", "is_first_quarter", "new_student"),
    "quarter_number": ("quarter", "current_quarter", "quarters_completed", "quarters_enrolled", "term_number"),
    "expected_graduation": ("graduation_date", "graduation_quarter", "expected_grad", "program_end_date", "i20_end_date"),
    "quarters_to_graduation": ("quarters_left", "quarters_remaining", "terms_remaining"),
    "days_to_deadline": ("deadline", "add_drop_deadline", "days_until_deadline", "drop_deadline"),
    "days_to_i20_end": ("i20_days_left", "days_to_program_end", "program_end"),
    "aid": ("financial_aid", "has_aid", "receives_aid", "aid_status", "scholarship"),
    "aid_type": ("scholarship_type", "aid_kind", "grant_type"),
    "college": ("college_affiliation", "residential_college"),
    "level": ("degree_level", "student_level", "program_level", "undergraduate"),
    "major": ("program", "degree", "field_of_study"),
}
_SYNONYM_INDEX = {alias: field for field, aliases in _FIELD_SYNONYMS.items() for alias in aliases}


def normalize_field(name: str) -> str | None:
    """Map a model-written field name onto the vocabulary, or None if it is not a student field."""
    key = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    if key in STUDENT_FIELDS:
        return key
    if key in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[key]
    for field_name in STUDENT_FIELDS:            # "current_units_enrolled" -> units
        if re.search(rf"(^|_){re.escape(field_name)}(_|$)", key):
            return field_name
    return None

_SECTION = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$")
_KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")
_ID_LINE = re.compile(r"^([FPQE])-(\d+[A-Za-z0-9]*)\s*\|\s*(.*)$")
_TABLE_SEP = re.compile(r"^\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_CLAUSE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|<=|>=|<|>|~)\s*(.*?)\s*$")


@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    authority: str
    source: str
    verified: bool


@dataclass(frozen=True)
class Precedence:
    id: str
    text: str
    wins: str = ""
    loses: str = ""


@dataclass(frozen=True)
class FAQ:
    id: str
    question: str
    answer: str


@dataclass(frozen=True)
class Escalation:
    id: str
    text: str
    when: str


@dataclass
class Section:
    number: int
    title: str
    lines: list[str] = field(default_factory=list)


@dataclass
class Box:
    name: str
    meta: dict[str, str] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    facts: dict[str, Fact] = field(default_factory=dict)
    precedence: dict[str, Precedence] = field(default_factory=dict)
    faq: dict[str, FAQ] = field(default_factory=dict)
    escalations: dict[str, Escalation] = field(default_factory=dict)
    permissions: dict[str, dict[str, str]] = field(default_factory=dict)
    preferences: list[str] = field(default_factory=list)
    text: str = ""

    # ---- derived views -------------------------------------------------
    @property
    def authority_order(self) -> list[str]:
        raw = self.meta.get("authority_order") or self.fields.get("authority_order") or ""
        return [p.strip().lower() for p in raw.split(">") if p.strip()]

    def authority_rank(self, level: str) -> int:
        """0 is highest. Unknown levels rank below every known one."""
        order = self.authority_order
        level = (level or "").strip().lower()
        return order.index(level) if level in order else len(order)

    def highest_authority(self, cite_ids) -> str:
        levels = [self.facts[c].authority for c in cite_ids if c in self.facts]
        if not levels:
            return ""
        return min(levels, key=self.authority_rank)

    @property
    def ids(self) -> set[str]:
        return set(self.facts) | set(self.precedence) | set(self.faq) | set(self.escalations)

    def has(self, cite: str) -> bool:
        return cite in self.ids

    def section(self, number: int) -> Section | None:
        return next((s for s in self.sections if s.number == number), None)

    def permission(self, field_name: str, dept: str) -> str:
        """Permission for one field toward one department. Unknown is `never`."""
        row = self.permissions.get(field_name)
        if not row:
            return "never"
        for key, value in row.items():
            if key.lower() == dept.lower():
                return value
        return "never"

    @property
    def departments(self) -> list[str]:
        seen: list[str] = []
        for row in self.permissions.values():
            for dept in row:
                if dept not in seen:
                    seen.append(dept)
        return seen

    def matching_escalations(self, context: dict, question: str = "") -> list[Escalation]:
        scope = {**context, "question": question}
        return [e for e in self.escalations.values() if match_condition(e.when, scope)]

    def knowledge_text(self) -> str:
        """The department knowledge a prompt may contain: facts, precedence, FAQ, triggers."""
        out: list[str] = []
        if self.facts:
            out.append("FACTS (id | fact | authority | source | verified)")
            out += [f"{f.id} | {f.text} | {f.authority} | {f.source} | {'yes' if f.verified else 'no'}"
                    for f in self.facts.values()]
        if self.precedence:
            out.append("\nPRECEDENCE (id | rule | wins | loses)")
            out += [f"{p.id} | {p.text} | {p.wins} | {p.loses}" for p in self.precedence.values()]
        if self.faq:
            out.append("\nFAQ (id | question | answer)")
            out += [f"{q.id} | {q.question} | {q.answer}" for q in self.faq.values()]
        if self.escalations:
            out.append("\nESCALATION TRIGGERS (id | trigger | when)")
            out += [f"{e.id} | {e.text} | {e.when}" for e in self.escalations.values()]
        return "\n".join(out)


# ---- parsing -----------------------------------------------------------
def _split(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _yes(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "y", "1"}


def parse_box(text: str, name: str = "box") -> Box:
    box = Box(name=name, text=text)
    current: Section | None = None
    table_header: list[str] | None = None
    in_table = False
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = _SECTION.match(line)
        if heading:
            current = Section(int(heading.group(1)), heading.group(2))
            box.sections.append(current)
            table_header, in_table = None, False
            continue
        if line.startswith("#"):
            table_header, in_table = None, False
            continue
        if current is not None:
            current.lines.append(line)
        stripped = line.strip()
        if not stripped:
            table_header, in_table = None, False
            continue

        # permissions table
        if in_table and table_header:
            if _TABLE_SEP.match(stripped):
                continue
            cells = _split(stripped)
            if "|" in stripped and cells and cells[0]:
                row = {}
                for dept, value in zip(table_header[1:], cells[1:]):
                    value = value.lower()
                    row[dept] = value if value in PERMISSION_VALUES else "never"
                box.permissions[cells[0]] = row
                continue
            in_table, table_header = False, None
        if "|" in stripped and _split(stripped)[0].lower() == "field":
            table_header = _split(stripped)
            in_table = True
            continue

        idm = _ID_LINE.match(stripped)
        if idm:
            kind, num, rest = idm.groups()
            ident = f"{kind}-{num}"
            cols = _split(rest)
            if kind == "F":
                cols += [""] * (4 - len(cols))
                box.facts[ident] = Fact(ident, cols[0], cols[1].lower(), cols[2], _yes(cols[3]))
            elif kind == "P":
                cols += [""] * (3 - len(cols))
                box.precedence[ident] = Precedence(ident, cols[0], cols[1].lower(), cols[2].lower())
            elif kind == "Q":
                cols += [""] * (2 - len(cols))
                box.faq[ident] = FAQ(ident, cols[0], cols[1])
            elif kind == "E":
                cols += [""] * (2 - len(cols))
                # the `when` column may hold a regex with alternations (a|b|c): rejoin it
                box.escalations[ident] = Escalation(ident, cols[0], "|".join(cols[1:]).strip())
            continue

        kv = _KV.match(stripped)
        if kv and not stripped.startswith("http"):
            key, value = kv.group(1), kv.group(2).strip()
            if key == "prefer":
                box.preferences.append(value)
            elif current is None:
                box.meta[key] = value
            elif value:
                box.fields[key] = value   # a blank `key:` line is a field the student has not filled in
    return box


# ---- conditions --------------------------------------------------------
def _coerce(value: str):
    v = value.strip().strip('"').strip("'")
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v.lower()


def _eval_clause(clause: str, scope: dict) -> bool:
    m = _CLAUSE.match(clause)
    if not m:
        return False
    key, op, rhs = m.groups()
    if key not in scope or scope[key] is None:
        return False
    left_raw = scope[key]
    if op == "~":
        try:
            return re.search(rhs, str(left_raw), re.IGNORECASE) is not None
        except re.error:
            return False
    left = _coerce(str(left_raw))
    right = _coerce(rhs)
    if isinstance(left, (int, float)) != isinstance(right, (int, float)):
        # number vs text: only equality is meaningful, never ordering
        left, right = str(left).lower(), str(right).lower()
        if op not in ("==", "!="):
            return False
    try:
        return {"==": left == right, "!=": left != right, "<": left < right,
                "<=": left <= right, ">": left > right, ">=": left >= right}[op]
    except TypeError:
        return False


def match_condition(when: str, scope: dict) -> bool:
    """`a == 1 and b ~ x or c < 3`; `and` binds tighter than `or`. Empty never matches."""
    if not when or not when.strip():
        return False
    return any(all(_eval_clause(c, scope) for c in re.split(r"\s+and\s+", group))
               for group in re.split(r"\s+or\s+", when.strip()))


# ---- stores ------------------------------------------------------------
def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def log_line(kind: str, *cols) -> str:
    cells = [stamp(), kind, *[str(c).replace("|", "/").replace("\n", " ") for c in cols]]
    return " | ".join(cells)


class BoxStore(Protocol):
    def exists(self, name: str) -> bool: ...
    def load(self, name: str) -> Box: ...
    def append(self, name: str, section: int, line: str) -> None: ...
    def write(self, name: str, text: str) -> None: ...


class MarkdownBoxStore:
    """Boxes as `<root>/<name>.md`. Falls back to `<name>.example.md` when the
    real export has not been dropped yet."""

    def __init__(self, root: str | os.PathLike | None = None):
        self.root = Path(root or os.environ.get("BOX_DIR") or DEFAULT_ROOT)

    def path(self, name: str) -> Path:
        if "/" in name or "\\" in name or name.startswith("."):
            raise ValueError("Box names are plain identifiers.")
        real = self.root / f"{name}.md"
        if real.exists():
            return real
        example = self.root / f"{name}.example.md"
        return example if example.exists() else real

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def load(self, name: str) -> Box:
        path = self.path(name)
        return parse_box(path.read_text(encoding="utf-8"), name)

    def write(self, name: str, text: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{name}.md").write_text(text, encoding="utf-8")

    def append(self, name: str, section: int, line: str) -> None:
        path = self.path(name)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        start = next((i for i, l in enumerate(lines)
                      if (m := _SECTION.match(l)) and int(m.group(1)) == section), None)
        if start is None:
            raise ValueError(f"Box {name} has no section {section}.")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        # keep one blank line after the heading, insert before the next heading
        block = lines[start + 1:end]
        while block and not block[-1].strip():
            block.pop()
        if not block:
            block = [""]
        new = lines[:start + 1] + block + [line.replace("\n", " ").rstrip(), ""] + lines[end:]
        path.write_text("\n".join(new).rstrip("\n") + "\n", encoding="utf-8")

    def set_field(self, name: str, key: str, value: str) -> None:
        """Change one `key: value` profile line in place (used by the demo to
        flip a field and re-ask). Not an agent tool."""
        path = self.path(name)
        pattern = re.compile(rf"^{re.escape(key)}:\s*.*$", re.MULTILINE)
        text, n = pattern.subn(f"{key}: {value}", path.read_text(encoding="utf-8"), count=1)
        if not n:
            raise KeyError(key)
        path.write_text(text, encoding="utf-8")

    def set_permission(self, name: str, field_name: str, dept: str, value: str) -> None:
        """Change one cell of the student's sharing table (the student's own decision, never an agent's)."""
        path = self.path(name)
        text = path.read_text(encoding="utf-8")
        old, new = permission_row_edit(text, field_name, dept, value)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")


def permission_row_edit(text: str, field_name: str, dept: str, value: str) -> tuple[str, str]:
    """The (old line, new line) pair that sets one cell of the sharing-permissions table.
    Raises KeyError when the field row or the department column does not exist."""
    value = value.strip().lower()
    if value not in PERMISSION_VALUES:
        raise ValueError(f"permission must be one of {sorted(PERMISSION_VALUES)}")
    lines = text.splitlines()
    header_i = next((i for i, l in enumerate(lines) if "|" in l and _split(l)[0].lower() == "field"), None)
    if header_i is None:
        raise KeyError("permissions table")
    header = _split(lines[header_i])
    col = next((i for i, h in enumerate(header) if h.lower() == dept.lower()), None)
    if col is None or col == 0:
        raise KeyError(dept)
    for l in lines[header_i + 1:]:
        if not l.strip():
            break
        cells = _split(l)
        if cells and cells[0] == field_name and not _TABLE_SEP.match(l):
            cells += [""] * (len(header) - len(cells))
            cells[col] = value
            return l, " | ".join(cells)
    raise KeyError(field_name)


class GoogleDocBoxStore:
    """TODO: read a box straight from the student's Google Doc.

    Plan: reuse the Google OAuth client registered in gremlin_app.create_app,
    request the additional scope `https://www.googleapis.com/auth/documents.readonly`,
    call `documents.get(documentId)` and flatten `body.content` paragraphs to
    Markdown lines before handing them to parse_box. Appends go through
    `documents.batchUpdate` with an insertText request anchored at the end of
    the numbered section. Nothing is implemented yet; every method raises.
    """

    SCOPE = "https://www.googleapis.com/auth/documents.readonly"

    def __init__(self, doc_ids: dict[str, str], credentials=None):
        self.doc_ids, self.credentials = doc_ids, credentials

    def exists(self, name: str) -> bool:
        return name in self.doc_ids

    def load(self, name: str) -> Box:
        raise NotImplementedError("GoogleDocBoxStore.load: wire the Docs API (documents.readonly).")

    def append(self, name: str, section: int, line: str) -> None:
        raise NotImplementedError("GoogleDocBoxStore.append: needs documents scope, not just readonly.")

    def write(self, name: str, text: str) -> None:
        raise NotImplementedError("GoogleDocBoxStore.write is not supported; create the Doc by hand.")


STUDENT_TEMPLATE = """# Student box

student: {student}
authority_order: federal > state > campus > department
synthetic: no
schema: 2
updated: {today}

## 1. Profile

name: {name}
email: {email}
level: undergraduate
rcl_on_file: no
part_time_program: no

## 2. Preferences

prefer: fewer units
prefer: more hours
prefer: sooner

## 3. Sharing permissions

Field | ISO | CMPM | College | FinAid
--- | --- | --- | --- | ---
name | never | never | never | never
email | never | never | never | never
level | yes | yes | yes | yes
visa | yes | no | no | ask
rcl_on_file | yes | no | ask | no
first_quarter | yes | no | no | no
units | ask | ask | ask | ask
hours | ask | ask | ask | ask
gpa | no | ask | ask | ask
major | ask | yes | yes | ask
major_declared | ask | yes | yes | no
final_quarter | ask | ask | ask | ask
days_to_deadline | yes | yes | yes | yes
days_to_i20_end | yes | no | no | no
aid | no | no | ask | ask
aid_type | never | no | no | ask
part_time_program | ask | ask | ask | ask

## 4. Session log

## 5. Converged answers

## 6. Escalated and disputed briefs

## 7. Shared fields and approvals

## 8. Open items the student must answer
"""


def seed_student_box(store: BoxStore, name: str, student_id: str, display_name: str, email: str) -> bool:
    """Create a student box on first login. Returns False if one already exists."""
    if store.exists(name):
        return False
    clean = lambda s: str(s or "").replace("\n", " ").replace("{", "(").replace("}", ")").strip()
    template = STUDENT_TEMPLATE
    root = getattr(store, "root", None)
    if root is not None and (Path(root) / "student.template.md").exists():
        template = (Path(root) / "student.template.md").read_text(encoding="utf-8")
    store.write(name, template.format(student=clean(student_id), name=clean(display_name),
                                      email=clean(email), today=stamp()[:10]))
    return True
