"""Pulse file / folder analyzers writing beside Pulse_measurements/analysis/."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..discovery import list_pulse_txt_files
from .loader import FAMILY_UNSUPPORTED, load_tsp
from .metrics import extract_file_metrics, flatten_metrics_row
from .plots import plot_pulse_dashboard


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (float,)):
        if obj != obj:  # NaN
            return None
        return obj
    try:
        import numpy as np

        if isinstance(obj, (np.floating, np.integer)):
            v = obj.item()
            if isinstance(v, float) and v != v:
                return None
            return v
        if isinstance(obj, np.ndarray):
            return None
    except Exception:
        pass
    return obj


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # union of keys
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


class PulseFileAnalyzer:
    """Analyze a single pulse TSP .txt file."""

    def __init__(self, filepath: Path | str):
        self.filepath = Path(filepath)

    def analyze(self, save_dir: Optional[Path | str] = None, save: bool = False) -> Dict[str, Any]:
        tsp = load_tsp(self.filepath)
        if tsp is None:
            return {
                "filename": self.filepath.name,
                "error": "parse_failed",
                "supported": False,
                "family": FAMILY_UNSUPPORTED,
            }
        metrics = extract_file_metrics(tsp, filepath=self.filepath.name)
        metrics["filepath"] = str(self.filepath)

        plot_path = None
        if save and save_dir is not None and metrics.get("supported"):
            save_dir = Path(save_dir)
            plots_dir = save_dir / "plots"
            plot_path = plot_pulse_dashboard(
                metrics, plots_dir / f"{self.filepath.stem}_dashboard.png"
            )
            if plot_path is not None:
                metrics["plot_path"] = str(plot_path)

        return metrics


class PulseFolderAnalyzer:
    """Analyze all supported pulse files in a Pulse_measurements folder."""

    def __init__(self, pulse_dir: Path | str):
        self.pulse_dir = Path(pulse_dir)
        self.analysis_dir = self.pulse_dir / "analysis"

    def analyze(self, save: bool = True) -> Dict[str, Any]:
        files = list_pulse_txt_files(self.pulse_dir)
        file_results: List[Dict[str, Any]] = []
        rows: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for path in files:
            try:
                result = PulseFileAnalyzer(path).analyze(
                    save_dir=self.analysis_dir if save else None,
                    save=save,
                )
                file_results.append(result)
                if result.get("error"):
                    warnings.append(f"{path.name}: {result['error']}")
                elif not result.get("supported"):
                    warnings.append(f"{path.name}: unsupported family ({result.get('test_name')})")
                else:
                    rows.append(flatten_metrics_row(result))
            except Exception as e:
                warnings.append(f"{path.name}: {e}")
                file_results.append(
                    {
                        "filename": path.name,
                        "error": str(e),
                        "supported": False,
                    }
                )

        supported = [r for r in file_results if r.get("supported")]
        summary = {
            "pulse_dir": str(self.pulse_dir),
            "n_files": len(files),
            "n_supported": len(supported),
            "n_unsupported": len(files) - len(supported),
            "families": sorted({r.get("family") for r in supported if r.get("family")}),
            "files": [_json_safe(r) for r in file_results],
            "warnings": warnings,
        }

        if save:
            self.analysis_dir.mkdir(parents=True, exist_ok=True)
            _write_csv(self.analysis_dir / "metrics.csv", rows)
            (self.analysis_dir / "files_summary.json").write_text(
                json.dumps(summary, indent=2, default=str),
                encoding="utf-8",
            )
            from ..llm_summary import brief_pulse_folder

            brief = brief_pulse_folder(summary)
            (self.analysis_dir / "llm_brief.md").write_text(brief, encoding="utf-8")
            summary["brief"] = brief
            summary["analysis_dir"] = str(self.analysis_dir)
        else:
            from ..llm_summary import brief_pulse_folder

            summary["brief"] = brief_pulse_folder(summary)

        return summary
