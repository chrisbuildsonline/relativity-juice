"""Submission media (no bpy): python3 -m src.media [frames_dir] [stills_dir] [media_dir] [cards_dir] [rear_dir].

Overlays the rear-view frames (out/rear, bun run rear) top-right on REAR_START..REAR_END, then cuts
out/cards/title.png + out/frames + out/cards/end.png with a synthesized sound bed (src/sound.py)
into media/relativity-juice.mp4, makes media/preview.gif, tiles every 30th flight frame into
media/contact.png (4x3 thumbnails), writes media/beat_lookback.png, and copies the cards and
out/stills/beat_*.png next to them.
Refuses unless all 360 frames, both cards (bun run cards) and the rear window frames exist.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

from src.encode import ROOT, tool
from src.sound import write_wav

FRAME_START, FRAME_END = 1, 360  # src.flight needs numpy, which system python lacks
TITLE, FLIGHT, END, FADE = 2.0, 15.0, 2.5, 0.5  # seconds: title card, the 360 frames, end card, fade each side
REAR_START, REAR_END = 13, 150  # inset window, 5.75 s: ends at the first flight frame with beta >= 0.9 (tests pin it to beta_at)
REAR_W, REAR_H = 800, 450  # rear frames' render size = the inset at 1920 wide (41.7%), so nothing is upscaled
LOOKBACK = REAR_END - 12  # frame of media/beat_lookback.png: beta ~0.86, inset red and dim but readable, still before the fade-out
REAR_FADE, BORDER = 0.4, "0x19b4ff"  # inset fade in/out seconds; border colour (the HUD cyan as displayed)
GIF_START, GIF_LEN = 1.0, 6.0  # preview.gif excerpt of the flight, seconds: the inset, then the build


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


def composite(frames_dir, rear_dir, out_dir):
    """All flight frames to out_dir; REAR_START..REAR_END get the rear view top-right in a cyan border, faded in and out."""
    n = REAR_END - REAR_START + 1
    shape = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,pix_fmt",
                            "-of", "json", os.path.join(frames_dir, "0001.png")], check=True, capture_output=True, text=True)
    info = json.loads(shape.stdout)["streams"][0]
    width, pix_fmt = info["width"], info["pix_fmt"]
    inset, margin, border = width * REAR_W // 1920 // 2 * 2, max(1, round(width * 24 / 1920)), max(1, round(width * 3 / 1920))
    os.makedirs(out_dir, exist_ok=True)
    for f in range(FRAME_START, FRAME_END + 1):
        if not REAR_START <= f <= REAR_END:
            shutil.copyfile(os.path.join(frames_dir, "%04d.png" % f), os.path.join(out_dir, "%04d.png" % f))
    graph = ("[1:v]scale=%d:-2:flags=lanczos,pad=iw+%d:ih+%d:%d:%d:color=%s,format=yuva420p,"
             "fade=t=in:st=0:d=%g:alpha=1,fade=t=out:st=%g:d=%g:alpha=1[r];"
             "[0:v][r]overlay=x=main_w-overlay_w-%d:y=%d:format=auto,format=%s"  # the frames' own pixel format: a change mid-clip stalls the cut's concat
             % (inset, 2 * border, 2 * border, border, border, BORDER, REAR_FADE, n / 24 - REAR_FADE, REAR_FADE, margin, margin, pix_fmt))
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                    "-framerate", "24", "-start_number", str(REAR_START), "-i", os.path.join(frames_dir, "%04d.png"),
                    "-framerate", "24", "-start_number", str(REAR_START), "-i", os.path.join(rear_dir, "%04d.png"),
                    "-filter_complex", graph, "-frames:v", str(n), "-start_number", str(REAR_START),
                    os.path.join(out_dir, "%04d.png")], check=True)
    print("media: rear inset on frames %d-%d" % (REAR_START, REAR_END))


def make_media(frames_dir, stills_dir, media_dir, cards_dir=os.path.join(ROOT, "out", "cards"),
               rear_dir=os.path.join(ROOT, "out", "rear")):
    missing = [f for f in range(FRAME_START, FRAME_END + 1) if not os.path.exists(os.path.join(frames_dir, "%04d.png" % f))]
    if missing:
        raise SystemExit("media: %d of %d frames missing in %s (first: %04d)" % (len(missing), FRAME_END, frames_dir, missing[0]))
    cards = [os.path.join(cards_dir, name) for name in ("title.png", "end.png")]
    if not all(os.path.exists(c) for c in cards):
        raise SystemExit("media: title/end cards missing in %s: run `bun run cards` first" % cards_dir)
    no_rear = [f for f in range(REAR_START, REAR_END + 1) if not os.path.exists(os.path.join(rear_dir, "%04d.png" % f))]
    if no_rear:
        raise SystemExit("media: %d rear frames missing in %s (first: %04d): run `bun run rear` first" % (len(no_rear), rear_dir, no_rear[0]))
    os.makedirs(media_dir, exist_ok=True)
    for card in cards:
        shutil.copyfile(card, os.path.join(media_dir, os.path.basename(card)))
    with tempfile.TemporaryDirectory() as shown:
        composite(frames_dir, rear_dir, shown)
        cut(shown, cards_dir, os.path.join(media_dir, "relativity-juice.mp4"))
        make_gif(shown, os.path.join(media_dir, "preview.gif"))
        contact = os.path.join(media_dir, "contact.png")
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-framerate", "24", "-pattern_type", "glob",
                        "-i", os.path.join(shown, "*.png"),
                        "-vf", "select='not(mod(n,30))',scale=320:180:flags=lanczos,tile=4x3",
                        "-frames:v", "1", "-update", "1", contact], check=True)
        print("media: %s" % contact)
        lookback = os.path.join(media_dir, "beat_lookback.png")
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", os.path.join(shown, "%04d.png" % LOOKBACK),
                        "-vf", "scale=960:540:flags=lanczos", "-frames:v", "1", "-update", "1", lookback], check=True)
        print("media: %s" % lookback)
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
               a[3] if len(a) > 3 else os.path.join(ROOT, "out", "cards"),
               a[4] if len(a) > 4 else os.path.join(ROOT, "out", "rear"))
