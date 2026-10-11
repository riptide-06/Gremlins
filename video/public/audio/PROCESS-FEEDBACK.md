# PROCESS FEEDBACK

The notes below document the original 60-second production, preserved with its assets under `video/versions/60s/public/audio`. Current 90-second results are in `README.md`, `asr-verification.json`, `timing-verification.json`, and `technical-verification.json`.

## 90-second revision

- Exact-text matching against the archived manifest preserves approved 01–04 as new 02–05 without another decode or normalization pass.
- Parse timings from script headings. Keep absolute audio offsets explicit and derive total frames instead of duplicating duration constants.
- New scene 08's original seed 6108 exceeded the 15% tempo ceiling. Seeds 6208–6808 were tried with the unchanged approved B reference. Seed 6208 retained the full text; shortening one silent sentence gap by 200 ms allowed a 1.13544× pitch-preserving tempo factor.
- Scene 06 needed a pronunciation repair: Parakeet and an independent local Whisper-small.en run both heard `permission tools`. Several unchanged-text rerolls did the same. Seed 6706 with synthesis-only spelling `permission’d` recovered canonical `permissioned tools` in Parakeet. The request provenance records the spelling cue; the script and manifest retain canonical wording.
- SA3's new 90-second decode peaked at 1.30962 before quantization. The existing wrapper applied gain 0.610864 first; delivered music peaks at 0.799957 with zero clipped samples.

## Original 60-second production

- Current Homebrew `audiocpp` accepted the established Qwen request-sequence format directly. Four 6.5–7.7-second voice auditions rendered in about 13 seconds of request time, with one model load. Use absolute reference paths and exact reference text for clone ICL.
- Qwen weights were located in `~/Code/bbb-artifact-tour/audio.cpp/models`, not a global audio cache. Their exact SHA-256 hashes and build identity are saved in `model-provenance.json`.
- SA3's installed medium weights were missing despite the older skill inventory. The CLI downloaded them successfully. A warm rerender took 6.23 seconds for 60 seconds of stereo audio.
- The upstream SA3 writer hard-clips floating samples above unity. First render had peak 1.304 and 286 full-scale samples. `video/sa3_headroom.py` injects a pre-quantization gain wrapper and regenerates the same seed, preserving waveform shape without changing the installed engine. Delivered music peak target is 0.8.
- Explicitly pin whether `audioStartSec` is absolute or scene-relative. The initial interpretation was scene-relative; the parent clarified the final mixer's absolute convention, now documented and asserted.
- Four-way auditions were delivered before final cast selection. A kept production moving provisionally; the user's explicit B selection triggered complete regeneration and reference-hash updates.
- Local Parakeet is used to check intelligible narration against the script. Musical taste, realized tempo, and absence of wordless vocals are listening judgments, not established by ASR or waveform statistics.
- Final B scene 05 seed 5105 was recognized as “A two way”; rerendering the exact canonical text with seed 5205 yielded “A 2A”. The final request sequence and production script both retain seed 5205. All six final B transcripts match canonical narration aside from casing, punctuation, whitespace and acronym normalization.
- Final verification passed: six scene WAVs fit their fixed slots with zero time stretching and at least 1.786 seconds of tail, music is exactly 60 seconds at stereo 44.1 kHz, and delivered narration/music have zero clipped PCM samples. Detailed durations, hashes and PCM statistics are in `technical-verification.json` and `timing-verification.json`.
- Generation logging belongs in files: verbose Metal shader compilation can flood context. The odometer checkpoint was predominantly cached-input usage.
