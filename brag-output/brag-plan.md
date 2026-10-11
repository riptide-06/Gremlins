# Brag Plan: Gremlins

## What is this app?
Gremlins is the student's own advocate agent for campus bureaucracy, built on Campus Cubbies (UCSC): one question goes to every office that matters, each office's gremlin answers only from its own policy box and cites every claim, and the student's gremlin shares the minimum, applies precedence in code, and comes back with a verdict and receipts instead of a blended paragraph. Built in one weekend at the hack.dev UCSC AI Hackathon, Cisco Outshift / AGNTCY track, Level 3 "When AI Agents Disagree".

## The angle
Everyone who has been told three different things by three campus offices knows the feeling. Gremlins does not pick one answer; it asks all of them at once, keeps the receipts, applies the rule of precedence in code, keeps real disagreements as disagreements, and hands the student the decision. Every claim in the video is shown by the real product doing it (judge mode, synthetic student Asha Rao), captured from the running app.

## Hook (first 2.5 seconds)
Hard cut, big type on the cream canvas: "Three offices. Three answers." then "Who's actually right?" The music's beatless 3-second intro runs under it; the first downbeat (3.02s) lands the wordmark.

## Key moments (the middle)
- The CONVERGED card for "drop from 17 to 12 units" with four office chips and the cite chips [F-01] [F-13] on it.
- The My Cubby permissions grid (never / ask / yes per office) and the ASKING YOU FIRST card with the one-click "Yes, share hours with ISO" button, with a cursor clicking it.
- The "Precedence applied" card: "ISO wins by authority_order (federal) over COLLEGE", then the DISPUTED card ("Two positions, kept").
- The demo room filling turn by turn with HOLD / REVISE / AGREE stance badges.
- The ESCALATED card and the escalation brief page.
- The Bring your own agent page with the MCP config block.
- The numbers: 9/10 vs 2/10 correct verdicts, 0 vs 120 protected fields leaked, 152 tests.

## Outro / punchline
"Cubbies is the boundary. The gremlins argue inside it." Then "Built on AGNTCY + Campus Cubbies, UCSC, one weekend." and the two links.

## User flow worth showing
Judge link -> chat with the four office chips -> ask -> CONVERGED card with cites -> ASKING YOU FIRST -> approve one field for one office -> answer -> precedence / DISPUTED -> `demo:` deliberation room -> ESCALATED -> Open the brief. Entry, key action (approve a share), result (verdict with receipts).

## Tone
- Preset: polished (the user asked for "hype"; it is not a preset, so polished carries the pacing and typography discipline)
- Creative direction: "hype but earned": fast cuts, punchy text, strong contrast, the app's orange/green/cream palette, the gremlin mascot as the recurring character; every claim backed by a shot of the real product; no stock footage, no fake UI, no invented stats.
- Interpretation: polished's restraint shows in typography (Sora, mixed case, one accent) and in never flashing text; the hype shows in cut speed (0.3s pushes), slams on beats, and full-saturation orange hits. Ten scenes instead of polished's usual three, because the user mandated seven promises plus numbers and an end card.

## Format: landscape — 1920x1080
## Duration: 25.0 seconds (ten scenes; the hard 20-25s ceiling leaves each promise about 2.5s, so every caption is cut to its key phrase)

## Visual identity (from the project)
- Background: #EEEFE9 (site --bg, cream); panels #F7F7F2; cards #FFFFFF
- Accent: #F54E00 (site --orange); secondary #F7A501 (yellow), #B9E5A6 (green), #1D4AFF (blue), #E8B86D (cubby wood)
- Text: #151515 (site --ink); muted #5A5A55
- Display font: Sora (site --display), weights 600/800
- Body font: Sora 400; JetBrains Mono for cites, chips, and field names (site --mono)
- Strongest visual element: the hard 1.5px ink borders with 3px offset solid shadows (the site's card style), the verdict pills, the mono cite chips, and the green gremlin on the wooden cubby (site SVG, reused as-is).
- Honesty chrome: a persistent small chip "JUDGE MODE · synthetic student · prototype" on every product-shot scene.

## Share copy (draft)
Introducing Gremlins: ask every campus office at once, get a verdict with receipts, keep your data in your own Drive. Built on AGNTCY + Campus Cubbies at UCSC in one weekend.

## Audio direction
- Role: dense but clean rhythmic layer; the music carries the cut rhythm.
- Music: `happy-beats-business-moves-vol-1-by-ende-dot-app.mp3` (most energetic bundled track, 120 BPM; its beat grid starts at 3.02s, which lines up with the wordmark slam after the beatless hook).
- Music treatment: starts at 0 at 0.36; ducks to 0.26 under the numbers so the bell hits read; fades to 0 over the last 0.9s.
- Music cue guidance: preset `assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json`, tempo 120.19 BPM; beat grid 3.02 + 0.5k. Strong cues to lock: 16.02 (ESCALATED card slam), 18.52 (Bring your own agent push), 23.02 (end line slam). Scene cuts sit on the grid: 2.52, 5.52, 8.02, 11.02, 13.52, 16.02, 18.52, 20.52, 22.52. Sequential text reveals snap to every other beat (1.0s) or hold the full set; non-text accents (cite chips, office chips, stance badges) may take every beat.
- Audio-reactive treatment: subtle; bass (band 0) breathes the orange radial glow behind the product shots and the scale of the verdict pill by 3 to 4 percent; nothing on body text. No waveform or equalizer visuals.
- SFX posture: moderate, motion-matched, low high-frequency risk: `impactSoft_medium_001` on scene pushes and text slams, `card-slide-1` / `drop_001` when office chips and cite chips arrive, `click_003` on the cursor click, `impactBell_heavy_000` when the numbers land, `impactBell_heavy_003` under the end line.
- Audio-coupled moments: hook slams; wordmark on the first downbeat; office chips arriving one by one; cite chips popping; cursor click on "Yes, share hours with ISO"; stance badges appearing in the room; counters landing on 21.02 and 22.02 beats; end line on 23.02.
- Restraint rule: no SFX on body captions; never more than one SFX per 0.4s outside the hook; the bell rings only twice.

## Storyboard

### Scene 1 — Hook — 2.52s (0.00-2.52)
Cream canvas, a faint orange radial glow upper-left and a large ghost "?" at 8 percent lower-right. Line 1 "Three offices. Three answers." slams in (scale 1.4 + blur to settled) at 0.15s, 120px Sora 800, "Three" words in orange. Line 2 "Who's actually right?" snaps in from the left at 1.15s under it. Both hold to the cut. No product shot in the hook; the next scene is the reveal.
Sequential/interaction: yes, two lines, one after the other, each held to the cut (1.0s and 1.3s settled).
Audio intent: dry, percussive, before the beat kicks in.
Audio-coupled idea: one soft impact per slam.
Music: the track's beatless intro.
Transition mood: hard (zoom-through, 0.3s) -> Scene 2

### Scene 2 — Reveal — 3.0s (2.52-5.52)
The site's gremlin-on-cubby SVG pops in at left (spring, no overshoot) at 2.6s; the wordmark "Gremlins" slams in at 3.02s (first downbeat), 150px Sora 800, with the orange underline stroke from the site drawing under it; at 3.6s the line "asks all of them. At once. With receipts." rises in under the wordmark, 56px. Small chip bottom-left: "hack.dev UCSC AI Hackathon · Cisco Outshift / AGNTCY · Level 3". The gremlin's waving arm rocks gently (finite sine).
Sequential/interaction: yes, mascot then wordmark then line (0.5s apart), all held to the cut (line holds 1.9s for 7 words).
Audio intent: the beat drops exactly on the wordmark.
Audio-coupled idea: wordmark beat-locked to 3.02s; the underline draw rides the next beat.
Music: upbeat, first downbeat.
Transition mood: hard (push slide left, 0.3s) -> Scene 3

### Scene 3 — One question, every office — 2.5s (5.52-8.02)
Right 58 percent of frame: the real CONVERGED card screenshot for "Can I drop my 5-unit GE and go from 17 to 12 units?" (c1-thread.png), cropped to the verdict card, framed in the site's ink border with offset shadow, scaled so the verdict pill and cite chips are legible. Over it, four office chips ISO / CMPM / College / FinAid arrive one per beat (5.52, 6.02, 6.52, 7.02) along the top of the card, then the CONVERGED pill pulses once. Left 40 percent: headline "One question. Every office. At once." (72px) at 5.6s; caption at 6.5s: "Uncited claims get deleted by code." (36px, held 1.5s for 6 words). Honesty chip bottom-left: "JUDGE MODE · synthetic student · prototype".
Sequential/interaction: yes, four office chips on consecutive beats (non-text accents), then two cite chips [F-01] [F-13] pop on 7.52 and 8.02 near the card.
Audio intent: things arriving in rhythm.
Audio-coupled idea: card-slide on each chip, drop on each cite chip.
Music: upbeat.
Transition mood: hard (push slide left, 0.3s) -> Scene 4

### Scene 4 — Your data stays yours — 3.0s (8.02-11.02)
Left: the real My Cubby permissions grid screenshot (perm-table.png) with its never / ask / yes cells, sliding in at 8.1s. Right: the real ASKING YOU FIRST card (a1-ask-thread.png) sliding in at 8.6s with the "Yes, share hours with ISO" button. An animated cursor darts to the button at 9.6s and clicks at 10.1s (press dip + one ripple ring); the card is then swapped for the real post-approval CONVERGED card (a1-thread.png) at 10.4s. Headline top: "Your data stays yours." (72px) at 8.1s. Caption at 9.0s: "Name and email never leave. It asks first." (36px, 8 words, held 2.0s). Honesty chip present.
Sequential/interaction: yes, grid then card, then a simulated cursor click that swaps the card to the answered state.
Audio intent: a real click the viewer can feel.
Audio-coupled idea: drop on the grid, card-slide on the card, click_003 exactly at the press, soft impact on the swap.
Music: upbeat.
Transition mood: hard (push slide left, 0.3s) -> Scene 5

### Scene 5 — When they disagree, nobody flips a coin — 2.5s (11.02-13.52)
Left 55 percent: the real "Precedence applied" card (p1-thread.png) cropped to the precedence line "ISO wins by authority_order (federal) over COLLEGE", with an orange highlight sweep drawn under that line at 11.5s. Right 45 percent at 12.3s: the real DISPUTED card (brief-disputed.png, "Two positions, kept") sliding up. Headline "When they disagree, nobody flips a coin." (64px) at 11.1s; caption at 12.0s: "Federal beats campus. The override is written down." (34px, 8 words, held 1.5s). Honesty chip present.
Sequential/interaction: yes, precedence card then the disputed card.
Audio intent: weight, a rule landing.
Audio-coupled idea: soft impact on the precedence card, card-slide on the disputed card.
Music: upbeat.
Transition mood: hard (push slide left, 0.3s) -> Scene 6

### Scene 6 — Watch them argue, live — 2.5s (13.52-16.02)
Full-bleed-ish: the real deliberation room screenshot (room-thread.png) inside the ink frame, revealed by a clip-path wipe from the top over 1.2s so the turns appear to fill in one by one; three small stance badges HOLD / REVISE / AGREE (the site's .stance styling, green and warn backgrounds) pop beside the frame on 14.02, 14.52, 15.02. Headline "Watch them argue. Live." (72px) at 13.6s. Caption at 14.4s: "Type demo: and only cited policy crosses." (34px, 7 words, held 1.6s). Honesty chip present.
Sequential/interaction: yes, the room fills top to bottom; badges on consecutive beats (non-text accents).
Audio intent: a conversation ticking along.
Audio-coupled idea: drop on each badge.
Music: upbeat.
Transition mood: hard (push slide up, 0.3s) -> Scene 7

### Scene 7 — A human when it matters — 2.5s (16.02-18.52)
At the 16.02 strong cue the real ESCALATED card (e2-thread.png) slams in center-left (scale from 1.15); at 17.02 the real brief page (brief.png) slides in behind-right, offset like a second sheet. Headline "A human when it matters." (72px) at 16.1s. Caption at 16.9s: "A trigger in code, not the model." (34px, 7 words, held 1.6s). Honesty chip present.
Sequential/interaction: yes, card then brief page.
Audio intent: a stop, then a hand-off.
Audio-coupled idea: beat-locked slam at 16.02 (soft impact), card-slide for the brief.
Music: strong cue.
Transition mood: hard (push slide left, 0.3s) -> Scene 8

### Scene 8 — Bring your own agent — 2.0s (18.52-20.52)
At the 18.52 strong cue the real Bring your own agent page (byoa.png) pushes in, framed, with the MCP config block region nudged to the center via a slow zoom. Headline "Bring your own agent." (72px) at 18.6s. Caption at 19.2s: "Same gremlin, same wall, over MCP." (34px, 6 words, held 1.3s, minimum floor). Small chip row at 19.6s: "A2A" "SLIM" "MCP" (the site's own chips).
Sequential/interaction: yes, page then three chips on consecutive beats (non-text accents).
Audio intent: open, outward.
Audio-coupled idea: beat-locked push at 18.52; drops on the chips.
Music: strong cue.
Transition mood: hard (zoom-through, 0.3s) -> Scene 9

### Scene 9 — The numbers — 2.0s (20.52-22.52)
Three counters in a row, 150px Sora 800 tabular, counting 0 -> 9 ("of 10 correct verdicts" label, with "vs 2 of 10 for one big prompt" in mono under it), 120 -> 0 ("protected fields leaked", with "vs 120" in mono), 0 -> 152 ("tests"). All three share one power3 ease over 1.0s starting 20.6s so they land together on the 21.52 beat; the suffix labels slide in at 21.6s. Below, one mono line at 21.9s: "integration-tested against Campus Cubbies' own server code". Big orange "9" and green "0" and ink "152".
Sequential/interaction: yes, three counters as a chord, labels after.
Audio intent: the payoff.
Audio-coupled idea: one bell when the counters land (21.52), chips-stack ticks during the count at low volume.
Music: ducked to 0.26.
Transition mood: hard (zoom-through, 0.3s) -> Scene 10

### Scene 10 — End card — 2.5s (22.52-25.02)
Cream canvas, gremlin on the cubby at left (same SVG), wordmark "Gremlins" at 22.6s; at the 23.02 strong cue the line "Cubbies is the boundary. The gremlins argue inside it." slams in (56px, orange "boundary"). At 23.7s two mono chips: "github.com/riptide-06/Gremlins" and "Built on AGNTCY + Campus Cubbies, UCSC, one weekend." At 24.1s a small credit line: "Campus Cubbies is an A2A service by Adam Smith · one department reachable over Cisco SLIM · prototype, synthetic student". The site URL chip reads "ask your team for the judge link" because the public URL is a temporary tunnel. Final scene may fade the glow, nothing else exits.
Sequential/interaction: yes, wordmark, line, chips, credit.
Audio intent: a clean landing and a soft ring-out.
Audio-coupled idea: beat-locked slam at 23.02 with the second bell; music fades over the last 0.9s.
Music: strong cue then fade.
Transition mood: none (final).

**Music mood for this video:** upbeat
**Audio summary:** a beatless two-and-a-half-second hook, the downbeat lands the wordmark, scene pushes ride the 120 BPM grid with soft impacts and card slides, two bell hits (numbers, end line), and a fade under the links.
