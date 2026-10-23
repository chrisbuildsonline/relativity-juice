import unittest

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from src.city import build_city, setup_view
from src.flight import FRAME_END, FRAME_START, time_of
from src.gauge import BAR_W, GLOW, add_gauge, gauge_text
from src.relativity import beta_at, gamma
from src.warp import add_warp, animate_flight

FRAMES = (FRAME_START, 180, FRAME_END)


class GaugeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.scene = bpy.context.scene
        cls.city = build_city(seed=7, length=600.0)
        setup_view(cls.scene)
        cls.cam = cls.scene.camera
        add_warp(cls.city, cls.cam)
        animate_flight(cls.scene, cls.city, cls.cam)
        cls.before = cls._city_vertices()
        add_gauge(cls.scene, cls.cam)

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    # add_gauge rebuilds its objects, so look them up fresh each time
    @property
    def text(self):
        return bpy.data.objects["GaugeText"]

    @property
    def bar(self):
        return bpy.data.objects["GaugeBar"]

    @property
    def objs(self):
        return [o for o in bpy.data.objects if o.name.startswith("Gauge")]

    @classmethod
    def _city_vertices(cls):
        ev = cls.city.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return len(ev.data.vertices)

    def test_text_format(self):
        self.assertEqual(gauge_text(0.999), "β = 0.999c\nγ = %.2f" % gamma(0.999))

    def test_text_follows_frame(self):
        for f in FRAMES:
            with self.subTest(frame=f):
                self.scene.frame_set(f)
                beta = beta_at(time_of(f))
                self.assertEqual(self.text.data.body, gauge_text(beta))
                self.assertIn("%.3f" % beta, self.text.data.body)
                self.assertIn("%.2f" % gamma(beta), self.text.data.body)

    def test_bar_tracks_beta(self):
        for f in FRAMES:
            with self.subTest(frame=f):
                self.scene.frame_set(f)
                self.assertAlmostEqual(self.bar.scale.x, BAR_W * beta_at(time_of(f)), places=5)

    def test_parented_and_unwarped(self):
        self.assertGreaterEqual(len(self.objs), 3)
        for o in self.objs:
            self.assertIs(o.parent, self.cam)
            self.assertIsNot(o, self.city)
            self.assertNotIn("Warp", o.modifiers)

    def test_city_untouched(self):
        self.assertEqual(self._city_vertices(), self.before)
        self.assertEqual([m.name for m in self.city.modifiers], ["Warp"])

    def test_in_camera_view(self):
        for f in FRAMES:
            self.scene.frame_set(f)
            bpy.context.view_layer.update()
            for o in self.objs:
                with self.subTest(frame=f, obj=o.name):
                    p = world_to_camera_view(self.scene, self.cam, o.matrix_world.translation)
                    self.assertTrue(0.0 < p.x < 1.0 and 0.0 < p.y < 1.0 and p.z > 0.0, tuple(p))

    def test_compact_with_margin_from_frame_edges(self):
        for f in FRAMES:
            self.scene.frame_set(f)
            bpy.context.view_layer.update()
            pts = [world_to_camera_view(self.scene, self.cam, o.matrix_world @ Vector(c))
                   for o in self.objs for c in o.bound_box]
            x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
            y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
            with self.subTest(frame=f):
                self.assertGreaterEqual(x0, 0.04)
                self.assertGreaterEqual(y0, 0.04)
                self.assertLess(x1, 0.5)
                self.assertLessEqual(y1 - y0, 0.2)

    def test_panel_is_a_translucent_backing_not_a_black_plate(self):
        tree = bpy.data.objects["GaugePanel"].data.materials[0].node_tree
        self.assertIn("ShaderNodeBsdfTransparent", {n.bl_idname for n in tree.nodes})
        mix = [n for n in tree.nodes if n.bl_idname == "ShaderNodeMixShader"][0]
        self.assertLess(mix.inputs["Fac"].default_value, 0.98)  # some of the frame always shows through
        self.assertGreater(mix.inputs["Fac"].default_value, 0.0)

    def test_frame_is_one_gauge_colour(self):
        glow = [n for n in bpy.data.objects["GaugeFrame"].data.materials[0].node_tree.nodes
                if n.bl_idname == "ShaderNodeEmission"][0]
        self.assertGreater(glow.inputs["Strength"].default_value, 0.0)
        for got, want in zip(glow.inputs["Color"].default_value, GLOW):
            self.assertAlmostEqual(got, want, places=5)

    def test_bundled_font(self):
        font = self.text.data.font
        self.assertEqual(font.filepath, "<builtin>")
        self.assertEqual([f.filepath for f in bpy.data.fonts], ["<builtin>"])

    def test_no_duplicate_handlers(self):
        add_gauge(self.scene, self.cam)
        add_gauge(self.scene, self.cam)
        mine = [h for h in bpy.app.handlers.frame_change_pre if h.__module__ == "src.gauge"]
        self.assertEqual(len(mine), 1)
        self.assertEqual(len([o for o in bpy.data.objects if o.name.startswith("GaugeText")]), 1)
