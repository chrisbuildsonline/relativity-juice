import unittest

import numpy as np

from src.relativity import (
    DISPLAY_BEAM_CAP,
    DISPLAY_DESAT_MAX,
    IR_EDGE_NM,
    UV_TINT_RGB,
    aberrate,
    beaming,
    beta_at,
    doppler,
    display_beaming,
    display_desaturation,
    display_infrared,
    gamma,
    shift_rgb,
    uv_tint,
    wavelength_rgb,
)

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


class WavelengthRgbTest(unittest.TestCase):
    def test_blue_green_red_dominant(self):
        b = wavelength_rgb(450.0)
        g = wavelength_rgb(550.0)
        r = wavelength_rgb(650.0)
        self.assertEqual(int(np.argmax(b)), 2)
        self.assertEqual(int(np.argmax(g)), 1)
        self.assertEqual(int(np.argmax(r)), 0)

    def test_shapes(self):
        self.assertEqual(wavelength_rgb(550.0).shape, (3,))
        self.assertEqual(wavelength_rgb(np.array([450.0, 550.0, 650.0])).shape, (3, 3))

    def test_outside_visible_is_black(self):
        np.testing.assert_array_equal(wavelength_rgb(np.array([300.0, 900.0])), 0.0)


class DisplayBeamingTest(unittest.TestCase):
    def test_monotone_bounded_and_unity_at_rest(self):
        d = np.linspace(0.01, 100.0, 5000)
        b = np.asarray(display_beaming(d))
        self.assertTrue(np.all(np.diff(b) >= 0.0))
        self.assertLessEqual(b.max(), DISPLAY_BEAM_CAP)
        self.assertGreater(b.min(), 0.0)
        self.assertAlmostEqual(display_beaming(1.0), 1.0)
        self.assertIsInstance(display_beaming(2.0), float)

    def test_compresses_d4(self):
        self.assertLess(display_beaming(4.4), beaming(4.4))
        self.assertLess(display_beaming(0.5), 1.0)  # still dims the receding side


class DisplayDesaturationTest(unittest.TestCase):
    def test_off_while_slow_full_when_late_monotone(self):
        self.assertEqual(display_desaturation(gamma(0.1)), 0.0)
        self.assertEqual(display_desaturation(gamma(0.9)), 0.0)  # gamma 2.3
        self.assertAlmostEqual(display_desaturation(gamma(0.999)), DISPLAY_DESAT_MAX)  # gamma 22
        g = np.linspace(1.0, 30.0, 500)
        d = np.asarray(display_desaturation(g))
        self.assertTrue(np.all(np.diff(d) >= 0.0))
        self.assertLess(DISPLAY_DESAT_MAX, 1.0)  # never greys out the colour completely


class ShiftRgbTest(unittest.TestCase):
    def test_unshifted_matches_wavelength(self):
        np.testing.assert_allclose(shift_rgb(550.0, 1.0), wavelength_rgb(550.0))

    def test_extreme_blueshift_is_saturated_violet(self):
        c = shift_rgb(550.0, 5.0)
        self.assertGreaterEqual(c[2], 0.9)
        self.assertLessEqual(c[0], 0.5)
        self.assertLessEqual(c[1], 0.3)

    def test_deep_uv_keeps_rest_colours_apart(self):
        blue, green, red = (shift_rgb(nm, 8.0) for nm in (440.0, 530.0, 640.0))  # all far below 260 nm
        for c in (blue, green, red):
            self.assertEqual(float(c[2]), 1.0)  # saturated: blue channel full, never white
            self.assertLess(float(c.min()), 0.4)
        self.assertGreater(red[0] - blue[0], 0.4)
        self.assertGreater(green[1] - blue[1], 0.2)
        np.testing.assert_allclose(uv_tint(np.array([420.0, 620.0, 700.0])), [UV_TINT_RGB[0], UV_TINT_RGB[2], UV_TINT_RGB[2]])

    def test_infrared_is_dim_deep_red_not_black(self):
        c = shift_rgb(550.0, 0.229)  # dead behind at 0.9c: 2400 nm
        self.assertGreater(c[0], 0.02)
        self.assertLessEqual(c[0], wavelength_rgb(IR_EDGE_NM)[0])
        self.assertEqual((c[1], c[2]), (0.0, 0.0))

    def test_infrared_keeps_falling_with_d(self):
        reds = [shift_rgb(550.0, d)[0] for d in (0.7, 0.4, 0.229, 0.1, 0.022)]
        self.assertTrue(all(a > b > 0.0 for a, b in zip(reds, reds[1:])))

    def test_display_infrared_matches_shift_rgb_past_the_edge(self):
        lam = np.array([781.0, 1000.0, 2400.0, 20000.0])
        np.testing.assert_allclose(display_infrared(lam), shift_rgb(lam, 1.0))
        np.testing.assert_allclose(display_infrared(IR_EDGE_NM), wavelength_rgb(IR_EDGE_NM))

    def test_display_infrared_goes_away_late_in_the_flight(self):
        np.testing.assert_array_equal(display_infrared(2400.0, gamma(0.999)), 0.0)
        self.assertGreater(display_infrared(2400.0, gamma(0.9))[0], 0.02)  # gamma 2.3: the rear window's range
    EPS = 1e-6
    TOL = 1e-4  # observed max jump across an edge is ~1e-6

    def test_continuous_at_uv_edge(self):
        # lambda_obs = 380 -/+ EPS
        lo = shift_rgb(380.0 - self.EPS, 1.0)
        hi = shift_rgb(380.0 + self.EPS, 1.0)
        np.testing.assert_allclose(lo, hi, atol=self.TOL)

    def test_continuous_at_ir_edge(self):
        lo = shift_rgb(780.0 - self.EPS, 1.0)
        hi = shift_rgb(780.0 + self.EPS, 1.0)
        np.testing.assert_allclose(lo, hi, atol=self.TOL)

    def test_rejects_non_positive_d(self):
        with self.assertRaises(ValueError):
            shift_rgb(550.0, 0.0)

    def test_broadcasts(self):
        out = shift_rgb(np.array([450.0, 550.0, 650.0])[:, None], np.array([0.5, 1.0]))
        self.assertEqual(out.shape, (3, 2, 3))


class ShiftRgbFuzzTest(unittest.TestCase):
    def test_finite_bounded_shape(self):
        rng = np.random.default_rng(777)
        nm = rng.uniform(380.0, 780.0, size=10_000)
        d = rng.uniform(0.05, 50.0, size=10_000)
        out = shift_rgb(nm, d)
        self.assertEqual(out.shape, (10_000, 3))
        self.assertTrue(np.all(np.isfinite(out)))
        self.assertTrue(np.all((out >= 0.0) & (out <= 1.0)))


class BetaAtTest(unittest.TestCase):
    def test_endpoints_exact(self):
        self.assertAlmostEqual(beta_at(0.0), 0.1, delta=1e-12)
        self.assertAlmostEqual(beta_at(15.0), 0.999, delta=1e-12)
        self.assertAlmostEqual(beta_at(4.0, duration=4.0, start=0.2, end=0.9), 0.9, delta=1e-12)

    def test_clamps(self):
        self.assertEqual(beta_at(-5.0), beta_at(0.0))
        self.assertEqual(beta_at(99.0), beta_at(15.0))

    def test_mid_strictly_between(self):
        self.assertTrue(0.1 < beta_at(7.5) < 0.999)

    def test_starts_slow_flattens_at_end(self):
        # eased in rapidity, so compare rapidity steps (beta itself saturates)
        phi = lambda t: float(np.arctanh(beta_at(t)))  # noqa: E731
        early = phi(1.0) - phi(0.0)
        mid = phi(8.5) - phi(7.5)
        late = phi(15.0) - phi(14.0)
        self.assertLess(early, mid)
        self.assertLess(late, mid)

    def test_scalar_float_array_array(self):
        self.assertIsInstance(beta_at(3.0), float)
        self.assertEqual(np.shape(beta_at(np.array([0.0, 1.0, 2.0]))), (3,))

    def test_rejects_bad_duration(self):
        with self.assertRaises(ValueError):
            beta_at(1.0, duration=0.0)

    def test_monotonic_and_bounded_on_dense_grid(self):
        t = np.linspace(-1.0, 16.0, 10_000)
        b = np.asarray(beta_at(t))
        self.assertTrue(np.all(np.diff(b) >= 0.0))
        self.assertTrue(np.all((b > 0.0) & (b < 1.0)))
        g = np.asarray(gamma(b))
        self.assertTrue(np.all(np.isfinite(g)))


if __name__ == "__main__":
    unittest.main()
