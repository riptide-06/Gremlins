# Gremlins

**When campus offices disagree, the student should not be the one who has to notice.**

Gremlins is a student-controlled advocate for UCSC built on [Campus Cubbies](prototypes/cubbies/README.md).
Every student has a cubby (their own state, in their own Google Drive, only their gremlin
reads it). Every department has a box (its policy, with sources). Department gremlins
answer only from their box and cite every claim. The student's gremlin asks the departments
that matter, shares the minimum the student allowed, applies precedence in code, and comes
back with one of five verdicts instead of a blended paragraph:

| verdict | meaning | what the student sees |
|---|---|---|
| `CONVERGED` | the departments agree, or a precedence rule settled it | one answer, cites, and (if there was an override) who overrode whom |
| `DISPUTED` | departments conflict at equal authority | both positions, what would resolve it, who decides (the student) |
| `ESCALATED` | an `E-xx` trigger matched the student's situation, in code | a brief for the human who must decide, and what to bring |
| `ASK_STUDENT` | a department needs a field the student has not released | the field, the department, a one-click approve |
| `UNANSWERED` | every department is out of scope, or the models failed | "I don't know", never an invention |

Hackathon teammates: Adam Smith (Computational Media, Campus Cubbies and BayLeaf) and
Tarun Nagaraju. hack.dev UCSC AI Hackathon, Cloud AI track (Cisco Outshift / AGNTCY,
"When AI Agents Disagree"), October 10 to 11, 2026. Level 3. Prototype, synthetic data
only, not an official UCSC service.

## Contents

1. [See it in 25 seconds](#1-see-it-in-25-seconds)
2. [Try it, step by step](#2-try-it-step-by-step)
3. [Put it on the internet](#3-put-it-on-the-internet)
4. [How it works](#4-how-it-works)
5. [The questions and the eval](#5-the-questions-and-the-eval)
6. [Level 3, criterion by criterion](#6-level-3-criterion-by-criterion)
7. [AGNTCY: what is real and what is a stand-in](#7-agntcy-what-is-real-and-what-is-a-stand-in)
8. [Repository map](#8-repository-map)
9. [What was built this weekend, and what was not](#9-what-was-built-this-weekend-and-what-was-not)
10. [Limits we know about](#10-limits-we-know-about)
11. [Campus Cubbies: the boundary](#campus-cubbies-the-boundary-adam-smith)

## 1. See it in 25 seconds

| asset | where |
|---|---|
| Teaser, landscape 1920x1080 (devpost, YouTube) | [brag-output/brag.mp4](brag-output/brag.mp4), poster [brag-output/brag.jpg](brag-output/brag.jpg) |
| Teaser, portrait 1080x1920 (socials) | [brag-output-2026-10-11-115500/brag.mp4](brag-output-2026-10-11-115500/brag.mp4) |
| Share captions | [brag-output/share-copy.txt](brag-output/share-copy.txt), [variants](brag-output/share-copy-variants.md) |
| The 90-second demo script (shot list and voiceover) | [docs/VIDEO.md](docs/VIDEO.md) |
| Three-minute pitch | [docs/PITCH.md](docs/PITCH.md) |
| Devpost copy | [docs/DEVPOST.md](docs/DEVPOST.md) |

Every frame of the teasers is a real screenshot of the running app in judge mode
(synthetic student); the storyboard is in [brag-output/brag-plan.md](brag-output/brag-plan.md).

## 2. Try it, step by step

### 2.1 Judge, no account (two minutes)

1. Open the judge link the team gives you (`https://<host>/demo?token=...`). You are the
   synthetic student Asha Rao (F-1, 17 units, 10 on-campus hours, CS: Computer Game Design,
   Crown). Nothing here is a real person.
2. Press a question card. Watch the verdict pill (`CONVERGED`, `DISPUTED`, ...), the cite
   chips (`F-01`), and the "Shared with" line that says exactly which fields each office got.
3. Ask "Can I take a second on-campus job, 12 more hours a week?". ISO needs `hours`, which
   the cubby marks *ask*. Press **Yes, share hours with ISO**: one field, one office, one
   question, then the answer.
4. Open **My Cubby**. The left table is the profile (name and email are *never shared*); the
   right table is the wall: `yes` / `ask` / `no` / `never` per office. Click `days_to_deadline`,
   set it to `2`, go back and ask the first question again: it is now `ESCALATED`, with
   **Open the brief** for the human who decides.
5. Start any question with `demo:` to watch the offices deliberate in the open (see 2.3).
6. **Reset the demo student** puts everything back for the next judge.

The full list of questions and the verdict each should produce is in
[docs/QUESTIONS.md](docs/QUESTIONS.md).

### 2.2 Student, the real thing (your own UCSC account)

1. Open the site root and press **Continue with UCSC Google**. That is Campus Cubbies' own
   approval page ([how pairing works](prototypes/cubbies/SKILL.md)): sign in with your UCSC
   account, consent once, and your **My Cubby** folder exists in your Drive.
2. From then on your gremlin keeps one file there, `gremlin-student.md`, and every verdict
   it writes lands in your own Drive. What belongs in that file, and what never does, is in
   [docs/CUBBY.md](docs/CUBBY.md).
3. Chat on the site, fill in your profile and sharing rules on **My Cubby**, or point your
   own agent at `/mcp` (2.4). Log out clears the session; revoking the agent on Campus
   Cubbies kills it from the other side.

### 2.3 Watch the offices talk (`demo:`)

Start any question with the word `demo:` and the departments deliberate in the open,
streamed turn by turn. Round 1: every office in scope answers at once, none sees another.
Round 2: an office whose box says another office must weigh in (`refers`, for example a
P-xx line naming financial aid) pulls it in, with its own cited position in view. Round 3:
every office that took a position hears the others' cited positions once and answers them:
hold, revise, or agree, with its own box as the reason. Agreement after that is CONVERGED
with the exchange recorded; disagreement at equal authority stays DISPUTED, kept rather than
averaged. Only cited policy ever crosses between offices; the student's fields go to each
office by the student's own rules, and no office sees what another office received. Same
thing over MCP: `ask(question, deliberate=true)`, transcript included.

### 2.4 Your own agent (MCP)

1. Pair your agent with Campus Cubbies ([its guide](prototypes/cubbies/SKILL.md)); that gives
   it a private token.
2. Add `https://<service>/mcp` to your MCP client with `Authorization: Bearer <that token>`.
   The **Bring your own agent** page on the site prints the exact config block.
3. Tools: `ask`, `my_box`, `approve_share`, `open_items`. Same cubby, same wall, same
   citations. Claude Desktop, Claude Code, a local model, any MCP client.

A department can also be reached directly as an A2A 1.0 agent: run
`uv run dept_gremlin.py serve --dept iso --port 10001`, fetch
`/.well-known/agent-card.json`, and send the `answer` skill
`{"session_id", "question", "context"}`.

### 2.5 Run everything on your laptop

1. Install [uv](https://docs.astral.sh/uv/), then:
   ```sh
   git clone https://github.com/riptide-06/Gremlins && cd Gremlins
   uv sync
   ```
2. Put at least one model key in `.env` (free tiers are enough; without a key the demo runs
   the scripted brain and says so):
   ```sh
   GROQ_API_KEY=...          # first choice, groq/openai/gpt-oss-120b
   NVIDIA_NIM_API_KEY=...    # fallback, nvidia_nim/nvidia/nemotron-3-super-120b-a12b
   GEMINI_API_KEY=...        # third, gemini/gemini-3.8-flash
   ```
   `CUBBY_URL` defaults to https://cubby.bayleaf.dev.
3. Run the tests (no network; they include our service against Campus Cubbies' own server
   code):
   ```sh
   uv run pytest -q                                  # 152 passed
   ```
4. Check keys, boxes, cache, ports, git, and one live call per model:
   ```sh
   uv run preflight.py --live
   ```
5. Start the site in judge mode and open the judge link:
   ```sh
   DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log
   # then open http://127.0.0.1:8080/demo?token=judge
   ```
6. The same six judge questions in the terminal, on a fresh copy of the boxes, and the
   ten-case eval against the one-call baseline:
   ```sh
   uv run demo.py                                    # --questions c1,d1 for a subset, --live to write into docs/boxes
   uv run eval.py                                    # writes the table shown in docs/EVAL.md
   ```
7. Optional pieces:
   ```sh
   uv run mcp_server.py                              # the advocate over MCP (stdio); BOX_STORE=cubby for your real cubby
   uv run dept_gremlin.py serve --dept cmpm --port 10002   # a department gremlin as its own A2A server
   uv run --script prototypes/slim/gremlin_slim.py node    # a SLIM node, then: uv run demo.py --transport slim
   ```

The pre-demo checklist we ran on judging morning is [docs/MORNING.md](docs/MORNING.md).

## 3. Put it on the internet

| option | cost | doc |
|---|---|---|
| Cloudflare quick tunnel from the laptop (30 seconds, lives while the laptop is up) | free | [docs/DEPLOY_FREE.md](docs/DEPLOY_FREE.md), section A |
| Hugging Face Docker Space (durable, naps when idle) | free | [docs/DEPLOY_FREE.md](docs/DEPLOY_FREE.md), section B, script [deploy/hf-space.sh](deploy/hf-space.sh) |
| Google Cloud Run (`Dockerfile.gremlins`, `cloudbuild.gremlins.yaml`) | paid | [docs/DEPLOY_GREMLINS.md](docs/DEPLOY_GREMLINS.md) |

In every case the service runs with `PUBLIC_URL` set to its real address (the sign-in
and same-origin checks need it) and `DEMO_TOKEN` set to a long random string for the judge link.

## 4. How it works

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
 |     recommendations that differ -> precedence (federal > state > campus > |
 |     department, by the rule each one rests on) or DISPUTED; else CONVERGED|
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
  and a sharing-permissions table. The four department boxes
  ([iso](docs/boxes/iso.md), [cmpm](docs/boxes/cmpm.md), [college](docs/boxes/college.md),
  [finaid](docs/boxes/finaid.md)) hold real UCSC policy with the URLs they were read from on
  2026-10-10 (`verified=yes`); practice that could not be confirmed on a published page is
  marked `verified=no` and the gremlin must say so. The demo student is
  [docs/boxes/student.md](docs/boxes/student.md); new students start from
  [student.template.md](docs/boxes/student.template.md).
- **Cubby** ([docs/CUBBY.md](docs/CUBBY.md)): what belongs in a student's state and what
  never does. Five kinds of entry (fact, answer, todo, permission, audit), one line each,
  latest entry per key wins, older entries never reach a prompt. [`cubby_store.py`](cubby_store.py)
  keeps that file in the student's Drive through Campus Cubbies.
- **The wall** ([`wall.py`](wall.py)) is code, not a prompt: `yes` is sent, `no` is sent as
  "not shared", `ask` waits for the student, `never` is not mentioned; identity never
  leaves; every inbound cite is checked against the department's own box.
- **The model only drafts.** Escalation, precedence, scope, sharing, and the verdict are
  decided by code from the boxes ([`advocate.py`](advocate.py)). Temperature 0 is not
  deterministic, so a replay cache (`brain.CachedBrain`, keyed by the prompt hash) makes a
  demo repeat exactly.

## 5. The questions and the eval

[docs/QUESTIONS.md](docs/QUESTIONS.md) lists the ten cases a judge can type and the verdict
each should produce. [docs/EVAL.md](docs/EVAL.md) is the measurement: `eval.py` runs the
same ten cases through the gremlins and through one LLM call given every box and the whole
student box, and scores both with the same wall.

| condition | correct verdicts | uncited claims | student fields that left the box (protected) |
|---|---|---|---|
| gremlins | 9/10 | 16, every one deleted by the wall before the student saw it | 144 (0) |
| one-call baseline | 3/10 | 33, all shown to the student | 210 (120) |

Live models, run 2 in [docs/EVAL.md](docs/EVAL.md); the per-case table and the two bugs the
eval caught are there too. The questions and the department prompt were iterated during
development, so these are not a held-out set.

## 6. Level 3, criterion by criterion

| criterion | where it is |
|---|---|
| three or more autonomous agents with competing objectives | ISO (status), CMPM advising (degree plan), college advising (load and standing), financial aid (money); each answers only from its own box and its own authority level |
| deliberate, negotiate, reach consensus without a central decision-maker | the advocate never answers from its own knowledge; departments are consulted in parallel and never see each other; agreement, precedence, and dispute are computed from their positions (`advocate.py: _positions`). With `demo:` (deliberation mode) the offices negotiate directly: a referral round pulls in an office another office's box names, and a reconsider round lets offices whose positions differ hear each other's cited position once and hold, revise, or agree; the exchange is streamed to the student and logged to the cubby (`DELIBERATION` line) |
| genuine disagreement and a real mechanism | `p1`: college approves 10 units, ISO says status terminates: federal outranks campus, CONVERGED with the override recorded. `d1`: CMPM recommends adding CMPM 120 now (offered once a year), college practice says stay at or below 19 credits while working 10 hours: both rest on department practice, DISPUTED, both positions kept, the student decides. Each office's position is the option it recommends, and its authority is the level of the rule that option rests on (`basis`), read from the box, so a permission quoted in passing cannot win an argument |
| the effect of new information | `a1`/`d1`: approving `hours` turns ASK_STUDENT into an answer or a dispute; `e2`: the same question as `c1` with `days_to_deadline` moved to 2 becomes ESCALATED |
| comparison against a simpler baseline | `eval.py`: one LLM call given every box and the whole student box, scored by the same wall. Ten cases, live models: gremlins 9/10 correct verdicts, 0 protected fields shared; baseline 3/10, 120 protected field-sends, 33 uncited sentences shown ([docs/EVAL.md](docs/EVAL.md)) |
| when to stop, keep the disagreement, or ask a human | UNANSWERED when nothing is in scope (`u1`), DISPUTED is kept and shown rather than resolved by a coin flip, ESCALATED names who decides and what to bring |

## 7. AGNTCY: what is real and what is a stand-in

| piece | status |
|---|---|
| A2A 1.0 JSON-RPC (a2a-sdk 1.2.2) between the advocate and department gremlins | real: [`dept_gremlin.py`](dept_gremlin.py) `serve`, agent card, skill `answer`, `advocate.over_a2a` |
| SLIM transport for a department | real: [`prototypes/slim/gremlin_slim.py`](prototypes/slim/gremlin_slim.py) gateway in front of the ISO gremlin, `demo.py --transport slim` when a node is up |
| in-process callers | the default so the demo runs anywhere; the contract is identical |
| Campus Cubbies A2A (`hello`, `list_files`, `read_file`, `create_file`, `edit_file`) | real: [`cubby_store.py`](cubby_store.py) keeps the student box as a file in the student's Drive cubby, exact-match edits against the revision just read. [`tests/test_campus_integration.py`](tests/test_campus_integration.py) runs our service against Campus Cubbies' own server code ([`prototypes/cubbies/cloud_app.py`](prototypes/cubbies/cloud_app.py), offline fakes): pairing, hello, the box created and edited in the cubby, `revoke_agents` logging the student out |
| AGNTCY Directory / OASF discovery | stand-in: each box's `topics:` line is the capability record the advocate selects on; publishing the agent cards to a directory is the next step |
| Observe | stand-in: structured JSON events on stdout and pointers-only session logs in each box |

## 8. Repository map

| path | what it is |
|---|---|
| [`gremlin_app.py`](gremlin_app.py) | the advocate service: Campus Cubbies pairing as sign-in, the site, judge mode, `/api/*`, `/mcp` |
| [`site.html`](site.html) | the single-page site (sign-in, chat, My Cubby, brief, Bring your own agent) |
| [`advocate.py`](advocate.py) | the student's gremlin: scope, wall out, consult, wall in, decide, write |
| [`wall.py`](wall.py) | permissions outbound, cite verification and leak rejection inbound |
| [`dept_gremlin.py`](dept_gremlin.py) | a stateless department gremlin, in-process or as an A2A server |
| [`box.py`](box.py), [`docs/boxes/`](docs/boxes/) | the box grammar, parser, store, the four department boxes, the student template and demo student |
| [`brain.py`](brain.py) | LiteLLM brains (groq, nvidia_nim, gemini), the scripted brain, the replay cache |
| [`cubby_store.py`](cubby_store.py) | the student box as a file in the student's Drive via Campus Cubbies |
| [`mcp_server.py`](mcp_server.py) | the advocate over MCP (stdio; `/mcp` in the service) |
| [`demo.py`](demo.py), [`eval.py`](eval.py), [`baseline.py`](baseline.py), [`preflight.py`](preflight.py) | the judge questions in a terminal, the eval, the one-call baseline, the pre-demo checklist |
| [`tests/`](tests/) | 152 tests, no network |
| [`docs/`](docs/) | [QUESTIONS](docs/QUESTIONS.md), [EVAL](docs/EVAL.md), [CUBBY](docs/CUBBY.md), [VIDEO](docs/VIDEO.md), [PITCH](docs/PITCH.md), [DEVPOST](docs/DEVPOST.md), [DEPLOY_FREE](docs/DEPLOY_FREE.md), [DEPLOY_GREMLINS](docs/DEPLOY_GREMLINS.md), [MORNING](docs/MORNING.md) |
| [`deploy/hf-space.sh`](deploy/hf-space.sh), [`Dockerfile.gremlins`](Dockerfile.gremlins), [`cloudbuild.gremlins.yaml`](cloudbuild.gremlins.yaml) | deployment of the gremlin service |
| [`brag-output/`](brag-output/), [`brag-output-2026-10-11-115500/`](brag-output-2026-10-11-115500/) | the 25-second teasers (landscape, portrait), their Hyperframes compositions, plans, and share copy |
| [`prototypes/cubbies/`](prototypes/cubbies/) | Campus Cubbies itself (Adam Smith), the boundary; [`Dockerfile`](Dockerfile) packages it |
| [`prototypes/`](prototypes/) | the earlier prototypes the project grew from (see the index below) |

## 9. What was built this weekend, and what was not

Built October 10 to 11: `box.py`, `brain.py`, `dept_gremlin.py`, `wall.py`, `advocate.py`,
`mcp_server.py`, `cubby_store.py`, `baseline.py`, `eval.py`, `demo.py`, `preflight.py`, the
judge mode and `/api` routes in `gremlin_app.py` (the advocate service: Campus Cubbies pairing
as sign-in, the site, judge mode, MCP), `site.html`, the four department boxes, the student
template and demo student, `docs/CUBBY.md`, `docs/QUESTIONS.md`, the deploy scripts, the
teasers, and the tests.

Pre-existing (Adam Smith's Campus Cubbies / BayLeaf work and the earlier memory
prototype in this repo): Campus Cubbies itself (`prototypes/cubbies/`: UCSC Google
login, the Drive folder per student, grants, contributions, the A2A tool surface at
cubby.bayleaf.dev), the Firestore memory notebook, the SLIM gateway, and the earlier
echo prototype. The BayLeaf brain (`brain.BayleafBrain`) is a stub with the interface
fixed. The Markdown store is the default; `cubby_store.py` is the same box living in
the real cubby.

Eval questions and the department prompt were iterated during development (the same ten
questions went 6/10 then 9/10 as two real bugs were fixed, both described in
[docs/EVAL.md](docs/EVAL.md)); the numbers are from the final run, not a held-out set.

## 10. Limits we know about

- Facts marked `verified=no` are advising practice we could not confirm on a published
  page. A gremlin that relies on one says so; a department should replace it with a
  sourced line before any real use.
- Conflict detection compares the option each department recommends by `units`; a
  disagreement that is not about units is reported as agreement unless an `E-xx` trigger
  catches it. The authority behind a position comes from the rule the department names as its
  `basis`; a model can still name the wrong rule, and the box's own level is the only check.
- A signed-in student's box lives in their Drive through Campus Cubbies, so it survives
  anything; the judge's synthetic box lives on the container's filesystem and resets with it.
- The session cookie carries the student's Campus Cubbies bearer (signed, httponly, 48 hours,
  the same lifetime Campus Cubbies gives the token). Log out clears it; Campus Cubbies'
  `revoke_agents` kills it from the other side.
- Free-tier models rate-limit under four parallel calls; the model order and the replay
  cache are the mitigation, not a solution. A card can say "did not answer (model failure)"
  for one office; the verdict then comes from the others and says so.
- The teasers and the eval numbers describe the synthetic student. The real-account sign-in
  and the Drive file are exercised by the integration tests against Campus Cubbies' own server
  code, not by a recording.

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
