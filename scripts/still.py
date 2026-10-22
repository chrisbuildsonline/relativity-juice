"""Render 960x540 stills (GPU CUDA if any, else CPU).

No args: the start-of-flight city at beta = 0 -> out/stills/city.png.
Betas after `--` (bun run still:warp): warped city, camera at the point of the
flight path where beta(t) reaches that beta -> out/stills/warp_<beta>.png.
"""
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.city import build_city, setup_view  # noqa: E402
from src.flight import DURATION, camera_y  # noqa: E402
from src.gauge import add_gauge, update_gauge  # noqa: E402
from src.relativity import beta_at  # noqa: E402
from src.warp import add_warp, set_beta  # noqa: E402

OUT = os.path.join(ROOT, "out", "stills")
betas = [float(a) for a in sys.argv[sys.argv.index("--") + 1:]] if "--" in sys.argv else []
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
city = build_city()
setup_view(scene)
if betas:
    add_warp(city, scene.camera)
add_gauge(scene, scene.camera)
bpy.app.handlers.frame_change_pre.clear()  # a render re-fires frame change: keep the beta we set by hand

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "CUDA"
    prefs.get_devices()
    gpus = [d for d in prefs.devices if d.type == "CUDA"]
    for d in prefs.devices:
        d.use = d.type == "CUDA"
    if gpus:
        scene.cycles.device = "GPU"
except Exception as e:  # no CUDA backend in this build/machine
    print("still: no CUDA (%s), using CPU" % e)
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

if not betas:
    scene.render.filepath = os.path.join(OUT, "city.png")
    bpy.ops.render.render(write_still=True)
    print("still: %s device=%s" % (scene.render.filepath, scene.cycles.device))

grid = np.linspace(0.0, DURATION, 15001)
for beta in betas:
    t = float(np.interp(beta, beta_at(grid), grid))
    scene.camera.location.y = camera_y(t)
    set_beta(city, beta)
    update_gauge(beta)
    scene.render.filepath = os.path.join(OUT, "warp_%g.png" % beta)
    bpy.ops.render.render(write_still=True)
    print("still: %s beta=%g t=%.2f y=%.0f device=%s" % (scene.render.filepath, beta, t, scene.camera.location.y, scene.cycles.device))
