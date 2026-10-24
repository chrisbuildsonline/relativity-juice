import os
import shutil
import tempfile
import unittest

import bpy
import numpy as np
from mathutils import Vector

from src.rear import add_rear
from src.render import build_scene, render_frames
from tests.test_look import frame_for
from tests.test_render import read

W, H = 96, 54
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
        cls.rear, cls.fwd = {}, {}
        for beta in (0.1, 0.35, 0.9, 0.999):
            f = frame_for(beta)
            for cam, store in ((cls.flight, cls.fwd), (cls.rear_cam, cls.rear)):
                cls.scene.camera = cam
                d = os.path.join(cls.dir, cam.name)
                render_frames(cls.scene, d, [f], W, H, 4, "cpu", False)
                store[beta] = stats(read(os.path.join(d, "%04d.png" % f)))
            print("rear beta=%g frame=%d rear lum=%.4f R/B=%.3f forward lum=%.4f R/B=%.3f"
                  % ((beta, f) + cls.rear[beta] + cls.fwd[beta]))

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

    def test_rear_dims_as_beta_rises(self):
        low = self.rear[0.1][0]
        self.assertLess(self.rear[0.35][0], 0.5 * low)
        self.assertLess(self.rear[0.9][0], 0.1 * low)  # only the dark world is left

    def test_rear_is_redder_than_forward(self):
        self.assertGreater(self.rear[0.35][1], 1.5 * self.fwd[0.35][1])

    def test_forward_is_brighter_than_rear_at_high_beta(self):
        for beta in (0.9, 0.999):
            with self.subTest(beta=beta):
                self.assertGreater(self.fwd[beta][0], 2 * self.rear[beta][0])
