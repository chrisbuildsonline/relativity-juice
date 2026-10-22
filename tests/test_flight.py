import unittest

import numpy as np

from src.flight import C, DURATION, FPS, FRAME_END, FRAME_START, camera_y, frame_of, time_of
from src.relativity import beta_at


class FlightPathTest(unittest.TestCase):
    def test_frames_and_time(self):
        self.assertEqual((FPS, FRAME_START, FRAME_END), (24, 1, 360))
        self.assertEqual(time_of(FRAME_START), 0.0)
        self.assertAlmostEqual(time_of(FRAME_END), DURATION - 1.0 / FPS)
        self.assertEqual(frame_of(time_of(180)), 180)

    def test_starts_at_zero_and_increases(self):
        self.assertEqual(camera_y(0.0), 0.0)
        y = camera_y(np.linspace(0.0, DURATION, 721))
        self.assertTrue(np.all(np.diff(y) > 0.0))

    def test_ends_inside_the_city(self):
        end = camera_y(DURATION)
        self.assertGreater(end, 500.0)
        self.assertLessEqual(end, 1500.0)

    def test_speed_is_beta_times_c(self):
        h = 1e-3
        for t in (0.5, 3.0, 7.5, 12.0, 14.5):
            speed = (camera_y(t + h) - camera_y(t - h)) / (2 * h)
            self.assertAlmostEqual(speed / (beta_at(t) * C), 1.0, places=4)

    def test_array_and_scalar(self):
        self.assertIsInstance(camera_y(1.0), float)
        self.assertEqual(np.shape(camera_y(np.array([1.0, 2.0]))), (2,))
