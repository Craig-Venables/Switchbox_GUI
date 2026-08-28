"""Public API for auxiliary (pulse + Solartron) analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .discovery import (
    DeviceLocation,
    discover_aux_devices,
    discover_pulse_devices,
    discover_solartron_devices,
)
from .llm_summary import brief_sample_aux
from .pulse.analyzer import PulseFolderAnalyzer
from .solartron.analyzer import SolartronDeviceAnalyzer


def analyze_pulse_folder(pulse_dir: Path | str, save: bool = True) -> Dict[str, Any]:
    """Analyze one Pulse_measurements folder."""
    return PulseFolderAnalyzer(pulse_dir).analyze(save=save)


def analyze_pulse_device(device_dir: Path | str, save: bool = True) -> Optional[Dict[str, Any]]:
    """Analyze Pulse_measurements under a device folder, if present."""
    from .discovery import PULSE_FOLDER

    device_dir = Path(device_dir)
    pulse_dir = device_dir / PULSE_FOLDER
    if not pulse_dir.is_dir():
        return None
    return analyze_pulse_folder(pulse_dir, save=save)


def analyze_sample_pulse(sample_dir: Path | str, save: bool = True) -> Dict[str, Any]:
    sample_dir = Path(sample_dir)
    devices = discover_pulse_devices(sample_dir)
    results = []
    highlights: List[str] = []
    warnings: List[str] = []
    for loc in devices:
        try:
            r = analyze_pulse_folder(loc.pulse_dir, save=save)
            r["device_id"] = loc.device_id
            r["section"] = loc.section
            r["device"] = loc.device
            results.append(r)
            warnings.extend(r.get("warnings") or [])
            # Numeric highlights for sample rollup
            for f in r.get("files") or []:
                if not f.get("supported"):
                    continue
                fam = f.get("family")
                if fam == "endurance":
                    highlights.append(
                        f"{loc.section}{loc.device} endurance ratio={f.get('on_off_ratio_mean')} "
                        f"window%={f.get('window_pct_change')} degrade={f.get('degrade_best_model')} "
                        f"[{f.get('filename')}]"
                    )
                elif fam == "pot_dep":
                    highlights.append(
                        f"{loc.section}{loc.device} pot_dep range={f.get('dynamic_range')} "
                        f"asym={f.get('asymmetry_dep_over_pot')} [{f.get('filename')}]"
                    )
                elif fam in ("multi_read", "pulse_train"):
                    highlights.append(
                        f"{loc.section}{loc.device} {fam} dR%={f.get('percent_change')} "
                        f"trend={f.get('trend')} [{f.get('filename')}]"
                    )
        except Exception as e:
            warnings.append(f"{loc.device_id} pulse: {e}")
    from .llm_summary import brief_sample_aux

    temp = {"sample": sample_dir.name, "devices": [], "pulse": {"devices": results}, "solartron": {}}
    return {
        "sample": sample_dir.name,
        "n_devices": len(results),
        "devices": results,
        "highlights": highlights,
        "warnings": warnings,
        "brief": brief_sample_aux(temp),
    }


def analyze_solartron_device(device_dir: Path | str, save: bool = True) -> Optional[Dict[str, Any]]:
    from .discovery import SOLARTRON_FOLDER

    device_dir = Path(device_dir)
    sol_dir = device_dir / SOLARTRON_FOLDER
    if not sol_dir.is_dir():
        return None
    return SolartronDeviceAnalyzer(sol_dir).analyze(save=save)


def analyze_sample_solartron(sample_dir: Path | str, save: bool = True) -> Dict[str, Any]:
    sample_dir = Path(sample_dir)
    devices = discover_solartron_devices(sample_dir)
    results = []
    highlights: List[str] = []
    warnings: List[str] = []
    for loc in devices:
        try:
            r = SolartronDeviceAnalyzer(loc.solartron_dir).analyze(save=save)
            r["device_id"] = loc.device_id
            r["section"] = loc.section
            r["device"] = loc.device
            results.append(r)
            warnings.extend(r.get("warnings") or [])
            highlights.append(
                f"{loc.section}{loc.device}: {r.get('n_runs', 0)} runs, {r.get('n_spectra', 0)} spectra; "
                f"best_models="
                + ",".join(
                    sorted(
                        {
                            str(s.get("best_model"))
                            for s in (r.get("spectra") or [])
                            if s.get("best_model")
                        }
                    )
                )
            )
        except Exception as e:
            warnings.append(f"{loc.device_id} solartron: {e}")
    return {
        "sample": sample_dir.name,
        "n_devices": len(results),
        "devices": results,
        "highlights": highlights,
        "warnings": warnings,
        "brief": "\n".join(
            [f"# Solartron sample {sample_dir.name}", f"- Devices: {len(results)}", ""]
            + [f"- {h}" for h in highlights[:40]]
        ),
    }


def analyze_sample_aux(
    sample_dir: Path | str,
    kinds: Sequence[str] = ("pulse", "solartron"),
    save: bool = True,
    log=None,
) -> Dict[str, Any]:
    """
    Walk a sample tree and analyze aux measurement folders.

    Returns an LLM-friendly dict with pulse/solartron sections and a brief.
    Failures are collected in warnings (do not raise).
    """
    sample_dir = Path(sample_dir)
    kinds_set = {k.lower().strip() for k in kinds}
    if log:
        log(f"Aux analysis: discovering devices under {sample_dir} ({', '.join(sorted(kinds_set))})")

    devices_meta: List[Dict[str, str]] = []
    for loc in discover_aux_devices(sample_dir, kinds=tuple(kinds_set)):
        devices_meta.append(
            {
                "device_id": loc.device_id,
                "section": loc.section,
                "device": loc.device,
                "has_pulse": str(loc.has_pulse()),
                "has_solartron": str(loc.has_solartron()),
            }
        )

    result: Dict[str, Any] = {
        "sample": sample_dir.name,
        "sample_dir": str(sample_dir),
        "devices": devices_meta,
        "warnings": [],
    }

    if "pulse" in kinds_set:
        if log:
            log("Aux analysis: running pulse…")
        try:
            result["pulse"] = analyze_sample_pulse(sample_dir, save=save)
            result["warnings"].extend(result["pulse"].get("warnings") or [])
        except Exception as e:
            result["warnings"].append(f"pulse sample: {e}")
            result["pulse"] = {"error": str(e), "n_devices": 0, "devices": [], "highlights": []}

    if "solartron" in kinds_set:
        if log:
            log("Aux analysis: running Solartron…")
        try:
            result["solartron"] = analyze_sample_solartron(sample_dir, save=save)
            result["warnings"].extend(result["solartron"].get("warnings") or [])
        except Exception as e:
            result["warnings"].append(f"solartron sample: {e}")
            result["solartron"] = {"error": str(e), "n_devices": 0, "devices": [], "highlights": []}

    result["brief"] = brief_sample_aux(result)

    if save:
        out_dir = sample_dir / "sample_analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        index = {
            "sample": result["sample"],
            "devices": devices_meta,
            "pulse_n_devices": (result.get("pulse") or {}).get("n_devices"),
            "solartron_n_devices": (result.get("solartron") or {}).get("n_devices"),
            "warnings": result["warnings"],
            "brief": result["brief"],
        }
        (out_dir / "aux_index.json").write_text(
            json.dumps(index, indent=2, default=str),
            encoding="utf-8",
        )
        (out_dir / "aux_llm_brief.md").write_text(result["brief"], encoding="utf-8")

    if log:
        log(
            f"Aux analysis complete: pulse devices={(result.get('pulse') or {}).get('n_devices', 0)}, "
            f"solartron devices={(result.get('solartron') or {}).get('n_devices', 0)}"
        )
    return result
