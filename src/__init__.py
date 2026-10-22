"""relativity-juice: special relativity math for the procedural city."""
import numpy as np


def gamma(beta):
    """Lorentz factor for speed beta = v/c (scalar or array), 0 <= |beta| < 1."""
    b = np.asarray(beta, dtype=float)
    if np.any(np.abs(b) >= 1.0):
        raise ValueError("beta must satisfy |beta| < 1")
    out = 1.0 / np.sqrt(1.0 - b * b)
    return float(out) if out.ndim == 0 else out
