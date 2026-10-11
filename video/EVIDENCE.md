# Story and evidence

This film illustrates a prospective ISO-to-student use case using fictional content.
It is not footage of an observed ISO deployment or a real federal regulation.
The ISO initiates delivery; the student's agent catches up when the student asks.
Agent interpretation belongs to the caller, not the Cubbies server.

## Implementation anchors

- `prototypes/cubbies/cubby_drive.py:67–105`: owner-authorized setup creates the green **My Cubby** Google Drive folder, shares it with the service identity, and verifies access.
- `prototypes/cubbies/cubbies.py:390–413`: authenticated, attributed, permission-checked delivery.
- `prototypes/cubbies/cubbies.py:416–449`: catch-up and own-folder operations.
- `prototypes/cubbies/cloud_app.py:507–517`: A2A interface.
- `prototypes/cubbies/test_cubbies.py:188–258`: contributor and administrator access boundaries, offline evidence.
- `prototypes/cubbies/test_changes.py:138–208`: offline update/catch-up workflow.

The contribution boundary is between campus participants. The service itself has
access to the shared folder; the film does not claim end-to-end encryption.

## Research process

Two read-only agents surveyed backend evidence and available visual material.
Their important finding: there is no native inbox dashboard worth filming.
The production therefore uses explicitly illustrative motion graphics, grounded
in the real file names, permission model, and caller/server responsibility split.
No production messages or user data were accessed for this film.

## Ninety-second production-status revision

Commit `7a5f9c2` explicitly identifies Campus Cubbies as a fully integrated
production service, replacing the former pilot/prototype language. This commit
clarifies existing integration and data boundaries rather than implementing new
connections. Current authoritative description: `prototypes/cubbies/README.md:3–10`.

Recorded live evidence includes campus OAuth/Drive onboarding, synthetic file
operations, and authenticated raw-HTTP A2A hello/list calls:
`prototypes/cubbies/DEPLOYMENT.md:110–122,131–137`.
BayLeaf Chat onboarding link deployment and live HTML verification:
`prototypes/cubbies/DEPLOYMENT.md:428–438`, revision `gremlin-00027-qdf`.
Infrastructure includes internal-UCSC OAuth, Cloud Run, Firestore, and UCSC Drive.
The video does not claim a registrar/SIS integration.

The official event page was read in the browser and confirms the event title
SF Tech Week Hackathon @ UCSC SVC and three tracks including Cloud AI:
https://events.ucsc.edu/event/sf-tech-week-hackathon-ucsc-svc/
Cloud AI is the team's track per Adam's direction. No affiliation beyond that
participation, and no award or event endorsement, is implied.
