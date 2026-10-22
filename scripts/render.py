"""Render the flight to out/frames/NNNN.png, resumable. Options go after `--`:
--out DIR --start 1 --end 360 --step 1 --width 1920 --height 1080 --samples 48 --device auto|gpu|cpu --no-denoise
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.flight import FRAME_END, FRAME_START  # noqa: E402
from src.render import build_scene, render_frames  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--out", default=os.path.join(ROOT, "out", "frames"))
p.add_argument("--start", type=int, default=FRAME_START)
p.add_argument("--end", type=int, default=FRAME_END)
p.add_argument("--step", type=int, default=1)
p.add_argument("--width", type=int, default=1920)
p.add_argument("--height", type=int, default=1080)
p.add_argument("--samples", type=int, default=48)
p.add_argument("--device", default="auto", choices=["auto", "gpu", "cpu"])
p.add_argument("--no-denoise", action="store_true")
a = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

frames = range(a.start, a.end + 1, a.step)
done = render_frames(build_scene(), a.out, frames, a.width, a.height, a.samples, a.device, not a.no_denoise)
print("render: finished, %d new of %d frames in %s" % (len(done), len(frames), a.out), flush=True)
