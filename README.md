# relativity-juice

A fully algorithmic, 15-second procedural animation of a cyberpunk megacity undergoing extreme relativistic Doppler beaming and Lorentz contraction as the camera accelerates to 0.999c, generated entirely via a headless Blender Python script and RenderJuice cloud batch rendering.

Built for [RenderJuice Blender Animation & Programmatic Rendering Contest](https://programmatic-rendering-contest.devpost.com/). Submissions close 2026-10-31.

## What it does

A fully algorithmic, 15-second procedural animation of a cyberpunk megacity undergoing extreme relativistic Doppler beaming and Lorentz contraction as the camera accelerates to 0.999c, generated entirely via a headless Blender Python script and RenderJuice cloud batch rendering.

## Stack

Blender 4.2+, Python (bpy), Geometry Nodes, NumPy (special relativity tensor transform math), RenderJuice Cloud REST API

## Run it

```
bun install            # pyright for the typecheck
bun run test           # unittest suite inside headless Blender
bun run typecheck      # pyright over src/ scripts/ tests/
bun run smoke          # 64x36 Cycles CPU render to out/smoke/smoke.png, fails if flat
```

Blender is found via the `BLENDER` env var, then `~/opt/blender/blender`, then `blender` on PATH (see `bin/blender`). Tested with Blender 4.5 LTS.

## License

MIT, see LICENSE.
