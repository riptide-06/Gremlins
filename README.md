# Gremlins

A student-controlled advocate capability for existing agent interfaces. Not a
dedicated chat app: A2A exposes memory tools and teaches connecting agents how to
use them. The agent client supplies conversational reasoning.

Hackathon teammates: Adam Smith and Tarun Nagaraju. Cloud AI track, October 2026.

## Boxes, department gremlins, and the advocate (October 10, 2026)

The memory prototype below is unchanged. On top of it, the repo now has a
compliant-consensus layer where code decides and the model only drafts:

| File | What it is |
|---|---|
| `box.py` | Parser and `BoxStore` for the Markdown boxes in `docs/boxes/` (facts `F-xx`, precedence `P-xx`, FAQ `Q-xx`, escalation triggers `E-xx`, the sharing permissions table). `MarkdownBoxStore` now, `GoogleDocBoxStore` stub for later. |
| `brain.py` | `Brain.complete(system, user, schema) -> dict | None`. LiteLLM (groq gpt-oss-120b, nvidia_nim fallback), temperature 0, JSON mode, one retry. `BayleafBrain` stub. Prompts come from the current box only. |
| `dept_gremlin.py` | Stateless A2A server, skill `answer`: `{session_id, question, context}` -> `{scope, answer, cites, needs, options, escalate, authority, confidence}`. Cites are checked against the box; `escalate` comes from `E-xx` triggers in code. `uv run dept_gremlin.py serve --dept iso --port 10001` |
| `wall.py` | Permissions outbound (yes / no -> "not shared" / ask -> approval / never), identity redaction, cite verification inbound, rejection of answers that echo protected fields. |
| `advocate.py` | The student gremlin: wall, every in-scope department, one resend round, preference scoring, verdict (CONVERGED, ESCALATED, DISPUTED, ASK_STUDENT) written to student sections 4 to 8. |
| `mcp_server.py` | The advocate over MCP: `ask`, `my_box`, `approve_share`, `open_items`. stdio via `uv run mcp_server.py`; `/mcp` on the cloud app behind the UCSC login. |
| `baseline.py`, `eval.py` | One-call baseline and the six-question eval. Results in [docs/EVAL.md](docs/EVAL.md). |
| `demo.py` | Three questions end to end, A2A over SLIM when a node is up, in-process otherwise. |

```sh
uv sync && uv run pytest -q          # unit tests, no network
uv run demo.py                       # live models, fresh copy of the boxes under out/demo/
uv run eval.py                       # one table: gremlin vs baseline
```

Drop `iso.md` and `student.md` into `docs/boxes/`; until then the `*.example.md`
files are used. Format: [docs/boxes/README.md](docs/boxes/README.md).

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
