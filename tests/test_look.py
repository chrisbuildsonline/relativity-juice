import os
import shutil
import tempfile
import unittest

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from src.flight import FRAME_END, FRAME_START, time_of
from src.relativity import DISPLAY_BEAM_CAP, beta_at
from src.render import build_scene, render_frames
from tests.test_render import read

W, H = 96, 54


def frame_for(beta):
    return min(range(FRAME_START, FRAME_END + 1), key=lambda f: abs(beta_at(time_of(f)) - beta))


def look(px):
    """(fraction of near-clipped pixels, mean saturation of lit pixels) of an RGBA image."""
    rgb = px[..., :3].reshape(-1, 3)
    hi, lo = rgb.max(axis=1), rgb.min(axis=1)
    lit = hi > 0.15
    return float(np.mean(lo > 0.9)), float(np.mean((hi[lit] - lo[lit]) / hi[lit]))


class LookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.scene = build_scene(length=1200.0)
        for o in bpy.data.objects:
            if o.name.startswith("Gauge"):
                o.hide_render = True
        cls.stats = {}
        for beta in (0.1, 0.9, 0.999):
            f = frame_for(beta)
            render_frames(cls.scene, cls.dir, [f], W, H, 4, "cpu", False)
            cls.stats[beta] = look(read(os.path.join(cls.dir, "%04d.png" % f)))
            print("look beta=%g frame=%d clipped=%.3f saturation=%.3f" % ((beta, f) + cls.stats[beta]))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_no_white_out(self):
        for beta in (0.9, 0.999):
            clipped, sat = self.stats[beta]
            with self.subTest(beta=beta):
                self.assertLess(clipped, 0.02)  # was 0.40 / 0.20 before the tone-map
                self.assertGreater(sat, 0.4)  # was 0.02 / 0.18

    def test_gauge_text_reads_cyan(self):
        for o in bpy.data.objects:
            o.hide_render = o.name == "City"
            if o.name == "GaugePanel":
                o.hide_render = True  # judge the text colour alone, not its blend with the plate
        f = frame_for(0.9)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        render_frames(self.scene, d, [f], 320, 180, 1, "cpu", False)
        rgb = read(os.path.join(d, "%04d.png" % f))[..., :3].reshape(-1, 3)
        text = rgb[rgb.max(axis=1) > 0.3]
        self.assertGreater(len(text), 30)
        r, g, b = text.mean(axis=0)
        self.assertGreater(g, 1.6 * r)
        self.assertGreater(b, 1.6 * r)

    def test_gauge_legible_over_a_blazing_frame(self):
        scene, cam = self.scene, self.scene.camera
        for o in bpy.data.objects:
            o.hide_render = o.name == "City"
        glare = bpy.data.objects.new("Glare", bpy.data.meshes.new("Glare"))  # emit 14 x beam cap 2, filling the frame
        glare.data.from_pydata([(-40, -40, 0), (40, -40, 0), (40, 40, 0), (-40, 40, 0)], [], [(0, 1, 2, 3)])
        mat = bpy.data.materials.new("Glare")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()
        glow, out = nodes.new("ShaderNodeEmission"), nodes.new("ShaderNodeOutputMaterial")
        glow.inputs["Strength"].default_value = 14.0 * DISPLAY_BEAM_CAP
        mat.node_tree.links.new(glow.outputs[0], out.inputs["Surface"])
        glare.data.materials.append(mat)
        glare.parent, glare.location = cam, (0, 0, -9)
        scene.collection.objects.link(glare)
        self.addCleanup(bpy.data.objects.remove, glare)
        f = frame_for(0.9)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        w, h = 640, 360
        render_frames(scene, d, [f], w, h, 1, "cpu", False)
        px = read(os.path.join(d, "%04d.png" % f))[..., :3]
        bpy.context.view_layer.update()
        corners = [world_to_camera_view(scene, cam, bpy.data.objects["GaugePanel"].matrix_world @ Vector(c))
                   for c in bpy.data.objects["GaugePanel"].bound_box]
        x0, x1 = min(p.x for p in corners), max(p.x for p in corners)
        y0, y1 = min(p.y for p in corners), max(p.y for p in corners)

        def region(fx0, fx1, fy0, fy1):
            xs = slice(int((x0 + fx0 * (x1 - x0)) * w), int((x0 + fx1 * (x1 - x0)) * w))
            ys = slice(int((y0 + fy0 * (y1 - y0)) * h), int((y0 + fy1 * (y1 - y0)) * h))
            return px[ys, xs].reshape(-1, 3)

        lum = lambda c: c @ np.array([0.2126, 0.7152, 0.0722])  # noqa: E731
        plate = lum(region(0.8, 0.97, 0.35, 0.95)).mean()  # right of the glyphs, above the bar
        self.assertLess(plate, 0.1)
        zone = region(0.03, 0.65, 0.35, 0.95)
        text = zone[zone.max(axis=1) > 0.25]
        self.assertGreater(len(text), 30)
        self.assertGreater(lum(text).mean(), 4.0 * max(plate, 0.01))
        r, g, b = text.mean(axis=0)
        self.assertGreater(g, 1.6 * r)
        self.assertGreater(b, 1.6 * r)

    def test_slow_flight_stays_colourful(self):
        clipped, sat = self.stats[0.1]
        self.assertLess(clipped, 0.02)
        self.assertGreater(sat, 0.55)  # 0.71 now
