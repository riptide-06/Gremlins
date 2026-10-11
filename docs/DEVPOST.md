# Devpost copy

**Title:** Gremlins: when campus offices disagree, your agent tells you who decides

**Tagline:** A student-controlled advocate for UCSC. Four department gremlins argue from
their own policy boxes; the student's gremlin shares the minimum, applies precedence in
code, and returns CONVERGED, DISPUTED, ESCALATED, ASK_STUDENT, or UNANSWERED. Built on
AGNTCY A2A with SLIM transport, on top of Campus Cubbies.

## Inspiration

An international student asks three offices whether they can drop to 10 units. The
international office says no without an RCL. The college says sure, with approval. Financial
aid says the scholarship pays out at 12. All three are right about their own rules and the
student is the one who has to notice the conflict. Multi-agent systems that "reach consensus"
by averaging would be worse: the right answer here is that federal rules outrank campus rules,
and that is a precedence fact, not a vote.

## What it does

- Every department has a **box**: its policy as facts with sources (`F-xx`), precedence
  rules, FAQ, and escalation triggers. We wrote four from real UCSC pages this weekend: ISO,
  Computational Media advising, Crown College advising, Financial Aid.
- Every student has a **cubby** (Campus Cubbies, in their own Google Drive): their facts,
  their sharing permissions per department, and everything their gremlin wrote back.
- **Department gremlins** are stateless A2A agents that answer only from their box; every
  sentence must cite a rule or it is deleted by the wall.
- The **advocate** (the student's gremlin) selects departments by the topics each box
  advertises, shares only permitted fields, consults them in parallel (none sees another),
  and decides in code: escalation triggers, missing fields, precedence, or dispute.
- A judge opens one link; a student adds one MCP URL to their own Claude.

## How we built it

Python, a2a-sdk 1.2.2 (A2A 1.0 JSON-RPC), AGNTCY SLIM for the ISO leg, litellm over free
tiers (Groq gpt-oss-120b, NVIDIA NIM Nemotron, Gemini 2.5 Flash), a Markdown box grammar
with a 400-line parser, a replay cache keyed by prompt hash so demos repeat exactly, MCP
(stdio and streamable HTTP) for bring-your-own-agent, Starlette on Cloud Run, Campus
Cubbies' A2A tools for the student's Drive folder. 154 tests, no network needed.

## Challenges

- Temperature 0 is not deterministic, and free tiers rate-limit four parallel calls. We made
  the model draft and the code decide, then cached the drafts.
- Leak checks need judgment in code: `yes` is not a secret, `F-1` in a policy sentence is not
  a leak of the student's visa, but the student's name anywhere is a rejection.
- "Consensus" was the wrong target. Precedence and kept disagreements were the right ones.

## Accomplishments

Real policy, real citations, a wall that is code, a dispute the system refuses to resolve
on the student's behalf, and an end-to-end path from a judge's browser to four A2A agents.

## What we learned

The same lesson as our stale-memory paper: the model should never see a superseded value,
and the thing that decides what is current has to be code. Also: three offices disagreeing
is a feature of a university, not a bug, and software should preserve that.

## What's next

Publish each gremlin's agent card to the AGNTCY Directory (OASF) so discovery replaces our
topics regex; Observe SDK traces for the audit trail; SLIM for all four departments; more
department boxes written by the departments themselves; the Drive box as the only store.

## Built with

python, a2a-sdk, agntcy-slim, litellm, mcp, starlette, google-drive-api, cloud-run, groq,
nvidia-nim, gemini
