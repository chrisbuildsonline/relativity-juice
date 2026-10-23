import json
import os
import shutil
import subprocess
import tempfile
import unittest

from src.encode import tool
from src.media import make_media


def lavfi_frames(out, n):
    os.makedirs(out, exist_ok=True)
    subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=24",
                    "-frames:v", str(n), os.path.join(out, "%04d.png")], check=True)


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
        os.makedirs(self.stills)
        os.makedirs(self.cards)
        for name in ("beat_cruise.png", "beat_build.png", "city.png"):
            open(os.path.join(self.stills, name), "w").close()
        for name, src in (("title.png", "color=c=0x101820"), ("end.png", "color=c=0x201018")):
            subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", src + ":size=64x36",
                            "-frames:v", "1", os.path.join(self.cards, name)], check=True)

    def test_refuses_unless_all_360_frames_exist(self):
        lavfi_frames(self.frames, 359)
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards)
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_one_frame_is_missing_in_the_middle(self):
        lavfi_frames(self.frames, 360)
        os.remove(os.path.join(self.frames, "0100.png"))
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media, self.cards)

    def test_refuses_when_a_card_is_missing(self):
        lavfi_frames(self.frames, 360)
        os.remove(os.path.join(self.cards, "end.png"))
        with self.assertRaises(SystemExit) as ctx:
            make_media(self.frames, self.stills, self.media, self.cards)
        self.assertIn("bun run cards", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_makes_mp4_contact_sheet_and_copies_beats(self):
        lavfi_frames(self.frames, 360)
        make_media(self.frames, self.stills, self.media, self.cards)
        self.assertEqual(sorted(os.listdir(self.media)),
                         ["beat_build.png", "beat_cruise.png", "contact.png", "preview.gif", "relativity-juice.mp4"])
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
