# Campus Cubbies

Permissioned campus correspondence in a person's UCSC Google Drive **My Cubby**
folder. The service is mechanical; the caller's agent supplies reasoning.
Production: https://cubby.bayleaf.dev. This is a prototype, not an institutionally
approved service for sensitive records.

## Sources of truth

- [SKILL.md](SKILL.md): authoritative agent connection and raw HTTP/A2A use guide,
  publicly served at `/SKILL.md`. `/llms.txt` is only a pointer.
- Agent Card: relevance, capabilities and endpoint, with `documentationUrl`
  pointing to the guide. The friendly human landing links directly to that guide,
  with matching HTML discovery metadata and an HTTP `Link` header, not a second manual.
- `cubbies.py` tool registry and authenticated `hello`: current role-dependent
  schemas and workspace conventions. Do not maintain a second tool catalog.
- [DEPLOYMENT.md](DEPLOYMENT.md): exact deployed resources, repeat-deployment
  playbook and live verification. [PLAN.md](PLAN.md): scope and remaining work.

Agents build their own A2A integration from the tested HTTP wire example. A2A is
the only hackathon tool interface; no active downloadable client is provided.
Historical clients remain in their archives.

## Development

From the repository root:

```sh
uv sync --frozen
uv run pytest -q
node --test prototypes/cubbies/domain-proxy.test.mjs
uv run python -m compileall -q prototypes/cubbies
LOCAL_HTTP=1 uv run uvicorn cloud_app:app --app-dir prototypes/cubbies --port 8080 --no-access-log
```

Public landing, guide, discovery and health work without cloud credentials.
Tests use fake repositories/Drive and HTTP mock transports, never campus data.
The guide's actual headers and JSON example are executed against the app and
compared with official SDK serialization. Historical tests are excluded.
Root-only discovery tests follow the published landing/guide/card links through
pairing and documented `hello`, including resolution at the custom HTTPS domain.

Export `.env.example` variables privately; dotenv is not loaded automatically.
The app lives in `cloud_app.py`, policy/Firestore in `cubbies.py`, and Drive in
`cubby_drive.py`. `domain-proxy.mjs` only forwards to the fixed Cloud Run origin,
without application content, auth logic, logging, caching or storage.

## Engineering boundaries

- **One worker, one active app instance, one writing revision.** Recipient
  mutexes plus 180-second Firestore leases serialize app operations. Leases are
  not renewable/fenced; a stalled operation can outlive its lease. Do not enable
  distributed writers without a durable queue or properly fenced serialization.
- User OAuth with `drive.file` creates/owns files. A keyless impersonated Drive
  identity accesses each shared folder. Arbitrary manually added files may be
  invisible to the owner's narrow scope. Supported content is direct UTF-8 text
  children, at most 100000 bytes; native Docs, shortcuts and other folders are
  not content/mutation targets. Lists can include unsupported metadata.
- The cubby is tracked by its saved Drive ID: renaming or moving it within the owner's My Drive preserves its name, color and contents; reconnect restores service sharing, but an unavailable/deleted folder requires restoration or administrator help, never automatic replacement.
- Exact edits check the supplied version, one search match, and version/location
  again after reading under the app lock. No documented Drive media-update ETag
  precondition is relied on. External manual moves/edits can race the final write;
  do not claim external-edit atomicity. Immediate post-create reads can encounter
  propagation version changes and should retry without weakening the guard.
- Delivery reserves an owner-created Drive ID before upload, rejects changed
  contents for the same retry key, and retries final status/deterministic audit.
  A file can exist without final status if a failed caller never retries. There
  is no background reconciliation. Receipts mean delivery, not reading.
- Firestore is server-only metadata, not note content: `cubby_users`, `grants`,
  `tokens`, `pairings`, `locks`, `deliveries`, and `audit` (all `cubby_` prefixed).
  Refresh tokens are encrypted; bearer/device secrets are hashed. Audit fields
  are allowlisted. Admin access is metadata/relationships, not others' files.
- Expiry enforcement is not deletion. Numeric credential timestamps are not
  native Firestore TTL fields. Retention/account deletion needs policy and a
  cleanup implementation. Preserve delivery retry records to prevent duplicates.

Existing offline and live evidence is recorded in the deployment file; mocks
do not establish campus policy, real consent, or external concurrency guarantees.
