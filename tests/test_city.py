import hashlib
import math
import time
import unittest

import bpy
import mathutils
import numpy as np

from src.city import CAM_Z, CORRIDOR_R, build_city, setup_view

LENGTH = 2000.0


def _coords(obj):
    n = len(obj.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def _vhash(obj):
    return hashlib.sha1(np.round(_coords(obj), 3).tobytes()).hexdigest()


def _attr(obj, name):
    a = obj.data.attributes[name]
    out = np.empty(len(a.data), dtype=np.float64)
    a.data.foreach_get("value", out)
    return out


class CityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        t = time.perf_counter()
        cls.obj = build_city(seed=7, length=LENGTH)
        cls.build_s = time.perf_counter() - t
        cls.co = _coords(cls.obj)
        n_edges = len(cls.obj.data.edges)
        e = np.empty(n_edges * 2, dtype=np.int64)
        cls.obj.data.edges.foreach_get("vertices", e)
        cls.edges = e.reshape(-1, 2)

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_single_mesh_object_named_city(self):
        self.assertEqual(self.obj.name, "City")
        self.assertEqual(self.obj.type, "MESH")
        self.assertEqual(len(bpy.data.objects), 1)

    def test_buildings_on_both_sides_with_varied_heights(self):
        co = self.co
        tall = co[:, 2] > 20
        self.assertGreater(np.count_nonzero(tall & (co[:, 0] > 0)), 1000)
        self.assertGreater(np.count_nonzero(tall & (co[:, 0] < 0)), 1000)
        self.assertGreater(co[:, 2].max(), 100.0)
        tops = np.unique(np.round(co[:, 2][tall], 1))
        self.assertGreater(len(tops), 20)

    def test_buildings_extend_behind_and_ahead(self):
        co = self.co
        tall = co[:, 2] > 20
        self.assertLess(co[tall, 1].min(), -100.0)
        self.assertGreater(co[tall, 1].max(), LENGTH + 100.0)

    def test_dark_ground_with_neon_lines(self):
        co = self.co
        emit = _attr(self.obj, "emit")
        ground = np.isclose(co[:, 2], 0.05)
        self.assertGreater(np.count_nonzero(ground), 100)
        self.assertTrue(np.all(emit[ground] > 0))
        flat = np.isclose(co[:, 2], 0.0)
        self.assertGreater(np.count_nonzero(flat), 1000)
        self.assertTrue(np.all(emit[flat] == 0))

    def test_base_nm_attribute_range(self):
        nm = _attr(self.obj, "base_nm")
        emit = _attr(self.obj, "emit")
        self.assertEqual(self.obj.data.attributes["base_nm"].data_type, "FLOAT")
        self.assertEqual(self.obj.data.attributes["base_nm"].domain, "POINT")
        lit = emit > 0
        self.assertGreater(np.count_nonzero(lit), 1000)
        self.assertGreaterEqual(nm[lit].min(), 420.0)
        self.assertLessEqual(nm[lit].max(), 680.0)
        self.assertGreater(np.count_nonzero(~lit), 1000)

    def test_material_reads_base_nm_through_wavelength_to_emission(self):
        mats = self.obj.data.materials
        self.assertGreaterEqual(len(mats), 1)
        tree = mats[0].node_tree
        wl = [n for n in tree.nodes if n.bl_idname == "ShaderNodeWavelength"]
        self.assertEqual(len(wl), 1)
        src = wl[0].inputs["Wavelength"].links[0].from_node
        self.assertEqual(src.bl_idname, "ShaderNodeAttribute")
        self.assertEqual(src.attribute_name, "base_nm")
        dest = wl[0].outputs["Color"].links[0].to_node
        self.assertEqual(dest.bl_idname, "ShaderNodeEmission")
        strength = dest.inputs["Strength"].links[0].from_node
        self.assertEqual(strength.attribute_name, "emit")

    def test_procedural_only(self):
        self.assertEqual(len(bpy.data.images), 0)
        self.assertEqual(len(bpy.data.libraries), 0)
        for m in bpy.data.materials:
            self.assertTrue(m.use_nodes)
            for n in m.node_tree.nodes:
                self.assertNotEqual(n.bl_idname, "ShaderNodeTexImage")

    def test_flight_corridor_clear(self):
        co = self.co
        d = np.hypot(co[:, 0], co[:, 2] - CAM_Z)
        self.assertGreaterEqual(d.min(), CORRIDOR_R)

    def test_vertex_budget(self):
        self.assertLessEqual(len(self.co), 300_000)

    def test_build_time(self):
        self.assertLess(self.build_s, 15.0)

    def test_max_edge_length(self):
        a = self.co[self.edges[:, 0]]
        b = self.co[self.edges[:, 1]]
        self.assertLessEqual(np.linalg.norm(a - b, axis=1).max(), 4.0 + 1e-4)

class SetupViewTest(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def tearDown(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_camera_at_path_start_looking_along_y(self):
        scene = bpy.context.scene
        setup_view(scene)
        bpy.context.view_layer.update()
        cam = scene.camera
        self.assertIsNotNone(cam)
        self.assertEqual(tuple(round(v, 6) for v in cam.location), (0.0, 0.0, CAM_Z))
        fwd = cam.matrix_world.to_3x3() @ mathutils.Vector((0, 0, -1))
        self.assertAlmostEqual(fwd.y, 1.0, places=5)
        self.assertGreater(cam.data.clip_end, LENGTH)


class CityDeterminismTest(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def tearDown(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def _build_hash(self, seed):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        return _vhash(build_city(seed=seed, length=400.0))

    def test_same_seed_same_hash(self):
        self.assertEqual(self._build_hash(3), self._build_hash(3))

    def test_different_seed_different_hash(self):
        self.assertNotEqual(self._build_hash(3), self._build_hash(4))

    def test_global_random_state_untouched(self):
        import random
        random.seed(123)
        expected = random.random()
        random.seed(123)
        build_city(seed=3, length=400.0)
        self.assertEqual(random.random(), expected)
        self.assertFalse(math.isnan(expected))
