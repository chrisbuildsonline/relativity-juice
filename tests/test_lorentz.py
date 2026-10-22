import unittest

import numpy as np

from src import gamma


class GammaTest(unittest.TestCase):
    def test_at_rest_is_one(self):
        self.assertEqual(gamma(0.0), 1.0)

    def test_known_value(self):
        self.assertAlmostEqual(gamma(0.6), 1.25)

    def test_accepts_numpy_arrays(self):
        out = gamma(np.array([0.0, 0.6]))
        np.testing.assert_allclose(out, [1.0, 1.25])

    def test_rejects_light_speed(self):
        with self.assertRaises(ValueError):
            gamma(1.0)


if __name__ == "__main__":
    unittest.main()
