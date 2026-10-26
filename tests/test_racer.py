import os
import shutil
import tempfile
import unittest
import wave

import bpy

from src.racer import SHOT_CUTS, WHEEL_R, build_racer_scene, hero_kmh, hero_x, hero_y, rival_y, shot_camera_pose
from src.synthwave import BPM, CUT_TIMES, RATE, synthesize_stereo, write_synthwave_wav


class RacerSceneTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = build_racer_scene()

    @classmethod
    def tearDownClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_hero_and_rival_wedge_cars_have_four_wheels_each(self):
        for car_name in ("HeroRacer", "RivalRacer"):
            self.assertIn(car_name, bpy.data.objects)
            car = bpy.data.objects[car_name]
            self.assertGreater(len(car.data.vertices), 80)
            self.assertEqual(len(car.data.materials), 4)
            wheels = [o for o in car.children if "Wheel" in o.name]
            self.assertEqual(len(wheels), 4)

    def test_hero_overtakes_rival_during_shot_3(self):
        self.assertLess(hero_y(0.0), rival_y(0.0))       # starts behind rival
        self.assertLess(hero_y(5.0), rival_y(5.0))       # closing gap in helicopter shot
        self.assertAlmostEqual(hero_y(8.5), rival_y(8.5), delta=1.0)  # side-by-side at frame 205
        self.assertGreater(hero_y(14.0), rival_y(14.0))  # pulls away in hyper-boost

    def test_wheels_spin_with_arc_length_and_chassis_banks(self):
        car = bpy.data.objects["HeroRacer"]
        w_fl = bpy.data.objects["HeroRacer_WheelFL"]
        self.scene.frame_set(1)
        a1 = w_fl.rotation_euler.x
        self.scene.frame_set(205)
        a205 = w_fl.rotation_euler.x
        self.assertLess(a205, a1 - 500.0)
        self.assertAlmostEqual(a205, -hero_y((205 - 1) / 24.0) / WHEEL_R, places=2)
        # During S-curve weave (around frame 100..135), chassis roll is non-zero
        rolls = []
        for f in (95, 110, 125, 140):
            self.scene.frame_set(f)
            rolls.append(abs(car.rotation_euler.y))
        self.assertGreater(max(rolls), 0.01)

    def test_geometry_nodes_modifiers_on_highway_and_plasma_trails(self):
        hw = bpy.data.objects["SynthHighway"]
        self.assertIn("HighwayNodes", hw.modifiers)
        self.assertEqual(hw.modifiers["HighwayNodes"].type, "NODES")

        tr = bpy.data.objects["PlasmaTrails"]
        self.assertIn("TrailNodes", tr.modifiers)
        self.assertEqual(tr.modifiers["TrailNodes"].type, "NODES")

        shock = bpy.data.objects["BoostShockwave"]
        self.scene.frame_set(100)
        self.assertLess(shock.scale.x, 0.01)
        self.scene.frame_set(265)
        self.assertGreater(shock.scale.x, 2.0)

    def test_four_shot_cameras_and_timeline_markers(self):
        markers = [(m.frame, m.name) for m in sorted(self.scene.timeline_markers, key=lambda m: m.frame)]
        self.assertEqual(markers, list(SHOT_CUTS))
        for _frame, cam_name in SHOT_CUTS:
            self.assertIn(cam_name, bpy.data.objects)
            self.assertEqual(bpy.data.objects[cam_name].type, "CAMERA")
        # Shot 4 widens FOV from 35 mm down to 20 mm
        _, _, _, lens_start, _ = shot_camera_pose(253)
        _, _, _, lens_end, _ = shot_camera_pose(360)
        self.assertAlmostEqual(lens_start, 35.0, places=2)
        self.assertAlmostEqual(lens_end, 20.0, places=2)

    def test_in_camera_3d_hud_updates_speed_and_relativity(self):
        self.scene.frame_set(1)
        body1 = bpy.data.objects["GaugeText"].data.body
        self.assertIn("KM/H", body1)
        self.scene.frame_set(360)
        body360 = bpy.data.objects["GaugeText"].data.body
        self.assertIn("420 KM/H", body360)
        self.assertIn("0.999c", body360)
        self.assertGreater(hero_kmh(15.0), 400.0)
        self.assertNotAlmostEqual(hero_x(0.0), hero_x(4.8))


class SynthwaveAudioTest(unittest.TestCase):
    def test_stereo_synthwave_wav_and_tempo(self):
        self.assertEqual(BPM, 124.0)
        self.assertEqual(CUT_TIMES, (3.5, 7.0, 10.5))
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        wav = os.path.join(d, "synthwave.wav")
        write_synthwave_wav(wav, 1.0, 4.0, 1.0, channels=2)
        with wave.open(wav, "rb") as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (RATE, 2, 2))
            self.assertEqual(w.getnframes(), int(6.0 * RATE))
        left, right = synthesize_stereo(0.5, 2.0, 0.5)
        # Stereo chorus and delay make Left and Right distinct channels
        diff = sum(abs(a - b) for a, b in zip(left, right)) / len(left)
        self.assertGreater(diff, 0.005)


if __name__ == "__main__":
    unittest.main()
