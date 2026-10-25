import json
import os
import shutil
import subprocess
import tempfile
import unittest

from src.encode import tool
from src.media import BEATS, FRAME_END, FRAME_START, REAR_END, REAR_H, REAR_START, REAR_W, composite, copy_beats, make_media


def lavfi_frames(out, n):
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=24",
                    "-frames:v", str(n), "-pix_fmt", "rgba", os.path.join(out, "%04d.png")], check=True)  # Blender's frames are RGBA


def rear_frames(out, first=REAR_START, last=REAR_END):
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=0xc02010:size=64x36:rate=24",
                    "-frames:v", str(last - first + 1), "-start_number", str(first), os.path.join(out, "%04d.png")], check=True)


PLATE = "x=4:y=20:w=30:h=12"  # the HUD plate in 64x36 test frames; the cyan glyph pixel is at 10,24


def streak_frames(out, n):
    """Black 64x36 RGBA flight frames with a bright streak under the plate region (y 24-27) and past it."""
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:size=64x36:rate=24,drawbox=x=0:y=24:w=64:h=4:color=white:t=fill,format=rgba",
                    "-frames:v", str(n), os.path.join(out, "%04d.png")], check=True)


def hud_frames(out, first=FRAME_START, last=FRAME_END):
    """Transparent RGBA HUD frames with an opaque black plate and one cyan pixel."""
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black@0:size=64x36:rate=24,format=rgba,drawbox=%s:color=black@1:t=fill:replace=1,"
                    "drawbox=x=10:y=24:w=1:h=1:color=0x00b4ff@1:t=fill:replace=1" % PLATE,
                    "-frames:v", str(last - first + 1), "-start_number", str(first), os.path.join(out, "%04d.png")], check=True)


def pixel(path, x, y, scale=""):
    """RGB tuple of one pixel of a PNG."""
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", path, "-vf", scale + "crop=1:1:%d:%d,format=rgb24" % (x, y),
                        "-f", "rawvideo", "-"], check=True, capture_output=True)
    return tuple(r.stdout)


def top_right(path):
    """Raw RGB bytes of the top-right quarter of a PNG, where the inset goes."""
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", path, "-vf", "crop=iw/2:ih/2:iw/2:0,format=rgb24",
                        "-f", "rawvideo", "-"], check=True, capture_output=True)
    return r.stdout


def probe(path, entries, stream="v:0"):
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", stream, "-count_frames",
                        "-show_entries", "stream=" + entries, "-of", "json", path],
                       check=True, capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]


def streams(path):
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,codec_name:format=duration",
                        "-of", "json", path], check=True, capture_output=True, text=True)
    return json.loads(r.stdout)


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.frames = os.path.join(self.dir, "frames")
        self.stills = os.path.join(self.dir, "stills")
        self.cards = os.path.join(self.dir, "cards")
        self.media = os.path.join(self.dir, "media")
        self.rear = os.path.join(self.dir, "rear")
        self.hud = os.path.join(self.dir, "hud")
        hud_frames(self.hud)
        os.makedirs(self.stills)
        os.makedirs(self.cards)
        for name in ("beat_cruise.png", "beat_build.png"):  # white 960x540 stills, like the real beats
            subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=white:size=960x540",
                            "-frames:v", "1", os.path.join(self.stills, name)], check=True)
        open(os.path.join(self.stills, "city.png"), "w").close()
        for name, src in (("title.png", "color=c=0x101820"), ("end.png", "color=c=0x201018")):
            subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", src + ":size=64x36",
                            "-frames:v", "1", os.path.join(self.cards, name)], check=True)

    def test_refuses_unless_all_360_frames_exist(self):
        lavfi_frames(self.frames, 359)
        rear_frames(self.rear)
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_one_frame_is_missing_in_the_middle(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.frames, "0100.png"))
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)

    def test_refuses_when_a_card_is_missing(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.cards, "end.png"))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)
        self.assertIn("bun run cards", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_a_rear_frame_is_missing(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.rear, "%04d.png" % ((REAR_START + REAR_END) // 2)))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)
        self.assertIn("bun run rear", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_composite_overlays_the_window_and_copies_the_rest(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        out = os.path.join(self.dir, "out")
        composite(self.frames, self.rear, out, self.hud)
        self.assertEqual(sorted(os.listdir(out)), ["%04d.png" % f for f in range(1, 361)])
        for f in (1, REAR_START - 1, REAR_END + 1, 360):  # outside the window only the HUD (lower-left) differs
            with self.subTest(frame=f):
                self.assertEqual(top_right(os.path.join(self.frames, "%04d.png" % f)), top_right(os.path.join(out, "%04d.png" % f)))
        mid = "%04d.png" % ((REAR_START + REAR_END) // 2)
        for name in (mid, "0001.png"):  # one pixel format all through, or the cut's concat stalls
            self.assertEqual(probe(os.path.join(out, name), "pix_fmt")["pix_fmt"], "rgba")
        self.assertNotEqual(top_right(os.path.join(self.frames, mid)), top_right(os.path.join(out, mid)))
        self.assertEqual(top_right(os.path.join(self.frames, "0001.png")), top_right(os.path.join(out, "0001.png")))

    def test_refuses_when_a_hud_frame_is_missing(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.hud, "0300.png"))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)
        self.assertIn("bun run hud", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_composite_hud_covers_the_streak_on_every_frame(self):
        streak_frames(self.frames, 360)
        rear_frames(self.rear)
        out = os.path.join(self.dir, "out")
        composite(self.frames, self.rear, out, self.hud)
        for f in (1, REAR_START - 1, REAR_START, (REAR_START + REAR_END) // 2, REAR_END, REAR_END + 1, 360):
            png = os.path.join(out, "%04d.png" % f)
            with self.subTest(frame=f):
                self.assertEqual(probe(png, "pix_fmt")["pix_fmt"], "rgba")  # the frames' own pixel format
                self.assertLess(max(pixel(png, 20, 25)), 8)  # streak under the plate is gone
                self.assertGreater(pixel(png, 10, 24)[2], 150)  # cyan glyph pixel
                self.assertEqual(pixel(png, 50, 25), (255, 255, 255))  # streak beyond the plate stays

    def test_composite_scales_the_hud_to_the_frame_width(self):
        os.makedirs(self.frames)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                        "color=c=white:size=128x72:rate=24,format=rgba", "-frames:v", "360", os.path.join(self.frames, "%04d.png")], check=True)
        rear_frames(self.rear)
        out = os.path.join(self.dir, "out")
        composite(self.frames, self.rear, out, self.hud)  # 64x36 HUD over 128x72 frames
        png = os.path.join(out, "0001.png")
        self.assertEqual(pixel(png, 40, 58), (0, 0, 0))  # plate x 8-68, y 40-64 at double size, clear of the glyph
        self.assertEqual(pixel(png, 120, 50), (255, 255, 255))

    def test_beats_get_their_hud_frame(self):
        copy_beats(self.stills, self.media, self.hud)
        for name in ("cruise", "build"):
            png = os.path.join(self.media, "beat_%s.png" % name)
            self.assertEqual(pixel(png, 200, 400), (0, 0, 0))  # plate: 64x36 HUD scaled to 960x540
            self.assertEqual(pixel(png, 800, 100), (255, 255, 255))
        self.assertEqual(BEATS, {"cruise": 48, "build": 150, "blueshift": 220, "singularity": 340})

    def test_composite_inset_is_at_least_40_percent_of_the_width(self):
        os.makedirs(self.frames)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=24",
                        "-frames:v", "360", "-pix_fmt", "rgba", os.path.join(self.frames, "%04d.png")], check=True)
        os.makedirs(self.rear)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=0xc02010:size=%dx%d:rate=24" % (REAR_W, REAR_H),
                        "-frames:v", str(REAR_END - REAR_START + 1), "-start_number", str(REAR_START),
                        os.path.join(self.rear, "%04d.png")], check=True)
        out = os.path.join(self.dir, "out")
        composite(self.frames, self.rear, out, self.hud)
        mid = os.path.join(out, "%04d.png" % ((REAR_START + REAR_END) // 2))
        row = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", mid, "-vf", "crop=iw:1:0:ih/10,format=gray",
                              "-f", "rawvideo", "-"], check=True, capture_output=True).stdout
        lit = sum(1 for p in row if p > 0)  # the inset plus its 2 px border, on a black frame
        border = max(1, round(640 * 3 / 1920))
        self.assertGreaterEqual((lit - 2 * border) / 640, 0.4)
        self.assertEqual(lit - 2 * border, 640 * REAR_W // 1920 // 2 * 2)

    def test_makes_mp4_contact_sheet_and_copies_beats(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        make_media(self.frames, self.stills, self.media, self.cards, self.rear, self.hud)
        self.assertEqual(sorted(os.listdir(self.media)),
                         ["beat_build.png", "beat_cruise.png", "beat_lookback.png", "contact.png", "end.png",
                          "preview.gif", "relativity-juice.mp4", "title.png"])
        lookback = probe(os.path.join(self.media, "beat_lookback.png"), "width,height")
        self.assertEqual((lookback["width"], lookback["height"]), (960, 540))
        mp4 = os.path.join(self.media, "relativity-juice.mp4")
        info = streams(mp4)
        self.assertEqual([s["codec_type"] for s in info["streams"]], ["video", "audio"])
        v = probe(mp4, "codec_name,width,height,nb_read_frames")
        self.assertEqual((v["codec_name"], v["width"], v["height"]), ("h264", 1920, 1080))
        self.assertEqual(int(v["nb_read_frames"]), 48 + 360 + 60)  # title 2 s + flight + end 2.5 s
        self.assertEqual(probe(mp4, "codec_name", "a:0")["codec_name"], "aac")
        duration = float(info["format"]["duration"])
        self.assertAlmostEqual(duration, 19.5, delta=0.1)
        audio = probe(mp4, "duration", "a:0")
        self.assertAlmostEqual(float(audio["duration"]), duration, delta=0.05)
        c = probe(os.path.join(self.media, "contact.png"), "width,height")
        self.assertEqual((c["width"], c["height"]), (4 * 320, 3 * 180))  # 12 thumbnails, 4x3 of the flight only
        self.assertGreater(os.path.getsize(os.path.join(self.media, "preview.gif")), 0)
