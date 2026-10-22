import unittest

import numpy as np

from src.relativity import aberrate, beaming, doppler, gamma

Y = np.array([0.0, 1.0, 0.0])


def dirs_at(cos_t, phi=0.3):
    """Unit vectors at angle acos(cos_t) from +Y, rotated by phi about Y."""
    cos_t = np.asarray(cos_t, dtype=float)
    s = np.sqrt(1.0 - cos_t**2)
    return np.stack([s * np.cos(phi), cos_t, s * np.sin(phi)], axis=-1)


class AberrateTest(unittest.TestCase):
    def test_fixed_points(self):
        for beta in (0.1, 0.6, 0.999):
            out = aberrate(np.array([[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]]), beta)
            np.testing.assert_array_equal(out, [[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]])

    def test_single_vector_shape(self):
        out = aberrate(np.array([1.0, 0.0, 0.0]), 0.5)
        self.assertEqual(out.shape, (3,))

    def test_perpendicular_goes_to_beta(self):
        for beta in (0.1, 0.5, 0.9, 0.999):
            out = aberrate(np.array([1.0, 0.0, 0.0]), beta)
            self.assertAlmostEqual(float(out @ Y), beta, places=12)

    def test_zero_beta_is_identity(self):
        d = dirs_at(np.array([-0.7, 0.0, 0.4, 0.95]))
        np.testing.assert_allclose(aberrate(d, 0.0), d, atol=1e-15)

    def test_custom_axis(self):
        x = (1.0, 0.0, 0.0)
        out = aberrate(np.array([0.0, 1.0, 0.0]), 0.6, axis=x)
        self.assertAlmostEqual(float(out[0]), 0.6, places=12)
        out0 = aberrate(np.array([1.0, 0.0, 0.0]), 0.6, axis=x)
        np.testing.assert_array_equal(out0, [1.0, 0.0, 0.0])

    def test_non_normalised_axis_is_normalised(self):
        a = aberrate(np.array([1.0, 0.0, 0.0]), 0.5, axis=(0.0, 3.0, 0.0))
        b = aberrate(np.array([1.0, 0.0, 0.0]), 0.5)
        np.testing.assert_allclose(a, b, atol=1e-15)

    def test_rejects_light_speed(self):
        with self.assertRaises(ValueError):
            aberrate(np.array([1.0, 0.0, 0.0]), 1.0)


class DopplerTest(unittest.TestCase):
    def test_straight_ahead(self):
        for beta in (0.0, 0.3, 0.9, 0.999):
            self.assertAlmostEqual(
                doppler(1.0, beta), np.sqrt((1 + beta) / (1 - beta)), places=9
            )

    def test_perpendicular_is_inverse_gamma(self):
        for beta in (0.3, 0.9, 0.999):
            self.assertAlmostEqual(doppler(0.0, beta), 1.0 / gamma(beta), places=12)

    def test_scalar_returns_float_array_returns_array(self):
        self.assertIsInstance(doppler(0.5, 0.5), float)
        self.assertEqual(np.shape(doppler(np.array([0.1, 0.2]), 0.5)), (2,))


class BeamingTest(unittest.TestCase):
    def test_square_squared(self):
        self.assertAlmostEqual(beaming(2.0), 16.0)

    def test_array(self):
        np.testing.assert_allclose(beaming(np.array([1.0, 2.0])), [1.0, 16.0])
        self.assertIsInstance(beaming(2.0), float)


class PropertyTest(unittest.TestCase):
    N = 10_000

    def setUp(self):
        self.rng = np.random.default_rng(12345)
        v = self.rng.normal(size=(self.N, 3))
        self.dirs = v / np.linalg.norm(v, axis=1, keepdims=True)
        # include the axis-parallel and axis-antiparallel cases
        self.dirs[0] = [0.0, 1.0, 0.0]
        self.dirs[1] = [0.0, -1.0, 0.0]
        self.betas = np.concatenate(
            [[0.0, 0.999], self.rng.uniform(0.0, 0.999, size=self.N - 2)]
        )

    def test_finite_and_unit_length(self):
        for beta in (0.0, 0.5, 0.999):
            out = aberrate(self.dirs, beta)
            self.assertTrue(np.all(np.isfinite(out)))
            np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-9)

    def test_finite_unit_with_sampled_betas(self):
        for beta in self.betas[:200]:
            out = aberrate(self.dirs, float(beta))
            self.assertTrue(np.all(np.isfinite(out)))
            np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-9)

    def test_round_trip(self):
        # Tolerance 1e-9 holds even at beta=0.999 (checked below).
        for beta in [0.0, 0.3, 0.9, 0.99, 0.999, *self.betas[:100]]:
            fwd = aberrate(self.dirs, float(beta))
            back = aberrate(fwd, -float(beta))
            np.testing.assert_allclose(back, self.dirs, atol=1e-9)

    def test_cos_non_decreasing_in_beta(self):
        grid = np.linspace(0.0, 0.999, 200)
        cos = np.array([aberrate(self.dirs, b) @ Y for b in grid])  # (B, N)
        self.assertTrue(np.all(np.diff(cos, axis=0) >= -1e-12))

    def test_doppler_matches_rest_frame_form(self):
        for beta in (0.0, 0.2, 0.7, 0.999):
            cos_rest = self.dirs @ Y
            cos_obs = aberrate(self.dirs, beta) @ Y
            expected = gamma(beta) * (1.0 + beta * cos_rest)
            np.testing.assert_allclose(
                doppler(cos_obs, beta), expected, rtol=1e-9
            )

    def test_doppler_beaming_finite_positive(self):
        d = doppler(aberrate(self.dirs, 0.999) @ Y, 0.999)
        self.assertTrue(np.all(np.isfinite(d)) and np.all(d > 0))
        self.assertTrue(np.all(np.isfinite(beaming(d))))


if __name__ == "__main__":
    unittest.main()
