# Eval: gremlins vs baseline

Two runs are recorded here. The first (Saturday evening) used one department box and six
questions. The second is the ten-case eval in `eval.py` against the four real boxes; run
`uv run eval.py` and paste the table into the section at the bottom.

## Run 1: one department (ISO example box), six questions

Run on 2026-10-10 (PT) with groq/openai/gpt-oss-120b (fallback nvidia_nim nemotron-3-super), temperature 0, JSON mode.
Six questions, two per expected outcome. Each case runs on a fresh copy of the example boxes.

- **gremlin**: advocate + wall + ISO department gremlin (box-only prompt, cites verified, escalation decided in code).
- **baseline**: one LLM call given the question, the full ISO box, and the full student box.

Columns: correct outcome k/n; uncited claims = cites not in the box + options without a valid cite + answer sentences without a valid [id] (same counter for both conditions); student fields that left the box = profile fields present in what the model saw (never/no fields in parentheses).

condition | correct outcome | uncited claims | student fields that left the box (protected)
--- | --- | --- | ---
gremlin | 6/6 | 0 | 24 (0)
baseline | 3/6 | 28 | 72 (18)

case | expected | gremlin | baseline
--- | --- | --- | ---
c1 | CONVERGED | CONVERGED | CONVERGED
c2 | CONVERGED | CONVERGED | CONVERGED
e1 | ESCALATED | ESCALATED | CONVERGED
e2 | ESCALATED | ESCALATED (brain failed) | CONVERGED
a1 | ASK_STUDENT | ASK_STUDENT | UNANSWERED
a2 | ASK_STUDENT | ASK_STUDENT | ASK_STUDENT

Reproduce: `uv run eval.py --json`. Model output varies slightly between runs even at temperature 0; a `(brain failed)` flag means both providers failed or returned non-conforming JSON for that case, and the verdict came from code alone.

## Per-case answers (first 200 chars)

### c1: I want to drop from 16 to 9 units this quarter because of my job. Can I?
- **gremlin** CONVERGED, uncited 0, fields left 4 (0 protected): You cannot drop to 9 units without an approved Reduced Course Load (RCL); dropping below the 12‑unit minimum without an RCL is a status violation [F-02]. Your job reason does not qualify for a medical
- **baseline** CONVERGED, uncited 3, fields left 12 (3 protected): You cannot drop to 9 units without an approved Reduced Course Load (RCL). Dropping below the 12‑unit full‑time minimum without an RCL is a status violation [F-02]. An RCL for academic difficulty (e.g.

### c2: Do I have to enroll in classes during summer quarter?
- **gremlin** CONVERGED, uncited 0, fields left 4 (0 protected): No, you do not have to enroll in summer quarter unless it is your first or final quarter of the program [F-08].
- **baseline** CONVERGED, uncited 1, fields left 12 (3 protected): No, you are not required to enroll in classes during the summer quarter unless it is your first or final quarter of the program.

### e1: I have a medical condition and need to take fewer units this quarter. What are my options?
- **gremlin** ESCALATED, uncited 0, fields left 4 (0 protected): You can request a medical Reduced Course Load (RCL), which may reduce your enrollment to zero units and does not require a minimum unit count [F-03] [F-07]. To obtain it, you must submit a completed R
- **baseline** CONVERGED, uncited 14, fields left 12 (3 protected): You can request a Reduced Course Load (RCL) based on your medical condition. A medical RCL may be approved for up to 12 months total and can reduce your enrollment to zero units, so you can take as fe

### e2: It is my final quarter and I only need 8 units to graduate. Can I enroll in just those?
- **gremlin** ESCALATED, uncited 0, fields left 4 (0 protected): (empty)
- **baseline** CONVERGED, uncited 3, fields left 12 (3 protected): Yes, as this is your final quarter you may enroll only in the 8 units you need to complete your degree, but you must obtain a Reduced Course Load (RCL) approval for the final term from the Internation

### a1: Am I currently over the on-campus work-hour limit?
- **gremlin** ASK_STUDENT, uncited 0, fields left 4 (0 protected): On-campus employment is limited to 20 hours per week while school is in session [F-06]; to tell you if you are over the limit I need to know your current weekly work hours.
- **baseline** UNANSWERED, uncited 0, fields left 12 (3 protected): (empty)

### a2: If I drop my one in-person class, will my remaining online classes keep me full-time?
- **gremlin** ASK_STUDENT, uncited 0, fields left 4 (0 protected): You can remain full‑time only if, after dropping the in‑person class, you still have at least 12 units counted toward the full‑time minimum, and you are not relying on more than one online or distance
- **baseline** ASK_STUDENT, uncited 7, fields left 12 (3 protected): To stay in full‑time F‑1 status you must be enrolled in at least 12 units that count toward the minimum each quarter. Federal rules allow only one online/distance class (up to 3 units) to count toward


## Run 2: four departments, ten cases (docs/QUESTIONS.md)

Run on 2026-10-11 00:50 PT, live models (groq/openai/gpt-oss-120b first, nvidia_nim
nemotron-3-super fallback), temperature 0, JSON mode, replay cache cold. The gremlin
condition is the advocate plus four department gremlins (ISO, CMPM advising, Crown
college advising, financial aid) behind the wall; the baseline is one model call given all
four boxes and the whole student box.

condition | correct outcome | uncited claims | student fields that left the box (protected)
--- | --- | --- | ---
gremlin | 9/10 | 16, every one deleted by the wall before the student saw it | 144 (0)
baseline | 3/10 | 33, all shown to the student | 210 (120)

case | expected | gremlin | asked | baseline
--- | --- | --- | --- | ---
c1 | CONVERGED | CONVERGED | iso,cmpm,college,finaid | ASK_STUDENT
c2 | CONVERGED | CONVERGED | iso,cmpm | CONVERGED
p1 | CONVERGED (precedence) | CONVERGED | iso,cmpm,college,finaid | ASK_STUDENT
e1 | ESCALATED | ESCALATED | iso,cmpm,college,finaid | ESCALATED
e2 | ESCALATED | ESCALATED | iso,cmpm,college,finaid | CONVERGED
a1 | ASK_STUDENT | ASK_STUDENT | iso,college | ESCALATED
a2 | ASK_STUDENT | CONVERGED (a model call failed on the fallback path) | iso,cmpm,college,finaid | CONVERGED
d1 | DISPUTED or CONVERGED by precedence | DISPUTED | iso,cmpm,college,finaid | CONVERGED
u1 | UNANSWERED | UNANSWERED | iso,cmpm,college,finaid | ASK_STUDENT
x1 | ESCALATED | ESCALATED (one model call failed, verdict still decided in code) | iso,cmpm,college,finaid | UNANSWERED

How to read it. "Student fields that left the box" counts profile fields present in what a
model saw, summed over cases; the gremlin shares only permitted, relevant fields per
department (144 field-sends over ten cases, none of them `no`/`never` fields), the baseline
pastes the whole box every time (210, of which 120 are fields the student marked `no` or
`never`, name and email included). The baseline's "correct" column is its self-reported
verdict mapped onto the same vocabulary; it has no wall, so a right verdict there still comes
with uncited, unverifiable sentences.

The one miss (a2) coincided with a provider rate limit during the burst; the sibling question
a1 asked for `hours` correctly in the same run and in the demo. The eval table now prints the
failure class next to the verdict so this is visible in future runs.

What changed between run 1 of this eval (6/10, same morning) and this run: departments were
asking for invented field names (`issp_approval`, `CMPM_120_modality`), which stalled
questions as ASK_STUDENT; needs are now normalized onto the student vocabulary in code, and a
position's authority in a conflict comes from the facts under its best option rather than
everything the office mentioned (financial aid quoting a federal Pell rule had tied with ISO).
These are development-time iterations on the same ten questions, not a held-out result.

Demo run (same build, `uv run demo.py`): c1 CONVERGED; p1 CONVERGED with the override
recorded; e1 ESCALATED (E-01, E-04); a1 ASK_STUDENT for `hours`, CONVERGED after approval;
d1 ASK_STUDENT for `gpa`, DISPUTED after approval; e2 ESCALATED (E-02) on the same question
as c1 after `days_to_deadline` moved to 2.
