"""Render 960x540 stills of four beats through the real render path (gauge, warp, motion blur).

-> out/stills/beat_{cruise,build,blueshift,singularity}.png (GPU CUDA if any, else CPU)
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.media import BEATS  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402

OUT = os.path.join(ROOT, "out", "stills")
os.makedirs(OUT, exist_ok=True)

scene = build_scene()
tmp = tempfile.mkdtemp()
render_frames(scene, tmp, sorted(BEATS.values()), 960, 540, 32)
for name, f in BEATS.items():
    shutil.copyfile(os.path.join(tmp, "%04d.png" % f), os.path.join(OUT, "beat_%s.png" % name))
    print("beats: %s frame %d" % (name, f))
shutil.rmtree(tmp, True)
