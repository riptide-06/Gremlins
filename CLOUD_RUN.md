# Cloud Run pilot

Only use project **gremlins-511221** (number **331254975906**). This guide does
not change the global gcloud project. Weekend budget: $10 target, not a hard cap.
Run commands from this repository. No local prototype memory or credentials
are uploaded: Docker and gcloud upload contexts use explicit file allowlists.

## Application contract

- Python/Starlette, official A2A SDK, Google OIDC through Authlib.
- Verified Google issuer, OIDC audience/nonce/state validation, verified email,
  and `hd=ucsc.edu` plus exact email domain restriction.
- Google login asks only `openid email`, not Google Docs access.
- Sessions: signed HttpOnly cookies, Secure in deployment, SameSite=Lax,
  one-hour lifetime. CSRF tokens protect credential generation/revocation.
- Google subject maps to a hashed per-student ID. No email address or Google
  access token is stored in Firestore.
- Student and contribution-only advisor bearer tokens expire after 48 hours.
  Only SHA-256 hashes are stored. New issuance or explicit revocation disables
  both prior tokens. Tokens are shown once and never placed in session cookies.
- Advisor identity is not verified: the advisor token is an invitation capability.
- Persistent, capped notebooks in Firestore: 200 entries, 3000 UTF-8 bytes each.
  Transactions prevent concurrent append loss. There is no automatic deletion
  policy yet, so use synthetic data and clean up the pilot after the event.
- A2A supports immediate non-streaming `SendMessage` replies only. No tasks,
  task histories, retrieval, streaming, subscriptions, or push notifications.
- No model, outbound agent calls, Google Docs, per-student service accounts,
  SLIM, or production institutional authorization is implemented.

## 1. Authenticate and confirm billing

```sh
gcloud auth login amsmith@ucsc.edu
gcloud projects describe gremlins-511221 --account=amsmith@ucsc.edu
gcloud billing projects describe gremlins-511221 --account=amsmith@ucsc.edu
```

Confirm billing is enabled for this project. If access is denied, the project
owner must grant the appropriate project access. Do not use the playground as
a substitute. Confirm a spending-alert budget with the billing account owner:
Cloud Run's instance limit does not cap total Firestore/build/storage costs.

## 2. Provision a small backend

Use `us-west1` for Cloud Run and the default Firestore database unless an
existing database dictates otherwise. Check before creating resources:

```sh
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com --project=gremlins-511221
gcloud firestore databases list --project=gremlins-511221
gcloud iam service-accounts list --project=gremlins-511221
```

If no default database or Gremlin runtime identity exists:

```sh
gcloud firestore databases create --database='(default)' --location=us-west1 --type=firestore-native --project=gremlins-511221
gcloud iam service-accounts create gremlin-runtime --display-name='Gremlin Cloud Run runtime' --project=gremlins-511221
gcloud projects add-iam-policy-binding gremlins-511221 --member='serviceAccount:gremlin-runtime@gremlins-511221.iam.gserviceaccount.com' --role=roles/datastore.user
```

The runtime identity needs Firestore access, not Owner/Editor. Source deployment
also needs a build identity with the documented Cloud Run source-build roles;
inspect the actual build identity rather than blindly granting broad roles.

## 3. Deploy the unconfigured service to obtain its URL

```sh
gcloud run deploy gremlin --source=. --region=us-west1 --project=gremlins-511221 --service-account=gremlin-runtime@gremlins-511221.iam.gserviceaccount.com --allow-unauthenticated --min-instances=0 --max-instances=1 --concurrency=20 --cpu=1 --memory=512Mi --timeout=30 --set-env-vars=GOOGLE_CLOUD_PROJECT=gremlins-511221,ALLOWED_DOMAIN=ucsc.edu
gcloud run services describe gremlin --region=us-west1 --project=gremlins-511221 --format='value(status.url)'
```

Public ingress is necessary for Google login and agent discovery. It does not
grant memory access: application-level role authentication protects `/a2a`.
An unconfigured revision can serve health and onboarding, but cannot sign in.
Set `PUBLIC_URL` to the returned HTTPS URL before testing discovery/login.

## 4. Create the Google OAuth web client

In Google Cloud Console, select **gremlins-511221**, then Google Auth Platform:

1. Configure branding and an appropriate audience. Use Internal only if this
   project is eligible under the UCSC organization. Otherwise use External in
   Testing and add Adam and Tarun's UCSC accounts as test users.
2. Request only `openid` and `email`.
3. Create a **Web application** OAuth client, not a desktop or service account.
4. Add the exact redirect URI: `https://SERVICE-URL/auth/callback`.
5. Keep its client secret in Secret Manager, not Git or a shared agent prompt.

The `hd` login hint improves account selection but does not enforce access.
The callback independently checks the verified hosted-domain/email claims.
Campus sign-in does not make this an institutionally approved student service.

## 5. Configure secrets and complete deployment

Create Secret Manager secrets named `gremlin-oauth-client-secret` and
`gremlin-session-secret`. Add values through stdin or Console, not command
arguments. Generate a high-entropy session secret. Grant the runtime service
account `roles/secretmanager.secretAccessor` on these two secrets only.

```sh
gcloud run services update gremlin --region=us-west1 --project=gremlins-511221 --update-env-vars=PUBLIC_URL=https://SERVICE-URL,GOOGLE_CLIENT_ID=CLIENT-ID --update-secrets=GOOGLE_CLIENT_SECRET=gremlin-oauth-client-secret:1,SESSION_SECRET=gremlin-session-secret:1
```

Never enable `LOCAL_HTTP` on Cloud Run. Pin secret versions; explicitly update
the revision when rotating them. Changing SESSION_SECRET signs browsers out;
agent access is revoked separately through stored credential hashes.

## 6. Verify end to end

1. Visit the site and sign in with a UCSC account.
2. Generate instructions; send the student block to the student's agent only.
3. Discover the card, `hello`, remember a synthetic fact, and read it back.
4. Give an outside agent the advisor block. Contribute guidance, then verify
   reading fails without a notebook read event.
5. Verify a different student sees a different notebook.
6. Revoke credentials and verify both roles fail authentication.
7. Restart/redeploy and verify memory persists in Firestore.
8. Inspect Cloud Logging: events only, no tokens or notebook content.

Cloud Run request logging is platform-managed even though Uvicorn access logs
are disabled. Never put secrets or student information in URLs/query strings.
Google's callback code is handled in a redirect query; restrict log access and
retention appropriately. Application logs do not emit callback query strings.

## Cost and teardown

Keep scale-to-zero and one maximum instance. Firestore has separate billing;
the notebook cap bounds storage per student, not total spend. Check project
billing during the event and delete the service afterward if no longer needed:

```sh
gcloud run services delete gremlin --region=us-west1 --project=gremlins-511221
```

This does not delete Firestore data, container images/build artifacts, or secret
versions. Review and remove only dedicated pilot resources separately, with the
owner's confirmation. Do not delete the whole project or database by default.
