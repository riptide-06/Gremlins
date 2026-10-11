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

**Judge, no account:** open the judge link the team gives you (`/demo?token=...` on
the Cloud Run service). You are signed in as a synthetic student (Asha Rao, F-1,
17 units, 10 on-campus hours, CS: Computer Game Design, Crown). Type any of the
questions in [docs/QUESTIONS.md](docs/QUESTIONS.md), or your own. Change a field in
the cubby panel (`days_to_deadline` to `2`) and ask the same question again.

**Student, your own agent:** sign in with your UCSC Google account at the service,
generate a student bearer token, and add `https://<service>/mcp` as an MCP
connector in Claude (or any MCP client) with `Authorization: Bearer <token>`.
Tools: `ask`, `my_box`, `approve_share`, `open_items`. Your box is seeded from
[docs/boxes/student.template.md](docs/boxes/student.template.md) on first login.

**Laptop, everything local:**

```sh
uv sync && uv run pytest -q                       # 87 tests, no network
uv run demo.py                                    # the six judge questions, four gremlins, fresh copy of the boxes
uv run eval.py                                    # ten cases: gremlins vs one-call baseline
uv run mcp_server.py                              # the advocate over MCP (stdio) for Claude Desktop / Claude Code
uv run dept_gremlin.py serve --dept cmpm --port 10002   # a department gremlin as its own A2A server
DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log   # then open /demo?token=judge
```

Model keys go in `.env` (`GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`, `GEMINI_API_KEY`; any
one is enough, free tiers). Without a key the demo runs the scripted brain and tells you.

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
| comparison against a simpler baseline | `eval.py`: one LLM call given every box and the whole student box, scored by the same wall ([docs/EVAL.md](docs/EVAL.md)) |
| when to stop, keep the disagreement, or ask a human | UNANSWERED when nothing is in scope (`u1`), DISPUTED is kept and shown rather than resolved by a coin flip, ESCALATED names who decides and what to bring |

## AGNTCY: what is real and what is a stand-in

| piece | status |
|---|---|
| A2A 1.0 JSON-RPC (a2a-sdk 1.2.2) between the advocate and department gremlins | real: `dept_gremlin.py serve`, agent card, skill `answer`, `advocate.over_a2a` |
| SLIM transport for a department | real: `gremlin_slim.py` gateway in front of the ISO gremlin, `demo.py --transport slim` when a node is up |
| in-process callers | the default so the demo runs anywhere; the contract is identical |
| AGNTCY Directory / OASF discovery | stand-in: each box's `topics:` line is the capability record the advocate selects on; publishing the agent cards to a directory is the next step |
| Observe | stand-in: structured JSON events on stdout and pointers-only session logs in each box |

## What was built this weekend, and what was not

Built October 10 to 11: `box.py`, `brain.py`, `dept_gremlin.py`, `wall.py`, `advocate.py`,
`mcp_server.py`, `baseline.py`, `eval.py`, `demo.py`, `chat.html`, the judge mode and
`/api` routes in `gremlin_app.py` (the advocate service, grown from the Firestore
prototype's login), the four department boxes, the student template and
demo student, `docs/CUBBY.md`, `docs/QUESTIONS.md`, and the tests.

Pre-existing (Adam Smith's Campus Cubbies / BayLeaf work and the earlier memory
prototype in this repo): the Cloud Run service with UCSC Google login and bearer
credentials, the Firestore memory notebook (`gremlin_memory.py`, `/a2a`), the SLIM
gateway, and the cubby-in-Drive design with a service account per student. The Drive
box store (`box.GoogleDocBoxStore`) and the BayLeaf brain (`brain.BayleafBrain`) are
stubs with the interface fixed; the Markdown store is the cubby today.

Eval questions and the department prompt were iterated during development; the
numbers in `docs/EVAL.md` are from the final run, not a held-out set.

## Limits we know about

- Facts marked `verified=no` are advising practice we could not confirm on a published
  page. A gremlin that relies on one says so; a department should replace it with a
  sourced line before any real use.
- Conflict detection compares each department's best option by `units`; a disagreement
  that is not about units is reported as agreement unless an `E-xx` trigger catches it.
- On Cloud Run the boxes live on the container's filesystem, so writes do not survive a
  new instance; the Drive store is the fix, not a bigger disk.
- Free-tier models rate-limit under four parallel calls; the model order and the replay
  cache are the mitigation, not a solution.

---

The sections below describe the earlier memory prototype this repo started from.

## Working local prototype

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv run gremlin_memory.py serve
```

The service listens on port 10000. By default its agent card advertises
`http://127.0.0.1:10000`. For another machine to connect, set `GREMLIN_URL` to the
reachable URL **before starting the server**, and use that URL in client calls.

At first startup the server creates two untracked, host-only files:

- `.gremlin-keys.json`: separate student and advisor bearer credentials.
- `student-notebook.md`: persistent memory simulating a shared Google Doc.

Give the student only the student credential. Never publish these files.

```sh
export GREMLIN_TOKEN='your-role-token'
uv run gremlin_memory.py hello
uv run gremlin_memory.py remember 'A synthetic private fact'
uv run gremlin_memory.py read
```

An advisor uses their own token and only:

```sh
uv run gremlin_memory.py contribute 'Attributed outside guidance'
```

For a remote service, append `--url https://your-service` to client commands.

## Self-instructing A2A

Discover `/.well-known/agent-card.json`, then send `hello` using authenticated
A2A 1.0 JSON-RPC. The greeting explains the caller's role and exact JSON tool
requests. A downloadable client is available at `/gremlin_memory.py`.

The runtime enforces permissions before reading memory. Advisors may contribute
but cannot read memory. Separate task stores prevent advisor task lookups from
retrieving student responses. External contributions are untrusted data, not
instructions. Stdout emits structured events with contents redacted.

## Boundaries

This local version is a **synthetic demonstration**, not production security:
plaintext HTTP, shared role credentials, host-readable files, and in-memory A2A
tasks. The host can inspect the notebook. Agent clients may retain conversations
and tool results. No model, Google Docs integration, student service accounts,
or consented outbound outreach is implemented. Optional SLIM transport is
provided by a separate gateway, described below.

`gremlin_a2a.py` preserves the earlier minimal A2A echo proof.

## Cloud Run direction

Live onboarding: **https://gremlin-331254975906.us-west1.run.app**.
Google login is **Internal, UCSC-only**. Use synthetic data for this pilot.
See [DEPLOYMENT.md](DEPLOYMENT.md) for the deployment and verification record.

Target project: `gremlins-511221`. `cloud_app.py` implements verified UCSC Google
login, a small onboarding page issuing copy-pasteable scoped agent credentials,
Firestore-backed per-student memory, HTTPS A2A, and redacted Cloud Logging.
Local test data and credentials are not migrated.

```sh
uv sync
uv run pytest -q
uv run uvicorn cloud_app:app --port 8080 --no-access-log
```

Without OAuth configuration, the local page explains that login is not yet
configured. See [CLOUD_RUN.md](CLOUD_RUN.md) for configuration, deployment,
privacy boundaries, costs, and cleanup. Tests use a fake repository, not real
Firestore or Google login. Real cloud/OAuth integration requires deployment.

## Optional SLIM transport

`gremlin_slim.py` connects agents over AGNTCY SLIM SlimRPC and forwards A2A to
the same permissioned backend. It runs separately, with no change to Cloud Run
or the core dependencies. Student/advisor permissions remain backend-enforced.
See [SLIM.md](SLIM.md) for a three-terminal laptop demo and security boundaries.
