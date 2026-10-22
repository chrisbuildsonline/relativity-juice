"""Encode a folder of PNG frames to H.264 (no bpy): python3 -m src.encode [frames_dir] [out.mp4] [fps]."""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tool(name):
    """ffmpeg / ffprobe: $FFMPEG (or $FFPROBE), then ~/.local/bin, then PATH."""
    env = os.environ.get(name.upper())
    local = os.path.expanduser("~/.local/bin/" + name)
    return env or (local if os.path.exists(local) else shutil.which(name) or name)


def encode(frames_dir, out, fps=24):
    """frames_dir/*.png in name order -> 1920x1080 yuv420p H.264 at `fps`."""
    if not glob.glob(os.path.join(frames_dir, "*.png")):
        raise SystemExit("encode: no PNG frames in " + frames_dir)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-framerate", str(fps), "-pattern_type", "glob",
                    "-i", os.path.join(frames_dir, "*.png"), "-vf", "scale=1920:1080:flags=lanczos",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-r", str(fps),
                    "-movflags", "+faststart", out], check=True)
    print("encode: %s" % out)


if __name__ == "__main__":
    a = sys.argv[1:]
    encode(a[0] if a else os.path.join(ROOT, "out", "frames"),
           a[1] if len(a) > 1 else os.path.join(ROOT, "out", "relativity-juice.mp4"),
           int(a[2]) if len(a) > 2 else 24)
