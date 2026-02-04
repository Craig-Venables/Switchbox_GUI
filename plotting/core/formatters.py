"""
Shared axis/formatter helpers for plotting. Used by IV grid, conduction, and SCLC plotters.
"""

import numpy as np


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
