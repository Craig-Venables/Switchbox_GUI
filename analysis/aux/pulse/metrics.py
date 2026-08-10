"""Deep pulse metrics: degradation / linearity / tau quality + anomaly tags."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit

from .loader import (
    FAMILY_DEP_ONLY,
    FAMILY_ENDURANCE,
    FAMILY_IV_SWEEP,
    FAMILY_LASER_READ,
    FAMILY_MULTI_READ,
    FAMILY_POT_DEP,
    FAMILY_POT_ONLY,
    FAMILY_PULSE_TRAIN,
    FAMILY_RANGE_FINDER,
    FAMILY_READ_ONLY,
    FAMILY_READ_REPEAT,
    FAMILY_RELAXATION,
    FAMILY_RETENTION,
    FAMILY_SLOW_PULSE,
    FAMILY_UNSUPPORTED,
    FAMILY_WIDTH_SWEEP,
    _PULSE_TOOL,
    classify_pulse_family,
    get_cycle_column,
    get_operation_column,
    get_phase_column,
    get_width_column,
)


def _finite(arr: np.ndarray) -> np.ndarray:
    a = np.asarray(arr, dtype=float)
    return a[np.isfinite(a)]


def _nanmean(arr) -> float:
    a = _finite(np.asarray(arr, dtype=float))
    return float(np.mean(a)) if a.size else float("nan")


def _nanstd(arr) -> float:
    a = _finite(np.asarray(arr, dtype=float))
    return float(np.std(a)) if a.size else float("nan")


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return float("nan")
    xx, yy = x[mask].astype(float), y[mask].astype(float)
    if np.allclose(xx, xx[0]):
        return float("nan")
    return float(np.polyfit(xx, yy, 1)[0])


def _r2(y, yhat) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    mask = np.isfinite(y) & np.isfinite(yhat)
    if mask.sum() < 3:
        return float("nan")
    yt, yp = y[mask], yhat[mask]
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def _label_str(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    return str(val).strip()


def fit_window_degradation(cyc: np.ndarray, window: np.ndarray) -> Dict[str, Any]:
    """Compete linear vs exponential vs power-law degradation of |window|."""
    mask = np.isfinite(cyc) & np.isfinite(window)
    x = cyc[mask].astype(float)
    y = np.abs(window[mask].astype(float))
    out: Dict[str, Any] = {
        "degrade_best_model": None,
        "degrade_best_r2": float("nan"),
    }
    if x.size < 5 or np.allclose(y, y[0]):
        return out

    models = {}

    # Linear: y = a + b x
    try:
        b1, a1 = np.polyfit(x, y, 1)
        yhat = a1 + b1 * x
        models["linear"] = {
            "r2": _r2(y, yhat),
            "a": float(a1),
            "b": float(b1),
        }
    except Exception:
        pass

    # Exp: y = y0 * exp(-k x)
    try:
        def exp_m(xx, y0, k):
            return y0 * np.exp(-k * xx)

        popt, _ = curve_fit(
            exp_m,
            x,
            y,
            p0=[y[0], 1e-3],
            bounds=([0, -1], [np.max(y) * 10 + 1, 1]),
            maxfev=5000,
        )
        yhat = exp_m(x, *popt)
        models["exponential"] = {
            "r2": _r2(y, yhat),
            "y0": float(popt[0]),
            "k": float(popt[1]),
        }
    except Exception:
        pass

    # Power: y = a * (x+1)^b
    try:
        def pow_m(xx, a, b):
            return a * np.power(xx + 1.0, b)

        popt, _ = curve_fit(
            pow_m,
            x,
            y,
            p0=[y[0], -0.1],
            bounds=([0, -5], [np.max(y) * 10 + 1, 5]),
            maxfev=5000,
        )
        yhat = pow_m(x, *popt)
        models["power"] = {
            "r2": _r2(y, yhat),
            "a": float(popt[0]),
            "b": float(popt[1]),
        }
    except Exception:
        pass

    out["degrade_models"] = models
    if models:
        best = max(
            models.items(),
            key=lambda kv: kv[1].get("r2") if np.isfinite(kv[1].get("r2", np.nan)) else -1,
        )
        best_r2 = best[1].get("r2", float("nan"))
        # Do not claim a degradation law if the fit is meaningless
        if np.isfinite(best_r2) and best_r2 >= 0.3:
            out["degrade_best_model"] = best[0]
            out["degrade_best_r2"] = best_r2
            for k, v in best[1].items():
                if k != "r2":
                    out[f"degrade_{k}"] = v
        else:
            out["degrade_best_model"] = "none_poor_fit"
            out["degrade_best_r2"] = best_r2
    return out


def extract_endurance_series(tsp_data) -> Dict[str, np.ndarray]:
    add = getattr(tsp_data, "additional_data", {}) or {}
    if "Resistance (Set)" in add and "Resistance (Reset)" in add:
        r_set = np.asarray(add["Resistance (Set)"], dtype=float)
        r_reset = np.asarray(add["Resistance (Reset)"], dtype=float)
        if "Cycle Number" in add:
            cyc = np.asarray(add["Cycle Number"], dtype=float)
        else:
            cyc = np.arange(len(r_set), dtype=float)
        n = min(len(cyc), len(r_set), len(r_reset))
        return {"cycle": cyc[:n], "r_set": r_set[:n], "r_reset": r_reset[:n]}

    R = np.asarray(tsp_data.resistances, dtype=float)
    ops = get_operation_column(tsp_data)
    cycles = get_cycle_column(tsp_data)

    if ops is None:
        if R.size < 2:
            return {"cycle": np.array([]), "r_set": np.array([]), "r_reset": np.array([])}
        r_set, r_reset, cyc = [], [], []
        i, c = 0, 0
        while i + 1 < len(R):
            r_set.append(R[i])
            r_reset.append(R[i + 1])
            cyc.append(c)
            c += 1
            i += 2
        return {
            "cycle": np.asarray(cyc, dtype=float),
            "r_set": np.asarray(r_set, dtype=float),
            "r_reset": np.asarray(r_reset, dtype=float),
        }

    ops_s = [_label_str(o).upper() for o in ops]
    cyc_arr = np.asarray(cycles, dtype=float) if cycles is not None else np.full(len(R), np.nan)
    by_cycle: Dict[int, Dict[str, float]] = {}
    synthetic = 0
    for i, op in enumerate(ops_s):
        if i >= len(R) or not np.isfinite(R[i]):
            continue
        if op in ("INIT", "INITIAL", "READ"):
            continue
        if "SET" in op and "RESET" not in op:
            key = "set"
        elif "RESET" in op or "RST" in op:
            key = "reset"
        else:
            continue
        if np.isfinite(cyc_arr[i]):
            c = int(cyc_arr[i])
        else:
            c = synthetic
            if key == "reset":
                synthetic += 1
        by_cycle.setdefault(c, {})
        by_cycle[c][key] = float(R[i])

    cycles_out, r_set, r_reset = [], [], []
    for c in sorted(by_cycle.keys()):
        entry = by_cycle[c]
        if "set" in entry or "reset" in entry:
            cycles_out.append(c)
            r_set.append(entry.get("set", float("nan")))
            r_reset.append(entry.get("reset", float("nan")))
    return {
        "cycle": np.asarray(cycles_out, dtype=float),
        "r_set": np.asarray(r_set, dtype=float),
        "r_reset": np.asarray(r_reset, dtype=float),
    }


def metrics_endurance(tsp_data) -> Dict[str, Any]:
    series = extract_endurance_series(tsp_data)
    cyc, r_set, r_reset = series["cycle"], series["r_set"], series["r_reset"]
    window = r_reset - r_set
    ratio = np.full_like(r_set, np.nan, dtype=float)
    for i in range(len(r_set)):
        a, b = r_set[i], r_reset[i]
        if np.isfinite(a) and np.isfinite(b) and min(a, b) != 0:
            ratio[i] = max(a, b) / min(a, b)

    n = int(np.sum(np.isfinite(r_set) | np.isfinite(r_reset)))
    mean_window = _nanmean(window)
    abs_w0 = abs(window[0]) if n and np.isfinite(window[0]) else float("nan")
    abs_wN = abs(window[-1]) if n and np.isfinite(window[-1]) else float("nan")
    window_pct_change = (
        (abs_wN - abs_w0) / abs_w0 * 100.0
        if np.isfinite(abs_w0) and abs_w0 != 0 and np.isfinite(abs_wN)
        else float("nan")
    )

    cycles_to_50 = float("nan")
    if n >= 4 and np.isfinite(window[0]) and window[0] != 0:
        target = 0.5 * abs(window[0])
        for i in range(len(window)):
            if np.isfinite(window[i]) and abs(window[i]) <= target:
                cycles_to_50 = float(cyc[i]) if i < len(cyc) else float(i)
                break

    last_n = min(10, len(r_set))
    out: Dict[str, Any] = {
        "family": FAMILY_ENDURANCE,
        "n_cycles": n,
        "r_set_mean": _nanmean(r_set),
        "r_set_std": _nanstd(r_set),
        "r_reset_mean": _nanmean(r_reset),
        "r_reset_std": _nanstd(r_reset),
        "r_set_first": float(r_set[0]) if n else float("nan"),
        "r_set_last": float(r_set[-1]) if n else float("nan"),
        "r_reset_first": float(r_reset[0]) if n else float("nan"),
        "r_reset_last": float(r_reset[-1]) if n else float("nan"),
        "window_mean": mean_window,
        "window_first": float(window[0]) if n else float("nan"),
        "window_last": float(window[-1]) if n else float("nan"),
        "window_pct_change": window_pct_change,
        "on_off_ratio_mean": _nanmean(ratio),
        "on_off_ratio_first": float(ratio[0]) if n and np.isfinite(ratio[0]) else float("nan"),
        "on_off_ratio_last": float(ratio[-1]) if n and np.isfinite(ratio[-1]) else float("nan"),
        "slope_r_set_per_cycle": _slope(cyc, r_set),
        "slope_r_reset_per_cycle": _slope(cyc, r_reset),
        "slope_window_per_cycle": _slope(cyc, window),
        "cycles_to_50pct_window": cycles_to_50,
        "last_n": last_n,
        "last_n_r_set_std": _nanstd(r_set[-last_n:]) if last_n else float("nan"),
        "last_n_r_reset_std": _nanstd(r_reset[-last_n:]) if last_n else float("nan"),
        "last_n_window_mean": _nanmean(window[-last_n:]) if last_n else float("nan"),
        "cv_last_n_window": (
            _nanstd(window[-last_n:]) / abs(_nanmean(window[-last_n:]))
            if last_n and abs(_nanmean(window[-last_n:])) > 0
            else float("nan")
        ),
        "_series": series,
    }
    out.update(fit_window_degradation(cyc, window))

    anomalies: List[str] = []
    if n >= 3 and (not np.isfinite(mean_window) or abs(mean_window) < 1.0):
        anomalies.append("no_switching_window")
    if np.isfinite(out.get("on_off_ratio_mean", np.nan)) and out["on_off_ratio_mean"] < 1.05:
        anomalies.append("failed_switch_ratio")
    if np.isfinite(window_pct_change) and window_pct_change < -50:
        anomalies.append("severe_window_collapse")
    if np.isfinite(cycles_to_50):
        anomalies.append("hit_50pct_window")
    out["anomalies"] = anomalies
    out["anomalies_str"] = ",".join(anomalies)
    return out


def _linearity(x: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return {"linearity_r2": float("nan"), "linearity_slope": float("nan")}
    xx, yy = x[mask].astype(float), y[mask].astype(float)
    slope, intercept = np.polyfit(xx, yy, 1)
    yhat = intercept + slope * xx
    return {"linearity_r2": _r2(yy, yhat), "linearity_slope": float(slope)}


def metrics_pot_dep(tsp_data) -> Dict[str, Any]:
    R = np.asarray(tsp_data.resistances, dtype=float)
    phases = get_phase_column(tsp_data)
    idx = np.arange(len(R))

    pot_mask = np.zeros(len(R), dtype=bool)
    dep_mask = np.zeros(len(R), dtype=bool)
    if phases is not None:
        for i, p in enumerate(phases):
            if i >= len(R):
                break
            pl = _label_str(p).lower()
            if "pot" in pl:
                pot_mask[i] = True
            elif "dep" in pl:
                dep_mask[i] = True
    else:
        if len(R) > 2:
            mid = len(R) // 2
            pot_mask[1:mid] = True
            dep_mask[mid:] = True

    r_pot, r_dep = R[pot_mask], R[dep_mask]
    r_all = _finite(R)
    r_min = float(np.min(r_all)) if r_all.size else float("nan")
    r_max = float(np.max(r_all)) if r_all.size else float("nan")
    dynamic_range = r_max - r_min if np.isfinite(r_max) and np.isfinite(r_min) else float("nan")

    pot_start = _nanmean(r_pot[:3]) if r_pot.size else float("nan")
    pot_end = _nanmean(r_pot[-3:]) if r_pot.size else float("nan")
    dep_start = _nanmean(r_dep[:3]) if r_dep.size else float("nan")
    dep_end = _nanmean(r_dep[-3:]) if r_dep.size else float("nan")
    pot_excursion = pot_end - pot_start if np.isfinite(pot_end) and np.isfinite(pot_start) else float("nan")
    dep_excursion = dep_end - dep_start if np.isfinite(dep_end) and np.isfinite(dep_start) else float("nan")

    asymmetry = float("nan")
    if np.isfinite(pot_excursion) and np.isfinite(dep_excursion) and abs(pot_excursion) > 0:
        asymmetry = abs(dep_excursion) / abs(pot_excursion)

    cycle_drift = float("nan")
    if phases is not None:
        cycle_ends = []
        prev = ""
        for i, p in enumerate(phases):
            pl = _label_str(p).lower()
            if "dep" in prev and "pot" in pl and i > 0:
                cycle_ends.append(R[i - 1])
            prev = pl
        if len(phases) and "dep" in _label_str(phases[-1]).lower():
            cycle_ends.append(R[-1])
        if len(cycle_ends) >= 2:
            cycle_drift = float(np.asarray(cycle_ends, dtype=float)[-1] - cycle_ends[0])

    dR = np.diff(R[np.isfinite(R)])
    max_dR = float(np.max(np.abs(dR))) if dR.size else float("nan")

    pot_lin = _linearity(np.arange(r_pot.size, dtype=float), r_pot) if r_pot.size else {}
    dep_lin = _linearity(np.arange(r_dep.size, dtype=float), r_dep) if r_dep.size else {}

    out: Dict[str, Any] = {
        "family": FAMILY_POT_DEP,
        "n_points": int(r_all.size),
        "n_pot": int(r_pot.size),
        "n_dep": int(r_dep.size),
        "r_min": r_min,
        "r_max": r_max,
        "dynamic_range": dynamic_range,
        "pot_excursion": pot_excursion,
        "dep_excursion": dep_excursion,
        "asymmetry_dep_over_pot": asymmetry,
        "cycle_drift": cycle_drift,
        "max_abs_delta_r": max_dR,
        "r_mean": _nanmean(R),
        "pot_linearity_r2": pot_lin.get("linearity_r2", float("nan")),
        "pot_linearity_slope": pot_lin.get("linearity_slope", float("nan")),
        "dep_linearity_r2": dep_lin.get("linearity_r2", float("nan")),
        "dep_linearity_slope": dep_lin.get("linearity_slope", float("nan")),
        "_r": R,
        "_phases": phases,
        "_index": idx,
    }
    anomalies: List[str] = []
    if not np.isfinite(dynamic_range) or dynamic_range < 100:
        anomalies.append("weak_pot_dep_range")
    if np.isfinite(asymmetry) and asymmetry > 5:
        anomalies.append("strongly_asymmetric_pot_dep")
    out["anomalies"] = anomalies
    out["anomalies_str"] = ",".join(anomalies)
    return out


def metrics_multi_read(tsp_data, family: str = FAMILY_MULTI_READ) -> Dict[str, Any]:
    R = np.asarray(tsp_data.resistances, dtype=float)
    t = (
        np.asarray(tsp_data.timestamps, dtype=float)
        if tsp_data.timestamps is not None and len(tsp_data.timestamps)
        else np.arange(len(R), dtype=float)
    )
    r_fin = _finite(R)
    if r_fin.size == 0:
        return {"family": family, "n_points": 0, "anomalies": ["empty"], "anomalies_str": "empty"}

    r0 = float(R[0]) if np.isfinite(R[0]) else float(r_fin[0])
    r_final = float(R[np.where(np.isfinite(R))[0][-1]])
    delta = r_final - r0
    pct = (delta / r0 * 100.0) if r0 != 0 else float("nan")

    tau = float("nan")
    r_squared = float("nan")
    fit_ok = False
    relax_type = ""
    if r_fin.size >= 8:
        try:
            import sys

            if str(_PULSE_TOOL) not in sys.path:
                sys.path.insert(0, str(_PULSE_TOOL))
            from core.statistics import DataStatistics  # type: ignore

            mask = np.isfinite(R) & np.isfinite(t)
            stats = DataStatistics(t[mask], R[mask], test_type="multi_read")
            rel = stats.relaxation_time()
            if rel.get("Fit Success"):
                tau = float(rel.get("Tau (Relaxation Time)", float("nan")))
                r_squared = float(rel.get("R_squared", float("nan")))
                relax_type = str(rel.get("Relaxation Type", ""))
                fit_ok = bool(np.isfinite(r_squared) and r_squared >= 0.85)
        except Exception:
            pass

    # Classify trend
    if abs(pct) < 2:
        trend = "flat"
    elif pct > 0:
        trend = "increase"
    else:
        trend = "decrease"

    out: Dict[str, Any] = {
        "family": family,
        "n_points": int(r_fin.size),
        "r_initial": r0,
        "r_final": r_final,
        "delta_r": delta,
        "percent_change": pct,
        "read_train_std": _nanstd(R),
        "r_mean": _nanmean(R),
        "r_min": float(np.min(r_fin)),
        "r_max": float(np.max(r_fin)),
        "tau_s": tau,
        "tau_r_squared": r_squared,
        "tau_fit_ok": fit_ok,
        "tau_type": relax_type,
        "trend": trend,
        "cv": _nanstd(R) / abs(_nanmean(R)) if abs(_nanmean(R)) > 0 else float("nan"),
        "_r": R,
        "_t": t,
    }
    anomalies: List[str] = []
    if np.isfinite(tau) and (tau > 1e4 or (np.isfinite(r_squared) and r_squared < 0.85)):
        anomalies.append("tau_unreliable")
    if trend == "flat" and r_fin.size > 5 and family in (
        FAMILY_RELAXATION,
        FAMILY_RETENTION,
        FAMILY_MULTI_READ,
        FAMILY_PULSE_TRAIN,
    ):
        anomalies.append("no_relaxation")
    out["anomalies"] = anomalies
    out["anomalies_str"] = ",".join(anomalies)
    return out


def metrics_mono_phase(tsp_data, family: str) -> Dict[str, Any]:
    """Potentiation-only or depression-only: excursion + linearity."""
    R = np.asarray(tsp_data.resistances, dtype=float)
    r = _finite(R)
    idx = np.arange(len(R))
    if r.size == 0:
        return {"family": family, "n_points": 0, "anomalies": ["empty"], "anomalies_str": "empty"}
    r0, rN = float(r[0]), float(r[-1])
    lin = _linearity(np.arange(r.size, dtype=float), r)
    out = {
        "family": family,
        "n_points": int(r.size),
        "r_initial": r0,
        "r_final": rN,
        "excursion": rN - r0,
        "percent_change": (rN - r0) / r0 * 100.0 if r0 != 0 else float("nan"),
        "r_min": float(np.min(r)),
        "r_max": float(np.max(r)),
        "dynamic_range": float(np.max(r) - np.min(r)),
        "linearity_r2": lin.get("linearity_r2", float("nan")),
        "linearity_slope": lin.get("linearity_slope", float("nan")),
        "_r": R,
        "_index": idx,
    }
    anomalies: List[str] = []
    if abs(out["excursion"]) < 100:
        anomalies.append("weak_pot_dep_range")
    out["anomalies"] = anomalies
    out["anomalies_str"] = ",".join(anomalies)
    return out


def metrics_width_sweep(tsp_data) -> Dict[str, Any]:
    """R vs pulse width: threshold width and dynamic range."""
    R = np.asarray(tsp_data.resistances, dtype=float)
    widths = get_width_column(tsp_data)
    t = (
        np.asarray(tsp_data.timestamps, dtype=float)
        if tsp_data.timestamps is not None and len(tsp_data.timestamps)
        else np.arange(len(R), dtype=float)
    )
    if widths is not None:
        w = np.asarray(widths, dtype=float)
    else:
        w = np.full(len(R), np.nan)

    mask = np.isfinite(R)
    if widths is not None:
        mask = mask & np.isfinite(w)
    r = R[mask]
    ww = w[mask] if widths is not None else np.arange(r.size, dtype=float)

    out: Dict[str, Any] = {
        "family": FAMILY_WIDTH_SWEEP,
        "n_points": int(r.size),
        "r_min": float(np.min(r)) if r.size else float("nan"),
        "r_max": float(np.max(r)) if r.size else float("nan"),
        "dynamic_range": float(np.ptp(r)) if r.size else float("nan"),
        "width_min": float(np.nanmin(ww)) if ww.size and np.any(np.isfinite(ww)) else float("nan"),
        "width_max": float(np.nanmax(ww)) if ww.size and np.any(np.isfinite(ww)) else float("nan"),
        "has_width_column": widths is not None,
        "_r": R,
        "_widths": w if widths is not None else None,
        "_t": t,
        "_index": np.arange(len(R)),
    }

    threshold = float("nan")
    if r.size >= 4 and np.any(np.isfinite(ww)):
        mid = 0.5 * (np.nanmin(r) + np.nanmax(r))
        order = np.argsort(ww)
        ww_s, r_s = ww[order], r[order]
        crossed = np.where(np.diff(np.sign(r_s - mid)) != 0)[0]
        if crossed.size:
            i = int(crossed[0])
            if ww_s[i + 1] != ww_s[i]:
                frac = (mid - r_s[i]) / (r_s[i + 1] - r_s[i]) if r_s[i + 1] != r_s[i] else 0.0
                threshold = float(ww_s[i] + frac * (ww_s[i + 1] - ww_s[i]))
            else:
                threshold = float(ww_s[i])
    out["threshold_width_s"] = threshold

    if r.size >= 4 and np.any(np.isfinite(ww)) and np.all(ww[np.isfinite(ww)] > 0):
        m = np.isfinite(ww) & np.isfinite(r)
        lin = _linearity(np.log10(ww[m]), r[m])
        out["logwidth_linearity_r2"] = lin.get("linearity_r2", float("nan"))
        out["logwidth_linearity_slope"] = lin.get("linearity_slope", float("nan"))

    anomalies: List[str] = []
    if not np.isfinite(out["dynamic_range"]) or out["dynamic_range"] < 100:
        anomalies.append("weak_width_response")
    out["anomalies"] = anomalies
    out["anomalies_str"] = ",".join(anomalies)
    return out


def metrics_read_repeat(tsp_data) -> Dict[str, Any]:
    """Read→Write→Read: op-labeled read stats when available, else multi-read train metrics."""
    base = metrics_multi_read(tsp_data, family=FAMILY_READ_REPEAT)
    ops = get_operation_column(tsp_data)
    R = np.asarray(tsp_data.resistances, dtype=float)
    if ops is not None and len(ops) == len(R):
        reads = []
        for i, op in enumerate(ops):
            if "READ" in _label_str(op).upper() or "INIT" in _label_str(op).upper():
                if np.isfinite(R[i]):
                    reads.append(float(R[i]))
        if len(reads) >= 2:
            reads_a = np.asarray(reads, dtype=float)
            base["n_reads"] = int(reads_a.size)
            base["read_mean"] = float(np.mean(reads_a))
            base["read_std"] = float(np.std(reads_a))
            d = np.diff(reads_a)
            base["mean_abs_delta_read"] = float(np.mean(np.abs(d))) if d.size else float("nan")
            base["max_abs_delta_read"] = float(np.max(np.abs(d))) if d.size else float("nan")
    return base


def metrics_range_finder(tsp_data) -> Dict[str, Any]:
    I = np.asarray(tsp_data.currents, dtype=float)
    R = np.asarray(tsp_data.resistances, dtype=float)
    V = np.asarray(tsp_data.voltages, dtype=float)
    i_fin = _finite(I)
    out = {
        "family": FAMILY_RANGE_FINDER,
        "n_points": int(i_fin.size),
        "i_min": float(np.min(np.abs(i_fin))) if i_fin.size else float("nan"),
        "i_max": float(np.max(np.abs(i_fin))) if i_fin.size else float("nan"),
        "i_mean_abs": float(np.mean(np.abs(i_fin))) if i_fin.size else float("nan"),
        "r_mean": _nanmean(R),
        "v_mean": _nanmean(V),
        "_r": R,
        "_i": I,
        "_t": np.arange(len(R)),
    }
    if i_fin.size and np.max(np.abs(i_fin)) > 0:
        out["suggested_i_range"] = float(10 ** np.ceil(np.log10(np.max(np.abs(i_fin)))))
    else:
        out["suggested_i_range"] = float("nan")
    out["anomalies"] = []
    out["anomalies_str"] = ""
    return out


def metrics_iv_in_pulse(tsp_data) -> Dict[str, Any]:
    V = np.asarray(tsp_data.voltages, dtype=float)
    I = np.asarray(tsp_data.currents, dtype=float)
    mask = np.isfinite(V) & np.isfinite(I)
    return {
        "family": FAMILY_IV_SWEEP,
        "n_points": int(mask.sum()),
        "v_min": float(np.nanmin(V)) if mask.any() else float("nan"),
        "v_max": float(np.nanmax(V)) if mask.any() else float("nan"),
        "i_min": float(np.nanmin(I)) if mask.any() else float("nan"),
        "i_max": float(np.nanmax(I)) if mask.any() else float("nan"),
        "_v": V,
        "_i": I,
        "anomalies": [],
        "anomalies_str": "",
    }


def extract_file_metrics(tsp_data, filepath: Optional[str] = None) -> Dict[str, Any]:
    family = classify_pulse_family(
        test_name=getattr(tsp_data, "test_name", "") or "",
        filename=filepath or getattr(tsp_data, "filename", "") or "",
    )
    params = dict(getattr(tsp_data, "parameters", {}) or {})
    base: Dict[str, Any] = {
        "filename": getattr(tsp_data, "filename", ""),
        "test_name": getattr(tsp_data, "test_name", ""),
        "sample": getattr(tsp_data, "sample", ""),
        "device": getattr(tsp_data, "device", ""),
        "timestamp": getattr(tsp_data, "timestamp", ""),
        "parameters": params,
        "family": family,
        "supported": family != FAMILY_UNSUPPORTED,
    }
    bits = []
    for k in (
        "set_voltage",
        "reset_voltage",
        "pulse_voltage",
        "pulse_width",
        "num_cycles",
        "num_reads",
        "num_pulses",
        "read_voltage",
    ):
        if k in params:
            bits.append(f"{k}={params[k]}")
    base["param_summary"] = ", ".join(bits)

    if family == FAMILY_ENDURANCE:
        base.update(metrics_endurance(tsp_data))
    elif family == FAMILY_POT_DEP:
        base.update(metrics_pot_dep(tsp_data))
    elif family == FAMILY_POT_ONLY:
        base.update(metrics_mono_phase(tsp_data, FAMILY_POT_ONLY))
    elif family == FAMILY_DEP_ONLY:
        base.update(metrics_mono_phase(tsp_data, FAMILY_DEP_ONLY))
    elif family == FAMILY_WIDTH_SWEEP:
        base.update(metrics_width_sweep(tsp_data))
    elif family == FAMILY_READ_REPEAT:
        base.update(metrics_read_repeat(tsp_data))
    elif family == FAMILY_RANGE_FINDER:
        base.update(metrics_range_finder(tsp_data))
    elif family == FAMILY_IV_SWEEP:
        base.update(metrics_iv_in_pulse(tsp_data))
    elif family in (
        FAMILY_MULTI_READ,
        FAMILY_PULSE_TRAIN,
        FAMILY_READ_ONLY,
        FAMILY_RELAXATION,
        FAMILY_RETENTION,
        FAMILY_LASER_READ,
        FAMILY_SLOW_PULSE,
    ):
        base.update(metrics_multi_read(tsp_data, family=family))
    else:
        R = np.asarray(tsp_data.resistances, dtype=float)
        r = _finite(R)
        base.update(
            {
                "n_points": int(r.size),
                "r_mean": _nanmean(R),
                "r_min": float(np.min(r)) if r.size else float("nan"),
                "r_max": float(np.max(r)) if r.size else float("nan"),
                "anomalies": ["unsupported_family"],
                "anomalies_str": "unsupported_family",
            }
        )
    return base


def flatten_metrics_row(metrics: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {}
    for k, v in metrics.items():
        if k.startswith("_"):
            continue
        if k == "parameters":
            for pk, pv in (v or {}).items():
                row[f"param_{pk}"] = pv
            continue
        if k == "anomalies" and isinstance(v, list):
            row["anomalies_str"] = ",".join(v)
            continue
        if k == "degrade_models" and isinstance(v, dict):
            for mk, mv in v.items():
                if isinstance(mv, dict) and "r2" in mv:
                    row[f"degrade_r2_{mk}"] = mv["r2"]
            continue
        if isinstance(v, (np.ndarray, list, dict)):
            continue
        if isinstance(v, (np.floating, np.integer)):
            row[k] = v.item()
        else:
            row[k] = v
    return row
