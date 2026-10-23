"""Special relativity math (NumPy only, no bpy)."""
import numpy as np


def _scalar_or_array(out):
    return float(out) if out.ndim == 0 else out


def gamma(beta):
    """Lorentz factor for speed beta = v/c (scalar or array), |beta| < 1."""
    b = np.asarray(beta, dtype=float)
    if np.any(np.abs(b) >= 1.0):
        raise ValueError("beta must satisfy |beta| < 1")
    return _scalar_or_array(1.0 / np.sqrt(1.0 - b * b))


def aberrate(dirs, beta, axis=(0.0, 1.0, 0.0)):
    """Apparent directions seen by an observer moving at beta along `axis`.

    dirs: (N, 3) or (3,) unit vectors from observer to a light source in the
    city (rest) frame. `axis` is the direction of motion (default +Y, the
    flight direction); it is normalised internally. Returns unit vectors of
    the same shape: cos(t') = (cos(t) + beta) / (1 + beta cos(t)) with the
    perpendicular direction kept. Negative beta is the inverse transform.
    Directions parallel or antiparallel to the axis are fixed points.
    """
    d = np.asarray(dirs, dtype=float)
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    beta = float(beta)
    g = gamma(beta)

    c = d @ a
    perp = d - c[..., None] * a
    sin = np.linalg.norm(perp, axis=-1)
    denom = 1.0 + beta * c
    c_new = (c + beta) / denom
    # sin(t') = sin(t) / (gamma (1 + beta cos t)): stays accurate near the axis
    s_new = sin / (g * denom)

    safe = np.where(sin > 0.0, sin, 1.0)
    unit_perp = np.where(sin[..., None] > 0.0, perp / safe[..., None], 0.0)
    return c_new[..., None] * a + s_new[..., None] * unit_perp


def doppler(cos_obs, beta):
    """Doppler factor D = nu_obs / nu_emit = 1 / (gamma (1 - beta cos t')).

    cos_obs is cos t' of the OBSERVED (already aberrated) angle between the
    apparent direction and the motion axis. Equivalent in the rest-frame
    angle: D = gamma (1 + beta cos t).
    """
    c = np.asarray(cos_obs, dtype=float)
    return _scalar_or_array(1.0 / (gamma(beta) * (1.0 - float(beta) * c)))


def beaming(D):
    """Relativistic beaming intensity factor D**4."""
    return _scalar_or_array(np.asarray(D, dtype=float) ** 4)


DISPLAY_BEAM_EXP = 2.0  # D^4 compressed to D^2 (a 1/2 gamma) so a 1920x1080 AgX frame is not all white
DISPLAY_BEAM_CAP = 2.0


def display_beaming(D):
    """Tone-mapped beaming used by the shader: min(D**2, 2), monotone in D and bounded."""
    return _scalar_or_array(np.minimum(np.asarray(D, dtype=float) ** DISPLAY_BEAM_EXP, DISPLAY_BEAM_CAP))


DISPLAY_DESAT_MAX = 0.35
DISPLAY_DESAT_GAMMA = (5.0, 12.0)


def display_desaturation(g):
    """Share of grey mixed into the visible-band Doppler colour at Lorentz factor g (display tone-map).

    Once gamma is large the whole spectrum is squeezed into a thin ring near the frame edge, and a sharp
    ring of pure green, yellow and red reads as an artefact, not light. Fades in from gamma 5 to 12 up to
    DISPLAY_DESAT_MAX; hue order and wavelength are untouched, only the saturation of 380-780 nm colours.
    """
    lo, hi = DISPLAY_DESAT_GAMMA
    t = np.clip((np.asarray(g, dtype=float) - lo) / (hi - lo), 0.0, 1.0)
    return _scalar_or_array(DISPLAY_DESAT_MAX * t * t * (3.0 - 2.0 * t))


UV_EDGE_NM = 380.0
IR_EDGE_NM = 780.0
# where deep UV ends up: saturated violet-blue (not white), nudged by the source's rest colour
# (violet 420 nm, azure 530 nm, magenta 620 nm) so windows of different colours stay distinguishable
UV_TINT_NM = (420.0, 530.0, 620.0)
UV_TINT_RGB = ((0.2, 0.04, 1.0), (0.04, 0.35, 1.0), (0.8, 0.05, 1.0))
_UV_RANGE_NM = 120.0  # blend finishes this far below the UV edge
_IR_FADE_NM = 220.0  # red fade finishes this far above the IR edge (780 -> 1000)


def wavelength_rgb(nm):
    """Approximate linear RGB in [0, 1] for visible wavelengths (Bruton).

    nm: scalar -> (3,), array (N,) -> (N, 3). Intensity falls to 0.3 at both
    ends of 380-780 nm. Outside that band the result is black.
    """
    w = np.asarray(nm, dtype=float)
    r = np.interp(w, [380, 440, 510, 580, 780], [1, 0, 0, 1, 1])
    g = np.interp(w, [380, 440, 490, 510, 580, 645, 780], [0, 0, 1, 1, 1, 0, 0])
    b = np.interp(w, [380, 440, 490, 510, 780], [1, 1, 1, 0, 0])
    k = np.interp(w, [380, 420, 700, 780], [0.3, 1.0, 1.0, 0.3])
    out = np.stack([r, g, b], axis=-1) * k[..., None]
    inside = (w >= UV_EDGE_NM) & (w <= IR_EDGE_NM)
    return np.where(inside[..., None], out, 0.0)


def uv_tint(base_nm):
    """Colour a source of rest wavelength base_nm turns into once shifted deep into the UV, (..., 3)."""
    nm = np.asarray(base_nm, dtype=float)
    return np.stack([np.interp(nm, UV_TINT_NM, ch) for ch in np.asarray(UV_TINT_RGB).T], axis=-1)


def shift_rgb(base_nm, D):
    """Observed RGB of a source of wavelength base_nm seen with Doppler factor D.

    lambda_obs = base_nm / D (D > 0), broadcast over both inputs; output shape
    is the broadcast shape + (3,), always finite and in [0, 1]. Visible light
    uses wavelength_rgb. Below 380 nm the colour blends linearly from the
    violet edge to the saturated uv_tint(base_nm) over 120 nm; above 780 nm the red edge
    colour fades smoothly to black by 1000 nm. Beaming is not applied.
    """
    d = np.asarray(D, dtype=float)
    if np.any(d <= 0.0):
        raise ValueError("D must be positive")
    lam = np.asarray(base_nm, dtype=float) / d
    visible = wavelength_rgb(lam)

    t = np.clip((UV_EDGE_NM - lam) / _UV_RANGE_NM, 0.0, 1.0)[..., None]
    uv_edge = wavelength_rgb(UV_EDGE_NM)
    uv = uv_edge + t * (uv_tint(base_nm) - uv_edge)

    s = np.clip((lam - IR_EDGE_NM) / _IR_FADE_NM, 0.0, 1.0)
    ir = wavelength_rgb(IR_EDGE_NM) * (1.0 - s * s * (3.0 - 2.0 * s))[..., None]

    out = np.where((lam < UV_EDGE_NM)[..., None], uv, visible)
    out = np.where((lam > IR_EDGE_NM)[..., None], ir, out)
    return np.clip(out, 0.0, 1.0)


def beta_at(t, duration=15.0, start=0.1, end=0.999):
    """Eased flight speed beta at time t (seconds), clamped to [0, duration].

    Rapidity phi = atanh(beta) is interpolated from start to end with a
    smoothstep (slow start, steady build, flat finish), so gamma grows
    through the whole clip. beta_at(0) == start, beta_at(duration) == end.
    """
    if duration <= 0.0:
        raise ValueError("duration must be positive")
    u = np.clip(np.asarray(t, dtype=float) / duration, 0.0, 1.0)
    s = u * u * (3.0 - 2.0 * u)
    phi = np.arctanh(start) * (1.0 - s) + np.arctanh(end) * s
    return _scalar_or_array(np.tanh(phi))
