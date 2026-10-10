# Gremlins

A student-controlled advocate capability for existing agent interfaces. Not a
dedicated chat app: A2A exposes memory tools and teaches connecting agents how to
use them. The agent client supplies conversational reasoning.

Hackathon teammates: Adam Smith and Tarun Nagaraju. Cloud AI track, October 2026.

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
consented outbound outreach, or SLIM transport is implemented.

`gremlin_a2a.py` preserves the earlier minimal A2A echo proof.

## Cloud Run direction

Target project: `gremlins-511221`. Next: verified UCSC Google login, a small
onboarding page issuing copy-pasteable scoped agent credentials, Firestore-backed
per-student memory, HTTPS A2A, and redacted Cloud Logging. Local test data and
credentials are not migrated.
