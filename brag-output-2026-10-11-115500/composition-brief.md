# Hyperframes Composition Brief: Gremlins

## Objective
Create a short launch-style brag video for Gremlins, the student's own advocate agent for campus bureaucracy built on Campus Cubbies (UCSC), for the hack.dev UCSC AI Hackathon (Cisco Outshift / AGNTCY track, Level 3 "When AI Agents Disagree").

## Output
- Composition directory: `brag-output-2026-10-11-115500/composition/`
- Rendered video: `brag-output-2026-10-11-115500/brag.mp4`
- Format: portrait — 1080x1920
- Duration: 25.0 seconds

## Source Material
- Project root: `~/Documents/Hack.Dev/Gremlins`
- Primary files read: `site.html` (palette, fonts, card/chip/verdict styles, the gremlin SVG), `README.md`, `docs/VIDEO.md`, `docs/EVAL.md`, the live judge-mode app at `http://127.0.0.1:8080/demo?token=judge`
- Product name: Gremlins (site wordmark "gremlin labs · by bayleaf · built on Campus Cubbies")
- Tagline / strongest claim: "Three offices, three answers? Your gremlin asks all of them, keeps the receipts, and tells you who actually decides."
- Key UI or visual moments to show (real screenshots in `assets/shots/`, captured from the running app in judge mode, synthetic student): the CONVERGED card with cites, the My Cubby permissions grid, the ASKING YOU FIRST card and its one-click approve button, the "Precedence applied" card, the DISPUTED card, the `demo:` deliberation room, the ESCALATED card and brief page, the Bring your own agent page.
- Copy that must appear verbatim:
  - "Three offices. Three answers. Who's actually right?"
  - "Gremlins asks all of them. At once. With receipts."
  - "ISO wins by authority_order (federal) over COLLEGE" (from the real card)
  - "Cubbies is the boundary. The gremlins argue inside it."
  - "Built on AGNTCY + Campus Cubbies, UCSC, one weekend."
  - "github.com/riptide-06/Gremlins"
  - "synthetic student" and "prototype" on every product-shot scene; "Campus Cubbies, an A2A service by Adam Smith"; "one department reachable over Cisco SLIM"

## Creative Direction
- Tone preset: polished
- Creative direction: hype but earned; fast cuts, punchy text, strong contrast, the app's orange/green/cream palette, the gremlin mascot as the recurring character
- Interpretation: polished typography discipline (Sora, mixed case, one accent, nothing flashed), hype pacing (0.3s pushes on the 120 BPM grid, slams on beats, full-saturation orange hits)
- Angle: see `brag-plan.md` — the student who has been told three different things; Gremlins asks all of them at once, keeps receipts, applies precedence in code, keeps disagreements as disagreements, hands the student the decision. Every claim is shown by the real product doing it.
- Hook: "Three offices. Three answers." / "Who's actually right?" on a beatless intro; the first downbeat lands the wordmark.
- Outro / punchline: "Cubbies is the boundary. The gremlins argue inside it."
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals, stock footage, fake UI, invented stats
  - Unrelated visual redesign
  - Claims the honesty rules forbid: "official UCSC", any real student's data, BayLeaf or any other chat being integrated, AI voices as real people, SLIM beyond "one department reachable over Cisco SLIM"

## Visual Identity
- Background: #EEEFE9 (panels #F7F7F2, cards #FFFFFF)
- Text: #151515 (muted #5A5A55)
- Accent: #F54E00 orange; supporting #F7A501 yellow, #B9E5A6 green, #1D4AFF blue, #E8B86D cubby wood
- Display font: Sora 800/600 (local `assets/fonts/Sora.ttf`, variable)
- Body font: Sora 400; JetBrains Mono 400/600 for chips, cites, field names (local `assets/fonts/JetBrainsMono.ttf`)
- Visual references from the project: 1.5px ink borders with 3px offset solid shadow (cards, chips, user pill), rounded verdict pills (CONVERGED green, DISPUTED yellow, ESCALATED orange-tinted, ASKING YOU FIRST sky), mono cite chips `[F-01]`, the gremlin-on-cubby SVG (`assets/mascot.svg`), the orange hand-drawn underline stroke under "cubby" on the sign-in page.

## Storyboard
Use the storyboard in `brag-output-2026-10-11-115500/brag-plan.md` (portrait deltas) over `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 2.52s — "Three offices. Three answers." then "Who's actually right?"
2. Reveal — 3.0s — gremlin SVG, wordmark on the 3.02 downbeat, "asks all of them. At once. With receipts."
3. One question, every office — 2.5s — real CONVERGED card, four office chips on beats, cite chips, "Uncited claims get deleted by code."
4. Your data stays yours — 3.0s — real permissions grid, real ASKING YOU FIRST card, cursor click on "Yes, share hours with ISO", swap to the real answered card
5. When they disagree — 2.5s — real "Precedence applied" card with highlight sweep, real DISPUTED card
6. Watch them argue, live — 2.5s — real deliberation room wiped in top to bottom, HOLD / REVISE / AGREE badges on beats
7. A human when it matters — 2.5s — real ESCALATED card slammed on the 16.02 cue, real brief page behind it
8. Bring your own agent — 2.0s — real page pushed in on the 18.52 cue, A2A / SLIM / MCP chips
9. The numbers — 2.0s — 9 of 10 vs 2 of 10, 0 vs 120 protected fields, 152 tests, counting as a chord
10. End card — 2.5s — wordmark, "Cubbies is the boundary. The gremlins argue inside it." on the 23.02 cue, links, credit line

## Audio
- Audio role: dense but clean rhythmic layer
- Audio arc: beatless hook, downbeat on the wordmark, pushes and chip arrivals on the grid, two bell hits (numbers, end line), fade under the links
- Music: `assets/music/happy-beats-business-moves-vol-1-by-ende-dot-app.mp3`
- Music treatment: 0.36 from 0; duck to 0.26 for the numbers scene; fade to 0 over the final 0.9s
- Music cue guidance: `assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json` (120.19 BPM, grid 3.02 + 0.5k). Lock 16.02, 18.52, 23.02. Scene cuts on 2.52, 5.52, 8.02, 11.02, 13.52, 16.02, 18.52, 20.52, 22.52. Sequential text no faster than every other beat; non-text accents may take every beat.
- Audio-reactive treatment: subtle; `assets/audio-data-25s.json` (30 fps, rms + 8 bands, first 25.2s) drives the scale of the orange radial glow behind product shots (bass, 8 to 14 percent swing) and a 3 percent breathe on the verdict pill; nothing on body text; no waveform or equalizer visuals.
- Audio-coupled moments:
  - Scene 1 — two soft impacts on the text slams
  - Scene 2 — wordmark beat-locked at 3.02
  - Scene 3 — card-slide per office chip (5.52, 6.02, 6.52, 7.02), drop per cite chip (7.52, 8.02)
  - Scene 4 — click_003 at the cursor press, soft impact on the card swap
  - Scene 6 — drop per stance badge (14.02, 14.52, 15.02)
  - Scene 7 — soft impact beat-locked at 16.02
  - Scene 8 — soft impact beat-locked at 18.52, drops on the three chips
  - Scene 9 — chips-stack ticks under the count, bell when the counters land (21.52)
  - Scene 10 — bell under the end line at 23.02
- SFX selection guidance: low high-frequency-risk picks only (`impactSoft_medium_001/004`, `drop_001/002`, `click_003`, `card-slide-1`, `bong_001`, `impactBell_heavy_000/003`), SFX fire at the start of the matching motion, never on body captions, never more than one per 0.4s outside the hook.
- SFX analysis guidance: `~/.claude/plugins/cache/brag/brag/0.2.2/skills/brag/assets/sfx/sfx-analysis.md`
- Exact SFX choice: Hyperframes chooses filenames, timestamps, density, and volume based on the implemented animation; the files staged in `assets/sfx/` are the candidate set.
- Audio files: already copied into `brag-output-2026-10-11-115500/composition/assets/` (music, cue preset, SFX, extracted audio data)

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core`, `hyperframes-animation`, `hyperframes-creative`, `hyperframes-keyframes`, `hyperframes-cli`. /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project (every product scene uses a real screenshot from `assets/shots/`).
- Keep all text readable in the final render (reading floors in the plan).
- Keep the video within 15-25 seconds.
- Include the planned music/SFX layer.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints; ignore cues that hurt readability, scene pacing, or the product story.
- Major reveals may move toward nearby strong cues within about 0.15s; smaller entrances within about 0.10s of a beat; 1-3 strong cue locks.
- Audio-reactive: pre-extracted data in `assets/audio-data-25s.json`, sampled per frame with `tl.call`, subtle, brand-specific motion only.
- Use local assets for audio, fonts, and screenshots (no network at render).
- Run `hyperframes check` before render — it is brag's single gate.
