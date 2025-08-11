from __future__ import annotations

import numpy as np


def hysteresis_loop_area(voltage: np.ndarray, current: np.ndarray) -> float:
    """Approximate loop area via polygon area of I-V curve.
    Returns absolute area in A*V.
    """
    if len(voltage) < 3 or len(current) < 3:
        return 0.0
    # Sort by voltage sweep order is assumed; compute area via shoelace on (V, I)
    x, y = np.asarray(voltage), np.asarray(current)
    return float(0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def on_off_ratio(i_on: float, i_off: float, eps: float = 1e-12) -> float:
    return float((abs(i_on) + eps) / (abs(i_off) + eps))


def photoresponse(i_on: float, i_off: float, eps: float = 1e-12) -> float:
    return float((i_on - i_off) / (abs(i_off) + eps))


def retention_alpha(times_s: np.ndarray, currents: np.ndarray) -> float:
    """Fit a power-law I(t) ~ t^-alpha using linear regression in log space."""
    t = np.asarray(times_s)
    i = np.asarray(currents)
    mask = (t > 0) & (i > 0)
    if mask.sum() < 2:
        return 0.0
    x = np.log(t[mask])
    y = np.log(i[mask])
    # slope is -alpha
    A = np.vstack([x, np.ones_like(x)]).T
    alpha = -float(np.linalg.lstsq(A, y, rcond=None)[0][0])
    return alpha


