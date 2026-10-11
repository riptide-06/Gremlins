# Campus Cubbies: ninety-second film

Creator presentation for the Cloud AI track of SF Tech Week Hackathon @ UCSC SVC,
featuring an illustrative ISO-to-student story and active campus integrations. Canonical narration
and shot order are in `script.md`; implementation evidence is in `EVIDENCE.md`.

## Build with restored audio

Restore the approved audio using [RELEASE.md](RELEASE.md), or regenerate it below.
Then, from this directory:

```sh
npm ci
npm run render
uv run finish.py --video out/picture.mp4
```

The visual composition is exactly 2,700 frames at 30 fps, 1920×1080.
The finishing script checks narration against scene boundaries, normalizes
voice takes, ducks instrumental music under speech, and creates a ninety-second
MP4 with a selectable English subtitle track plus a separate SRT.
Subtitle phrase timing is estimated proportionally within measured takes.

## Outputs

- `out/campus-cubbies.mp4`: film with narration, music, selectable subtitles.
- `out/campus-cubbies.srt`: separate captions.
- `out/picture.mp4`: animation without soundtrack.
- `out/soundtrack.wav`: mixed soundtrack.
- `public/manifest.json`: measured audio timing and scene manifest.
- `versions/60s/`: preserved first cut and its source snapshot.

Generated media and dependencies stay local. Keep audio provenance and casting
notes with the source to support revisions.

## Fresh-checkout audio regeneration

Run this in a fresh checkout or a separate copy: generation replaces files in
`public/audio/`, and `finish` updates `public/manifest.json`. These commands are
not needed to play the approved film. Git carries recipes, not model weights or
the ignored `versions/60s/` archive.

External prerequisites:

- Apple Silicon macOS, Python 3, Node/npm, `uv`, and FFmpeg on `PATH`.
- Installed `audiocpp` with Qwen3-TTS Metal support, including its `vdes`, `tts`,
  and `--request-sequence` interfaces.
- Both `Qwen3-TTS-12Hz-1.7B-VoiceDesign-GGUF` and
  `Qwen3-TTS-12Hz-1.7B-Base-GGUF` directories in the model parent below,
  with their required tokenizer/codec assets.
- Installed Stable Audio 3 MLX, its Python environment, and medium/SAME-L plus
  text-encoder weights. Follow that installation's download/auth instructions.
  The headroom wrapper uses its `scripts/sa3_mlx.py`, `save_wav`, and `np` APIs.

Defaults and overrides (paths may be outside this repository):

```sh
export AUDIOCPP_MODELS="$HOME/Code/bbb-artifact-tour/audio.cpp/models"
export SA3_ROOT="$HOME/Code/sa3/stable-audio-3/optimized/mlx"
export SA3_PYTHON="$SA3_ROOT/.venv/bin/python"
command -v audiocpp ffmpeg uv
"$SA3_PYTHON" -c 'import mlx.core, numpy'
```

These are the default locations if unset. Equivalent stage options are
`--models PATH`, `--sa3-root PATH`, and `--sa3-python PATH`.
From `video/` in the fresh checkout:

```sh
python3 audio_production.py narration --no-reuse
python3 audio_production.py finish
python3 audio_production.py music
python3 audio_production.py verify
python3 audio_production.py asr
npm ci
npm run render
uv run finish.py --video out/picture.mp4
```

`narration` recreates only the B reference when missing, using the recorded design,
transcript, and seed. Casting stays **APPROVED B**, even without `casting.json`;
this records the original casting decision, not approval of newly generated takes.
The audition reel is optional and verification does not require it. To recreate
all four auditions and the reel separately, run `auditions` then `reel` (the
reel also requires macOS `say` with Samantha).

Without `--no-reuse`, narration optionally reuses exact-text takes from
`versions/60s/public/` if the manifest, timing report, delivered WAV, raw WAV,
and trimmed WAV are all present. Missing archive assets fall back to synthesis.
`finish` follows the reuse decisions recorded by `narration`.

Seeds do not promise identical samples across model/runtime versions. No old
selected-take pause cuts are applied to new speech. If a take needs more than
1.15× tempo to fit, finishing stops with the scene number: select a new seed in
`SELECTED_SEEDS` and rerun narration and finish, or deliberately revise the
script/timing. Listen to every regenerated take and inspect the ASR differences
in `public/audio/asr-verification.json` before approving. ASR uses local
Parakeet MLX via `uvx` and may download its package/weights; it reports differences
rather than approving them automatically.

## Optional exact-audio restoration

To retain the approved takes rather than resynthesize them, use the release
download, checksum verification, and extraction commands in [RELEASE.md](RELEASE.md).
That bundle restores the audio consumed by the committed timing manifest,
including the B reference. Keep the matching committed manifest and do not run
`narration`, audio `finish`, or `music` after restoration. The ignored 60-second
archive is not required. Exact final encoded video bytes still depend on the
browser and FFmpeg versions; retain the release MP4 when byte identity matters.

## Story boundaries

The international office initiates an update. The student asks their agent later,
before enrolling. The agent catches up then: no continuously running agent or
automatic legal interpretation is implied. The policy itself is fictional.
The ordinary Drive folder is the central reveal, not a fabricated product UI.

The new A2A sequence shows how distinct harnesses use a shared agent interface.
The integration sequence reflects production-status commit `7a5f9c2` and recorded
live verification of sign-in, Drive operations, and authenticated A2A calls.
It does not represent the illustrative ISO workflow as an observed deployment.

Event: https://events.ucsc.edu/event/sf-tech-week-hackathon-ucsc-svc/
