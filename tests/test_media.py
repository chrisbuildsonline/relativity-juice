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


def probe(path, entries):
    r = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_frames",
                        "-show_entries", "stream=" + entries, "-of", "json", path],
                       check=True, capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]


class MediaTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.frames = os.path.join(self.dir, "frames")
        self.stills = os.path.join(self.dir, "stills")
        self.media = os.path.join(self.dir, "media")
        os.makedirs(self.stills)
        for name in ("beat_cruise.png", "beat_build.png", "city.png"):
            open(os.path.join(self.stills, name), "w").close()

    def test_refuses_unless_all_360_frames_exist(self):
        lavfi_frames(self.frames, 359)
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media)
        self.assertFalse(os.path.exists(os.path.join(self.media, "relativity-juice.mp4")))

    def test_refuses_when_one_frame_is_missing_in_the_middle(self):
        lavfi_frames(self.frames, 360)
        os.remove(os.path.join(self.frames, "0100.png"))
        with self.assertRaises(SystemExit):
            make_media(self.frames, self.stills, self.media)

    def test_makes_mp4_contact_sheet_and_copies_beats(self):
        lavfi_frames(self.frames, 360)
        make_media(self.frames, self.stills, self.media)
        self.assertEqual(sorted(os.listdir(self.media)),
                         ["beat_build.png", "beat_cruise.png", "contact.png", "relativity-juice.mp4"])
        v = probe(os.path.join(self.media, "relativity-juice.mp4"), "codec_name,width,height,nb_read_frames")
        self.assertEqual((v["codec_name"], v["width"], v["height"], int(v["nb_read_frames"])), ("h264", 1920, 1080, 360))
        c = probe(os.path.join(self.media, "contact.png"), "width,height")
        self.assertEqual((c["width"], c["height"]), (4 * 320, 3 * 180))  # 12 thumbnails, 4x3
