"""Solartron run / device analyzers writing beside Solartron_1260/analysis/."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..discovery import list_solartron_runs
from .loader import list_origin_csvs, tag_run_from_name
from .metrics import analyze_origin_file, flatten_spectrum_row
from .plots import plot_bias_overlay, plot_hrs_lrs_compare, plot_rs_vs_bias


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    try:
        import numpy as np

        if isinstance(obj, (np.floating, np.integer)):
            v = obj.item()
            if isinstance(v, float) and v != v:
                return None
            return v
    except Exception:
        pass
    return obj


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: List[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = {}
            for k, v in row.items():
                if isinstance(v, float) and v != v:
                    clean[k] = ""
                else:
                    clean[k] = v
            writer.writerow(clean)


class SolartronRunAnalyzer:
    def __init__(self, run_dir: Path | str):
        self.run_dir = Path(run_dir)
        self.run_name = self.run_dir.name

    def analyze(self) -> Dict[str, Any]:
        spectra: List[Dict[str, Any]] = []
        warnings: List[str] = []
        for csv_path in list_origin_csvs(self.run_dir):
            try:
                m = analyze_origin_file(csv_path, run_name=self.run_name)
                spectra.append(m)
            except Exception as e:
                warnings.append(f"{csv_path.name}: {e}")
        return {
            "run_dir": str(self.run_dir),
            "run": self.run_name,
            "run_tag": tag_run_from_name(self.run_name),
            "n_spectra": len(spectra),
            "spectra": spectra,
            "warnings": warnings,
        }


class SolartronDeviceAnalyzer:
    def __init__(self, solartron_dir: Path | str):
        self.solartron_dir = Path(solartron_dir)
        self.analysis_dir = self.solartron_dir / "analysis"

    def analyze(self, save: bool = True, force: bool = False) -> Dict[str, Any]:
        runs = list_solartron_runs(self.solartron_dir)
        all_spectra: List[Dict[str, Any]] = []
        run_summaries: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for run_dir in runs:
            result = SolartronRunAnalyzer(run_dir).analyze()
            warnings.extend(result.get("warnings") or [])
            run_summaries.append(
                {
                    "run": result["run"],
                    "run_tag": result["run_tag"],
                    "run_dir": result["run_dir"],
                    "n_spectra": result["n_spectra"],
                }
            )
            all_spectra.extend(result["spectra"])

        # Optional combined_bias_long.csv enrichment note
        combined = self.solartron_dir / "combined_bias_long.csv"
        has_combined = combined.is_file()

        rows = [flatten_spectrum_row(s) for s in all_spectra]
        summary: Dict[str, Any] = {
            "solartron_dir": str(self.solartron_dir),
            "n_runs": len(runs),
            "n_spectra": len(all_spectra),
            "runs": run_summaries,
            "spectra": [_json_safe(s) for s in all_spectra],
            "has_combined_bias_long": has_combined,
            "warnings": warnings,
            "plot_paths": [],
        }

        if save:
            self.analysis_dir.mkdir(parents=True, exist_ok=True)
            plots_dir = self.analysis_dir / "plots"
            plots_dir.mkdir(parents=True, exist_ok=True)

            _write_csv(self.analysis_dir / "spectra_metrics.csv", rows)
            (self.analysis_dir / "runs_summary.json").write_text(
                json.dumps(
                    {
                        "solartron_dir": summary["solartron_dir"],
                        "n_runs": summary["n_runs"],
                        "n_spectra": summary["n_spectra"],
                        "runs": run_summaries,
                        "spectra": summary["spectra"],
                        "has_combined_bias_long": has_combined,
                        "warnings": warnings,
                    },
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

            plot_paths = []
            p1 = plot_bias_overlay(all_spectra, plots_dir / "bias_Zmag_overlay.png")
            if p1:
                plot_paths.append(str(p1))
            p2 = plot_rs_vs_bias(all_spectra, plots_dir / "Rs_vs_bias.png")
            if p2:
                plot_paths.append(str(p2))

            hrs = [s for s in all_spectra if s.get("run_tag") == "hrs"]
            lrs = [s for s in all_spectra if s.get("run_tag") == "lrs"]
            p3 = plot_hrs_lrs_compare(hrs, lrs, plots_dir / "hrs_vs_lrs.png")
            if p3:
                plot_paths.append(str(p3))

            summary["plot_paths"] = plot_paths

            from ..llm_summary import brief_solartron_device

            brief = brief_solartron_device(summary)
            (self.analysis_dir / "llm_brief.md").write_text(brief, encoding="utf-8")
            summary["brief"] = brief
            summary["analysis_dir"] = str(self.analysis_dir)
        else:
            from ..llm_summary import brief_solartron_device

            summary["brief"] = brief_solartron_device(summary)

        return summary
