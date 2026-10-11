# Gremlins

**When campus offices disagree, the student should not be the one who has to notice.**

Gremlins is a student-controlled advocate for UCSC built on Campus Cubbies. Every
student has a cubby (their own state, in their own Google Drive, only their gremlin
reads it). Every department has a box (its policy, with sources). Department
gremlins answer only from their box and cite every claim. The student's gremlin
asks the departments that matter, shares the minimum the student allowed, applies
precedence in code, and comes back with one of five verdicts instead of a blended
paragraph:

| verdict | meaning | what the student sees |
|---|---|---|
| `CONVERGED` | the departments agree, or a precedence rule settled it | one answer, cites, and (if there was an override) who overrode whom |
| `DISPUTED` | departments conflict at equal authority | both positions, what would resolve it, who decides (the student) |
| `ESCALATED` | an `E-xx` trigger matched the student's situation, in code | a brief for the human who must decide, and what to bring |
| `ASK_STUDENT` | a department needs a field the student has not released | the field, the department, a one-click approve |
| `UNANSWERED` | every department is out of scope, or the models failed | "I don't know", never an invention |

Hackathon teammates: Adam Smith (Computational Media, Campus Cubbies and BayLeaf) and
Tarun Nagaraju. Cloud AI track (Cisco Outshift / AGNTCY, "When AI Agents Disagree"),
October 10 to 11, 2026. Level 3.

## Try it

**Student (the real thing):** open the site, press *Continue with UCSC Google*. That is
Campus Cubbies' own approval page: you sign in with your UCSC account, consent once, and
your My Cubby folder exists in your Drive. From then on your gremlin keeps one file there,
`gremlin-student.md`, and every verdict it writes lands in your own Drive. Chat on the site,
fill in your profile and sharing rules on *My Cubby*, or point your own Claude at `/mcp`
with the token Campus Cubbies gave your agent.

**Judge, no account:** the team gives you a link (`/demo?token=...`). You are the synthetic
student Asha Rao (F-1, 17 units, 10 on-campus hours, CS: Computer Game Design, Crown). Try
the question cards, approve a field when asked, change `days_to_deadline` to 2 on *My Cubby*
and ask the first question again. *Reset the demo student* puts everything back.

**Your own agent (MCP):** pair any agent with Campus Cubbies ([its guide](prototypes/cubbies/SKILL.md)),
then add `https://<service>/mcp` with `Authorization: Bearer <that token>`. Tools: `ask`,
`my_box`, `approve_share`, `open_items`. Same cubby, same wall.

**Laptop, everything local:**

```sh
uv sync && uv run pytest -q                       # 142 tests, no network
uv run preflight.py --live                        # keys, boxes, cache, ports, git, one call per model
DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log   # then open /demo?token=judge
uv run demo.py                                    # the six judge questions in the terminal, fresh copy of the boxes
uv run eval.py                                    # ten cases: gremlins vs one-call baseline
uv run mcp_server.py                              # the advocate over MCP (stdio); BOX_STORE=cubby for your real cubby
uv run dept_gremlin.py serve --dept cmpm --port 10002   # a department gremlin as its own A2A server
```

Model keys go in `.env` (`GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`, `GEMINI_API_KEY`; any
one is enough, free tiers). Without a key the demo runs the scripted brain and tells you.
`CUBBY_URL` defaults to https://cubby.bayleaf.dev.

## How it works

```
 student's own agent (Claude, ChatGPT, anything MCP)        judge / student browser
            |  MCP: ask / my_box / approve_share                    |  /chat -> /api/ask
            v                                                       v
 +---------------------------------------------------------------------------+
 |  ADVOCATE (the student's gremlin)            reads the student box fresh  |
 |  1. scope: which departments?  <- each box advertises `topics:`           |
 |  2. wall out: share only `yes` fields the box mentions; `ask` waits       |
 |  3. consult every department AT ONCE (asyncio.gather), none sees another  |
 |  4. wall in: drop uncited claims, reject answers that echo protected data |
 |  5. decide in code: E-xx triggers -> ESCALATED; needs -> ASK_STUDENT;     |
 |     conflicting best options -> precedence (federal > state > campus >    |
 |     department) or DISPUTED; else CONVERGED                               |
 |  6. append the verdict to the student box (sections 4 to 8, pointers)     |
 +---------------------------------------------------------------------------+
      |  A2A `answer` {session_id, question, context}   (in-process, HTTP, or SLIM)
      v
 +----------+  +----------+  +-----------+  +----------+
 |   ISO    |  |   CMPM   |  |  COLLEGE  |  |  FINAID  |   department gremlins: stateless,
 | iso.md   |  | cmpm.md  |  | college.md|  | finaid.md|   one box each, every claim cites
 +----------+  +----------+  +-----------+  +----------+   an id, escalation decided in code
```

- **Boxes** are Markdown with a line grammar ([docs/boxes/README.md](docs/boxes/README.md)):
  facts `F-xx | text | authority | source | verified`, precedence `P-xx`, FAQ `Q-xx`,
  escalation triggers `E-xx | text | condition`, and for students a profile, preferences,
  and a sharing-permissions table. The four department boxes hold real UCSC policy with
  the URLs they were read from on 2026-10-10 (`verified=yes`); practice that could not be
  confirmed on a published page is marked `verified=no` and the gremlin must say so.
- **Cubby** ([docs/CUBBY.md](docs/CUBBY.md)): what belongs in a student's state and what
  never does. Five kinds of entry (fact, answer, todo, permission, audit), one line each,
  latest entry per key wins, older entries never reach a prompt.
- **The wall** (`wall.py`) is code, not a prompt: `yes` is sent, `no` is sent as
  "not shared", `ask` waits for the student, `never` is not mentioned; identity never
  leaves; every inbound cite is checked against the department's own box.
- **The model only drafts.** Escalation, precedence, scope, sharing, and the verdict are
  decided by code from the boxes. Temperature 0 is not deterministic, so a replay cache
  (`brain.CachedBrain`, keyed by the prompt hash) makes a demo repeat exactly.

## Level 3, criterion by criterion

| criterion | where it is |
|---|---|
| three or more autonomous agents with competing objectives | ISO (status), CMPM advising (degree plan), college advising (load and standing), financial aid (money); each answers only from its own box and its own authority level |
| deliberate, negotiate, reach consensus without a central decision-maker | the advocate never answers from its own knowledge; departments are consulted in parallel and never see each other; agreement, precedence, and dispute are computed from their positions (`advocate.py: _positions`) |
| genuine disagreement and a real mechanism | `p1`: college approves 10 units, ISO says status terminates: federal outranks campus, CONVERGED with the override recorded. `d1`: CMPM says add CMPM 120 now, college says not while working 10 hours: equal authority, DISPUTED, both positions kept |
| the effect of new information | `a1`/`d1`: approving `hours` turns ASK_STUDENT into an answer or a dispute; `e2`: the same question as `c1` with `days_to_deadline` moved to 2 becomes ESCALATED |
| comparison against a simpler baseline | `eval.py`: one LLM call given every box and the whole student box, scored by the same wall. Ten cases, live models: gremlins 9/10 correct verdicts, 0 protected fields shared; baseline 3/10, 120 protected field-sends, 33 uncited sentences shown ([docs/EVAL.md](docs/EVAL.md)) |
| when to stop, keep the disagreement, or ask a human | UNANSWERED when nothing is in scope (`u1`), DISPUTED is kept and shown rather than resolved by a coin flip, ESCALATED names who decides and what to bring |

## AGNTCY: what is real and what is a stand-in

| piece | status |
|---|---|
| A2A 1.0 JSON-RPC (a2a-sdk 1.2.2) between the advocate and department gremlins | real: `dept_gremlin.py serve`, agent card, skill `answer`, `advocate.over_a2a` |
| SLIM transport for a department | real: `gremlin_slim.py` gateway in front of the ISO gremlin, `demo.py --transport slim` when a node is up |
| in-process callers | the default so the demo runs anywhere; the contract is identical |
| Campus Cubbies A2A (`hello`, `list_files`, `read_file`, `create_file`, `edit_file`) | real: `cubby_store.py` keeps the student box as a file in the student's Drive cubby, exact-match edits against the revision just read |
| AGNTCY Directory / OASF discovery | stand-in: each box's `topics:` line is the capability record the advocate selects on; publishing the agent cards to a directory is the next step |
| Observe | stand-in: structured JSON events on stdout and pointers-only session logs in each box |

## What was built this weekend, and what was not

Built October 10 to 11: `box.py`, `brain.py`, `dept_gremlin.py`, `wall.py`, `advocate.py`,
`mcp_server.py`, `cubby_store.py`, `baseline.py`, `eval.py`, `demo.py`, `chat.html`, the judge mode and
`/api` routes in `gremlin_app.py` (the advocate service: Campus Cubbies pairing as sign-in,
the site, judge mode, MCP), `site.html`, the four department boxes, the student template and
demo student, `docs/CUBBY.md`, `docs/QUESTIONS.md`, and the tests.

Pre-existing (Adam Smith's Campus Cubbies / BayLeaf work and the earlier memory
prototype in this repo): Campus Cubbies itself (`prototypes/cubbies/`: UCSC Google
login, the Drive folder per student, grants, contributions, the A2A tool surface at
cubby.bayleaf.dev), the Firestore memory notebook, the SLIM gateway, and the earlier
echo prototype. The BayLeaf brain (`brain.BayleafBrain`) is a stub with the interface
fixed. The Markdown store is the default; `cubby_store.py` is the same box living in
the real cubby.

Eval questions and the department prompt were iterated during development (the same ten
questions went 6/10 then 9/10 as two real bugs were fixed, both described in
`docs/EVAL.md`); the numbers are from the final run, not a held-out set.

## Limits we know about

- Facts marked `verified=no` are advising practice we could not confirm on a published
  page. A gremlin that relies on one says so; a department should replace it with a
  sourced line before any real use.
- Conflict detection compares each department's best option by `units`; a disagreement
  that is not about units is reported as agreement unless an `E-xx` trigger catches it.
- A signed-in student's box lives in their Drive through Campus Cubbies, so it survives
  anything; the judge's synthetic box lives on the container's filesystem and resets with it.
- The session cookie carries the student's Campus Cubbies bearer (signed, httponly, 48 hours,
  the same lifetime Campus Cubbies gives the token). Log out clears it; Campus Cubbies'
  `revoke_agents` kills it from the other side.
- Free-tier models rate-limit under four parallel calls; the model order and the replay
  cache are the mitigation, not a solution.


Gremlins are the agents; Campus Cubbies is the boundary they argue inside. The gremlin
layer (everything above this line) lives at the repository root and runs as its own
service (`gremlin_app.py`, `Dockerfile.gremlins`). Campus Cubbies is below, as Adam
wrote it, with the earlier prototypes it grew from under `prototypes/`.

## Campus Cubbies: the boundary (Adam Smith)

An **A2A 1.0** service for permissioned campus correspondence and personal Google
Drive tools for people's agents. The server is mechanical: the caller supplies
reasoning. A2A is the showcased interface for this Cisco-sponsored hackathon.
Hackathon teammates: Adam Smith and Tarun Nagaraju, October 2026.

### Prototype index

| Folder | Prototype | Status |
| --- | --- | --- |
| [cubbies](prototypes/cubbies/) | Campus Cubbies, with Google Drive integration | Active pilot at https://cubby.bayleaf.dev |
| [a2a-echo](prototypes/a2a-echo/) | Original no-memory A2A echo | Historical |
| [markdown-memory](prototypes/markdown-memory/) | Permissioned local Markdown memory | Historical |
| [firestore](prototypes/firestore/) | Google login and Firestore-backed memory | Historical |
| [slim](prototypes/slim/) | Isolated A2A-over-SLIM gateway and client | Historical |

Historical source and documentation are retained as development records;
their original commands, deployment claims, and sibling-file assumptions may
no longer apply. Only Campus Cubbies is the active runnable target.

### Campus Cubbies development

Use the shared root `pyproject.toml` and `uv.lock`:

```sh
uv sync
uv run pytest -q
LOCAL_HTTP=1 uv run uvicorn cloud_app:app --app-dir prototypes/cubbies --port 8080 --no-access-log
```

The root Dockerfile and upload allowlists package `prototypes/cubbies/`.
See [current configuration, security boundaries, and deployment setup](prototypes/cubbies/README.md).
Agent connection instructions are canonical in [SKILL.md](prototypes/cubbies/SKILL.md);
current live evidence is in [DEPLOYMENT.md](prototypes/cubbies/DEPLOYMENT.md).
Earlier deployment records in `prototypes/firestore/` are historical, not current setup instructions.
