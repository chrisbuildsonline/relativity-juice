"""Submission media (no bpy): python3 -m src.media [frames_dir] [stills_dir] [media_dir] [cards_dir] [rear_dir] [hud_dir].

Overlays the rear-view frames (out/rear, bun run rear) top-right on REAR_START..REAR_END, then two contrast
cuts that break the single dolly: a Newtonian/relativistic split (out/newton, bun run newton) on
SPLIT_START..SPLIT_END, and a full-frame rear whip (out/rear-whip, bun run rear:whip) on WHIP_START..WHIP_END.
The gauge-only frames (out/hud, bun run hud) go on all 360 flight frames and the beat stills (the baked gauge
is see-through, so city geometry can cross the digits), then it cuts
out/cards/title.png + out/frames + out/cards/end.png with a synthesized sound bed (src/sound.py)
into media/relativity-juice.mp4, makes media/preview.gif, tiles every 30th flight frame into
media/contact.png (4x3 thumbnails), writes media/beat_lookback.png, and copies the cards and
out/stills/beat_*.png next to them.
Refuses unless all 360 frames, both cards (bun run cards), the rear window, the split frames, the whip frames
and all 360 gauge frames exist.
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
SPLIT_START, SPLIT_END = 107, 142  # 1.5 s, beta ~0.70 to ~0.85: left half unwarped, right half the flight
WHIP_START, WHIP_END = 151, 180  # 1.25 s full-frame rear view, the first frames after beta reaches 0.9
LOOKBACK = 148  # frame of media/beat_lookback.png: beta ~0.90, inset still up (after the split, before the whip)
REAR_FADE, BORDER = 0.4, "0x19b4ff"  # inset fade in/out seconds; border colour (the HUD cyan as displayed)
BEATS = {"cruise": 48, "build": 150, "blueshift": 220, "singularity": 340}  # beat still (scripts/beats.py) -> its flight frame
GIF_START, GIF_LEN = 1.0, 6.0  # preview.gif excerpt of the flight, seconds: the inset, then the build


def cut(frames_dir, cards_dir, out, channels=1):
    """Title card, flight frames and end card with fades through black, plus the sound bed, to an H.264 + AAC mp4."""
    scale = "scale=1920:1080:flags=lanczos,setsar=1"
    fades = lambda d: "fade=t=in:st=0:d=%g,fade=t=out:st=%g:d=%g" % (FADE, d - FADE, FADE)
    graph = ("[0:v]%s,%s[a];[1:v]%s,%s[b];[2:v]%s,%s[c];[a][b][c]concat=n=3:v=1:a=0,fps=24,format=yuv420p[v]"
             % (scale, fades(TITLE), scale, fades(FLIGHT), scale, fades(END)))
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "bed.wav")
        write_wav(wav, TITLE, FLIGHT, END, channels=channels)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                        "-loop", "1", "-framerate", "24", "-t", str(TITLE), "-i", os.path.join(cards_dir, "title.png"),
                        "-framerate", "24", "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png"),
                        "-loop", "1", "-framerate", "24", "-t", str(END), "-i", os.path.join(cards_dir, "end.png"),
                        "-i", wav, "-filter_complex", graph, "-map", "[v]", "-map", "3:a",
                        "-c:v", "libx264", "-crf", "16", "-r", "24", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", out], check=True)
    print("media: %s" % out)


def make_gif(frames_dir, out):
    """Looping 640 px, 12 fps excerpt of the flight, palette-optimised."""
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-ss", str(GIF_START), "-t", str(GIF_LEN), "-framerate", "24",
                    "-pattern_type", "glob", "-i", os.path.join(frames_dir, "*.png"), "-vf",
                    "fps=12,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
                    "-loop", "0", out], check=True)
    print("media: %s" % out)


def composite(frames_dir, rear_dir, out_dir, hud_dir, newton_dir, whip_dir):
    """Flight frames to out_dir: rear inset, then the split and the whip, then the gauge on every frame."""
    with tempfile.TemporaryDirectory() as inset, tempfile.TemporaryDirectory() as split, tempfile.TemporaryDirectory() as whip:
        rear_inset(frames_dir, rear_dir, inset)
        split_compare(inset, frames_dir, newton_dir, split)
        whip_cut(split, whip_dir, whip)
        add_hud(whip, hud_dir, out_dir)


def frame_info(frames_dir):
    """(width, height, pix_fmt) of the first flight frame."""
    shape = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,pix_fmt", "-of", "json",
                            os.path.join(frames_dir, "0001.png")], check=True, capture_output=True, text=True)
    info = json.loads(shape.stdout)["streams"][0]
    return info["width"], info["height"], info["pix_fmt"]


def add_hud(frames_dir, hud_dir, out_dir):
    """Overlay the gauge-only RGBA frame N (scaled to the frames' width) on frame N for all frames, in the frames' pixel format."""
    width, _height, pix_fmt = frame_info(frames_dir)
    os.makedirs(out_dir, exist_ok=True)
    graph = "[1:v]scale=%d:-2:flags=lanczos,format=rgba[h];[0:v][h]overlay=0:0:format=auto,format=%s" % (width, pix_fmt)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                    "-framerate", "24", "-start_number", str(FRAME_START), "-i", os.path.join(frames_dir, "%04d.png"),
                    "-framerate", "24", "-start_number", str(FRAME_START), "-i", os.path.join(hud_dir, "%04d.png"),
                    "-filter_complex", graph, "-frames:v", str(FRAME_END), "-start_number", str(FRAME_START),
                    os.path.join(out_dir, "%04d.png")], check=True)
    print("media: gauge overlay on frames %d-%d" % (FRAME_START, FRAME_END))


def rear_inset(frames_dir, rear_dir, out_dir):
    """All flight frames to out_dir; REAR_START..REAR_END get the rear view top-right in a cyan border, faded in and out."""
    n = REAR_END - REAR_START + 1
    width, _height, pix_fmt = frame_info(frames_dir)
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


def _copy_outside(src_dir, out_dir, first, last):
    os.makedirs(out_dir, exist_ok=True)
    for f in range(FRAME_START, FRAME_END + 1):
        if not first <= f <= last:
            shutil.copyfile(os.path.join(src_dir, "%04d.png" % f), os.path.join(out_dir, "%04d.png" % f))


def split_compare(base_dir, frames_dir, newton_dir, out_dir):
    """Copy base_dir, then replace SPLIT_START..SPLIT_END: left half unwarped, right half the flight frame."""
    width, height, pix_fmt = frame_info(frames_dir)
    half = width // 2
    _copy_outside(base_dir, out_dir, SPLIT_START, SPLIT_END)
    graph = ("[1:v]scale=%d:%d:flags=lanczos,crop=%d:%d:0:0[left];"
             "[0:v]crop=%d:%d:%d:0[right];[left][right]hstack=inputs=2,format=%s"
             % (width, height, half, height, width - half, height, half, pix_fmt))
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                    "-framerate", "24", "-start_number", str(SPLIT_START), "-i", os.path.join(frames_dir, "%04d.png"),
                    "-framerate", "24", "-start_number", str(SPLIT_START), "-i", os.path.join(newton_dir, "%04d.png"),
                    "-filter_complex", graph, "-frames:v", str(SPLIT_END - SPLIT_START + 1), "-start_number", str(SPLIT_START),
                    os.path.join(out_dir, "%04d.png")], check=True)
    print("media: newtonian split on frames %d-%d" % (SPLIT_START, SPLIT_END))


def whip_cut(base_dir, whip_dir, out_dir):
    """Copy base_dir, then replace WHIP_START..WHIP_END with the full-frame rear view."""
    width, height, pix_fmt = frame_info(base_dir)
    _copy_outside(base_dir, out_dir, WHIP_START, WHIP_END)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y",
                    "-framerate", "24", "-start_number", str(WHIP_START), "-i", os.path.join(whip_dir, "%04d.png"),
                    "-vf", "scale=%d:%d:flags=lanczos,setsar=1,format=%s" % (width, height, pix_fmt),
                    "-frames:v", str(WHIP_END - WHIP_START + 1), "-start_number", str(WHIP_START),
                    os.path.join(out_dir, "%04d.png")], check=True)
    print("media: full-frame rear whip on frames %d-%d" % (WHIP_START, WHIP_END))


def _missing(directory, first, last):
    return [f for f in range(first, last + 1) if not os.path.exists(os.path.join(directory, "%04d.png" % f))]


def make_media(frames_dir, stills_dir, media_dir, cards_dir=os.path.join(ROOT, "out", "cards"),
               rear_dir=os.path.join(ROOT, "out", "rear"), hud_dir=os.path.join(ROOT, "out", "hud"),
               newton_dir=os.path.join(ROOT, "out", "newton"), whip_dir=os.path.join(ROOT, "out", "rear-whip")):
    missing = [f for f in range(FRAME_START, FRAME_END + 1) if not os.path.exists(os.path.join(frames_dir, "%04d.png" % f))]
    if missing:
        raise SystemExit("media: %d of %d frames missing in %s (first: %04d)" % (len(missing), FRAME_END, frames_dir, missing[0]))
    cards = [os.path.join(cards_dir, name) for name in ("title.png", "end.png")]
    if not all(os.path.exists(c) for c in cards):
        raise SystemExit("media: title/end cards missing in %s: run `bun run cards` first" % cards_dir)
    no_rear = _missing(rear_dir, REAR_START, REAR_END)
    if no_rear:
        raise SystemExit("media: %d rear frames missing in %s (first: %04d): run `bun run rear` first" % (len(no_rear), rear_dir, no_rear[0]))
    no_newton = _missing(newton_dir, SPLIT_START, SPLIT_END)
    if no_newton:
        raise SystemExit("media: %d newtonian frames missing in %s (first: %04d): run `bun run newton` first" % (len(no_newton), newton_dir, no_newton[0]))
    no_whip = _missing(whip_dir, WHIP_START, WHIP_END)
    if no_whip:
        raise SystemExit("media: %d whip frames missing in %s (first: %04d): run `bun run rear:whip` first" % (len(no_whip), whip_dir, no_whip[0]))
    no_hud = _missing(hud_dir, FRAME_START, FRAME_END)
    if no_hud:
        raise SystemExit("media: %d gauge overlay frames missing in %s (first: %04d): run `bun run hud` first" % (len(no_hud), hud_dir, no_hud[0]))
    os.makedirs(media_dir, exist_ok=True)
    for card in cards:
        shutil.copyfile(card, os.path.join(media_dir, os.path.basename(card)))
    with tempfile.TemporaryDirectory() as shown:
        composite(frames_dir, rear_dir, shown, hud_dir, newton_dir, whip_dir)
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
    copy_beats(stills_dir, media_dir, hud_dir)


def copy_beats(stills_dir, media_dir, hud_dir):
    """Beat stills to media_dir, each with its beat's gauge overlay frame (scaled to 960x540) on top."""
    os.makedirs(media_dir, exist_ok=True)
    for beat in sorted(glob.glob(os.path.join(stills_dir, "beat_*.png"))):
        name = os.path.basename(beat)
        hud = os.path.join(hud_dir, "%04d.png" % BEATS.get(name[5:-4], 0))
        if os.path.exists(hud):
            subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", beat, "-i", hud, "-filter_complex",
                            "[1:v]scale=960:540:flags=lanczos,format=rgba[h];[0:v][h]overlay=0:0:format=auto,format=rgba",
                            "-frames:v", "1", "-update", "1", os.path.join(media_dir, name)], check=True)
        else:
            shutil.copyfile(beat, os.path.join(media_dir, name))
        print("media: %s" % name)


def make_racer_media(frames_dir=os.path.join(ROOT, "out", "racer"),
                     media_dir=os.path.join(ROOT, "media"),
                     cards_dir=os.path.join(ROOT, "out", "cards")):
    """Build all submission media directly from the 360 native Blender Neon Racer frames + stereo 90s Synthwave audio."""
    missing = _missing(frames_dir, FRAME_START, FRAME_END)
    if missing:
        raise SystemExit("media: %d of %d racer frames missing in %s (first: %04d)" % (len(missing), FRAME_END, frames_dir, missing[0]))
    cards = [os.path.join(cards_dir, name) for name in ("title.png", "end.png")]
    if not all(os.path.exists(c) for c in cards):
        raise SystemExit("media: title/end cards missing in %s: run `bun run cards` first" % cards_dir)
    os.makedirs(media_dir, exist_ok=True)
    for card in cards:
        shutil.copyfile(card, os.path.join(media_dir, os.path.basename(card)))
    cut(frames_dir, cards_dir, os.path.join(media_dir, "relativity-juice.mp4"), channels=2)
    make_gif(frames_dir, os.path.join(media_dir, "preview.gif"))
    contact = os.path.join(media_dir, "contact.png")
    subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-framerate", "24", "-pattern_type", "glob",
                    "-i", os.path.join(frames_dir, "*.png"),
                    "-vf", "select='not(mod(n,30))',scale=320:180:flags=lanczos,tile=4x3",
                    "-frames:v", "1", "-update", "1", contact], check=True)
    print("media: %s" % contact)
    racer_beats = {
        "beat_cruise.png": 36,       # Shot 1: Low Wheel/Exhaust Launch Cam
        "beat_build.png": 115,       # Shot 2: Sweeping Helicopter Orbit Cam
        "beat_lookback.png": 148,    # Shot 2: S-curve drift closing on RivalRacer
        "beat_blueshift.png": 205,   # Shot 3: Door-to-door 3/4 Overtake Cam
        "beat_singularity.png": 265, # Shot 4: Hyper-Boost Shockwave & Segmented Sun
    }
    for name, f_num in racer_beats.items():
        dst = os.path.join(media_dir, name)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-i", os.path.join(frames_dir, "%04d.png" % f_num),
                        "-vf", "scale=960:540:flags=lanczos", "-frames:v", "1", "-update", "1", dst], check=True)
        print("media: %s (frame %d)" % (dst, f_num))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--racer"]:
        r_args = a[1:]
        make_racer_media(
            r_args[0] if r_args else os.path.join(ROOT, "out", "racer"),
            r_args[1] if len(r_args) > 1 else os.path.join(ROOT, "media"),
            r_args[2] if len(r_args) > 2 else os.path.join(ROOT, "out", "cards"),
        )
        sys.exit(0)
    if a[:1] == ["--stills-only"]:  # refresh just the beat stills, no frames needed
        hud = os.path.join(ROOT, "out", "hud")
        if not os.path.isdir(hud):
            print("media: no %s, beat stills copied without the gauge overlay" % hud)
        copy_beats(os.path.join(ROOT, "out", "stills"), os.path.join(ROOT, "media"), hud)
        sys.exit(0)
    make_media(a[0] if a else os.path.join(ROOT, "out", "frames"),
               a[1] if len(a) > 1 else os.path.join(ROOT, "out", "stills"),
               a[2] if len(a) > 2 else os.path.join(ROOT, "media"),
               a[3] if len(a) > 3 else os.path.join(ROOT, "out", "cards"),
               a[4] if len(a) > 4 else os.path.join(ROOT, "out", "rear"),
               a[5] if len(a) > 5 else os.path.join(ROOT, "out", "hud"),
               a[6] if len(a) > 6 else os.path.join(ROOT, "out", "newton"),
               a[7] if len(a) > 7 else os.path.join(ROOT, "out", "rear-whip"))
