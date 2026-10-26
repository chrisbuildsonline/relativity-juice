"""Unwarped pass for the split-screen beat: same flight, warp off, gauge hidden.

-> out/newton/NNNN.png, 1920x1080, frames SPLIT_START..SPLIT_END (resumable; GPU CUDA if any, else CPU).
The gauge is composited later, so it is hidden here.
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.media import SPLIT_END, SPLIT_START  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402
from src.warp import NAME  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = a[0] if a else os.path.join(ROOT, "out", "newton")
scene = build_scene()
city = next(o for o in bpy.data.objects if NAME in o.modifiers)
city.modifiers[NAME].show_render = False  # Newtonian: the camera moves, light does not bend
for o in bpy.data.objects:
    if o.name.startswith("Gauge"):
        o.hide_render = True
render_frames(scene, out, list(range(SPLIT_START, SPLIT_END + 1)), 1920, 1080, 16)
