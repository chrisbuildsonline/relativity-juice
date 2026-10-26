import os
import shutil
import tempfile
import unittest
import wave

import bpy

from src.racer import RACER_FRAMES, SHOT_CUTS, WHEEL_R, build_racer_scene, hero_kmh, hero_x, hero_y, rival_kmh, rival_y, shot_camera_pose
from src.synthwave import BEAT, BPM, CUT_TIMES, RATE, snare_on, synthesize_stereo, write_synthwave_wav


class RacerSceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = build_racer_scene()

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_hero_and_rival_wedge_cars_have_four_wheels_each(self):
        self.assertEqual(self.scene.frame_end, RACER_FRAMES)
        self.assertEqual(RACER_FRAMES, 600)
        for car_name in ("HeroRacer", "RivalRacer"):
            self.assertIn(car_name, bpy.data.objects)
            car = bpy.data.objects[car_name]
            self.assertGreater(len(car.data.vertices), 80)
            self.assertEqual(len(car.data.materials), 4)
            wheels = [o for o in car.children if "Wheel" in o.name]
            self.assertEqual(len(wheels), 4)
        self.assertIn("HeroPlate", bpy.data.objects)
        self.assertIn("HeroPlateText", bpy.data.objects)
        self.assertEqual(bpy.data.objects["HeroPlateText"].data.body, "RENDERJUICE")
        self.assertEqual(bpy.data.objects["HeroPlateText"].parent, bpy.data.objects["HeroRacer"])

    def test_hero_overtakes_rival_and_both_blast_off_in_shot_5(self):
        self.assertLess(hero_y(0.0), rival_y(0.0))       # starts behind rival
        self.assertLess(hero_y(5.0), rival_y(5.0))       # closing gap in helicopter shot
        self.assertAlmostEqual(hero_y(8.5), rival_y(8.5), delta=1.0)  # side-by-side at frame 205
        self.assertGreater(hero_y(14.0), rival_y(14.0))  # pulls ahead in boost
        # In Shot 5 (17.5 s -> 25.0 s), cars accelerate past 480 u/s and rocket into the horizon
        self.assertGreater(hero_y(25.0) - hero_y(17.5), 2500.0)

    def test_wheels_spin_with_arc_length_and_chassis_banks(self):
        car = bpy.data.objects["HeroRacer"]
        w_fl = bpy.data.objects["HeroRacer_WheelFL"]
        self.scene.frame_set(1)
        a1 = w_fl.rotation_euler.x
        self.scene.frame_set(205)
        a205 = w_fl.rotation_euler.x
        self.assertLess(a205, a1 - 500.0)
        self.assertAlmostEqual(a205, -hero_y((205 - 1) / 24.0) / WHEEL_R, places=2)
        rolls = []
        for f in (95, 110, 125, 140):
            self.scene.frame_set(f)
            rolls.append(abs(car.rotation_euler.y))
        self.assertGreater(max(rolls), 0.01)

    def test_geometry_nodes_particle_sparks_on_both_cars(self):
        hw = bpy.data.objects["SynthHighway"]
        self.assertIn("HighwayNodes", hw.modifiers)
        self.assertEqual(hw.modifiers["HighwayNodes"].type, "NODES")

        for tr_name in ("PlasmaTrails", "RivalTrails"):
            tr = bpy.data.objects[tr_name]
            self.assertIn("TrailNodes", tr.modifiers)
            self.assertEqual(tr.modifiers["TrailNodes"].type, "NODES")
            ev = tr.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            self.assertGreater(len(ev.vertices), 400)  # realized 3D icosphere particle sparks
            self.assertIn("heat", ev.attributes)
            tr.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()

        shock = bpy.data.objects["BoostShockwave"]
        self.scene.frame_set(100)
        self.assertLess(shock.scale.x, 0.01)
        self.scene.frame_set(265)
        self.assertGreater(shock.scale.x, 2.0)
        self.scene.frame_set(481)  # Shot 5 overview must keep the shockwave hidden so no road disc appears
        self.assertLess(shock.scale.x, 0.01)

    def test_tail_lamps_flash_on_snare_beats_2_and_4(self):
        self.assertFalse(snare_on(0.0))
        self.assertTrue(snare_on(BEAT))
        self.assertFalse(snare_on(2.0 * BEAT))
        self.assertTrue(snare_on(3.0 * BEAT))
        # Frame 1 (t = 0.0 s) is off snare; frame 13 (t = 0.50 s, inside beat 2 snare window 0.4839..0.6239 s) is on snare
        h_tail = bpy.data.materials["HeroRacer_Tail"].node_tree.nodes["Emission"].inputs["Strength"]
        r_tail = bpy.data.materials["RivalRacer_Tail"].node_tree.nodes["Emission"].inputs["Strength"]
        self.scene.frame_set(1)
        self.assertAlmostEqual(h_tail.default_value, 8.0, places=1)
        self.assertAlmostEqual(r_tail.default_value, 8.0, places=1)
        self.scene.frame_set(13)
        self.assertAlmostEqual(h_tail.default_value, 110.0, places=1)
        self.assertAlmostEqual(r_tail.default_value, 110.0, places=1)

    def test_five_shot_cameras_and_top_overview_disappearance(self):
        markers = [(m.frame, m.name) for m in sorted(self.scene.timeline_markers, key=lambda m: m.frame)]
        self.assertEqual(markers, list(SHOT_CUTS))
        self.assertEqual(len(SHOT_CUTS), 5)
        for _frame, cam_name in SHOT_CUTS:
            self.assertIn(cam_name, bpy.data.objects)
            self.assertEqual(bpy.data.objects[cam_name].type, "CAMERA")
        # Shot 4 widens FOV from 35 mm down to 20 mm
        _, _, _, lens_start, _ = shot_camera_pose(253)
        _, _, _, lens_end, _ = shot_camera_pose(420)
        self.assertAlmostEqual(lens_start, 35.0, places=2)
        self.assertAlmostEqual(lens_end, 20.0, places=2)
        # Shot 5 (CamOverview) sits high above the road and watches the cars rocket >700 u ahead into the horizon
        shot5, pos430, _, _, _ = shot_camera_pose(430)
        _, pos600, _, _, _ = shot_camera_pose(600)
        self.assertEqual(shot5, "CamOverview")
        self.assertGreater(pos430[2], 24.0)
        self.assertGreater(hero_y((600 - 1) / 24.0) - pos600[1], 700.0)

    def test_gta_bottom_right_dual_speed_bars_max_out(self):
        self.scene.frame_set(1)
        h1 = bpy.data.objects["GaugeText"].data.body
        r1 = bpy.data.objects["RivalGaugeText"].data.body
        self.assertIn("R-CAR", h1)
        self.assertIn("L-CAR", r1)
        self.scene.frame_set(600)
        h600 = bpy.data.objects["GaugeText"].data.body
        r600 = bpy.data.objects["RivalGaugeText"].data.body
        self.assertIn("999 KM/H", h600)
        self.assertIn("MAX!", h600)
        self.assertIn("MAX!", r600)
        self.assertAlmostEqual(hero_kmh(25.0), 999.0, places=1)
        self.assertGreater(rival_kmh(25.0), 920.0)
        self.assertNotAlmostEqual(hero_x(0.0), hero_x(4.8))


class SynthwaveAudioTest(unittest.TestCase):
    def test_stereo_synthwave_wav_and_tempo(self):
        self.assertEqual(BPM, 124.0)
        self.assertEqual(CUT_TIMES, (3.5, 7.0, 10.5, 17.5))
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        wav = os.path.join(d, "synthwave.wav")
        write_synthwave_wav(wav, 1.0, 4.0, 1.0, channels=2)
        with wave.open(wav, "rb") as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (RATE, 2, 2))
            self.assertEqual(w.getnframes(), int(6.0 * RATE))
        left, right = synthesize_stereo(0.5, 2.0, 0.5)
        diff = sum(abs(a - b) for a, b in zip(left, right)) / len(left)
        self.assertGreater(diff, 0.005)


if __name__ == "__main__":
    unittest.main()
