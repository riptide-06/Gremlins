# Video release assets

The `campus-cubbies-video-v1` GitHub release publishes:

- `campus-cubbies.mp4`: the approved 90-second, 1080p film.
- `campus-cubbies.srt`: optional captions (phrase timing estimates).
- `campus-cubbies-audio.tar.gz`: approved narration, music, and B voice reference.
- `SHA256SUMS`: checksums for those assets.

Generated media are release assets, not Git objects. Source, dependency locks,
small licensed font/logo assets, script, timing manifest, and provenance live in
Git. The audio bundle restores the approved cut without rerunning inference.

## Restore approved audio and render

From the repository root, with GitHub CLI, Node/npm, uv, and FFmpeg installed:

```sh
gh release download campus-cubbies-video-v1 --repo riptide-06/Gremlins \
  --pattern 'campus-cubbies-audio.tar.gz' --pattern SHA256SUMS --dir video/out
cd video/out
shasum -a 256 --ignore-missing -c SHA256SUMS
cd ../..
tar -xzf video/out/campus-cubbies-audio.tar.gz -C video
cd video
npm ci
npm run render
uv run finish.py --video out/picture.mp4
uv run check.py
```

The archive contains only paths under `public/audio/`. It supplies all audio
consumed by the committed manifest. Visual output and mixing are deterministic
given the same inputs and software environment; encoded bytes may differ across
browser/FFmpeg versions. Audio regeneration uses the recorded model recipes and
seeds, but exact regenerated samples are not guaranteed.
