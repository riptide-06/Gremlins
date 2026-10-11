# The 90-second demo video (what judges evaluate)

Record the real thing. One take per shot is fine; cut in Screen Studio, CapCut, or
QuickTime + iMovie. Narration is you, not TTS. Keep the cursor slow. 1080p, landscape.

Before recording:
- `DEMO_TOKEN=judge LOCAL_HTTP=1 uv run uvicorn gremlin_app:app --port 8080 --no-access-log`,
  open `http://localhost:8080/demo?token=judge` (or the Cloud Run judge link). For the real
  sign-in shot, open `http://localhost:8080` in a second browser profile and pair with
  cubby.bayleaf.dev using your own UCSC account.
- Run every question once beforehand so the replay cache answers instantly on camera.
- Claude Desktop with the `gremlin` MCP server added (`claude mcp add gremlin -- uv run --directory <repo> mcp_server.py`).
- A terminal with `uv run demo.py --transport slim --questions c1` ready, SLIM node up
  (`uv run --script prototypes/slim/gremlin_slim.py node`). If SLIM is not up, skip shot 6 and
  say "in-process" honestly.
- Google Drive open on your My Cubby folder with `gremlin-student.md` (shot 7, optional).

| t | shot | what is on screen | you say |
|---|---|---|---|
| 0:00 | hook | the site's sign-in page, gremlin on the cubby | "Ask three campus offices the same question and you get three answers. Last year that was my problem. Now it's the gremlins' problem." |
| 0:08 | the cubby | press Continue with UCSC Google, approve on Campus Cubbies, land on Welcome (your real cubby) or switch to the judge tab; open My Cubby | "This is a student's cubby: their own facts, their own sharing rules. Only their gremlin reads it. Name and email are marked never. Hours are marked ask." |
| 0:18 | c1 | type "Can I drop my 5-unit GE and go from 17 to 12 units?", verdict card CONVERGED | "The advocate picks the offices from what each box says it covers, shares the minimum, asks all four at once. Every claim cites a rule. Twelve units: everyone agrees. Converged." |
| 0:30 | p1 | type the "my college adviser approved 10 units" question, CONVERGED with override | "Here the college says yes and ISO says no. Nobody voted. Federal immigration rules outrank campus rules, so the answer is no, and the override is written down, with who overrode whom." |
| 0:42 | a1 then approve | "second on-campus job" question, ASK_STUDENT, click share hours with ISO, re-ask, CONVERGED | "ISO needs my hours. It didn't get them. I approve, once, for ISO only. Now it can answer: ten more hours keeps me under the cap." |
| 0:54 | d1 | CMPM 120 question, ASK (hours for the college), press "Yes, share all and ask again", DISPUTED | "Two advisers, same authority, opposite advice: CMPM says add it now, it runs once a year; the college says not at 22 units with a job. The system keeps the disagreement instead of flipping a coin: both positions, what would settle it, and that I decide." (If the live run lands CONVERGED with a precedence line instead, say that: "this time a rule outranked the advice, and it says which.") |
| 1:00 | demo word | type "demo: Should I add CMPM 120 now and go to 22 units, or wait until next year?" and let the room fill: round 1 positions, an office joining, hold/revise badges, then the verdict | "Say demo and they argue in the open. Each office answers from its own box, an office can call in another office its rules name, and when two of them differ they hear each other once. What crosses is cited policy, never my fields. If they still disagree, that stays on the record." |
| 1:04 | e2 | My Cubby: click days_to_deadline, set 2, back to chat, re-ask c1, ESCALATED | "Same question, new information: the deadline is in two days. A trigger in code, not the model, escalates it to a human with a brief." |
| 1:14 | bring your own agent | Claude Desktop: ask the gremlin tool the same c1 question; result shows what left the box | "You don't need our chat. Add one MCP URL to your own Claude and it's the same gremlin, the same wall." |
| 1:22 | SLIM | terminal: demo.py with the SLIM gateway lines, ISO call travelling agent to SLIM to A2A | "Departments are A2A agents. Here ISO is reached over Cisco's SLIM transport; the others run in process. Same contract either way." |
| 1:30 | evidence | eval table from docs/EVAL.md | "Against one big prompt with every box pasted in: we cite, it doesn't; we leak nothing, it leaks everything, including the name." |
| 1:38 | close | README top, repo URL | "Gremlins. Cubbies is the boundary, the gremlins argue inside it. Built on AGNTCY, at UCSC, this weekend." |

Honesty rules for the voiceover: say "in process" if SLIM isn't running; say "synthetic
student"; never say "accepted at NeurIPS" (it is "co-author on a poster at the NeurIPS 2026
AI4GOOD workshop; stale-memory paper under review at NORA 2026").

## The 20-second teaser (/brag, Hyperframes)

Run from the repo root after pushing: `/brag --tone polished --format landscape --title "Gremlins"`
with the direction: "Campus offices give three different answers; the student's gremlin asks
all of them, shares only what the student allowed, and tells you who decides. Show the site
and the verdict badges CONVERGED / DISPUTED / ESCALATED." Hook line if it comes out generic:
"Three offices gave three answers. The gremlins didn't pick one. They told me who decides."
Use the teaser for the devpost header and LinkedIn; the 90-second recording is the demo.
