# Three minutes with the judges

Say it like a person. Hyphens only, no slides needed beyond the chat page and the eval table.

## 0:00 Who we are (15 s)

"I'm Tarun, a junior at UCSC. I'm a co-author on a poster at the NeurIPS 2026 AI4GOOD
workshop, and my stale-memory paper is under review at NORA 2026. That paper is why this
project looks the way it does. My teammate is Adam Smith, professor in Computational Media,
who built Campus Cubbies, the thing this runs on."

## 0:15 The problem (25 s)

"An international student asks whether they can drop to 10 units. The international office
says not without an RCL. The college says sure, with approval. Financial aid says the
scholarship pays out at 12. All three are right about their own rules. The student is the
one who has to notice that they conflict, and which one wins. That's the disagreement we
built for: three agents with different objectives and a correct answer that is not an
average."

## 0:40 What it is (30 s)

"Every department has a box: its policy as facts with sources, precedence rules, and
escalation triggers. Every student has a cubby in their own Google Drive with their facts and
their sharing rules. Department gremlins are A2A agents that answer only from their box and
must cite every sentence. The student's gremlin asks the departments whose boxes cover the
question, shares only the fields the student allowed, asks them all at once, and decides in
code: converged, disputed, escalated, ask the student, or unanswered."

## 1:10 Show it (60 s)

Live on the chat page, from the replay cache so it is instant:
1. c1: "drop to 12 units" - CONVERGED, four departments, every claim cited.
2. p1: "college approved 10 units" - college says yes, ISO says no, federal outranks campus,
   the override is recorded. "Nobody voted."
3. d1: "add CMPM 120 now or wait" - two advisers, equal authority, DISPUTED. "We keep the
   disagreement. The student decides, and the brief says what would settle it."
4. Set days_to_deadline to 2, re-ask c1 - ESCALATED. "Same question, new information, a
   trigger in code, a human gets a brief."

## 2:10 Why it holds up (30 s)

"The model only drafts. Scope, sharing, escalation, precedence, and the verdict are code
reading the boxes. The wall is code: name and email never leave, uncited sentences are
deleted, an answer that echoes a protected field is rejected. Against a baseline that pastes
every box and the whole student file into one prompt: we cite, it doesn't; we leak nothing,
it leaks everything. Departments talk A2A, ISO over SLIM, and a student can plug the gremlin
into their own Claude with one MCP URL."

## 2:40 What's next and the ask (20 s)

"Publish each gremlin's card to the AGNTCY Directory so discovery is real, Observe traces
for the audit trail, and department boxes written by the departments. The ask: we want to
run this for one real office at UCSC with Adam's cubbies as the boundary."

## Questions they will ask

- **Why not one LLM with everything in the prompt?** That's our baseline. It blends, it
  can't say who decides, and it has the student's name in context so it can leak it. The
  eval table is the answer.
- **Where is the "no central decision-maker"?** The advocate never answers from its own
  knowledge and departments never see each other. Agreement, precedence, and dispute are
  computed from their positions. Precedence is a fact in the boxes (authority_order), not a
  judge agent.
- **Is the disagreement real or scripted?** Real boxes, real policy, real model drafts. The
  replay cache only makes the demo repeat; `GREMLIN_CACHE=0` runs live.
- **What's actually AGNTCY here?** A2A 1.0 between advocate and department gremlins
  (a2a-sdk), SLIM transport for the ISO gremlin, and Campus Cubbies' own A2A tool surface
  for the student's Drive folder. Directory and Observe are the next step and we say so.
- **What about 1,000 students?** Each question is a handful of stateless calls; the state
  is one file per student that only their gremlin reads. The limit today is free-tier model
  rate, not the design.
- **Privacy / FERPA?** Student data stays in the student's own UCSC Drive. Departments see
  only permitted fields, logged per session. Boxes hold policy, never student data. This is
  a synthetic-data pilot and we say that on every page.
- **What if a box is wrong?** Every fact has a source and a verified flag. An unverified
  fact makes the gremlin say so. Fixing policy is editing a text file the department owns.
- **Why Markdown?** Departments can edit it, students can read it, git can diff it, and the
  parser is 400 lines nobody has to trust blindly.
- **Where did the eval questions come from?** We wrote them, and iterated the prompt on
  them, so they are not held out. Verdicts decided in code hold regardless of the model.
