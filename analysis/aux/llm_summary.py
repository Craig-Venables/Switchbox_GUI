"""LLM-oriented brief text builders (no model calls). Rich digests for prompting."""

from __future__ import annotations

from typing import Any, Dict, List


def _fmt(v: Any, fmt: str = ".3g") -> str:
    if v is None:
        return "n/a"
    try:
        if isinstance(v, float) and v != v:
            return "n/a"
        return format(float(v), fmt)
    except Exception:
        return str(v)


def _anom(f: Dict[str, Any]) -> str:
    a = f.get("anomalies_str") or ""
    if not a and isinstance(f.get("anomalies"), list):
        a = ",".join(f["anomalies"])
    return f" [{a}]" if a else ""


def _params(f: Dict[str, Any]) -> str:
    ps = f.get("param_summary")
    if ps:
        return f" ({ps})"
    # fall back from flattened param_ keys if present
    bits = []
    for k in (
        "param_set_voltage",
        "param_reset_voltage",
        "param_pulse_voltage",
        "param_pulse_width",
        "param_num_cycles",
    ):
        if f.get(k) is not None:
            bits.append(f"{k.replace('param_', '')}={f[k]}")
    return f" ({', '.join(bits)})" if bits else ""


def brief_pulse_folder(summary: Dict[str, Any]) -> str:
    lines = [
        "# Pulse analysis brief (deep)",
        f"- Folder: `{summary.get('pulse_dir')}`",
        f"- Files: {summary.get('n_files', 0)} total, {summary.get('n_supported', 0)} supported",
        f"- Families: {', '.join(summary.get('families') or []) or 'none'}",
        "",
        "## Per-file metrics",
    ]
    highlights: List[str] = []
    anomaly_lines: List[str] = []
    for f in summary.get("files") or []:
        if f.get("error"):
            anomaly_lines.append(f"- `{f.get('filename')}`: {f.get('error')}")
            continue
        if not f.get("supported"):
            anomaly_lines.append(
                f"- `{f.get('filename')}`: unsupported ({f.get('test_name')})"
            )
            continue
        fam = f.get("family")
        name = f.get("filename", "?")
        p = _params(f)
        a = _anom(f)
        if fam == "endurance":
            highlights.append(
                f"- **Endurance** `{name}`{p}: n={f.get('n_cycles')}, "
                f"R_SET {_fmt(f.get('r_set_first'))}->{_fmt(f.get('r_set_last'))} "
                f"(mean {_fmt(f.get('r_set_mean'))}), "
                f"R_RESET {_fmt(f.get('r_reset_first'))}->{_fmt(f.get('r_reset_last'))}, "
                f"ratio {_fmt(f.get('on_off_ratio_first'))}->{_fmt(f.get('on_off_ratio_last'))} "
                f"(mean {_fmt(f.get('on_off_ratio_mean'))}), "
                f"window {_fmt(f.get('window_first'))}->{_fmt(f.get('window_last'))} "
                f"({_fmt(f.get('window_pct_change'))}% ), "
                f"degrade={f.get('degrade_best_model')} R2={_fmt(f.get('degrade_best_r2'))}, "
                f"cycles_to_50%={_fmt(f.get('cycles_to_50pct_window'))}{a}"
            )
        elif fam == "pot_dep":
            highlights.append(
                f"- **Pot/Dep** `{name}`{p}: range={_fmt(f.get('dynamic_range'))} "
                f"({_fmt(f.get('r_min'))}-{_fmt(f.get('r_max'))}), "
                f"pot_dR={_fmt(f.get('pot_excursion'))} (linR2={_fmt(f.get('pot_linearity_r2'))}), "
                f"dep_dR={_fmt(f.get('dep_excursion'))} (linR2={_fmt(f.get('dep_linearity_r2'))}), "
                f"asymmetry={_fmt(f.get('asymmetry_dep_over_pot'))}, "
                f"drift={_fmt(f.get('cycle_drift'))}{a}"
            )
        elif fam in ("multi_read", "pulse_train"):
            label = "Pulse-Train" if fam == "pulse_train" else "Multi-Read"
            highlights.append(
                f"- **{label}** `{name}`{p}: R {_fmt(f.get('r_initial'))}->{_fmt(f.get('r_final'))} "
                f"(d={_fmt(f.get('percent_change'))}%, trend={f.get('trend')}), "
                f"std={_fmt(f.get('read_train_std'))}, "
                f"tau={_fmt(f.get('tau_s'))}s R2={_fmt(f.get('tau_r_squared'))} "
                f"ok={f.get('tau_fit_ok')}{a}"
            )
        if f.get("anomalies_str") or f.get("anomalies"):
            anomaly_lines.append(f"- `{name}`: {f.get('anomalies_str') or ','.join(f.get('anomalies') or [])}")

    if not highlights:
        lines.append("- No supported pulse files.")
    else:
        lines.extend(highlights[:60])

    if anomaly_lines:
        lines.append("")
        lines.append("## Anomalies / warnings")
        lines.extend(anomaly_lines[:40])

    warns = summary.get("warnings") or []
    if warns:
        lines.append("")
        lines.append("## Parser warnings")
        for w in warns[:20]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def brief_solartron_device(summary: Dict[str, Any]) -> str:
    lines = [
        "# Solartron / CF analysis brief (deep)",
        f"- Folder: `{summary.get('solartron_dir')}`",
        f"- Runs: {summary.get('n_runs', 0)}, spectra: {summary.get('n_spectra', 0)}",
        "",
        "## Runs",
    ]
    for r in summary.get("runs") or []:
        lines.append(f"- `{r.get('run')}` (tag={r.get('run_tag')}, n={r.get('n_spectra')})")

    lines.append("")
    lines.append("## Spectra (fits + capacitance)")
    spectra = summary.get("spectra") or []

    def _key(s):
        b = s.get("bias_V")
        return (b is None, b if b is not None else 0, s.get("filename") or "")

    for s in sorted(spectra, key=_key)[:40]:
        # Prefer circuit-fit Rs; show corrected intercepts separately from legacy Nyquist heuristic
        lines.append(
            f"- `{s.get('run')}` / `{s.get('filename')}`: bias={_fmt(s.get('bias_V'))} V, "
            f"tag={s.get('run_tag')}, "
            f"best_model={s.get('best_model')} R2={_fmt(s.get('best_model_r2'))} "
            f"AIC={_fmt(s.get('best_aic'))} "
            f"fit_Rs={_fmt(s.get('fit_Rs'))} fit_Rp={_fmt(s.get('fit_Rp'))} "
            f"fit_C={_fmt(s.get('fit_C'))} fit_Q={_fmt(s.get('fit_Q'))} alpha={_fmt(s.get('fit_alpha'))}, "
            f"intercept_Rs={_fmt(s.get('intercept_Rs'))} intercept_Rp={_fmt(s.get('intercept_Rp'))}, "
            f"legacy_nyquist_Rs={_fmt(s.get('series_resistance_ohms'))} "
            f"(heuristic; prefer fit/intercept), "
            f"Cp_1Hz={_fmt(s.get('Cp_1Hz'))} Cp_1kHz={_fmt(s.get('Cp_1kHz'))} "
            f"Z_1Hz={_fmt(s.get('Zmag_1Hz'))} Z_1kHz={_fmt(s.get('Zmag_1kHz'))} "
            f"(Z_1Hz is LF resistance proxy), "
            f"quality={s.get('data_quality')}, "
            f"anomalies={s.get('anomalies_str') or ''}"
        )

    hrs = [s for s in spectra if s.get("run_tag") == "hrs"]
    lrs = [s for s in spectra if s.get("run_tag") == "lrs"]
    if hrs and lrs:
        def _mean(group, key):
            vals = [s.get(key) for s in group if isinstance(s.get(key), (int, float)) and s.get(key) == s.get(key)]
            return sum(vals) / len(vals) if vals else None

        lines.append("")
        lines.append("## HRS vs LRS")
        lines.append(
            f"- HRS vs LRS: fit-Rs {_fmt(_mean(hrs, 'fit_Rs'))} vs {_fmt(_mean(lrs, 'fit_Rs'))}; "
            f"Z_1Hz {_fmt(_mean(hrs, 'Zmag_1Hz'))} vs {_fmt(_mean(lrs, 'Zmag_1Hz'))}; "
            f"Cp_1kHz {_fmt(_mean(hrs, 'Cp_1kHz'))} vs {_fmt(_mean(lrs, 'Cp_1kHz'))} "
            f"(folder tags are history labels; compare Z_1Hz for LF resistance)"
        )

    # Bias trend of fit_Rs
    bias_pts = [
        (s.get("bias_V"), s.get("fit_Rs") or s.get("series_resistance_ohms"), s.get("best_model"))
        for s in spectra
        if isinstance(s.get("bias_V"), (int, float))
    ]
    bias_pts = [(b, r, m) for b, r, m in bias_pts if r == r]
    if len(bias_pts) >= 2:
        bias_pts.sort(key=lambda x: x[0])
        lines.append("")
        lines.append("## Bias trend (fit Rs)")
        for b, r, m in bias_pts:
            lines.append(f"- V={_fmt(b)}: Rs={_fmt(r)} (model={m})")

    warns = summary.get("warnings") or []
    if warns:
        lines.append("")
        lines.append("## Warnings")
        for w in warns[:20]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"


def _device_pulse_digest(dev_result: Dict[str, Any]) -> List[str]:
    """Compact numeric digest for one device's pulse folder result."""
    sec = dev_result.get("section", "?")
    dev = dev_result.get("device", "?")
    lines = [f"### Device {sec}{dev} pulse"]
    files = [f for f in (dev_result.get("files") or []) if f.get("supported")]
    if not files:
        lines.append("- No supported pulse files")
        return lines

    # Best endurance by mean ratio
    endu = [f for f in files if f.get("family") == "endurance"]
    if endu:
        best = max(
            endu,
            key=lambda f: f.get("on_off_ratio_mean") if isinstance(f.get("on_off_ratio_mean"), (int, float)) and f.get("on_off_ratio_mean") == f.get("on_off_ratio_mean") else -1,
        )
        lines.append(
            f"- Best endurance ratio: `{best.get('filename')}` "
            f"ratio={_fmt(best.get('on_off_ratio_mean'))}, "
            f"window%={_fmt(best.get('window_pct_change'))}, "
            f"degrade={best.get('degrade_best_model')} R2={_fmt(best.get('degrade_best_r2'))}"
        )
        collapsed = [f for f in endu if "no_switching_window" in (f.get("anomalies_str") or "") or "failed_switch" in (f.get("anomalies_str") or "")]
        if collapsed:
            lines.append(f"- Failed/no-window endurance files: {len(collapsed)}/{len(endu)}")

    pot = [f for f in files if f.get("family") == "pot_dep"]
    if pot:
        widest = max(pot, key=lambda f: f.get("dynamic_range") or -1)
        lines.append(
            f"- Widest pot/dep: `{widest.get('filename')}` range={_fmt(widest.get('dynamic_range'))}, "
            f"asym={_fmt(widest.get('asymmetry_dep_over_pot'))}"
        )

    mr = [f for f in files if f.get("family") in ("multi_read", "pulse_train")]
    if mr:
        big = max(mr, key=lambda f: abs(f.get("percent_change") or 0))
        lines.append(
            f"- Largest multi-read/train change: `{big.get('filename')}` "
            f"dR%={_fmt(big.get('percent_change'))}, trend={big.get('trend')}, "
            f"tau_ok={big.get('tau_fit_ok')}"
        )

    all_anom = []
    for f in files:
        if f.get("anomalies_str"):
            all_anom.append(f"{f.get('filename')}: {f.get('anomalies_str')}")
    if all_anom:
        lines.append("- Anomalies: " + "; ".join(all_anom[:8]))
    return lines


def _device_solartron_digest(dev_result: Dict[str, Any]) -> List[str]:
    sec = dev_result.get("section", "?")
    dev = dev_result.get("device", "?")
    lines = [f"### Device {sec}{dev} Solartron"]
    spectra = dev_result.get("spectra") or []
    lines.append(f"- Runs={dev_result.get('n_runs')}, spectra={dev_result.get('n_spectra')}")
    if not spectra:
        return lines
    # Prefer best R2 spectrum
    scored = [s for s in spectra if isinstance(s.get("best_model_r2"), (int, float))]
    if scored:
        best = max(scored, key=lambda s: s.get("best_model_r2") or -1)
        lines.append(
            f"- Best EIS fit: `{best.get('filename')}` model={best.get('best_model')} "
            f"R2={_fmt(best.get('best_model_r2'))} Rs={_fmt(best.get('fit_Rs'))} "
            f"Rp={_fmt(best.get('fit_Rp'))} C={_fmt(best.get('fit_C'))} "
            f"Q={_fmt(best.get('fit_Q'))} a={_fmt(best.get('fit_alpha'))} "
            f"quality={best.get('data_quality')}"
        )
    hrs = [s for s in spectra if s.get("run_tag") == "hrs"]
    lrs = [s for s in spectra if s.get("run_tag") == "lrs"]
    if hrs and lrs:
        lines.append(
            f"- HRS vs LRS fit-Rs: {_fmt(hrs[0].get('fit_Rs'))} vs "
            f"{_fmt(lrs[0].get('fit_Rs'))}; "
            f"Cp_1kHz: {_fmt(hrs[0].get('Cp_1kHz'))} vs {_fmt(lrs[0].get('Cp_1kHz'))}"
        )
    anom = [s for s in spectra if s.get("anomalies_str")]
    if anom:
        lines.append(
            "- EIS anomalies: "
            + "; ".join(f"{s.get('filename')}:{s.get('anomalies_str')}" for s in anom[:6])
        )
    return lines


def brief_sample_aux(result: Dict[str, Any]) -> str:
    """Sample-level digest with numbers (LLM-friendly, not a filename dump)."""
    lines = [
        f"# Sample aux analysis brief — {result.get('sample', '')}",
        f"- Devices with aux folders: {len(result.get('devices') or [])}",
        "",
        "## Device digests",
    ]
    pulse = result.get("pulse") or {}
    for dev in pulse.get("devices") or []:
        lines.extend(_device_pulse_digest(dev))
        lines.append("")

    sol = result.get("solartron") or {}
    for dev in sol.get("devices") or []:
        lines.extend(_device_solartron_digest(dev))
        lines.append("")

    warns = result.get("warnings") or []
    if warns:
        lines.append("## Warnings")
        for w in warns[:40]:
            lines.append(f"- {w}")
    return "\n".join(lines) + "\n"
