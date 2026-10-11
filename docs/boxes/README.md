# Boxes

A box is one Markdown file (an export of a Google Doc) that is the *only*
thing a gremlin reasons from. Department boxes are read-only policy. The
student box is the student's own memory plus sharing permissions.

Drop `iso.md` and `student.md` here. Until they exist, the loader falls back
to `iso.example.md` and `student.example.md` (synthetic data only).

## Line grammar (parsed by `box.py`)

| Shape | Meaning |
|---|---|
| `key: value` | metadata (before the first heading) or profile field (inside a section) |
| `## N. Title` | numbered section; everything until the next `## ` belongs to it |
| `F-xx \| fact \| authority \| source \| verified` | fact; authority is one of the `authority_order` levels; verified is yes/no |
| `P-xx \| rule \| wins \| loses` | precedence rule between two authority levels (last two columns optional) |
| `Q-xx \| question \| answer` | FAQ; answers may cite `[F-xx]` |
| `E-xx \| trigger \| when` | escalation trigger; `when` is a condition over context fields (see below) |
| `Field \| ISO \| Registrar` + `---` + rows | sharing permissions table; cell values are `yes`, `no`, `ask`, `never` |
| `prefer: fewer units` | preference line, kept in order |
| `authority_order: federal > state > campus > department` | precedence of authority levels, highest first |

`when` conditions: clauses joined by ` and ` / ` or `, each `field op value`.
Ops: `==`, `!=`, `<`, `<=`, `>`, `>=`, `~` (case-insensitive regex search).
`question` is always available as a field. A missing field makes the clause false.

## Student box sections

1. Profile (`key: value`)
2. Preferences (`prefer:` lines, `authority_order:`)
3. Sharing permissions (table)
4. Session log (append only, pointers only)
5. Converged answers (append only)
6. Escalated and disputed briefs (append only)
7. Shared fields and approvals (append only)
8. Open items the student must answer (append only)

Sections 4 to 8 are the only sections an agent writes to. Appended lines are
`timestamp | kind | fields...`.

## Department box sections

1. Facts, 2. Precedence, 3. FAQ, 4. Escalation triggers, 5. Session log (append only).
