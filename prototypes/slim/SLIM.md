# Optional A2A over SLIM

`gremlin_slim.py` is a small gateway and client using AGNTCY's official
[`slima2a`](https://github.com/agntcy/slim-a2a-python) implementation:

```text
agent → SLIM node → SlimRPC gateway → HTTPS A2A → Gremlin
```

Gremlin still enforces student/advisor roles, notebook ownership, token expiry,
and revocation. The gateway has no stored bearer credentials or notebook, and
does not implement task lookup, history, streaming, or subscriptions. Its
`hello` response adds transport instructions to the backend's role greeting.

## Laptop demo

Requires uv, Python 3.11+ and internet for initial dependency downloads. Tested
on Apple Silicon with Python 3.12. No Docker or separately installed SLIM daemon
is needed: the native Python bindings provide the loopback node.

Create a random shared secret for the local SLIM group:

```sh
uv run --no-project python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

In **each of three terminals**, set the same generated secret (not a Gremlin
student/advisor token):

```sh
export SLIM_SHARED_SECRET='paste-the-generated-random-secret'
```

Terminal 1, local loopback node:

```sh
uv run --script gremlin_slim.py node
```

Terminal 2, gateway to the live Gremlin service:

```sh
uv run --script gremlin_slim.py gateway
```

Terminal 3, sign in at https://gremlin-331254975906.us-west1.run.app and generate
connection instructions. Use your student credential privately:

```sh
export GREMLIN_TOKEN='your-student-bearer-token'
uv run --script gremlin_slim.py call hello
uv run --script gremlin_slim.py call remember 'A synthetic fact'
uv run --script gremlin_slim.py call read
```

Switch `GREMLIN_TOKEN` to an advisor credential to contribute. `read` must return
a denial, not notebook contents:

```sh
export GREMLIN_TOKEN='advisor-bearer-token'
uv run --script gremlin_slim.py call contribute 'Synthetic outside guidance'
uv run --script gremlin_slim.py call read
```

Stop node and gateway with Ctrl-C. Credentials expire after 48 hours and can
be revoked/rotated in the onboarding site without losing memory.

### Completely local backend

Run `uv run gremlin_memory.py serve` in a fourth terminal. Start the gateway
with `--upstream http://127.0.0.1:10000` and use that prototype's tokens from
`.gremlin-keys.json`, not the cloud tokens. The original prototype's local
file/task limitations remain; the gateway does not turn it into the cloud app.

### Connecting another SLIM-capable agent

Default node: `http://127.0.0.1:46357`. Default gateway name:
`ucsc/gremlins/gateway`. Gateway and client accept `--node` and `--name`.
Call `lf.a2a.v1.A2AService/SendMessage` with an A2A 1.0 protobuf request and
RPC metadata `authorization: Bearer <your-role-token>`. The message's text part
contains JSON such as `{"action":"hello"}`. Credentials belong in metadata,
not the message. SLIM names and the shared secret do **not** grant student rights.

No SLIM endpoint is advertised by the public HTTP agent card: this laptop
gateway is not a deployed, globally reachable service. This adds transport
support, not a Claude.ai connector.

## Isolation and tests

The adapter pins `slima2a==0.7.1`, `slim-bindings==2.0.0`, and therefore A2A SDK
1.1.0. Cloud Run uses A2A SDK 1.2.2. PEP 723 script dependencies let uv keep
these separate. Do not add SLIM to the core project's dependency environment.

```sh
uv run --script slim_tests.py
uv run pytest -q test_cloud.py
```

Gateway tests cover header/version forwarding, malformed/invalid/revoked auth
responses, advisor denial propagation, size limits, disabled task lookup,
same-origin discovery, and redacted logs. The live node/gateway/client round
trip was also tested for both greetings, student read, advisor read denial,
and an invalid bearer, without printing or modifying notebook contents.

## Security and hosting boundaries

- The included node binds **127.0.0.1 only** and uses plaintext. Synthetic
  testing only. A shared application secret is not TLS or node access control.
- Node/gateway operators can see bearer credentials and message contents;
  use trusted processes/hosts. Client responses intentionally contain memory,
  while gateway activity logs redact it.
- Remote SLIM hosting needs explicit TLS, node authentication, routing policy,
  and credential/logging review. `--node` supports an existing configured node,
  but this demo does not provision those controls.
- The gateway forwards only to its configured upstream's discovered same-origin
  JSONRPC endpoint, never a URL selected by a caller. Redirects are disabled.
- Cloud Run is unchanged: no paid always-on SLIM infrastructure was provisioned.
  A persistent SLIM listener needs a suitable separately managed process, not
  this scale-to-zero, request-driven Cloud Run deployment.
