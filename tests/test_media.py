import filecmp
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from src.encode import tool
from src.media import REAR_END, REAR_START, composite, make_media


def lavfi_frames(out, n):
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=24",
                    "-frames:v", str(n), "-pix_fmt", "rgba", os.path.join(out, "%04d.png")], check=True)  # Blender's frames are RGBA


def rear_frames(out, first=REAR_START, last=REAR_END):
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "color=c=0xc02010:size=64x36:rate=24",
                    "-frames:v", str(last - first + 1), "-start_number", str(first), os.path.join(out, "%04d.png")], check=True)


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
        os.makedirs(self.stills)
        os.makedirs(self.cards)
        for name in ("beat_cruise.png", "beat_build.png", "city.png"):
            open(os.path.join(self.stills, name), "w").close()
        for name, src in (("title.png", "color=c=0x101820"), ("end.png", "color=c=0x201018")):
            subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", src + ":size=64x36",
                            "-frames:v", "1", os.path.join(self.cards, name)], check=True)

    def test_refuses_unless_all_360_frames_exist(self):
        lavfi_frames(self.frames, 359)
        rear_frames(self.rear)
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards, self.rear)
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_one_frame_is_missing_in_the_middle(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.frames, "0100.png"))
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards, self.rear)

    def test_refuses_when_a_card_is_missing(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.cards, "end.png"))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards, self.rear)
        self.assertIn("bun run cards", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_a_rear_frame_is_missing(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        os.remove(os.path.join(self.rear, "%04d.png" % ((REAR_START + REAR_END) // 2)))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards, self.rear)
        self.assertIn("bun run rear", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_composite_overlays_the_window_and_copies_the_rest(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        out = os.path.join(self.dir, "out")
        composite(self.frames, self.rear, out)
        self.assertEqual(sorted(os.listdir(out)), ["%04d.png" % f for f in range(1, 361)])
        for f in (1, REAR_START - 1, REAR_END + 1, 360):
            with self.subTest(frame=f):
                self.assertTrue(filecmp.cmp(os.path.join(self.frames, "%04d.png" % f), os.path.join(out, "%04d.png" % f), shallow=False))
        mid = "%04d.png" % ((REAR_START + REAR_END) // 2)
        for name in (mid, "0001.png"):  # one pixel format all through, or the cut's concat stalls
            self.assertEqual(probe(os.path.join(out, name), "pix_fmt")["pix_fmt"], "rgba")
        self.assertNotEqual(top_right(os.path.join(self.frames, mid)), top_right(os.path.join(out, mid)))
        self.assertEqual(top_right(os.path.join(self.frames, "0001.png")), top_right(os.path.join(out, "0001.png")))

    def test_makes_mp4_contact_sheet_and_copies_beats(self):
        lavfi_frames(self.frames, 360)
        rear_frames(self.rear)
        make_media(self.frames, self.stills, self.media, self.cards, self.rear)
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
