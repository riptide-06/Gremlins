# Campus Cubbies audio

## Casting

`audition-reel.wav` presents A–D with spoken labels (macOS Samantha). Individual, unlabeled Qwen auditions are in `auditions/`.

- A: Warm peer, American woman, conversational and grounded.
- B: Quiet assurance, American baritone, softly textured.
- C: Bright guide, British alto, thoughtful and precise.
- D: Thoughtful builder, Indian-English man, curious and approachable.

Every candidate reads exactly: “Campus Cubbies brings campus knowledge to your own agent. Ordinary files become useful context, ready when you ask.”

**B remains APPROVED: explicitly selected by the user after auditions.** No recasting. `casting.json` retains exact prompts and seeds. `auditions/requests.json` is the original voice-design request sequence. `raw/requests.json` contains the five new clone requests with B's unchanged reference transcript. `narration-provenance.json` records selected requests, source and reference hashes, and exact-text reuse provenance.

Before modification, all six original delivered/raw takes, music, auditions, ASR and provenance were copied to `video/versions/60s/public/audio`. New scenes 02–05 reuse old scenes 01–04 byte-for-byte, identified by exact narration-text match against the archived manifest. Their raw and trimmed sources are remapped too.

## Integration

`01.wav` through `09.wav` contain narration only. In `../manifest.json`, `audioStartSec` is **ABSOLUTE on the 90-second timeline**, equal to scene start plus 0.35 seconds: 0.35, 8.35, 17.35, 27.35, 38.35, 52.35, 64.35, 74.35, 84.35. This matches deterministic sample placement in `finish.py`. `audioDurationSec` is measured from each delivered WAV. Scene boundaries come directly from the canonical script headings: 0/8/17/27/38/52/64/74/84/90 seconds, 30 fps, 2700 frames. `timing-verification.json` records source durations, tempo adjustment, and remaining tail.

Scene 08 uses same-reference seed 6208 after timing rerolls. A measured sentence pause is shortened by 200 ms (5.9–6.1 seconds in the trimmed source, wholly within silence), retaining about 291 ms of that pause. Pitch-preserving tempo is 1.13544×. The final 08 take is 9.33046 seconds with 0.31954 seconds of scene tail. No spoken content is cut. The processing code asserts that removed samples are below −40 dBFS.

Scene 06 uses seed 6706 and the synthesis-only spelling cue `permission’d` for canonical `permissioned`. Earlier takes lost the final consonant in both Parakeet and Whisper recognition. The selected take recovers `permissioned tools` in independent Parakeet ASR. Canonical manifest/script text remains `permissioned`. Reference B is unchanged.

Scene 06 retains native speech tempo by shortening its 703 ms sentence pause to 323 ms (remove trimmed-source 3.6–3.98 seconds, with the same silence-level assertion). Other than scene 08's documented tempo factor, delivered speech is native-rate.

`music.wav` is the separate 90-second SA3 medium/SAME-L cue. Its saved prompt requests restrained, instrumental, 100 BPM electronic/acoustic texture. Musical fit, realized tempo and absence of wordless vocals still require human listening. `music-provenance.json` contains the complete invocation. `music.headroom.json` records gain applied to the decoded floating-point signal before PCM quantization, preserving the prior clipping fix.

## Reproduction

From repository root: `python3 video/audio_production.py STAGE`. For this approved cast, use `narration`, `finish`, `music`, `asr`, `verify` in that order. `narration` reuses exact-text matches from the immutable 60-second archive and synthesizes changed lines. `finish` rejects any scene needing more than 15% acceleration. The Qwen clone path uses reference audio and reference text, not unsupported clone-time voice-design directions. The archival `auditions` stage is for new casting sessions and must not be rerun for this approved B revision.

Local models: Qwen3-TTS 1.7B Q8 VoiceDesign and Base GGUF through Homebrew audiocpp, Metal backend. SA3 medium MLX with SAME-L, seed 101160, 8 steps, CFG 2. No paid API calls. The `music` stage automatically uses `video/sa3_headroom.py` with SA3's Python environment, applying gain before the upstream PCM writer. The upstream installation is unchanged.

`asr-verification.json` compares independent local Parakeet transcripts to the canonical narration, normalizing letter spacing in UCSC, A two A/A2A, punctuation, BayLeaf/My Cubby spacing, and homophonic Cubby's/Cubbies. Per-token timestamps remain in `asr/`. `technical-verification.json` records measured durations, sample rates, peaks, clipping counts and delivered hashes. `verify` checks frame totals, absolute starts, tails, zero clipped samples and byte-identical reused WAVs.
