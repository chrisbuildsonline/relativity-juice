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
