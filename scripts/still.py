"""Render the start-of-flight city view at 960x540 to out/stills/city.png (GPU CUDA if any, else CPU)."""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.city import build_city, setup_view  # noqa: E402

OUT = os.path.join(ROOT, "out", "stills")
PNG = os.path.join(OUT, "city.png")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
build_city()
setup_view(scene)

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
scene.render.filepath = PNG

bpy.ops.render.render(write_still=True)
print("still: %s device=%s" % (PNG, scene.cycles.device))
