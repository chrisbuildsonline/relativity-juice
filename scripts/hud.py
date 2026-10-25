"""Render the gauge alone as a transparent RGBA overlay, composited over the flight frames in post.

-> out/hud/NNNN.png, 1920x1080, frames 1..360 (resumable; GPU CUDA if any, else CPU). `-- OUT_DIR` overrides the folder.
Same camera, flight and gauge handler as the forward render (build_scene), so the digits and the cyan match it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.flight import FRAME_END, FRAME_START  # noqa: E402
from src.gauge import hud_only  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = a[0] if a else os.path.join(ROOT, "out", "hud")
SAMPLES = 8  # the overlay is flat emission on a plate: no noise to average out

scene = build_scene()
hud_only(scene)
render_frames(scene, out, list(range(FRAME_START, FRAME_END + 1)), 1920, 1080, SAMPLES, "auto", False)
