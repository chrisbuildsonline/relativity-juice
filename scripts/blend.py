"""Export the procedural Synthwave Neon Racer scene + packed 90s Synthwave audio strip to out/neon-racer.blend.

This standalone .blend file contains all procedural meshes, Geometry Nodes modifiers, F-curve vehicle rigs,
4 timeline-marker cameras, and the synthesized 124 BPM soundtrack in Blender's Video Sequence Editor, ready
for finalist verification or direct upload to RenderJuice Cloud (app.renderjuice.com).
"""
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.flight import DURATION  # noqa: E402
from src.racer import build_racer_scene  # noqa: E402
from src.sound import write_wav  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out_blend = a[0] if a else os.path.join(ROOT, "out", "neon-racer.blend")
os.makedirs(os.path.dirname(out_blend), exist_ok=True)

wav_path = os.path.join(os.path.dirname(out_blend), "synthwave.wav")
write_wav(wav_path, 0.0, DURATION, 0.5, channels=2)

scene = build_racer_scene()
if not scene.sequence_editor:
    scene.sequence_editor_create()
seqs = getattr(scene.sequence_editor, "strips", None) or getattr(scene.sequence_editor, "sequences", None)
if seqs is not None and hasattr(seqs, "new_sound"):
    seqs.new_sound("Synthwave124BPM", wav_path, channel=1, frame_start=1)

bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
print("blend: saved %s" % out_blend, flush=True)
