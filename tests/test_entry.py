import json
import os
import subprocess
import unittest

from src.encode import tool
from tests.test_render import read

MEDIA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")


class EntryFilesTest(unittest.TestCase):
    def test_video_meets_the_contest_rules(self):
        mp4 = os.path.join(MEDIA, "relativity-juice.mp4")
        self.assertTrue(os.path.isfile(mp4))
        probe = subprocess.run([tool("ffprobe"), "-v", "error", "-show_entries",
                                "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
                                "-of", "json", mp4], check=True, capture_output=True, text=True)
        info = json.loads(probe.stdout)
        video = [s for s in info["streams"] if s["codec_type"] == "video"]
        self.assertEqual([s["codec_type"] for s in info["streams"]], ["video", "audio"])
        self.assertEqual((video[0]["codec_name"], video[0]["width"], video[0]["height"], video[0]["r_frame_rate"]),
                         ("h264", 1920, 1080, "24/1"))
        self.assertEqual(info["streams"][1]["codec_name"], "aac")
        duration = float(info["format"]["duration"])
        self.assertTrue(5 <= duration <= 30)
        self.assertAlmostEqual(duration, 2.0 + 15.0 + 2.5, delta=0.1)  # title + flight + end card

    def test_preview_gif_is_small(self):
        gif = os.path.join(MEDIA, "preview.gif")
        self.assertTrue(os.path.isfile(gif))
        self.assertLess(os.path.getsize(gif), 8 * 1024 * 1024)

    def test_wip_screenshot_is_a_real_picture(self):
        wip = os.path.join(MEDIA, "wip.png")
        self.assertTrue(os.path.isfile(wip))
        px = read(wip)
        self.assertGreaterEqual(px.shape[1], 800)
        self.assertGreater(px[..., :3].std(), 0.02)

    def test_beat_stills_exist(self):
        for name in ("blueshift", "build", "cruise", "singularity"):
            self.assertTrue(os.path.isfile(os.path.join(MEDIA, "beat_%s.png" % name)), name)

    def test_lookback_still_and_cards_are_committed_pngs(self):
        for name in ("beat_lookback.png", "title.png", "end.png"):
            path = os.path.join(MEDIA, name)
            self.assertTrue(os.path.isfile(path), name)
            with open(path, "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n", name)
            px = read(path)
            self.assertGreaterEqual(px.shape[1], 800, name)
            self.assertGreater(os.path.getsize(path), 5000, name)

    def test_readme_describes_the_lookback_inset(self):
        with open(os.path.join(os.path.dirname(MEDIA), "README.md"), encoding="utf-8") as f:
            text = f.read()
        for needle in ("Looking back", "bun run rear", "media/beat_lookback.png", "media/title.png", "media/end.png"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
