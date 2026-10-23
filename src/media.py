"""Submission media (no bpy): python3 -m src.media [frames_dir] [stills_dir] [media_dir] [cards_dir].

Cuts out/cards/title.png + out/frames + out/cards/end.png with a synthesized sound bed (src/sound.py)
into media/relativity-juice.mp4, makes media/preview.gif, tiles every 30th flight frame into
media/contact.png (4x3 thumbnails) and copies out/stills/beat_*.png next to them.
Refuses unless all 360 frames and both cards (bun run cards) exist.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile

from src.encode import ROOT, tool
from src.sound import write_wav

FRAME_START, FRAME_END = 1, 360  # src.flight needs numpy, which system python lacks
TITLE, FLIGHT, END, FADE = 2.0, 15.0, 2.5, 0.5  # seconds: title card, the 360 frames, end card, fade each side
GIF_START, GIF_LEN = 6.0, 6.0 # preview.gif excerpt of the flight, seconds


def cut(frames_dir, cards_dir, out):
    """Title card, flight frames and end card with fades through black, plus the sound bed, to an H.264 + AAC mp4."""
    scale = "scale=1920:1080:flags=lanczos,setsar=1"
    fades = lambda d: "fade=t=in:st=0:d=%g,fade=t=out:st=%g:d=%g" % (FADE, d - FADE, FADE)
    graph = ("[0:v]%s,%s[a];[1:v]%s,%s[b];[2:v]%s,%s[c];[a][b][c]concat=n=3:v=1:a=0,fps=24,format=yuv420p[v]"
             % (scale, fades(TITLE), scale, fades(FLIGHT), scale, fades(END)))
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "bed.wav")
        write_wav(wav, TITLE, FLIGHT, END)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                        "-loop", "1", "-framerate", "24", "-t", str(TITLE), "-i", os.path.join(cards_dir, "title.png"),
                        "-framerate", "24", "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png"),
                        "-loop", "1", "-framerate", "24", "-t", str(END), "-i", os.path.join(cards_dir, "end.png"),
                        "-i", wav, "-filter_complex", graph, "-map", "[v]", "-map", "3:a",
                        "-c:v", "libx264", "-crf", "16", "-r", "24", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", out], check=True)
    print("media: %s" % out)


def make_gif(frames_dir, out):
    """Looping 640 px, 12 fps excerpt of the flight, palette-optimised."""
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", str(GIF_START), "-t", str(GIF_LEN), "-framerate", "24",
                    "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png"), "-vf",
                    "fps=12,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
                    "-loop", "0", out], check=True)
    print("media: %s" % out)


def make_media(frames_dir, stills_dir, media_dir, cards_dir=os.path.join(ROOT, "out", "cards")):
    missing = [f for f in range(FRAME_START, FRAME_END + 1) if not os.path.exists(os.path.join(frames_dir, "%04d.png" % f))]
    if missing:
        raise SystemExit("media: %d of %d frames missing in %s (first: %04d)" % (len(missing), FRAME_END, frames_dir, missing[0]))
    cards = [os.path.join(cards_dir, name) for name in ("title.png", "end.png")]
    if not all(os.path.exists(c) for c in cards):
        raise SystemExit("media: title/end cards missing in %s: run `bun run cards` first" % cards_dir)
    os.makedirs(media_dir, exist_ok=True)
    cut(frames_dir, cards_dir, os.path.join(media_dir, "relativity-juice.mp4"))
    make_gif(frames_dir, os.path.join(media_dir, "preview.gif"))
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
               a[2] if len(a) > 2 else os.path.join(ROOT, "media"),
               a[3] if len(a) > 3 else os.path.join(ROOT, "out", "cards"))
