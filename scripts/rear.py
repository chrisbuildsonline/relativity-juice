"""Render the rear-view inset frames through the real render path (warp, motion blur, label).

-> out/rear/NNNN.png, REAR_W x REAR_H (800x450), frames REAR_START..REAR_END (resumable; GPU CUDA if any, else CPU).
Probe: `-- OUT_DIR WIDTH HEIGHT SAMPLES FRAME...` renders just those frames and prints their mean luminance.
"""
import os
import sys

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.flight import time_of  # noqa: E402
from src.media import REAR_END, REAR_H, REAR_START, REAR_W  # noqa: E402
from src.rear import add_rear  # noqa: E402
from src.relativity import beta_at  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = a[0] if a else os.path.join(ROOT, "out", "rear")
width, height, samples = (int(x) for x in a[1:4]) if len(a) >= 4 else (REAR_W, REAR_H, 48)
frames = [int(x) for x in a[4:]] or list(range(REAR_START, REAR_END + 1))

scene = build_scene()
add_rear(scene)
for name in ("RearLabel", "RearPanel"):
    bpy.data.objects[name].hide_render = len(a) > 4  # a probe (explicit frames) measures the city alone
render_frames(scene, out, frames, width, height, samples)
for f in frames:
    img = bpy.data.images.load(os.path.join(out, "%04d.png" % f))
    rgb = np.array(img.pixels[:], dtype=float).reshape(-1, 4)[:, :3]
    bpy.data.images.remove(img)
    lum = float((rgb @ np.array([0.2126, 0.7152, 0.0722])).mean())
    print("rear: frame %d beta %.3f mean luminance %.4f R/B %.3f" % (f, beta_at(time_of(f)), lum, rgb[:, 0].mean() / max(rgb[:, 2].mean(), 1e-9)))
