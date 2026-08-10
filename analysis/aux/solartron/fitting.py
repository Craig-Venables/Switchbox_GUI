"""
Deep Solartron / EIS calculations: admittance, capacitance models,
equivalent-circuit fits, and data-quality flags.

Sign convention
---------------
Physics uses Z = |Z| e^{jφ} with capacitive φ < 0 ⇒ Im(Z) < 0.
Origin exports often store Z_Imag_Ohms as (-Im(Z)) for Nyquist plotting.
Always prefer magnitude+phase when available; if only Origin Re/Im are
present, treat Origin Im as -Im(Z) via ``origin_imag_is_negated=True``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import least_squares


def _clean_spectrum(
    f: np.ndarray,
    z_re: np.ndarray,
    z_im: np.ndarray,
    max_freq: float = 1e6,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mask = (
        np.isfinite(f)
        & np.isfinite(z_re)
        & np.isfinite(z_im)
        & (f > 0)
        & (f <= max_freq)
    )
    f, z_re, z_im = f[mask], z_re[mask], z_im[mask]
    order = np.argsort(f)
    return f[order], z_re[order], z_im[order]


def complex_from_mag_phase(mag: np.ndarray, phase_deg: np.ndarray) -> np.ndarray:
    phase = np.deg2rad(phase_deg)
    return np.abs(mag) * (np.cos(phase) + 1j * np.sin(phase))


def nyquist_intercepts(f: np.ndarray, z_re: np.ndarray, z_im: np.ndarray) -> Dict[str, float]:
    """
    Correct Randles-style intercepts:
      Rs  ≈ Re(Z) at high frequency (left of capacitive arc)
      Rtot ≈ Re(Z) at low frequency (right) ≈ Rs + Rp
      Rp  ≈ Rtot - Rs
      f_peak at max(-Im(Z)) for capacitive arcs
    """
    f, z_re, z_im = _clean_spectrum(f, z_re, z_im)
    out = {
        "intercept_Rs": float("nan"),
        "intercept_Rtot": float("nan"),
        "intercept_Rp": float("nan"),
        "intercept_f_peak_hz": float("nan"),
        "intercept_tau_s": float("nan"),
    }
    if len(f) < 4:
        return out
    neg_im = -z_im
    hf = f >= np.percentile(f, 80)
    lf = f <= np.percentile(f, 20)
    # HF → series resistance (typically smallest Re)
    out["intercept_Rs"] = float(np.nanmedian(z_re[hf]))
    out["intercept_Rtot"] = float(np.nanmedian(z_re[lf]))
    rp = out["intercept_Rtot"] - out["intercept_Rs"]
    out["intercept_Rp"] = float(rp)
    out["flag_inverted_intercepts"] = bool(rp < 0)
    if rp < 0:
        # Not a classic HF-left / LF-right arc; still report values but Rp meaningless
        out["intercept_Rp"] = float("nan")
    peak_i = int(np.argmax(neg_im))
    fp = float(f[peak_i])
    out["intercept_f_peak_hz"] = fp
    if fp > 0:
        out["intercept_tau_s"] = 1.0 / (2.0 * np.pi * fp)
    return out


def admittance_metrics(f: np.ndarray, z: np.ndarray) -> Dict[str, Any]:
    """Y, Cs, Cp, loss tangent. Requires physics Im(Z) (capacitive < 0)."""
    out: Dict[str, Any] = {}
    if len(f) < 3:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        y = 1.0 / z
        w = 2.0 * np.pi * f
        cp_raw = np.imag(y) / w  # capacitive ⇒ Im(Y)>0 ⇒ Cp>0
        cp = np.where(cp_raw > 0, cp_raw, np.nan)
        cs_raw = np.where(np.abs(np.imag(z)) > 0, -1.0 / (w * np.imag(z)), np.nan)
        cs = np.where(cs_raw > 0, cs_raw, np.nan)
        tan_d = np.where(cp_raw > 0, np.real(y) / np.imag(y), np.nan)

    def _at_nearest(arr, f0):
        i = int(np.argmin(np.abs(f - f0)))
        v = arr[i]
        return float(v) if np.isfinite(v) else float("nan")

    for f0, tag in ((1.0, "1Hz"), (10.0, "10Hz"), (100.0, "100Hz"), (1e3, "1kHz"), (1e4, "10kHz")):
        if f.min() <= f0 <= f.max():
            out[f"Cp_{tag}"] = _at_nearest(cp, f0)
            out[f"Cs_{tag}"] = _at_nearest(cs, f0)
            out[f"tan_delta_{tag}"] = _at_nearest(tan_d, f0)

    cp_fin = cp[np.isfinite(cp)]
    cs_fin = cs[np.isfinite(cs)]
    out["Cp_median"] = float(np.median(cp_fin)) if cp_fin.size else float("nan")
    out["Cs_median"] = float(np.median(cs_fin)) if cs_fin.size else float("nan")
    out["Cp_std"] = float(np.std(cp_fin)) if cp_fin.size else float("nan")
    out["frac_capacitive_points"] = float(np.mean(np.isfinite(cp))) if len(cp) else float("nan")
    if f.min() <= 10 and f.max() >= 1e3:
        c10 = _at_nearest(cp, 10.0)
        c1k = _at_nearest(cp, 1e3)
        out["Cp_dispersion_10Hz_over_1kHz"] = (
            c10 / c1k if np.isfinite(c10) and np.isfinite(c1k) and c1k != 0 else float("nan")
        )
    return out


def _ssr(z_meas: np.ndarray, z_fit: np.ndarray) -> float:
    return float(np.sum(np.abs(z_meas - z_fit) ** 2))


def _r2_complex(z_meas: np.ndarray, z_fit: np.ndarray) -> float:
    ss_res = _ssr(z_meas, z_fit)
    ss_tot = float(np.sum(np.abs(z_meas - np.mean(z_meas)) ** 2))
    if ss_tot <= 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def _rmse_rel(z_meas: np.ndarray, z_fit: np.ndarray) -> float:
    denom = np.maximum(np.abs(z_meas), 1e-30)
    return float(np.sqrt(np.mean((np.abs(z_meas - z_fit) / denom) ** 2)))


def _aic(ssr: float, n: int, k: int) -> float:
    """Akaike information criterion for complex residual (2n real points)."""
    n_obs = 2 * n  # real + imag
    if n_obs <= k + 1 or ssr <= 0:
        return float("inf")
    return n_obs * np.log(ssr / n_obs) + 2 * k


def _model_rs(w: np.ndarray, rs: float) -> np.ndarray:
    return np.full_like(w, rs, dtype=complex)


def _model_rs_c(w: np.ndarray, rs: float, c: float) -> np.ndarray:
    return rs + 1.0 / (1j * w * c)


def _model_rs_rp_c(w: np.ndarray, rs: float, rp: float, c: float) -> np.ndarray:
    return rs + 1.0 / (1.0 / rp + 1j * w * c)


def _model_rs_rp_cpe(w: np.ndarray, rs: float, rp: float, q: float, alpha: float) -> np.ndarray:
    # Z = Rs + 1 / (1/Rp + Q (jω)^α)  — standard parallel CPE–Rp with series Rs
    jw_a = (1j * w) ** alpha
    return rs + 1.0 / (1.0 / rp + q * jw_a)


def _fit_model(
    name: str,
    w: np.ndarray,
    z: np.ndarray,
    x0: List[float],
    bounds: Tuple[List[float], List[float]],
    model_fn,
    n_params: int,
) -> Dict[str, Any]:
    def residual(x):
        zf = model_fn(w, *x)
        return np.concatenate([np.real(z - zf), np.imag(z - zf)])

    try:
        res = least_squares(residual, x0, bounds=bounds, max_nfev=8000)
        z_fit = model_fn(w, *res.x)
        ssr = _ssr(z, z_fit)
        r2 = _r2_complex(z, z_fit)
        rmse = _rmse_rel(z, z_fit)
        return {
            "model": name,
            "success": bool(res.success),
            "r2": float(r2),
            "rmse_rel": float(rmse),
            "ssr": float(ssr),
            "aic": float(_aic(ssr, len(z), n_params)),
            "n_params": n_params,
            "x": [float(v) for v in res.x],
        }
    except Exception as e:
        return {
            "model": name,
            "success": False,
            "r2": float("nan"),
            "rmse_rel": float("nan"),
            "ssr": float("inf"),
            "aic": float("inf"),
            "n_params": n_params,
            "error": str(e),
            "x": [],
        }


def fit_equivalent_circuits(
    f: np.ndarray,
    z_re: np.ndarray,
    z_im: np.ndarray,
) -> Dict[str, Any]:
    """
    Compete EIS models; select by AIC (lower better), with R² reported.
    Models: Rs, Rs-C, Rs-(Rp||C), Rs-(Rp||CPE).
    """
    f, z_re, z_im = _clean_spectrum(f, z_re, z_im)
    out: Dict[str, Any] = {"n_points_fit": int(len(f)), "models": {}, "best_model": None}
    if len(f) < 8:
        out["error"] = "insufficient_points"
        return out

    z = z_re + 1j * z_im
    w = 2.0 * np.pi * f

    # Guesses: HF Re ≈ Rs, LF Re - Rs ≈ Rp
    n_tail = max(3, len(z_re) // 10)
    rs0 = float(np.median(z_re[-n_tail:]))
    r_lf = float(np.median(z_re[:n_tail]))
    rp0 = float(max(r_lf - rs0, abs(rs0) * 0.05, 1.0))
    im_abs = np.abs(z_im)
    i_peak = int(np.argmax(im_abs)) if im_abs.size else len(w) // 2
    w_peak = float(w[i_peak]) if w[i_peak] > 0 else float(np.median(w))
    c0 = float(np.clip(1.0 / (w_peak * max(rp0, 1.0)), 1e-15, 1e-3))
    q0 = c0
    rs0 = float(max(rs0, 1e-3))

    im_frac = float(np.median(np.abs(z_im)) / max(np.median(np.abs(z_re)), 1e-30))
    out["im_over_re_median"] = im_frac

    candidates: List[Dict[str, Any]] = []

    m_rs = _fit_model("Rs", w, z, [rs0], ([1e-3], [1e12]), lambda ww, rs: _model_rs(ww, rs), 1)
    if m_rs.get("x"):
        m_rs["named_params"] = {"Rs": m_rs["x"][0]}
        candidates.append(m_rs)

    m_rsc = _fit_model(
        "Rs_C", w, z, [rs0, c0], ([1e-3, 1e-15], [1e12, 1e-3]),
        lambda ww, rs, c: _model_rs_c(ww, rs, c), 2,
    )
    if m_rsc.get("x"):
        m_rsc["named_params"] = {"Rs": m_rsc["x"][0], "C": m_rsc["x"][1]}
        candidates.append(m_rsc)

    m_rrc = _fit_model(
        "Rs_Rp_C", w, z, [rs0, rp0, c0], ([1e-3, 1e-3, 1e-15], [1e12, 1e15, 1e-3]),
        lambda ww, rs, rp, c: _model_rs_rp_c(ww, rs, rp, c), 3,
    )
    if m_rrc.get("x"):
        m_rrc["named_params"] = {
            "Rs": m_rrc["x"][0],
            "Rp": m_rrc["x"][1],
            "C": m_rrc["x"][2],
            "tau_RC": m_rrc["x"][1] * m_rrc["x"][2],
        }
        candidates.append(m_rrc)

    m_cpe = _fit_model(
        "Rs_Rp_CPE", w, z, [rs0, rp0, q0, 0.9],
        ([1e-3, 1e-3, 1e-15, 0.2], [1e12, 1e15, 1e-3, 1.0]),
        lambda ww, rs, rp, q, a: _model_rs_rp_cpe(ww, rs, rp, q, a), 4,
    )
    if m_cpe.get("x"):
        m_cpe["named_params"] = {
            "Rs": m_cpe["x"][0],
            "Rp": m_cpe["x"][1],
            "Q": m_cpe["x"][2],
            "alpha": m_cpe["x"][3],
        }
        candidates.append(m_cpe)

    for m in candidates:
        out["models"][m["model"]] = {
            "r2": m.get("r2"),
            "rmse_rel": m.get("rmse_rel"),
            "aic": m.get("aic"),
            "success": m.get("success"),
            **(m.get("named_params") or {}),
        }

    if not candidates:
        return out

    # Primary: lowest AIC among successful / finite fits
    valid = [m for m in candidates if np.isfinite(m.get("aic", np.nan))]
    if not valid:
        valid = candidates
    best = min(valid, key=lambda m: m.get("aic", np.inf))

    # Nearly ohmic + flat Re(Z): prefer Rs. If Re disperses, a CPE/RC may still be justified
    # even when Im/Re is small.
    rs_cand = next((c for c in candidates if c["model"] == "Rs"), None)
    re_cv = float(np.nanstd(z_re) / max(np.nanmedian(np.abs(z_re)), 1e-30))
    out["re_cv"] = re_cv
    if rs_cand and im_frac < 0.05 and re_cv < 0.05:
        r2_rs = rs_cand.get("r2", float("nan"))
        r2_best = best.get("r2", float("nan"))
        if np.isfinite(r2_rs) and np.isfinite(r2_best) and r2_rs >= max(0.0, r2_best - 0.02):
            best = rs_cand
        elif np.isfinite(rs_cand.get("aic")) and rs_cand["aic"] <= best.get("aic", np.inf) + 6:
            best = rs_cand

    # Degenerate CPE (alpha≈1 and Q≈C): prefer Rs_Rp_C if close in AIC
    if best["model"] == "Rs_Rp_CPE" and best.get("named_params", {}).get("alpha", 0) > 0.97:
        rrc = next((c for c in candidates if c["model"] == "Rs_Rp_C"), None)
        if rrc and np.isfinite(rrc.get("aic")) and rrc["aic"] <= best.get("aic", np.inf) + 4:
            best = rrc

    out["best_model"] = best["model"]
    out["best_r2"] = best.get("r2")
    out["best_rmse_rel"] = best.get("rmse_rel")
    out["best_aic"] = best.get("aic")
    for k, v in (best.get("named_params") or {}).items():
        out[f"fit_{k}"] = v
    return out


def quality_flags(f: np.ndarray, z_re: np.ndarray, z_im: np.ndarray, fit: Dict[str, Any]) -> Dict[str, Any]:
    f, z_re, z_im = _clean_spectrum(f, z_re, z_im)
    out: Dict[str, Any] = {}
    r2 = fit.get("best_r2")
    rmse = fit.get("best_rmse_rel")
    out["fit_ok"] = bool(isinstance(r2, (int, float)) and r2 == r2 and r2 > 0.7)
    out["data_quality"] = (
        "good" if out["fit_ok"] and isinstance(rmse, (int, float)) and rmse == rmse and rmse < 0.15
        else "fair" if out["fit_ok"]
        else "poor"
    )
    hf = f >= np.percentile(f, 90)
    lf = f <= np.percentile(f, 10)
    # +Im(Z) at HF ⇒ inductive artifact (physics convention)
    out["flag_hf_inductive"] = bool(np.nanmedian(z_im[hf]) > 0)
    out["flag_lf_noisy"] = bool(
        np.nanstd(z_re[lf]) / max(abs(np.nanmedian(z_re[lf])), 1.0) > 0.05
    )
    im_frac = float(np.median(np.abs(z_im)) / max(np.median(np.abs(z_re)), 1e-30))
    out["flag_nearly_resistive"] = bool(im_frac < 0.02)
    out["im_over_re_median"] = im_frac
    return out


def deep_eis_analysis(
    f: np.ndarray,
    z_re: np.ndarray,
    z_im: np.ndarray,
    mag: Optional[np.ndarray] = None,
    phase_deg: Optional[np.ndarray] = None,
    origin_imag_is_negated: bool = False,
) -> Dict[str, Any]:
    """
    Full deep bundle for one spectrum.

    Prefer mag+phase. If only Re/Im from Origin, set origin_imag_is_negated=True
    so stored (+Nyquist) imag is converted to physics Im(Z).
    """
    f = np.asarray(f, dtype=float)
    z_re = np.asarray(z_re, dtype=float)
    z_im = np.asarray(z_im, dtype=float)

    if mag is not None and phase_deg is not None:
        z = complex_from_mag_phase(np.asarray(mag, dtype=float), np.asarray(phase_deg, dtype=float))
        # Align lengths with cleaned frequency via shared mask later
        z_re = np.real(z)
        z_im = np.imag(z)
        mag = np.abs(z)
        phase_deg = np.rad2deg(np.angle(z))
    elif origin_imag_is_negated:
        z_im = -z_im
        mag = np.abs(z_re + 1j * z_im)
        phase_deg = np.rad2deg(np.arctan2(z_im, z_re))

    f, z_re, z_im = _clean_spectrum(f, z_re, z_im)
    # Re-sync mag/phase after clean
    z = z_re + 1j * z_im
    mag = np.abs(z)
    phase_deg = np.rad2deg(np.angle(z))

    out: Dict[str, Any] = {}
    out.update(admittance_metrics(f, z))
    out.update(nyquist_intercepts(f, z_re, z_im))

    fits = fit_equivalent_circuits(f, z_re, z_im)
    out["circuit_fit"] = fits
    out["best_model"] = fits.get("best_model")
    out["best_model_r2"] = fits.get("best_r2")
    out["best_aic"] = fits.get("best_aic")
    for k, v in fits.items():
        if k.startswith("fit_"):
            out[k] = v
    for name, m in (fits.get("models") or {}).items():
        out[f"r2_{name}"] = m.get("r2")
        out[f"aic_{name}"] = m.get("aic")

    q = quality_flags(f, z_re, z_im, fits)
    out.update(q)

    anomalies: List[str] = []
    if q.get("data_quality") == "poor":
        anomalies.append("poor_eis_fit")
    if q.get("flag_nearly_resistive"):
        anomalies.append("nearly_resistive")
    if q.get("flag_hf_inductive"):
        anomalies.append("hf_inductive_artifact")
    if q.get("flag_lf_noisy"):
        anomalies.append("lf_noisy")
    if fits.get("best_r2") is not None and fits["best_r2"] == fits["best_r2"] and fits["best_r2"] < 0.5:
        anomalies.append("low_model_r2")
    # Inconsistent: capacitive Cp median negative ⇒ wrong imag sign upstream
    if isinstance(out.get("Cp_median"), float) and out["Cp_median"] == out["Cp_median"] and out["Cp_median"] < 0:
        anomalies.append("negative_Cp_check_imag_sign")
    if out.get("flag_inverted_intercepts"):
        anomalies.append("inverted_nyquist_intercepts")
    out["anomalies"] = anomalies
    return out
