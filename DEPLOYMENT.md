# Hackathon deployment record

## Resources

- Project: `gremlins-511221`, number `331254975906`.
- Organization: `ucsc.edu`.
- Cloud Run: `gremlin`, `us-west1`.
- URL: https://gremlin-331254975906.us-west1.run.app
- Health endpoint: `/health` (the platform returns 404 for `/healthz`).
- Default Firestore database: Native, Standard, `us-west1`, free-tier eligible.
- Runtime identity: `gremlin-runtime`, Firestore user plus accessor on the two
  application secrets only.
- Build identity: `gremlin-build`, Cloud Run Builder role.
- Secret Manager: `gremlin-session-secret`, `gremlin-oauth-client-secret`.
- Google OAuth web client: `Gremlin Cloud Run onboarding`, Internal audience;
  redirect is the service URL plus `/auth/callback`.
- Cloud Run: scale to zero; maximum one instance at both service and revision
  levels; 1 CPU, 512 MiB memory, concurrency 20, 30-second timeout.
- Project-specific $10 weekend alert budget, not a hard spending cap.

## Verification completed

- 14 local tests pass on Python 3.12.
- GitHub Actions passes.
- Actual Firestore transactions, token issuance/authorization/revocation, and
  separation of auth metadata from notebook contents tested with synthetic data.
- Live HTTPS A2A discovery and student/advisor greetings tested.
- Live student remember/read and advisor contribute tested.
- Live advisor read denied without returning private content.
- Live revocation rejects both roles with HTTP 401.
- Backend test records and credentials removed after the test. No local
  role-play notebook, secrets, or injection payload was migrated.
- Real Google OIDC login completed using `amsmith@ucsc.edu`, including the
  provider's Internal account restriction and the app's domain checks.
- Browser testing caught an Origin/Referrer-Policy conflict on form submission.
  Policy changed to `same-origin`; cross-origin/null-origin requests remain
  rejected and CSRF tokens remain required.

## Remaining acceptance checks

- Retest real browser credential issuance after the Referrer-Policy fix, then
  use those credentials over A2A.
- A second UCSC user signs in independently and sees a separate memory space.
- Real Claude.ai connector requires the separate MCP/OAuth adapter described
  in `CLAUDE.md`; it is not implemented.

This is a synthetic-data hackathon pilot, not an institutionally approved
service for health, immigration, or other sensitive student records.
