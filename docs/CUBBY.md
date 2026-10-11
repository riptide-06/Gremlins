# What goes in a cubby

A cubby is not an inbox. It is the student's state, written by people and
agents the student allowed in, read only by the student's own gremlin. Email
piles up messages; a cubby holds the current answer to "what is true about me
and what do I still have to do". That is the whole difference, and it is why
the gremlin never reads a stale value: the code picks the current entry, the
model never sees the old one.

## The five kinds of entry

| kind | who writes it | example |
|---|---|---|
| `fact` | a department (or the student) | `units = 15`, `rcl_on_file = yes (winter 2027, 8 units)`, `advising_hold = cleared` |
| `answer` | the student's gremlin | a CONVERGED / DISPUTED / ESCALATED verdict with its cites |
| `todo` | the student's gremlin, derived from facts and answers | `Submit RCL request in iGlobal by 2026-11-30 (from ISO F-07)` |
| `permission` | the student only | `hours -> ISO: ask`, `gpa -> FinAid: never` |
| `audit` | any agent, pointers only | `shared units, visa with ISO for session s-0042` |

Nothing else goes in. No chat transcripts, no policy text (that lives in the
department box), no tokens or passwords, no ID numbers, no free-form notes from
a department about the student. A department that wants to tell the student
something writes a `fact` with a source, or it does not write.

## One entry = one line

```
timestamp | contributor | kind | key | value | authority | source | supersedes | expires
```

- `timestamp` ISO 8601, written by the writer's clock, used only for ordering.
- `contributor` `student`, `advocate`, or a department id (`iso`, `cmpm`, `college`, `finaid`).
- `kind` one of the five above.
- `key` a stable name (`units`, `rcl_on_file`, `todo:rcl-request`, `answer:s-0042`).
- `value` the current value, plain text, no newlines.
- `authority` `federal`, `state`, `campus`, `department`, or `student`.
- `source` where it came from: a box line id (`iso F-07`), a form id, a URL, or a session id.
- `supersedes` the timestamp of the entry this replaces, or `-`.
- `expires` a date after which the value is stale, or `-`.

Rule that makes it work: **for each (contributor, key) the latest unexpired
entry is the only one that exists.** Older entries stay on disk for audit and
never enter a prompt. If two contributors assert the same key, the higher
authority wins; equal authority is a dispute and is shown as one.

## How the Markdown student box carries this today

The student box (`docs/boxes/student.md` for the demo student, template in
`student.template.md`) is the same thing in a shape the parser already reads:

| cubby kind | student box section | who writes |
|---|---|---|
| `fact` (about the student) | 1. Profile (`key: value`) | student now; departments later via Drive |
| `permission` | 3. Sharing permissions (table) and 2. Preferences | student only |
| `audit` | 4. Session log and 7. Shared fields and approvals | advocate, pointers only |
| `answer` | 5. Converged answers and 6. Escalated and disputed briefs | advocate |
| `todo` | 8. Open items the student must answer | advocate |

Sections 1 to 3 are the student's parameters. The agent reads them and never
edits them. Sections 4 to 8 are append only, one timestamped line per event.

## The profile parameters, and which gremlin needs each

| field | type | used by | why |
|---|---|---|---|
| `name`, `email` | text | nobody outside the box | identity never leaves; `never` for every department |
| `college` | text | college, cmpm, finaid | which college's rules and deadlines apply |
| `level` | undergraduate / graduate | all | full-time minimum differs (12 vs 10 credits) |
| `major`, `major_declared` | text, yes/no | cmpm, iso | CPT needs a declared major; declaration deadline triggers |
| `quarter_number` | number | cmpm, college | declaration deadline (sixth quarter) |
| `units` | number | all | the single most-used fact: full time, aid proration, overload |
| `hours` | number | iso, college | 20-hour cap; advising load practice |
| `gpa` | number | college, cmpm | standing, overload permission, declaration GPA |
| `visa` | F-1 / J-1 / none | iso | whether immigration rules apply at all |
| `rcl_on_file` | yes/no | iso, college | below 12 without it is a status violation |
| `first_quarter`, `final_quarter` | yes/no | iso | academic RCL and final-term RCL rules |
| `expected_graduation`, `quarters_to_graduation` | date, number | cmpm, iso | OPT window, track planning |
| `days_to_deadline` | number | all | add/drop/withdraw escalation; computed by the client from the Registrar calendar |
| `days_to_i20_end` | number | iso | 60-day grace period escalation |
| `aid`, `aid_type` | yes/no, text | finaid | proration and scholarship conditions |
| `part_time_program` | yes/no | college, finaid, iso | changes fees, aid, and whether an RCL is already paired |

A missing field is never guessed. Every `E-xx` condition over a missing field
is false, and a department that needs it returns it under `needs`, which the
advocate turns into an ASK_STUDENT item.

## What the gremlin writes back after a question

```
# 4. Session log            (always, one line)
2026-10-11T06:12:00Z | SESSION | s-0042 | iso,college,finaid | CONVERGED | cites iso:F-01,college:F-04
# 7. Shared fields           (what left, to whom)
2026-10-11T06:12:00Z | SHARED | iso | units,visa,days_to_deadline
# 5. Converged answers       (one line, the answer plus cites)
2026-10-11T06:12:01Z | CONVERGED | s-0042 | 12 units keeps F-1 status and needs no college approval | iso:F-01 college:F-04
# 6. Briefs                  (disputed or escalated: positions, what would resolve it, who decides)
2026-10-11T06:20:00Z | DISPUTED | s-0043 | cmpm: add CMPM 120 now (F-15) vs college: at most two heavy technical courses while working 10h (F-13) | resolves: student priority, on-time graduation vs workload | decides: student with college adviser
# 8. Open items              (ASK_STUDENT)
2026-10-11T06:19:30Z | ASK | s-0043 | college | hours | needed to apply the load practice
```

## Seeding a new student (first login)

Copy `student.template.md`, fill `student`, `name`, `email`, `updated`, leave
everything else blank, and set every department column to `ask` except the
three identity rows (`never`) and `visa`/`rcl_on_file`/`first_quarter` for ISO
(`yes`, because ISO cannot answer anything without them). The student fills
the rest in the cubby page or by telling their gremlin ("I'm taking 15 units"),
which appends a `fact` line and updates the profile value.

## The Drive form (Adam's cubby) and this file

Same entries, different container. In Campus Cubbies the cubby is a Google Doc
the student shares with the gremlin service account in editor mode. Each
contributor appends lines in the nine-column format above. The advocate loads
the doc, keeps the latest entry per (contributor, key), and builds the same
profile the Markdown box gives it. `box.py`'s `GoogleDocBoxStore` is the stub
for that; until it is live, the Markdown file is the cubby.
