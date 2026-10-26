# Official Contest Submission Package (RenderJuice Discord & Devpost Mirror)

## 1. How to Post the Official Entry (Mandatory for Prize Eligibility)
1. Create a free account at `https://app.renderjuice.com`.
2. Join the RenderJuice Discord (`https://discord.gg/FpAEQPpKvv`), open `#start-here`, click **Join contest**, and submit the email address attached to your RenderJuice account.
3. Optional (unlocks **Best RenderJuice Promo** $100 track): Upload `out/neon-racer.blend` (generated via `bun run blend`) to `https://app.renderjuice.com` and render a frame batch on RenderJuice Cloud.
4. Before **October 31, 2026 at 23:59 UTC**, post the following in `#contest-submissions` (and optionally mirror on Devpost):
   - Attach or link `media/relativity-juice.mp4`
   - Attach `media/wip.png` (Blender 4.5 GUI work-in-progress screenshot)
   - Paste the submission text below.

---

## 2. Copy-Paste Text for `#contest-submissions`

**Title:** Relativity Juice: Neon Racer (Procedural 70s/80s Synthwave Supercar & 124 BPM Soundtrack in Blender Python + Geometry Nodes)

**Entrant / Team Name:** Chris

**Interpretation of Speed (What It Is):**
Speed is felt through relative motion, camera choreography, and rhythm. In this 15-second procedural Blender animation (19.5 seconds with Blender-rendered title and end cards), a 1970s/80s wedge supercar (`HeroRacer`, metallic gunmetal with cyan neon piping) launches from 85 KM/H to 420 KM/H (`0.1c to 0.999c` on the in-camera 3D telemetry gauge) down a wet-mirror neon highway flanked by wireframe mountains and overhead speed-gantries. Across four beat-synced native Blender camera cuts (low wheel launch cam, sweeping helicopter orbit cam, front-3/4 door-to-door overtake cam, and wide-FOV hyper-boost chase cam), the hero racer carves glowing cyan plasma light-ribbons, drafts and overtakes a crimson rival interceptor (`RivalRacer`), and triggers a frame-253 supersonic shockwave ring as the camera lens widens from 35 mm to 20 mm into a segmented OutRun sunset sun.

**Workflow Notes (Best Procedural & Programmatic Animation / Best Motion Design / Best Simulation & FX):**
Nothing is hand-modelled, hand-keyed, or hand-painted. Running `bun run racer` and `bun run media:racer` (or `bun run blend` to produce `out/neon-racer.blend`) builds the entire scene from Python (`src/racer.py`, `src/synthwave.py`):
- **Procedural Wedge Supercars & Wheel Rigs (`src/racer.py`):** Both 70s wedge supercars (`HeroRacer` and `RivalRacer`) are generated from procedural quad profiles with metallic clearcoat `Principled BSDF` paint, tinted canopy glass, emissive neon edge piping, 5 rear window louvers, rear spoilers, full-width 80s grid lightbars, dual plasma thrusters, and 4 child wheel objects per car. Wheel rotation (`rotation_euler.x = -distance / radius`) and lateral S-curve chassis roll/pitch banking are keyframed mathematically on Blender F-curves at every frame with Cycles 3D motion blur (`shutter = 0.35`).
- **Geometry Nodes Modifiers (`HighwayNodes` & `TrailNodes`):** Two `GeometryNodeTree` modifiers are constructed node-by-node in Python: `HighwayNodes` pulses the flanking wireframe mountain ridges and overhead speed-gantries at 124 BPM, while `TrailNodes` ripples and flares the twin Tron-style plasma light-ribbons streaming behind both cars' dual exhausts, paired with an expanding `BoostShockwave` ring at frame 253.
- **Native Multi-Camera Timeline Editing & In-Camera 3D HUD:** Four Blender cameras (`CamLaunch`, `CamHeli`, `CamOvertake`, `CamBoost`) are placed on `scene.timeline_markers` at frames `1, 85, 169, 253` with shutter-safe guard keyframes. The 3D telemetry HUD (`RacerHUD_Rig` + `GaugeText`) is parented directly to the camera in 3D space so every pixel renders natively inside Blender Cycles with zero post-composited `ffmpeg` overlays.
- **Programmatic 124 BPM Stereo 90s Synthwave Soundtrack (`src/synthwave.py`):** Synthesized in pure Python at 48 kHz stereo (analog pitch-swept kick, gated-reverb snare, 16th-note hi-hats, stereo Simmons tom fills synced to the 3 camera cuts at `3.5 s, 7.0 s, 10.5 s`, sidechained 16th-note sawtooth arp bass over `Am - F - C - G`, stereo chorus polysynth pads, dotted-eighth delayed lead melody, and a speed-synced turbo plasma whine).

**Assets and AI Disclosure:**
- **Third-Party Assets:** None. Zero external 3D models, textures, HDRIs, audio files, or music samples are used. Every mesh, shader, Geometry Nodes tree, animation curve, and the entire stereo 90s Synthwave soundtrack are generated programmatically by our Python scripts. The only font used is Blender's built-in font (`<builtin>`).
- **AI Disclosure:** No AI-generated images, 3D meshes, or video frames are used; every pixel is rendered by Blender 4.5 LTS (Cycles). The Python scripts, tests, and documentation were written with the assistance of an AI coding assistant (Claude).
