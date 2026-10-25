import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import bpy
import numpy as np

import src.city
from src.city import OVERHANG
from src.encode import encode, tool
from src.flight import FRAME_END, FRAME_START
from src.render import build_scene, render_frames
from src.status import status


def tiny(scene, out, frames, width=64, height=36):
    return render_frames(scene, out, frames, width, height, 1, "cpu", False)


def read(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=float).reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return px


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def png(self, f):
        return os.path.join(self.dir, "%04d.png" % f)

    def test_resume_only_rerenders_missing(self):
        scene = build_scene(length=300.0)
        self.assertEqual(tiny(scene, self.dir, [1, 2, 3]), [1, 2, 3])
        self.assertEqual(sorted(os.listdir(self.dir)), ["0001.png", "0002.png", "0003.png"])
        os.remove(self.png(2))
        m1, m3 = os.stat(self.png(1)).st_mtime_ns, os.stat(self.png(3)).st_mtime_ns
        self.assertEqual(tiny(scene, self.dir, [1, 2, 3]), [2])
        self.assertEqual(sorted(os.listdir(self.dir)), ["0001.png", "0002.png", "0003.png"])
        self.assertEqual((os.stat(self.png(1)).st_mtime_ns, os.stat(self.png(3)).st_mtime_ns), (m1, m3))

    def test_gauge_changes_between_frames(self):
        scene = build_scene(length=300.0)
        scene.objects["City"].hide_render = True  # only the gauge is left to change
        tiny(scene, self.dir, [FRAME_START, FRAME_END], 320, 180)
        a, b = (read(self.png(f))[:60, :200, :3] for f in (FRAME_START, FRAME_END))  # lower-left, rows from the bottom
        self.assertGreater(a.max(), 0.0)  # the gauge is in the crop
        self.assertGreater(np.abs(a - b).mean(), 0.005)

    def test_motion_blur_is_on_and_moves_the_warped_city(self):
        scene = build_scene(length=1200.0)
        self.assertTrue(scene.render.use_motion_blur)
        self.assertLessEqual(scene.render.motion_blur_shutter, 0.5)  # a smear, not mush
        out = {}
        for on in (True, False):
            scene.render.use_motion_blur = on
            d = os.path.join(self.dir, str(on))
            render_frames(scene, d, [300], 96, 54, 8, "cpu", False)
            out[on] = read(os.path.join(d, "0300.png"))[..., :3]
        self.assertGreater(np.abs(out[True] - out[False]).mean(), 0.003)

    def test_forward_view_never_sees_the_backdrop_behind_the_start(self):
        build = src.city._building
        skip_wall = lambda m, rng, x0, y0, *a: None if y0 < -OVERHANG else build(m, rng, x0, y0, *a)
        out = {}
        for wall in (True, False):
            with mock.patch("src.city._building", build if wall else skip_wall):
                scene = build_scene(length=1200.0)
            d = os.path.join(self.dir, str(wall))
            render_frames(scene, d, [1, 138, 300, 360], 96, 54, 4, "cpu", False)
            out[wall] = [read(os.path.join(d, "%04d.png" % f)) for f in (1, 138, 300, 360)]
        # not bit-identical: extra emitters shift Cycles' sampling a little. Measured mean |diff| 0.0046 / 0.0014 / 0.0001 / 0.0001
        # at frames 1 / 138 / 300 / 360, scattered over the frame with a zero mean, against 0.03 to 0.05 for a change of seed
        for a, b in zip(out[True], out[False]):
            self.assertLess(float(np.abs(a - b).mean()), 0.01)

    def test_gauge_follows_frame_when_rendering(self):
        scene = build_scene(length=300.0)
        tiny(scene, self.dir, [FRAME_END])
        self.assertIn("0.999", bpy.data.objects["GaugeText"].data.body)
        self.assertTrue(scene.render.use_lock_interface)


class EncodeTest(unittest.TestCase):
    def test_360_frames_make_15s_1080p_h264(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        frames, mp4 = os.path.join(d, "frames"), os.path.join(d, "out.mp4")
        os.mkdir(frames)
        subprocess.run([tool("ffmpeg"), "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=24",
                        "-frames:v", "360", os.path.join(frames, "%04d.png")], check=True)
        encode(frames, mp4)
        probe = subprocess.run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-count_frames",
                                "-show_entries", "stream=codec_name,pix_fmt,width,height,nb_read_frames:format=duration",
                                "-of", "json", mp4], check=True, capture_output=True, text=True)
        info = json.loads(probe.stdout)
        s = info["streams"][0]
        self.assertEqual((s["codec_name"], s["pix_fmt"], s["width"], s["height"]), ("h264", "yuv420p", 1920, 1080))
        self.assertEqual(int(s["nb_read_frames"]), 360)
        self.assertAlmostEqual(float(info["format"]["duration"]), 15.0, delta=0.1)


class StatusTest(unittest.TestCase):
    def test_counts_frames_and_dead_process(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        for f in (1, 2, 3, 4, 5):
            open(os.path.join(d, "%04d.png" % f), "w").close()
        open(os.path.join(d, "0006.part"), "w").close()  # a half-written frame is not done
        log = os.path.join(d, "render.log")
        with open(log, "w") as fh:
            fh.write("render: frame 4 10.00s\nrender: frame 5 20.00s\n")
        pid = os.path.join(d, "render.pid")
        with open(pid, "w") as fh:
            fh.write(str(os.getpid()))
        out = status(d, log, pid)
        self.assertIn("5/360", out)
        self.assertIn("render running", out)
        self.assertIn("render: frame 5 20.00s", out)
        self.assertIn("eta", out)
        with open(pid, "w") as fh:
            fh.write("999999999")
        self.assertIn("not running", status(d, log, pid))
        empty = os.path.join(d, "empty")
        self.assertIn("0/360", status(empty, os.path.join(empty, "x.log"), os.path.join(empty, "x.pid")))
