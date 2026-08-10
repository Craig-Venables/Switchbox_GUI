"""Sanity checks for aux analysis math (run: py -3 -m analysis.aux.selftest)."""

from __future__ import annotations

import numpy as np

from .solartron.fitting import (
    _model_rs_rp_c,
    _model_rs_rp_cpe,
    deep_eis_analysis,
    fit_equivalent_circuits,
    nyquist_intercepts,
)


def _approx(a, b, rtol=0.05, atol=1e-12):
    return abs(a - b) <= (atol + rtol * abs(b))


def test_synth_rc():
    f = np.logspace(1, 6, 80)
    w = 2 * np.pi * f
    Rs, Rp, C = 100.0, 1000.0, 1e-8
    Z = _model_rs_rp_c(w, Rs, Rp, C)
    fit = fit_equivalent_circuits(f, np.real(Z), np.imag(Z))
    assert fit["best_model"] == "Rs_Rp_C", fit["best_model"]
    assert fit["best_r2"] > 0.999, fit["best_r2"]
    assert _approx(fit["fit_Rs"], Rs, 0.02), fit["fit_Rs"]
    assert _approx(fit["fit_Rp"], Rp, 0.02), fit["fit_Rp"]
    assert _approx(fit["fit_C"], C, 0.05), fit["fit_C"]
    inter = nyquist_intercepts(f, np.real(Z), np.imag(Z))
    assert _approx(inter["intercept_Rs"], Rs, 0.15), inter
    assert inter["intercept_Rp"] > 0.5 * Rp


def test_synth_cpe():
    f = np.logspace(1, 6, 80)
    w = 2 * np.pi * f
    Z = _model_rs_rp_cpe(w, 50.0, 2000.0, 5e-9, 0.85)
    fit = fit_equivalent_circuits(f, np.real(Z), np.imag(Z))
    assert fit["best_model"] == "Rs_Rp_CPE", fit
    assert fit["best_r2"] > 0.999
    assert _approx(fit["fit_alpha"], 0.85, 0.05)


def test_resistive_prefers_rs():
    f = np.logspace(1, 6, 60)
    z_re = np.full_like(f, 1e4)
    z_im = 1e4 * 0.001 * np.sin(np.log(f))  # tiny imag noise, flat Re
    fit = fit_equivalent_circuits(f, z_re, z_im)
    assert fit["best_model"] == "Rs", fit


def test_dispersive_re_keeps_complex_model():
    """Small Im but strongly dispersive Re should not be forced to Rs."""
    f = np.logspace(1, 6, 60)
    # Re drops with frequency (dispersion), Im tiny
    z_re = 2e4 / (1 + (f / 1e3) ** 0.3)
    z_im = -0.01 * z_re
    fit = fit_equivalent_circuits(f, z_re, z_im)
    assert fit["best_model"] != "Rs", fit
    assert fit.get("best_r2", -1) > 0.5


def test_origin_imag_negated():
    f = np.logspace(2, 5, 50)
    w = 2 * np.pi * f
    Z = _model_rs_rp_c(w, 200.0, 800.0, 2e-9)
    # Origin stores -Im
    deep = deep_eis_analysis(
        f, np.real(Z), -np.imag(Z), origin_imag_is_negated=True
    )
    assert deep["best_model"] in ("Rs_Rp_C", "Rs_Rp_CPE")
    assert deep.get("Cp_median", -1) > 0 or deep.get("Cp_1kHz", -1) > 0
    assert "negative_Cp_check_imag_sign" not in (deep.get("anomalies") or [])


def test_pulse_window_sign():
    from .pulse.metrics import fit_window_degradation

    cyc = np.arange(50, dtype=float)
    window = 5000 * np.exp(-0.02 * cyc)
    d = fit_window_degradation(cyc, window)
    assert d["degrade_best_model"] in ("exponential", "power", "linear")
    assert d["degrade_best_r2"] >= 0.3

    flat = np.full(50, 100.0)
    d2 = fit_window_degradation(cyc, flat)
    # flat → poor / none
    assert d2.get("degrade_best_model") in (None, "none_poor_fit") or (
        d2.get("degrade_best_r2") is not None and d2.get("degrade_best_r2") < 0.3
    ) or d2.get("degrade_best_model") is None


class _FakeTSP:
    def __init__(self, test_name, resistances, **kw):
        self.test_name = test_name
        self.filename = kw.get("filename", "fake.tsp")
        self.sample = "X"
        self.device = "A1"
        self.timestamp = ""
        self.parameters = kw.get("parameters", {})
        self.resistances = np.asarray(resistances, dtype=float)
        self.currents = np.asarray(kw.get("currents", np.full_like(self.resistances, 1e-6)), dtype=float)
        self.voltages = np.asarray(kw.get("voltages", np.full_like(self.resistances, 0.1)), dtype=float)
        self.timestamps = kw.get("timestamps", np.arange(len(self.resistances), dtype=float))
        self.additional_data = kw.get("additional_data", {})


def test_pulse_family_aliases():
    from .pulse.loader import (
        FAMILY_DEP_ONLY,
        FAMILY_IV_SWEEP,
        FAMILY_LASER_READ,
        FAMILY_POT_ONLY,
        FAMILY_RANGE_FINDER,
        FAMILY_READ_REPEAT,
        FAMILY_RELAXATION,
        FAMILY_RETENTION,
        FAMILY_WIDTH_SWEEP,
        classify_pulse_family,
    )

    cases = [
        ("Width Sweep (Full)", FAMILY_WIDTH_SWEEP),
        ("Pulse Width Sweep (+ I)", FAMILY_WIDTH_SWEEP),
        ("Potentiation", FAMILY_POT_ONLY),
        ("Depression", FAMILY_DEP_ONLY),
        ("Relaxation after Multi Pulse", FAMILY_RELAXATION),
        ("SMU: Retention", FAMILY_RETENTION),
        ("Laser and Read", FAMILY_LASER_READ),
        ("Current Range Finder", FAMILY_RANGE_FINDER),
        ("Read → Write → Read", FAMILY_READ_REPEAT),
        ("IV Sweep (Hysteresis)", FAMILY_IV_SWEEP),
    ]
    for name, fam in cases:
        got = classify_pulse_family(test_name=name)
        assert got == fam, f"{name!r} → {got!r}, expected {fam!r}"


def test_pulse_new_family_metrics_smoke():
    from .pulse.metrics import extract_file_metrics
    from .pulse.plots import plot_pulse_dashboard
    from pathlib import Path
    import tempfile

    n = 40
    R = 1e4 * np.exp(-0.03 * np.arange(n))
    widths = np.logspace(-6, -3, n)
    cases = [
        _FakeTSP("Width Sweep", R, additional_data={"Pulse Width": widths}),
        _FakeTSP("Potentiation", R),
        _FakeTSP("Depression", R[::-1].copy()),
        _FakeTSP("Relaxation", R, timestamps=np.linspace(0, 10, n)),
        _FakeTSP("Retention", R, timestamps=np.linspace(0, 100, n)),
        _FakeTSP("Laser and Read", R),
        _FakeTSP(
            "Current Range Finder",
            R,
            currents=np.logspace(-9, -5, n),
        ),
        _FakeTSP(
            "IV Sweep",
            R,
            voltages=np.linspace(-1, 1, n),
            currents=np.linspace(-1e-6, 1e-6, n),
        ),
        _FakeTSP(
            "Pulse Read Repeat",
            R,
            additional_data={
                "Operation": ["READ", "WRITE"] * (n // 2),
            },
        ),
    ]
    with tempfile.TemporaryDirectory() as td:
        for tsp in cases:
            m = extract_file_metrics(tsp)
            assert m["supported"] is True, m
            assert m["family"] != "unsupported", m
            assert m.get("n_points", 0) > 0, m
            png = plot_pulse_dashboard(m, Path(td) / f"{m['family']}.png")
            assert png is not None and png.exists(), m["family"]


def main():
    tests = [
        test_synth_rc,
        test_synth_cpe,
        test_resistive_prefers_rs,
        test_dispersive_re_keeps_complex_model,
        test_origin_imag_negated,
        test_pulse_window_sign,
        test_pulse_family_aliases,
        test_pulse_new_family_metrics_smoke,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"OK  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    if failed:
        raise SystemExit(f"{failed} test(s) failed")
    print("All aux math self-tests passed.")


if __name__ == "__main__":
    main()
