# relativity-juice

A 15-second procedural Blender animation: a cyberpunk megacity seen from a camera that accelerates from 0.1c to 0.999c, with the real special-relativity effects applied to what the camera sees. Entry for the [RenderJuice Blender Animation & Programmatic Rendering Contest](https://programmatic-rendering-contest.devpost.com/), theme "Speed".

[Watch the video (media/relativity-juice.mp4)](media/relativity-juice.mp4)

| cruise, frame 48 | build, frame 150 |
| --- | --- |
| ![cruise](media/beat_cruise.png) | ![build](media/beat_build.png) |
| **blueshift, frame 220** | **singularity, frame 340** |
| ![blueshift](media/beat_blueshift.png) | ![singularity](media/beat_singularity.png) |

Every 30th frame of the final render:

![contact sheet](media/contact.png)

Blender with the scene open at frame 220:

![Blender work in progress](media/wip.png)

## What it is

Our reading of "Speed": speed is not only how fast something moves, it changes what you see. Near the speed of light a road ahead does not just rush past. Light from the world gets bent toward the direction of travel, forward windows shift to blue and then to ultraviolet, the rear world shifts to red and dies away, and the whole view collapses into a bright ring ahead. The animation lets you watch that happen as the speed climbs: calm at 0.1c, a visible bend by 0.5c, a tunnel by 0.9c, and a near-singularity at 0.999c. A gauge in the corner shows the current β and γ.

The city is a static neon canyon. Only the camera moves. The strange look is computed, not painted: the script moves every vertex of the city to where the camera would see it, and colours it by its Doppler shift.

Light is deliberately slow in the scene (C = 120 units per second) so a 15-second flight covers about 1400 units of city and the buildings stay readable instead of flashing by.

## The physics

All of it is in `src/relativity.py` (NumPy, no Blender) and mirrored in the Geometry Nodes modifier in `src/warp.py`. Tests check the node tree against the NumPy functions.

Setup: the camera moves along +Y at speed β = v/c. Everything else is at rest in the "city frame". θ is the angle between the direction to a point and +Y, measured in the city frame.

- Lorentz factor: γ = 1 / √(1 − β²). At 0.999c, γ ≈ 22.4.
- Slow light: the scene speed of light is C = 120 units per second (`src/flight.py`), far slower than real life, so the 15 s flight covers about 1400 units.
- Speed curve (`beta_at`): the rapidity φ = atanh(β) is interpolated from atanh(0.1) to atanh(0.999) with a smoothstep over 15 s, then β = tanh(φ). Slow start, steady build, flat finish, and γ grows through the whole clip. The camera path is the integral of β·C over time (`camera_y`).
- Aberration: the apparent direction of a point is cos θ' = (cos θ + β) / (1 + β cos θ), and the part of the direction perpendicular to Y is scaled by 1 / (γ(1 + β cos θ)). Directions along ±Y do not move. As β rises, everything crowds toward the forward point.
- Doppler factor: D = γ(1 + β cos θ), with θ the city-frame angle above. In terms of the observed angle it is D = 1 / (γ(1 − β cos θ')). Observed wavelength is λ_obs = λ_rest / D. Dead ahead at 0.999c, D ≈ 45. Dead behind, D ≈ 0.022.
- Colour: visible wavelengths use a Bruton-style wavelength to RGB mapping. Below 380 nm (ultraviolet) the colour blends to a saturated violet-blue tinted by the source's rest colour, so windows of different colours stay distinguishable. Above 780 nm (infrared) the colour fades to black by 1000 nm.
- Beaming: true relativistic beaming scales intensity as D⁴. Applied as is, it blows the frame out to white. The brightness shown is a display tone-map, min(D², 2), applied to camera rays only, so light bouncing off walls stays at its rest brightness. It is a choice to keep the picture readable, not the physical intensity.
- What the code does to the geometry: each vertex is moved along its new direction at the same distance from the camera (the warp changes direction, not range). Because the city is static, city-frame directions plus aberration give the exact visual for a point source. Lorentz contraction is not modelled as a separate step. What you see of it is the aberration: straight edges bend into curves and the scene stretches out and is pulled toward the forward point. Surfaces are subdivided (max edge 4 units) so the per-vertex warp bends them smoothly, but they are still meshes, so very long faces are approximated.

## How to run

Needs Blender 4.5 LTS, Python 3 and `ffmpeg`. The tests and the Blender scripts run inside Blender's own Python, so no pip packages are needed.

```
bun install            # pyright for the typecheck
bun run test           # unittest suite inside headless Blender
bun run typecheck      # pyright over src/ scripts/ tests/
bun run smoke          # 64x36 Cycles CPU render to out/smoke/smoke.png, fails if flat
bun run preview        # CPU only: every 15th frame at 480x270 to out/preview.mp4
bun run render         # the full render, detached: frames to out/frames, log out/render.log, pid out/render.pid
bun run render:status  # frames done, whether the render is alive, last log line, eta
bun run render:wait    # block until 360/360 frames or the render process ends (--max-min N to give up)
bun run encode         # out/frames to out/relativity-juice.mp4 (H.264, 1920x1080, 24 fps)
bun run media          # out/frames to media/relativity-juice.mp4, media/contact.png, and copies the beat stills
bun run wip            # Blender GUI screenshot of the scene to media/wip.png
```

`bun run render` is resumable: it skips frames that already exist, so run it again to continue after an interruption. A frame only gets its `.png` name once it is finished. `bun run media` refuses to run until all 360 frames exist.

Extra stills: `bun run still`, `still:warp`, `still:gauge` and `still:beats` render single frames to `out/stills/`.

Blender is found via the `BLENDER` env var, then `~/opt/blender/blender`, then `blender` on PATH (see `bin/blender`). ffmpeg and ffprobe are found via `FFMPEG` / `FFPROBE`, then `~/.local/bin`, then PATH (see `src/encode.py`). `bun run wip` uses your display if there is one, and otherwise runs Blender under `xvfb-run`.

## Workflow notes

Nothing is hand-modelled, hand-keyed or hand-painted. One script builds the whole scene each time, and the same code builds it for rendering, stills, tests and the screenshot (`build_scene` in `src/render.py`).

What the script controls:

- The city (`src/city.py`): a seeded random generator (seed 7) lays out buildings, windows, neon strips, street lines and the ground as one mesh. Each vertex carries a rest wavelength and an emission value as attributes.
- The warp (`src/warp.py`): a Geometry Nodes modifier, built node by node from Python, moves every vertex by the aberration formula and stores the Doppler factor per vertex. It reads the camera's position live.
- The speed: β is keyframed on the modifier at every frame from `beta_at`, and the camera's Y position is keyframed at every frame from the integral of β·C. Interpolation is linear between frames.
- The shader (`src/city.py`): a node material divides the rest wavelength by D, turns it into a colour, applies the UV tint and IR fade, and applies the display beaming to camera rays only.
- The gauge (`src/gauge.py`): a text object, a bar and a black plate parented to the camera. A `frame_change_pre` handler writes the current β and γ into the text and scales the bar every frame.
- The camera: a path along +Y at a fixed height, set from the flight code. Motion blur is on with shutter 0.3.
- Render settings: Cycles, 1920x1080, 48 samples, denoising, AgX view transform, near-black world, 24 fps, frames 1 to 360.

## How it was rendered

Locally, on one RTX 3090 with Cycles on CUDA. 1920x1080, 24 fps, 360 frames (15 s), 48 samples, denoised, motion blur with a 0.3 shutter. About 25 to 33 seconds per frame, 3 hours for the whole clip. It was not rendered on the RenderJuice cloud. The frames were encoded to H.264 with ffmpeg (`bun run media`).

## Assets and AI disclosure

- There are no third-party assets: no models, textures, HDRIs, music or sound. The video has no audio.
- The only font is Blender's bundled font, the default for text objects, used for the gauge.
- No AI-generated images or video. Every pixel comes from the procedural script rendered by Cycles.
- The code, tests and this README were written with the help of an AI coding assistant (Claude). The physics follows standard special relativity.
- Tools: Blender 4.5 LTS (Cycles, Geometry Nodes), Python with NumPy (Blender's own), ffmpeg, Bun and pyright for the dev scripts.

## License

MIT, see LICENSE.
