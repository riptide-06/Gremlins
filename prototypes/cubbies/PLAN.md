# Campus Cubbies scope and follow-up

## Contract

- Each verified UCSC person owns a green My Cubby Drive folder and app-created
  text files, shared with the service's keyless Drive identity.
- Contributions are attributed outside information. Recipient-specific inbound
  grants authorize delivery, never contributor reads. Grants record owner/admin
  management, reason, source, actor and timestamp. Owners cannot overwrite
  admin-managed grants; admins can provision grants before recipients onboard.
- Every person has owner/contributor tools; admins add a metadata/relationship
  overlay without cross-person file access. No office aliases, directory search,
  outbound-recipient listing, streaming or autonomous/model reasoning.
- Human consent remains explicit on pairing pages. Landing copy is for people,
  not a technical manual. Agents implement HTTP themselves.

## Ownership of information

| Surface | Responsibility |
| --- | --- |
| Landing | Friendly explanation and the URL to give an agent |
| Agent Card | Relevance, capabilities, endpoint, guide link |
| [SKILL.md](SKILL.md) | Connection, wire format, private credentials and responsible use |
| Tool registry / authenticated `hello` | Current role-dependent schemas and workspace conventions |
| [README.md](README.md) | Development and engineering limits |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Resource identities, playbook, live evidence |
| Cloudflare Worker | Fixed-origin forwarding only |

`/llms.txt` only points to the guide. A2A is the only hackathon tool interface;
there is no downloadable client. Historical prototypes remain untouched.

## Verification requirements

Keep tests for identity isolation, grant races/admin protection, transactional
pairing single use/expiry/revocation, OAuth state/CSRF, redacted logs/audit, bounded
requests, constrained Drive content, exact edits, idempotent onboarding/delivery,
official SDK transport, and the served guide's raw HTTP headers/body/parsing.
Public responses must not leak credentials or identity state. Landing/discovery
must not regain duplicated integration recipes or retired download routes.

## Remaining work

- Independently onboard a second campus person and verify live peer delivery,
  revocation and retries. Offline policy tests are not that acceptance test.
- Verify narrow-scope behavior for manually added files if broader management
  is ever promised. External-edit atomicity is not currently guaranteed.
- Add retention/account deletion policy and cleanup; retain delivery retry IDs.
  Decide whether background reconciliation is warranted.
- Before multi-instance hosting, replace unfenced leases with safely distributed
  serialization. Current Cloud Run limits are not a strict overlap guarantee
  during rollout: deploy during a quiet window.
