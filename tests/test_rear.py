import math
import os
import shutil
import tempfile
import unittest
from unittest import mock

import bpy
import numpy as np
from mathutils import Vector

from src.flight import time_of
from src.media import REAR_END, REAR_START
from src.rear import EXPOSURE_MAX, add_rear, exposure_stops, label_text
from src.relativity import beta_at, gamma
from src.render import build_scene, render_frames
from tests.test_look import frame_for
from tests.test_render import read

W, H = 96, 54
READABLE = 0.05  # mean luminance; set from the probe in the README (0.1c view 0.152, uncompensated 0.9c view 0.015)
LUM = np.array([0.2126, 0.7152, 0.0722])


def stats(px):
    """(mean luminance, mean R / mean B) of an RGBA image."""
    rgb = px[..., :3].reshape(-1, 3)
    return float((rgb @ LUM).mean()), float(rgb[:, 0].mean() / max(rgb[:, 2].mean(), 1e-9))


class RearTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.scene = build_scene(length=1200.0)
        cls.flight = cls.scene.camera
        cls.rear_cam = add_rear(cls.scene)
        for o in bpy.data.objects:
            if o.name.startswith("Rear") and o.name != "RearCam":
                o.hide_render = True  # judge the city alone, not the label
        cls.rear, cls.raw, cls.fwd = {}, {}, {}
        for beta in (0.1, 0.35, 0.9, 0.999):
            f = frame_for(beta)
            for cam, store, gain in ((cls.flight, cls.fwd, True), (cls.rear_cam, cls.raw, False), (cls.rear_cam, cls.rear, True)):
                cls.scene.camera = cam
                d = os.path.join(cls.dir, "%s%d" % (cam.name, gain))
                with mock.patch("src.rear.exposure_stops", (lambda b: exposure_stops(b)) if gain else (lambda b: 0.0)):
                    render_frames(cls.scene, d, [f], W, H, 4, "cpu", False)
                store[beta] = stats(read(os.path.join(d, "%04d.png" % f)))
            print("rear beta=%g frame=%d rear lum=%.4f R/B=%.3f (no gain %.4f) forward lum=%.4f R/B=%.3f"
                  % ((beta, f) + cls.rear[beta] + (cls.raw[beta][0],) + cls.fwd[beta]))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_rear_cam_looks_back_from_the_flight_camera(self):
        self.scene.frame_set(200)
        bpy.context.view_layer.update()
        fwd = self.flight.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        back = self.rear_cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        self.assertAlmostEqual(fwd.y, 1.0, places=5)
        self.assertAlmostEqual(back.y, -1.0, places=5)
        for a, b in zip(self.rear_cam.matrix_world.translation, self.flight.matrix_world.translation):
            self.assertAlmostEqual(a, b, places=5)

    def test_gauge_is_hidden_from_the_rear_view(self):
        self.assertTrue(all(o.hide_render for o in bpy.data.objects if o.name.startswith("Gauge")))

    def test_uncompensated_rear_dims_as_beta_rises(self):
        low = self.raw[0.1][0]
        self.assertLess(self.raw[0.35][0], 0.5 * low)
        self.assertLess(self.raw[0.9][0], 0.2 * low)  # without the gain only the dim deep-red infrared is left

    def test_rear_is_redder_than_forward(self):
        self.assertGreater(self.rear[0.35][1], 1.5 * self.fwd[0.35][1])

    def test_exposure_compensation_keeps_09c_readable_and_red(self):
        self.assertGreaterEqual(self.rear[0.9][0], READABLE)
        self.assertGreater(self.rear[0.9][0], 3 * self.raw[0.9][0])
        self.assertGreater(self.rear[0.9][1], 1.2 * self.fwd[0.9][1])

    def test_forward_is_brighter_than_uncompensated_rear_at_high_beta(self):
        for beta in (0.9, 0.999):
            with self.subTest(beta=beta):
                self.assertGreater(self.fwd[beta][0], 2 * self.raw[beta][0])

    def test_gain_follows_d_and_is_capped(self):
        self.assertAlmostEqual(exposure_stops(0.9), -1.25 * math.log2(1 / (gamma(0.9) * 1.9)), places=6)
        self.assertGreater(exposure_stops(0.9), exposure_stops(0.35))
        self.assertLess(exposure_stops(0.1), 1.0)
        self.assertEqual(exposure_stops(0.999), EXPOSURE_MAX)

    def test_gain_only_applies_to_the_rear_camera(self):
        self.scene.camera = self.flight
        self.scene.frame_set(frame_for(0.9))
        self.assertEqual(self.scene.view_settings.exposure, 0.0)
        self.scene.camera = self.rear_cam
        self.scene.frame_set(frame_for(0.9))
        self.assertAlmostEqual(self.scene.view_settings.exposure, exposure_stops(beta_at(time_of(frame_for(0.9)))), places=5)

    def test_label_shows_d_and_the_exposure(self):
        text = label_text(0.9)
        self.assertIn("LOOKING BACK", text)
        self.assertIn("D = 0.229", text)
        self.assertIn("exposure +%.1f stops" % exposure_stops(0.9), text)

    def test_window_ends_at_the_first_frame_at_09c(self):
        beta = lambda f: beta_at(time_of(f))
        self.assertGreaterEqual(beta(REAR_END), 0.9)
        self.assertLess(beta(REAR_END - 1), 0.9)
        self.assertEqual(REAR_START, 13)
