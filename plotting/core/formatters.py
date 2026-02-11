"""
Shared axis/formatter helpers for plotting. Used by IV grid, conduction, and SCLC plotters.
Plain-text formatters avoid matplotlib mathtext parsing errors during draw/savefig.
"""

import numpy as np


def plain_linear_formatter(x, pos):
    """
    Format linear-scale values as plain ASCII (no ×, no $, no superscripts).
    Prevents mathtext ParseException during figure save/draw.
    """
    try:
        if not np.isfinite(x):
            return "0"
        if abs(x) < 1e-4 and x != 0 or abs(x) >= 1e4:
            s = f"{x:.2e}"
            return s.replace("e", "e").replace("E", "e")  # plain ASCII
        if abs(x) < 1:
            return f"{x:.4f}"
        return f"{x:.3f}"
    except Exception:
        return "0"


def plain_log_formatter(x, pos):
    """
    Format log scale values as plain text without math symbols.
    Avoids matplotlib math text parsing errors.
    Returns plain string that will not be parsed as math text.
    """
    try:
        if x <= 0 or not np.isfinite(x):
            return '0'
        if x < 0.01 or x > 1000:
            val_str = f'{x:.2e}'
            return val_str.replace('×', 'x').replace('·', '*')
        if x < 1:
            return f'{x:.3f}'
        return f'{x:.1f}'
    except Exception:
        return '0'
