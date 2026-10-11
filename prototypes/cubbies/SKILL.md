---
name: cubbies
description: Connect an agent to Campus Cubbies over direct HTTP or a same-origin browser JavaScript runtime, then discover its current tools.
---

# Connect to Campus Cubbies

Use this guide when a person asks you to connect to their campus cubby.
Production origin: **https://cubby.bayleaf.dev**. Use A2A 1.0 JSON-RPC over HTTPS;
there is no client download or required SDK. This is first-party browser pairing,
not an OAuth provider for arbitrary clients. No model runs in this service.

The Agent Card describes relevance, capabilities and the supported endpoint;
this file is the authoritative connection/use guide. A2A is the only tool
interface for this hackathon: implement the tested HTTP envelope below. After connection,
`hello` owns current role-dependent schemas and workspace conventions.

Prefer direct HTTP from your agent's network runtime. If the host denies runtime
egress, a browser tool that can **execute JavaScript in a target-origin tab** is
an acceptable fallback using the same A2A protocol and human authorization below.
Navigation/read/click-only tools are insufficient. Do not assume every claude.ai
browser tool can execute JavaScript, or try to override its sandbox policy.
See the browser sequence after section 3; there is no alternative authorization,
cross-origin proxy, SDK, or native unattended Claude connector.

## 1. Discover without credentials

Use the origin of this guide as `ORIGIN` (the production origin above unless
explicitly testing locally). Follow these steps now to connect the requesting
person, then use `hello` to discover what you can do.

GET the [Agent Card](/.well-known/agent-card.json) at `ORIGIN/.well-known/agent-card.json`. Require a successful JSON response and
an A2A 1.0 `supportedInterfaces` entry with `protocolBinding: "JSONRPC"` and
`url` exactly `ORIGIN/a2a`. Reject a card advertising a different origin/path.
Use a trusted HTTPS origin without userinfo, path, query or fragment. HTTP is
only for explicit loopback development. Never follow credential-bearing redirects
or forward a token to an endpoint merely because discovery advertised it.

Public discovery and this guide require no Authorization header. Reuse an
unexpired credential for this exact origin if you already hold one privately;
otherwise pair below. Do not publish credentials while inspecting discovery.

## 2. Request human approval

POST to [start pairing](/auth/device) at `ORIGIN/auth/device` with an empty body and no bearer. A 200 JSON response
has `device_code`, `user_code`, `verification_uri`, `verification_uri_complete`,
`expires_in` (600 seconds), and `interval` (5 seconds). Keep `device_code` secret.
Validate that `verification_uri` is exactly `ORIGIN/connect` and that the complete
link has that same HTTPS origin/path and only its `code` query parameter.

Show the human `verification_uri_complete` and ask them to approve **only the
connection they requested**. They choose their UCSC Google account and consent to
Campus Cubbies accessing app-created Drive files. The service creates/reuses their
My Cubby folder and shares it with its Drive identity. You may open the link, but
do not approve consent on their behalf or ask them to paste a Google code, private
key, refresh token, or service credential. Keep browser cookies in the browser.

After waiting at least `interval`, POST to the [pairing exchange](/auth/token) at `ORIGIN/auth/token` using
`Content-Type: application/x-www-form-urlencoded` and these two form fields:
`user_code=RETURNED_USER_CODE&device_code=RETURNED_DEVICE_CODE` (URL-encode values).
No bearer or browser cookie is needed for polling. Do not put the device secret
in the URL, logs, shared files, or chat. Allow only one polling process per pairing.

Handle status and body explicitly:

| Response | Action |
| --- | --- |
| 400, `error: "authorization_pending"` | Wait the current interval, then poll again. |
| 400, `error: "slow_down"` | Increase the interval by 5 seconds and wait before retrying. |
| 400, `error: "expired_token"` | Stop. The pairing expired, was consumed, or is invalid. Start a new human-approved pairing. |
| 400, `error: "invalid_request"` | Fix the form fields; do not loop unchanged requests. |
| 503 | Back off within the original pairing deadline; report persistent service failure. |
| 200 | Read `access_token`, `token_type: "Bearer"`, and `expires_in` (172800 seconds). Stop polling: exchange is single-use. |

Stop at the pairing deadline even if approval is still pending. There is no
separate denial-poll result: a cancelled browser flow stays pending until expiry.
If a successful exchange response is lost, do not assume a second exchange can
recover it. Start a new pairing. Never print a token on success.

For direct HTTP, store the bearer and its absolute expiry in your private credential store,
keyed by the exact service origin, not a shared advisor capability. For local
files, use an owner-only directory (0700) and file (0600), with atomic writes that
refuse unsafe existing temp paths. Existing local credentials may be found at
`$XDG_CONFIG_HOME/campus-cubbies/SHA256(ORIGIN).json` (default
`~/.config/campus-cubbies/`), with `token` and Unix-seconds `expires` fields.
Do not transmit a token until discovery passes the origin check above.

## 3. Call A2A and discover tools

POST `ORIGIN/a2a` with these headers (substitute your private token):

```http
POST /a2a HTTP/1.1
Content-Type: application/json
Accept: application/json
A2A-Version: 1.0
Authorization: Bearer YOUR_PRIVATE_TOKEN
```

The `A2A-Version` header is required: omitting it selects the older 0.3 protocol
and produces a JSON-RPC version error rather than a successful tool result.
Use A2A **1.0** JSON-RPC method `SendMessage`, not the older `message/send` or
older `kind`-tagged message format. This complete request is tested against the
service and the official SDK's protobuf JSON representation. The request body is:

```json
{
  "jsonrpc": "2.0",
  "id": "hello-1",
  "method": "SendMessage",
  "params": {
    "message": {
      "messageId": "hello-message-1",
      "role": "ROLE_USER",
      "parts": [{"text": "{\"action\":\"hello\"}"}]
    }
  }
}
```

Generate fresh request/message IDs for new calls. Check HTTP status first, then
JSON-RPC `error`; on success read `result.message.parts`, concatenate their `text`
values, and JSON-decode that text. Its application object has `ok: true` plus
tool results, or `ok: false` with `error`. HTTP 200 alone does not mean a tool
succeeded. HTTP 401 means missing/expired/revoked authentication: reconnect with
the human, not silent credential renewal. Back off on 503. Requests over 128000
bytes return 413. Non-SendMessage methods return 400; there is no streaming,
task retrieval, history lookup, subscription, or generic OAuth discovery.

`hello` returns your verified `identity`, `roles`, current `tools` with
`input_schema`, and workspace `instructions`. Those are authoritative: do not
hard-code a tool list from this guide. For a tool call, validate its arguments
against the returned schema and put the JSON tool object in the message's text
part using the same envelope. Follow `hello`'s conventions for attribution,
organization, exact edits, and safe delivery retries. Transport IDs alone do not
make a write idempotent; use the tool's documented retry key when available.

## Browser-runtime fallback: keep one tab alive

Open **https://cubby.bayleaf.dev/** in a dedicated browser tab. Verify its actual
`location.origin` is exactly `https://cubby.bayleaf.dev`, not a reader view,
search cache, or embedded document. Execute the following JavaScript expression
in that tab using your tool's page-evaluation facility (not a script element).
The strict CSP allows same-origin fetch but does not allow page scripts or
cross-origin connections. This helper lives only in tab memory and uses the
discovery checks, pairing exchange and A2A envelope documented above.

Never inspect/serialize the helper's internals, network response bodies containing
credentials, or the page heap. Never write the device secret or bearer to the DOM,
console, browser storage, files, or tool/chat output. Return only the expression's
safe result. The secret is held in a closure, not a returned pairing object.

```javascript
(async () => {
  const origin = "https://cubby.bayleaf.dev";
  const checkOrigin = () => {
    if (location.origin !== origin) throw new Error("Wrong browser origin");
  };
  checkOrigin();
  if (window.cubby) return {status: "Already initialized; reuse this tab"};
  const request = async (path, options = {}, deadline = Date.now() + 15000) => {
    checkOrigin();
    const remaining = deadline - Date.now();
    if (remaining <= 0) throw new Error("Deadline reached; reconnect");
    const response = await fetch(origin + path, {
      ...options, credentials: "omit", redirect: "error", cache: "no-store",
      signal: AbortSignal.timeout(Math.min(15000, remaining))
    });
    return {status: response.status, body: await response.json()};
  };
  const card = await request("/.well-known/agent-card.json");
  if (card.status !== 200 || !card.body.supportedInterfaces?.some(i =>
    i.protocolBinding === "JSONRPC" && i.protocolVersion === "1.0" &&
    i.url === origin + "/a2a")) throw new Error("Discovery rejected");
  const startedAt = Date.now();
  const start = await request("/auth/device", {method: "POST", body: ""});
  if (start.status !== 200) throw new Error("Pairing start failed");
  let pairing = start.body;
  const link = new URL(pairing.verification_uri_complete);
  if (pairing.verification_uri !== origin + "/connect" ||
      link.origin !== origin || link.pathname !== "/connect" ||
      link.username || link.password || link.hash ||
      [...link.searchParams.keys()].join() !== "code" ||
      link.searchParams.get("code") !== pairing.user_code ||
      typeof pairing.device_code !== "string" || !pairing.device_code ||
      !(pairing.interval > 0) || !(pairing.expires_in > 0))
    throw new Error("Pairing response rejected");
  const approvalURL = link.href;
  const deadline = startedAt + Math.min(pairing.expires_in, 600) * 1000;
  let interval = Math.max(5, pairing.interval) * 1000;
  let nextPoll = Date.now() + interval;
  let bearer = null, bearerExpiry = 0, busy = false, stopped = false;
  const stop = () => { pairing = null; bearer = null; stopped = true; };
  window.cubby = Object.freeze({
    async poll() {
      if (busy) return {status: "Poll already running"};
      if (bearer) return {status: "Connected"};
      if (stopped || Date.now() >= deadline) {
        stop(); return {status: "Stopped; reconnect"};
      }
      busy = true;
      try {
        // One bounded poll per invocation, never an unattended polling loop.
        const delay = Math.max(0, nextPoll - Date.now());
        if (Date.now() + delay >= deadline) {
          stop(); return {status: "Expired; reconnect"};
        }
        await new Promise(resolve => setTimeout(resolve, delay));
        const result = await request("/auth/token", {
          method: "POST", headers: {"Content-Type": "application/x-www-form-urlencoded"},
          body: new URLSearchParams({user_code: pairing.user_code, device_code: pairing.device_code})
        }, deadline);
        if (result.status === 200) {
          if (result.body.token_type !== "Bearer" ||
              typeof result.body.access_token !== "string" || !result.body.access_token ||
              !(result.body.expires_in > 0)) {
            stop(); return {status: "Invalid exchange; reconnect"};
          }
          bearer = result.body.access_token;
          bearerExpiry = Date.now() + result.body.expires_in * 1000;
          pairing = null; // Single-use exchange: never poll again.
          return {status: "Connected"};
        }
        const error = result.body.error;
        if (result.status === 400 && error === "authorization_pending") {
          nextPoll = Date.now() + interval; return {status: "Awaiting human approval"};
        }
        if ((result.status === 400 && error === "slow_down") || result.status === 503) {
          interval += 5000; nextPoll = Date.now() + interval;
          return {status: "Back off; retry later within pairing deadline"};
        }
        stop(); return {status: "Pairing failed or expired; reconnect"};
      } catch {
        // An uncertain exchange might have consumed the secret. Do not retry it.
        stop(); return {status: "Exchange response lost; reconnect"};
      } finally { busy = false; }
    },
    async call(tool) {
      if (!bearer || Date.now() >= bearerExpiry) {
        stop(); return {status: "Not connected or expired; reconnect"};
      }
      const result = await request("/a2a", {
        method: "POST", headers: {"Content-Type": "application/json",
          "Accept": "application/json", "A2A-Version": "1.0", "Authorization": "Bearer " + bearer},
        body: JSON.stringify({jsonrpc: "2.0", id: crypto.randomUUID(), method: "SendMessage",
          params: {message: {messageId: crypto.randomUUID(), role: "ROLE_USER",
            parts: [{text: JSON.stringify(tool)}]}}})
      });
      if (result.status === 401) { stop(); return {status: "Authentication rejected; reconnect"}; }
      if (result.status !== 200) return {status: "A2A HTTP error", httpStatus: result.status};
      if (result.body.error) return {status: "A2A protocol error"};
      return JSON.parse(result.body.result.message.parts.map(p => p.text || "").join(""));
    },
    disconnect() { stop(); return {status: "Local credentials cleared"}; }
  });
  return {status: "Awaiting human approval", approvalURL};
})()
```

Give the human only the returned approval URL/status and ask them to open it
**separately**, in another tab or browser. Do not navigate the original runtime
tab away, choose an account, or approve consent for them. After the human has had
time to approve, evaluate this expression in the original tab. Each invocation
waits for the advertised interval and makes at most one poll; repeat only for
pending/backoff status, within the original ten-minute deadline. Report persistent
503 failures rather than continuing indefinitely. `invalid_request` is terminal
for this helper: correct the setup before a new pairing. A cancelled approval
stays pending until expiry. No successful poll returns a token.

```javascript
window.cubby.poll()
```

When the result is `Connected`, discover tools:

```javascript
window.cubby.call({action: "hello"})
```

Read the returned `ok`, identity, tool schemas and instructions as in section 3.
For subsequent calls, pass the schema-valid tool object to `window.cubby.call`,
for example replacing `{action: "hello"}` with the desired action and arguments.
This uses the same required A2A headers/envelope, not another interface. Handle
tool errors and write retries as documented above; back off on HTTP 503. Do not
blindly retry writes after a network exception. Output may contain private cubby
information, so share it only as the owner requested, never credentials.

To abandon or reconnect, run `window.cubby.disconnect()` and reload the origin,
then initialize again. Reload, navigation or tab loss requires reconnection;
the helper deliberately has no persistent storage or token export. Browser
availability does not create an unattended native Claude connector. This works
only while the host permits page JavaScript and keeps the tab/runtime alive.

## Permissions and credential lifecycle

Each verified person can manage only their own cubby. Recipient-specific inbound
grants permit a contributor to deliver notes, not read that recipient's files.
Admins have a separate management/metadata overlay, not permission to read other
people's cubbies. Discover your actual roles through `hello`; the service checks
permission again on every call. Shared office/group identities are unsupported.

Bearers last 48 hours and allow unattended calls until expiry. There is no
automatic renewal: reconnect through the browser. If the owner requests agent
revocation, discover and invoke the revocation tool from `hello`; it invalidates
all that person's existing bearers on subsequent authentication, not calls
already in flight. Remove the now-invalid local credential. Revoking agents does
not withdraw Google Drive consent; the human can revoke Campus Cubbies in Google
account settings separately. No account-deletion tool is implemented.
