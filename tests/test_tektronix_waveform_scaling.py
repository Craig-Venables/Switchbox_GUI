import numpy as np
import pytest

try:
    from Equipment.Oscilloscopes.TektronixTBS1000C import TektronixTBS1000C
except Exception as exc:  # pragma: no cover - import guard for environments without pyvisa
    pytest.skip(f"Tektronix driver unavailable: {exc}", allow_module_level=True)


def test_scale_waveform_values_uses_tektronix_formula():
    preamble = {'YMULT': 0.01, 'YOFF': 127, 'YZERO': 0.0}
    raw = np.array([127, 227, 27], dtype=np.float64)

    scaled = TektronixTBS1000C._scale_waveform_values(raw, preamble)

    np.testing.assert_allclose(scaled, [0.0, 1.0, -1.0])


def test_build_time_array_respects_offsets():
    preamble = {'XINCR': 1e-6, 'XZERO': -5e-6, 'PT_OFF': 1}

    time_vals = TektronixTBS1000C._build_time_array(3, preamble)

    np.testing.assert_allclose(time_vals, [-6e-6, -5e-6, -4e-6])

