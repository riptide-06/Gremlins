# Campus Cubbies visual implementation

Entry point: `src/index.tsx`. Composition: `CampusCubbies`, 2700 frames, 30 fps, 1920×1080. Canonical timing and narration: `script.md`. The previous 60-second version is archived in `versions/60s/`.

## Commands

Run inside `video/`:

```sh
npm install
npm run typecheck
npm run studio
npm run render
npm run still -- out/stills90/05-opening.png --frame=150
npm run still -- out/stills90/60-a2a.png --frame=1800
npm run still -- out/stills90/80-integrations.png --frame=2400
npm run still -- out/stills90/88-closing.png --frame=2640
```

On this Mac the config uses installed Google Chrome. Override with `REMOTION_BROWSER_EXECUTABLE=/absolute/path/to/browser`. On other platforms without that local path, Remotion uses its default browser discovery.

## Integration

`Visuals`, `CampusCubbies`, `Root`, `SCENES`, `FPS`, and `DURATION` are exported. Visuals do not fetch the manifest. `npm run render` produces silent `out/picture.mp4`; `uv run finish.py --video out/picture.mp4` mixes the manifest-timed audio and muxes optional captions into the final `out/campus-cubbies.mp4`.

Scene boundaries: 0 / 240 / 510 / 810 / 1140 / 1560 / 1920 / 2220 / 2520 / 2700 frames, corresponding to 0 / 8 / 17 / 27 / 38 / 52 / 64 / 74 / 84 / 90 seconds. Each Sequence is exactly bounded; transitions animate inside its allotted scene and never alter duration.

Local OFL fonts in `public/fonts/` are loaded with an explicit render barrier. Custom SVG artwork lives in the entry file. The green folder uses `#34a853`, matching the service's `folderColorRgb`. Generated media and render outputs are ignored. Branded creator cards use local Roboto and the official transparent horizontal UCSC–Baskin Engineering lockup on white, at 100px high with 100px minimum clear space. Asset provenance is in `public/brand/README.md`.

## Visual intent

- Student: warm chat, thread rail, message bubble, agent typing indicator, personal planning artifact. Later, source and private plan converge into a compact briefing within the same chat design.
- ISO: cool pane-based workbench, outbound queue, source/delivery pane, moving update, delivered status. A distinct harness design, never a purported live capture.
- A rewinding ruler marks earlier; catch-up reconnects the update and plan. A cubby rotates away while the green Drive folder unfolds and exposes ordinary files.
- Permissions diagram shows a forward contribution route and a blocked reverse path for private notes. The notes feed only the personal agent.
- The approved folder reveal is preserved at 38–52 seconds, with only its chapter number updated.
- The 12-second A2A diagram connects visibly different chat/workbench layouts through A2A 1.0 and an Agent Card to permissioned tools. Discover / Connect / Use tools highlights progress in three stages.
- The 10-second integration map connects campus Google sign-in, UCSC Drive, and BayLeaf Chat to the active service. Three verified-operation chips and the Cloud Run + Firestore infrastructure footnote settle before 80 seconds.
- Opening and ending share legible, textual-only creator credits, Tarun first, with exact supplied names, emails, roles, and school. Official brand colors are navy `#003c6c`, orange `#f29813`, and yellow `#fdc700`; the independent product folder stays green. The closing uses a restrained campus-network pullback, service URL, active-service badge, and the event/Cloud AI track attribution.

## Process feedback

The fixed timeline and visual-only component make parallel audio work safe: no manifest access or shared media writes are needed. Screen copy is deliberately terse so the narration supplies explanation instead of reading a slide. The initial browser download reported success but Remotion could not locate the downloaded executable; installed Chrome rendered successfully, so the local configuration handles that environment issue. Stills are checked at meaningful settled moments; final motion/audio synchronization belongs to the parent render pass.

90-second verification: TypeScript passes. The four new stills listed above were rendered sequentially and visually inspected at full resolution. Creator credits, the official lockup, protocol routing, proof chips, and infrastructure labels are legible without observed clipping. Full motion rendering and audio synchronization are reserved for the parent render pass.
