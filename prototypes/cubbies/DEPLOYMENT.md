# Campus Cubbies deployment

Public URL: **https://cubby.bayleaf.dev**. Agent protocol lives in [SKILL.md](SKILL.md);
this file owns infrastructure and acceptance evidence, not a second connection guide.

## Resource identities

- Google project `gremlins-511221` (331254975906), deployer `amsmith@ucsc.edu`.
  Cloud Run service `gremlin`, `us-west1`; fixed upstream
  `https://gremlin-331254975906.us-west1.run.app`.
- Runtime `gremlin-runtime@gremlins-511221.iam.gserviceaccount.com`, display name
  **Campus Cubbies runtime**, project `roles/datastore.user`. Build identity
  `gremlin-build@gremlins-511221.iam.gserviceaccount.com`, display name
  **Campus Cubbies source build identity**, `roles/run.builder`.
- Drive target `cubbies-drive@gremlins-511221.iam.gserviceaccount.com`, display
  name **Campus Cubbies shared Drive identity**, no project role. Custom role
  `projects/gremlins-511221/roles/cubbiesDriveTokenMinter` contains only
  `iam.serviceAccounts.getAccessToken`, granted to runtime **on that target only**.
  No service-account private key or domain-wide delegation. Project-derived email
  suffixes cannot disappear through display-name changes; preserve existing shares.
- OAuth brand **Campus Cubbies**, Internal UCSC audience, home page
  `https://cubby.bayleaf.dev`. Existing web client ID
  `331254975906-sb4fjjp7rvn99i7t6o56v6qa8vaji0a7.apps.googleusercontent.com`.
  Both `https://cubby.bayleaf.dev/auth/callback` and the upstream's `/auth/callback`
  are registered. Requested scopes: `openid email drive.file` with offline consent.
- Existing version-1 secrets: `gremlin-session-secret`,
  `gremlin-oauth-client-secret`, `cubbies-drive-token-key` (Fernet encryption).
  Runtime accessor grants are secret-level only. Never print/rotate these while
  deploying; rotating encryption without migration breaks stored refresh access.
- `PUBLIC_URL=https://cubby.bayleaf.dev`, `ALLOWED_DOMAIN=ucsc.edu`,
  `CUBBY_ADMINS=amsmith@ucsc.edu`. Hosted `LOCAL_HTTP` is unset.
- One Uvicorn worker, service/revision max one, minimum zero, 1 CPU, 512 MiB,
  concurrency 20, timeout 30 seconds. Public invoker remains enabled; app bearer
  checks protect tools. Default Native Firestore database is in `us-west1`.
- Required Drive, IAM Credentials, Firestore, Secret Manager, Cloud Run and build
  APIs enabled. `_Default` Logging exclusion `cubbies-sensitive-urls` excludes
  this service's `/auth/callback` and `/connect` platform request logs. Only
  `_Default` and audit-only `_Required` sinks were present at setup.
- Cloudflare account **BayLeaf**, `1a49fb69291d42e23c4ed4dcffce5bbc`, explicit
  profile `ucsc`; active `bayleaf.dev` zone `2cdc9d687b938704965a00188f8877ad`.
  Dedicated `campus-cubbies-domain` Worker custom domain `cubby.bayleaf.dev`,
  managed HTTPS/DNS. No bindings, runtime secrets, storage, observability,
  Logpush, workers.dev or preview endpoints. Other BayLeaf apps are untouched.
- Proxy forwards only to the fixed upstream, preserving auth/cookies/browser
  Origin and never following upstream redirects with credentials. Use fetch
  `cache: "no-store"`, not `cf.cacheTtl: 0` (the latter stripped session cookies).
  Response `no-store, no-transform` also suppresses automatic analytics injection
  without changing zone-wide rules. Existing lite analytics rules could not accept
   another exclusion; none were modified. CSP permits only same-origin form actions.
   The CSRF-protected login POST finishes with a same-origin 200 page; its ordinary
   Google sign-in link starts a new top-level navigation, outside the form redirect
   chain. Authlib still stores OAuth state, nonce and the PKCE verifier in the session.

## Repeat deployment

From the repository root, inspect existing resources and deploy during a quiet
window with agents stopped. Never split writes across revisions. Limits alone
do not strictly prevent transient overlapping instances during rollout.

```sh
uv sync --frozen
uv run pytest -q
node --test prototypes/cubbies/domain-proxy.test.mjs
node --test prototypes/cubbies/browser-guide.test.mjs
uv run python -m compileall -q prototypes/cubbies
gcloud run services describe gremlin --region=us-west1 --project=gremlins-511221 --account=amsmith@ucsc.edu
gcloud run deploy gremlin --source=. --region=us-west1 --project=gremlins-511221 --account=amsmith@ucsc.edu --service-account=gremlin-runtime@gremlins-511221.iam.gserviceaccount.com --build-service-account=projects/gremlins-511221/serviceAccounts/gremlin-build@gremlins-511221.iam.gserviceaccount.com --min=0 --max=1 --max-instances=1 --concurrency=20 --cpu=1 --memory=512Mi --timeout=30 --quiet
curl --fail https://cubby.bayleaf.dev/health
curl --fail https://cubby.bayleaf.dev/.well-known/agent-card.json
curl --fail https://cubby.bayleaf.dev/SKILL.md
curl --fail https://cubby.bayleaf.dev/llms.txt
```

The deploy command preserves existing env/secret bindings. Never reset PUBLIC_URL
to the upstream. Root upload allowlists and Dockerfile package active app code
and the canonical guide only, not archives/private configuration. For a new
environment use `.env.example` and provision the scoped resources above; do not
replace identities or copy the existing secrets into images.

Re-deploy the domain proxy only when its source/config changes:

```sh
node --test prototypes/cubbies/domain-proxy.test.mjs
uv run prototypes/cubbies/deploy-domain.py
```

The helper verifies active zone/account using explicit `ucsc`, refreshes its OAuth
via a real API call, and privately passes credentials to account-pinned Wrangler.

## Acceptance evidence

Recorded October 11, 2026 UTC (October 10 local):

- Adam approved real campus OAuth/Drive onboarding at the original origin.
  Pairing exchange, owner/contributor/admin discovery, impersonated starter-file
  listing, and synthetic file create/read/exact-edit/read-back/rename/trash passed.
  Starter contents were not read or changed. Immediate post-create version change
  was safely rejected; a settled retry passed. Only synthetic files were trashed.
- Real Firestore pairing/pending exchange and lease acquisition, competing-lease
  rejection and release passed. The separate lease test used the deployer;
  hosted pairing verified runtime access. Only its test lock was removed.
- Custom-domain HTTPS, session cookies, CSRF-protected Google redirect and existing
  bearer access to `hello`/Drive listing passed. Google's callback configuration
  briefly returned redirect mismatch while propagating, then reached sign-in
  confirmation branded Campus Cubbies. Final fresh-domain human approval/callback
  was not claimed from the confirmation screen alone.
- Browser testing found/fixed a CSP restriction on Google's OAuth form redirect.
  Public page/card/download checks passed before retiring downloads. The active
  guide replaces those client routes; they must now return 404, not stale code.
- Current guide refactor: 35 Python tests pass, including the exact **served**
  A2A headers/body, protobuf JSON comparison, role-dependent hello, tool errors,
  expiry/single-use pairing, no public credential leaks and revocation. Three
  Node proxy tests pass. An upstream Authlib HTTPX deprecation warning remains.

Earlier revision **`gremlin-00018-98c`**, then 100% traffic, agent version 0.4.0.
Live checks confirm the served guide exactly matches source, the card's
`documentationUrl` points to it, `/llms.txt` is only a pointer, `/health` is 200,
and both former download routes are 404. The guide's exact raw HTTP headers/body
completed authenticated Adam `hello` and Drive listing without an SDK or bundled
client. No note contents were read or changed. Mobile browser shows only friendly
human copy and the URL, with no integration wall or reported page errors.
Canonical URL, administrator allowlist, runtime/Drive identities, pinned secret
bindings and one-instance limits were independently checked and preserved.
Build-upload inspection confirms exactly seven files: Dockerfile, pyproject,
uv.lock, three app modules and SKILL.md. Explicit nested directory exclusions
prevent archives, private config, tests, Worker code and bytecode from being
admitted by parent-directory allowlist rules. The Worker remains unchanged.

Root-first discovery update: 50 Python tests and three proxy tests pass, plus
frozen dependency sync and compilation. Two traversal tests follow actual served
landing/guide/card links through pairing and the guide's raw A2A `hello` request,
at loopback and the custom HTTPS origin. The landing adds one visible connection
link and matching HTML/HTTP discovery links; `/llms.txt` and the card converge on
`/SKILL.md`, which alone owns pairing and connection instructions. Existing saved
Drive-folder deletion/sharing safeguards and tests were preserved and deployed.
Live custom-domain traversal verified all root links, exact served guide, card,
llms pointer, pairing start, human verification page and pending token poll.
No live consent or Drive operations were performed in this update. Authenticated
pairing/A2A completion was tested offline, not newly claimed live. Mobile browser
text confirms the friendly landing and visible connection link. Resource checks
confirm 100% traffic, unchanged OAuth client/secret bindings, identities, public
origin and one-instance limits. Cloudflare was not changed.

Form-navigation CSP fix: live inspection found exactly one matching CSP header
at the custom domain and upstream, no proxy-origin mismatch, and a login 302 to
`accounts.google.com/o/oauth2/v2/auth`, followed by Google's sign-in page. The
tester-specific block was not reproduced in the available signed-in browser;
no additional Google redirect origin is claimed as observed. Browser form-action
redirect enforcement is inconsistent, so login now completes on a same-origin
200 page with an ordinary Google link instead of allowing more external origins.
The 50-test Python suite verifies the absence of a form redirect, CSRF/origin
rejection, state/nonce persistence, exact PKCE challenge/verifier agreement,
campus hint and canonical callback. The three proxy tests still pass.
Deployed as `gremlin-00017-jhp` with 100% traffic. Live browser verification
followed a fresh connection form to the same-origin `/login` page, then its link
to Google's UCSC account chooser without a reported CSP error. No account was
selected and no consent was granted. Live HTTP checks confirmed login 200 without
Location, pending pairing, healthy discovery routes and an unchanged canonical
guide. All environment/secret bindings, runtime identity, CPU/memory, concurrency,
timeout and service/revision one-instance limits match the pre-deploy settings.
The Worker was unchanged. Testers should start a fresh agent connection and use
the additional Google sign-in link, not resubmit an old connection tab.

Owner storage visibility update: deployed as `gremlin-00018-98c`, 100% traffic.
Authenticated `hello` now returns `cubby.folder_id` from the caller's persisted
user record and its validated `cubby.folder_url`, plus one instruction to share
the link with the owner. Formatting and Drive ID validation are centralized;
renaming or moving the saved folder does not change this reference. No per-user
state was added to the public home or other discovery routes, and no folder
references were added to relationship, receipt, permission or admin metadata tools.
All 60 Python tests and three proxy tests pass; compilation passes. Offline tests
cover owner/admin self-only references, concurrent authenticated A2A isolation,
public and other-user metadata non-disclosure, invalid IDs, and stable references
after external folder renames/moves. Live unauthenticated root, health, guide,
card and llms responses are byte-for-byte unchanged from `00017-jhp`, including
their CSP headers; retired downloads remain 404 and unauthenticated A2A remains
401. Runtime identity, OAuth/environment and pinned secret bindings, CPU/memory,
concurrency, timeout and both one-instance limits match the pre-deploy settings.
The OAuth/CSP fix and Worker are unchanged. No live consent, authenticated Drive
inspection or private Drive changes were performed; authenticated behavior was
verified offline, not newly claimed live.

Browser-runtime fallback update: current revision **`gremlin-00019-lnn`**, 100%
traffic, agent version 0.4.0. Canonical `SKILL.md` prefers direct HTTP and teaches
same-origin browser JavaScript as a fallback using the same human pairing and A2A
protocol. Its closure retains credentials only in tab memory, returns safe pairing
status/approval URL, makes one interval/deadline-bounded poll per invocation, and
uses the required A2A 1.0 envelope for `hello` and discovered tools. No client
bundle, connector, proxy API or CORS access was added; friendly landing, Agent Card
and llms pointer are unchanged. Page CSP adds only `connect-src 'self'`; strict
default, form-action, frame-ancestors and base-uri restrictions remain intact.

All 61 Python tests and six Node tests pass, with frozen sync and compilation.
The served JavaScript runs against the actual offline ASGI pairing/A2A APIs through
a Node transport, including pending, simulated human approval and authenticated
`hello`. Additional extracted-snippet tests cover backoff, deadline, concurrent
poll suppression, single-use exchange, terminal/lost responses, bearer expiry,
subsequent tool envelopes and no serialized credential results. The proxy test
asserts CSP preservation and no added CORS header. Authlib's existing deprecation
warning remains. Build upload still contains only the seven allowlisted files.

Live Chrome (Rodney page evaluation) ran the exact canonical setup/poll expressions
on `https://cubby.bayleaf.dev/`: same-origin `/auth/device` succeeded and token
polling remained pending, without printing device secrets or obtaining a bearer.
The original runtime tab retained its helper with empty local/session storage;
cross-origin fetch was blocked. A separate approval tab submitted the local
connection form and reached `/login` HTTP 200 with only an ordinary Google link,
then the original tab polled pending again. No Google account was selected, consent
granted, or Drive data read/changed. Live authenticated browser A2A is not claimed;
that path passed offline only. JavaScript-capable browser tools are required;
read/click-only tools and unattended native Claude connectors remain unsupported.

Live custom-domain and upstream responses have exactly one identical CSP header,
with no CORS header, so no Cloudflare change was needed. Health/discovery succeed,
served guide matches source exactly, retired downloads return 404 and unauthenticated
A2A returns 401. Runtime/Drive identities, OAuth client, public URL, administrator
allowlist, pinned secret bindings, CPU/memory, concurrency, timeout and both
service/revision one-instance limits were checked against the pre-deploy settings
and preserved. Cloudflare Worker source/config and secrets were not changed.

Second-person peer delivery, manual-file scope behavior, institutional approval,
account deletion and distributed writer safety remain unverified or unimplemented;
see [PLAN.md](PLAN.md) and [README.md](README.md).
