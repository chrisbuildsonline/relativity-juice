"""Submission media (no bpy): python3 -m src.media [frames_dir] [stills_dir] [media_dir].

Encodes out/frames to media/relativity-juice.mp4, tiles every 30th frame into media/contact.png
(4x3 thumbnails) and copies out/stills/beat_*.png next to them. Refuses unless all 360 frames exist.
"""
import glob
import os
import shutil
import subprocess
import sys

from src.encode import ROOT, encode, tool

FRAME_START, FRAME_END = 1, 360  # src.flight needs numpy, which system python lacks

def make_media(frames_dir, stills_dir, media_dir):
    missing = [f for f in range(FRAME_START, FRAME_END + 1) if not os.path.exists(os.path.join(frames_dir, "%04d.png" % f))]
    if missing:
        raise SystemExit("media: %d of %d frames missing in %s (first: %04d)" % (len(missing), FRAME_END, frames_dir, missing[0]))
    os.makedirs(media_dir, exist_ok=True)
    encode(frames_dir, os.path.join(media_dir, "relativity-juice.mp4"))
    contact = os.path.join(media_dir, "contact.png")
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-framerate", "24", "-pattern_type", "glob",
                    "-i", os.path.join(frames_dir, "*.png"),
                    "-vf", "select='not(mod(n,30))',scale=320:180:flags=lanczos,tile=4x3",
                    "-frames:v", "1", "-update", "1", contact], check=True)
    print("media: %s" % contact)
    copy_beats(stills_dir, media_dir)


def copy_beats(stills_dir, media_dir):
    os.makedirs(media_dir, exist_ok=True)
    for beat in sorted(glob.glob(os.path.join(stills_dir, "beat_*.png"))):
        shutil.copyfile(beat, os.path.join(media_dir, os.path.basename(beat)))
        print("media: %s" % os.path.basename(beat))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--stills-only"]:  # refresh just the beat stills, no frames needed
        copy_beats(os.path.join(ROOT, "out", "stills"), os.path.join(ROOT, "media"))
        sys.exit(0)
    make_media(a[0] if a else os.path.join(ROOT, "out", "frames"),
               a[1] if len(a) > 1 else os.path.join(ROOT, "out", "stills"),
               a[2] if len(a) > 2 else os.path.join(ROOT, "media"))
