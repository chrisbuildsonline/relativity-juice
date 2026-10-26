"""Full-frame rear view for the whip cut. Same RearCam as the inset, at 1920x1080, labels kept.

-> out/rear-whip/NNNN.png, frames WHIP_START..WHIP_END (resumable; GPU CUDA if any, else CPU).
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.media import WHIP_END, WHIP_START  # noqa: E402
from src.rear import add_rear  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = a[0] if a else os.path.join(ROOT, "out", "rear-whip")
scene = build_scene()
add_rear(scene)
# The gauge overlay owns the lower-left corner, so the caption sits at the top of the frame.
bpy.data.objects["RearLabel"].location = (-1.7, 0.85, -5.0)
bpy.data.objects["RearPanel"].location = (-1.78, 0.59, -5.05)
render_frames(scene, out, list(range(WHIP_START, WHIP_END + 1)), 1920, 1080, 16)
