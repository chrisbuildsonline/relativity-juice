"""Headless Cycles CPU smoke render: the city at beta=0 in 64x36, fails if near-black or flat."""
import os
import sys
import time

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.city import build_city, setup_view  # noqa: E402

OUT = os.path.join(ROOT, "out", "smoke")
PNG = os.path.join(OUT, "smoke.png")
MIN_MEAN = 0.02
MIN_STD = 0.02
os.makedirs(OUT, exist_ok=True)
if os.path.exists(PNG):
    os.remove(PNG)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
t0 = time.perf_counter()
city = build_city()
print("smoke: city %d vertices built in %.2fs" % (len(city.data.vertices), time.perf_counter() - t0))
setup_view(scene)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.render.resolution_x = 64
scene.render.resolution_y = 36
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = PNG

bpy.ops.render.render(write_still=True)

if not os.path.exists(PNG):
    sys.exit("smoke: no PNG written at " + PNG)

img = bpy.data.images.load(PNG)
w, h = img.size
if (w, h) != (64, 36):
    sys.exit("smoke: unexpected size %dx%d" % (w, h))
px = np.array(img.pixels[:], dtype=float).reshape(-1, 4)
lum = px[:, :3] @ np.array([0.2126, 0.7152, 0.0722])
mean, std = float(lum.mean()), float(lum.std())
if mean < MIN_MEAN:
    sys.exit("smoke: render is near-black (mean luminance %.4f < %.2f)" % (mean, MIN_MEAN))
if std < MIN_STD:
    sys.exit("smoke: render is flat (luminance std %.4f < %.2f)" % (std, MIN_STD))
print("smoke ok: %dx%d, mean luminance %.3f, std %.3f -> %s" % (w, h, mean, std, PNG))
