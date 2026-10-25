import os
import shutil
import tempfile
import unittest

import bpy
from bpy_extras.object_utils import world_to_camera_view

from src.gauge import BACKING_ALPHA, OVERLAY_PLATE_ALPHA, hud_only
from src.render import build_scene, render_frames
from tests.test_render import read

W, H = 384, 216
FRAME = 300  # late: beta 0.999, the longest digits


def panel_fac():
    mix = [n for n in bpy.data.objects["GaugePanel"].data.materials[0].node_tree.nodes if n.type == "MIX_SHADER"][0]
    return mix.inputs["Fac"].default_value


def panel_box(scene):
    """Pixel box (x0, x1, y0, y1 from the top) of the GaugePanel plate in the render."""
    scene.frame_set(FRAME)
    panel = bpy.data.objects["GaugePanel"]
    pts = [world_to_camera_view(scene, scene.camera, panel.matrix_world @ v.co) for v in panel.data.vertices]
    xs, ys = [p.x * W for p in pts], [(1 - p.y) * H for p in pts]
    return int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys))


class HudTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.scene = build_scene(length=300.0)
        cls.forward_fac = panel_fac()
        hud_only(cls.scene)
        cls.box = panel_box(cls.scene)
        render_frames(cls.scene, cls.dir, [FRAME], W, H, 4, "cpu", False)
        cls.px = read(os.path.join(cls.dir, "%04d.png" % FRAME))[::-1]  # top row first

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_forward_render_keeps_the_translucent_backing(self):
        self.assertEqual(BACKING_ALPHA, 0.94)
        self.assertAlmostEqual(self.forward_fac, 0.94, places=5)

    def test_overlay_plate_is_opaque(self):
        self.assertEqual(OVERLAY_PLATE_ALPHA, 1.0)
        self.assertAlmostEqual(panel_fac(), OVERLAY_PLATE_ALPHA, places=5)
        x0, x1, y0, y1 = self.box
        self.assertGreaterEqual(self.px[y0 + 3:y1 - 3, x0 + 3:x1 - 3, 3].min(), 0.97)

    def test_transparent_away_from_the_gauge(self):
        x0, x1, y0, y1 = self.box
        self.assertEqual(self.px[:y0 - 4, :, 3].max(), 0.0)  # everything above the gauge: no city
        self.assertEqual(self.px[:, x1 + 4:, 3].max(), 0.0)  # and to its right

    def test_glyphs_are_cyan_on_the_plate(self):
        x0, x1, y0, y1 = self.box
        p = self.px[y0 + 3:y1 - 3, x0 + 3:x1 - 3]
        cyan = (p[..., 2] > 0.3) & (p[..., 1] > 0.15) & (p[..., 0] < 0.5 * p[..., 2])
        self.assertGreater(int(cyan.sum()), 20)

    def test_overlay_setup(self):
        r = self.scene.render
        self.assertTrue(r.film_transparent)
        self.assertEqual(r.image_settings.color_mode, "RGBA")
        self.assertFalse(r.use_motion_blur)
        for o in bpy.data.objects:
            self.assertEqual(o.hide_render, not o.name.startswith("Gauge"), o.name)
