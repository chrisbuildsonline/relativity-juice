"""Flight timing and camera path along +Y (NumPy only, no bpy)."""
import numpy as np

from src.relativity import beta_at

C = 120.0  # "slow light": scene units per second, so the 15 s flight covers ~1100 units
FPS = 24
DURATION = 15.0
FRAME_START = 1
FRAME_END = int(DURATION * FPS)  # 360

_GRID = np.linspace(0.0, DURATION, 15001)
_BETA = np.asarray(beta_at(_GRID))
_Y = np.concatenate([[0.0], np.cumsum((_BETA[1:] + _BETA[:-1]) * 0.5 * np.diff(_GRID))]) * C


def time_of(frame):
    """Seconds since the start for a frame number (frame 1 is t = 0)."""
    return (frame - FRAME_START) / FPS


def frame_of(t):
    """Nearest frame number for time t in seconds."""
    return int(round(t * FPS)) + FRAME_START


def camera_y(t):
    """Camera Y at time t: integral of beta(s) * C ds (trapezoid on a fine grid)."""
    out = np.interp(np.asarray(t, dtype=float), _GRID, _Y)
    return float(out) if out.ndim == 0 else out
