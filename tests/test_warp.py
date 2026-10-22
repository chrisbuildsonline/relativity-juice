import time
import unittest

import bpy
import numpy as np

from src.city import build_city, setup_view
from src.flight import FRAME_END, FRAME_START, camera_y, time_of
from src.relativity import aberrate, beta_at, doppler, gamma
from src.warp import animate_flight, add_warp, set_beta

LENGTH = 600.0
CAM_Y = 250.0


def _co(mesh):
    n = len(mesh.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    return co.reshape(n, 3).astype(np.float64)


def _evaluated(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    pos = _co(mesh)
    attr = mesh.attributes["doppler"]
    d = np.empty(len(attr.data), dtype=np.float32)
    attr.data.foreach_get("value", d)
    n = len(mesh.vertices)
    ev.to_mesh_clear()
    return pos, d.astype(np.float64), n


class WarpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.scene = bpy.context.scene
        cls.city = build_city(seed=7, length=LENGTH)
        setup_view(cls.scene, CAM_Y)
        cls.cam = cls.scene.camera
        cls.rest = _co(cls.city.data)
        add_warp(cls.city, cls.cam)
        cls.cam_pos = np.array(cls.cam.location, dtype=np.float32).astype(np.float64)
        t = time.perf_counter()
        _evaluated(cls.city)
        cls.eval_s = time.perf_counter() - t
        print("warp evaluate %.2fs for %d vertices" % (cls.eval_s, len(cls.rest)))

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _at(self, beta):
        set_beta(self.city, beta)
        pos, d, n = _evaluated(self.city)
        b = float(np.float32(beta))
        return pos, d, n, b

    def test_topology_unchanged(self):
        for beta in (0.0, 0.9):
            self.assertEqual(self._at(beta)[2], len(self.rest))

    def test_beta_zero_is_identity(self):
        pos, d, _, _ = self._at(0.0)
        self.assertLess(np.abs(pos - self.rest).max(), 1e-4)
        self.assertLess(np.abs(d - 1.0).max(), 1e-6)

    def test_aberration_matches_numpy(self):
        v = self.rest - self.cam_pos
        r = np.linalg.norm(v, axis=1)
        dirs = v / r[:, None]
        for beta in (0.1, 0.5, 0.9, 0.999):
            with self.subTest(beta=beta):
                pos, _, _, b = self._at(beta)
                v2 = pos - self.cam_pos
                r2 = np.linalg.norm(v2, axis=1)
                app = v2 / r2[:, None]
                err = np.abs(app - aberrate(dirs, b)).max()
                self.assertLess(err, 1e-4, "max dir error %g" % err)
                self.assertLess(np.abs(r2 / r - 1.0).max(), 1e-5)

    def test_doppler_attribute_matches_numpy(self):
        for beta in (0.1, 0.5, 0.9, 0.999):
            with self.subTest(beta=beta):
                pos, d, _, b = self._at(beta)
                v2 = pos - self.cam_pos
                cos_obs = v2[:, 1] / np.linalg.norm(v2, axis=1)
                rel = np.abs(d / doppler(cos_obs, b) - 1.0).max()
                self.assertLess(rel, 1e-4, "max doppler rel error %g" % rel)

    def test_warp_compresses_view_forward(self):
        pos, _, _, _ = self._at(0.9)
        v = self.rest - self.cam_pos
        v2 = pos - self.cam_pos
        cos0 = v[:, 1] / np.linalg.norm(v, axis=1)
        cos1 = v2[:, 1] / np.linalg.norm(v2, axis=1)
        self.assertGreater(np.mean(cos1 >= cos0 - 1e-6), 0.999)
        self.assertGreater(np.count_nonzero(cos0 < 0.0), 100)
        self.assertGreater(np.count_nonzero(cos1 > 0.0), np.count_nonzero(cos0 > 0.0))


class FlightWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.scene = bpy.context.scene
        cls.city = build_city(seed=7, length=LENGTH)
        setup_view(cls.scene)
        add_warp(cls.city, cls.scene.camera)
        animate_flight(cls.scene, cls.city, cls.scene.camera)

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_scene_timing(self):
        s = self.scene
        self.assertEqual((s.render.fps, s.frame_start, s.frame_end), (24, FRAME_START, FRAME_END))

    def test_beta_and_camera_follow_frame(self):
        mod = self.city.modifiers["Warp"]
        key = mod.node_group.interface.items_tree["Beta"].identifier
        for f in (1, 90, 180, 270, 360):
            self.scene.frame_set(f)
            t = time_of(f)
            self.assertAlmostEqual(mod[key], beta_at(t), places=5)
            self.assertAlmostEqual(self.scene.camera.location.y, camera_y(t), places=2)
            self.assertAlmostEqual(self.scene.camera.location.x, 0.0)

    def test_gamma_is_consistent(self):
        self.assertGreater(gamma(beta_at(time_of(360))), 20.0)

    def test_linear_keyframes_every_frame(self):
        fc = self.scene.camera.animation_data.action.fcurves.find("location", index=1)
        self.assertEqual(len(fc.keyframe_points), FRAME_END - FRAME_START + 1)
        self.assertTrue(all(k.interpolation == "LINEAR" for k in fc.keyframe_points))


class WarpMaterialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.tree = build_city(seed=7, length=100.0).data.materials[0].node_tree

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    @staticmethod
    def _src(sock):
        return sock.links[0].from_node

    def test_wavelength_fed_from_clamped_base_over_doppler(self):
        wl = [n for n in self.tree.nodes if n.bl_idname == "ShaderNodeWavelength"]
        self.assertEqual(len(wl), 1)
        clamp = self._src(wl[0].inputs["Wavelength"])
        self.assertEqual(clamp.bl_idname, "ShaderNodeClamp")
        self.assertEqual((clamp.inputs["Min"].default_value, clamp.inputs["Max"].default_value), (380.0, 780.0))
        div = self._src(clamp.inputs["Value"])
        self.assertEqual((div.bl_idname, div.operation), ("ShaderNodeMath", "DIVIDE"))
        names = {self._src(div.inputs[0]).attribute_name, self._src(div.inputs[1]).attribute_name}
        self.assertEqual(names, {"base_nm", "doppler"})
        self.assertEqual(self._src(div.inputs[0]).attribute_name, "base_nm")

    def test_uv_and_ir_handling_reaches_emission(self):
        glow = [n for n in self.tree.nodes if n.bl_idname == "ShaderNodeEmission"][0]
        ir = self._src(glow.inputs["Color"])
        self.assertEqual(ir.bl_idname, "ShaderNodeMix")
        uv = self._src(ir.inputs[7])  # RGBA B
        self.assertEqual(uv.bl_idname, "ShaderNodeMix")
        self.assertEqual(tuple(round(c, 3) for c in uv.inputs[7].default_value[:3]), (0.85, 0.8, 1.0))

    def test_strength_is_emit_times_capped_beaming(self):
        glow = [n for n in self.tree.nodes if n.bl_idname == "ShaderNodeEmission"][0]
        mul = self._src(glow.inputs["Strength"])
        self.assertEqual(mul.operation, "MULTIPLY")
        srcs = [self._src(mul.inputs[0]), self._src(mul.inputs[1])]
        emit = [n for n in srcs if n.bl_idname == "ShaderNodeAttribute"][0]
        cap = [n for n in srcs if n.bl_idname == "ShaderNodeMath"][0]
        self.assertEqual(emit.attribute_name, "emit")
        self.assertEqual(cap.operation, "MINIMUM")
        power = [self._src(i) for i in cap.inputs[:2] if i.links][0]
        self.assertEqual(power.operation, "POWER")
        self.assertEqual(self._src(power.inputs[0]).attribute_name, "doppler")
        self.assertEqual(power.inputs[1].default_value, 4.0)
        self.assertGreater(cap.inputs[1].default_value, 1.0)


class ViewTransformTest(unittest.TestCase):
    def test_agx_view_transform(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.view_settings.view_transform = "Standard"
        setup_view(scene)
        self.assertEqual(scene.view_settings.view_transform, "AgX")
