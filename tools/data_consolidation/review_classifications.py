"""
GUI to review batch classification results and record your labels.

Loads pre-computed classification_results.json (from batch_classify.py).
Shows IV plot, predicted type, scores, and lets you agree/disagree.

Usage:
    python tools/data_consolidation/launch_review.py
"""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

_TOOL_DIR = Path(__file__).resolve().parent
_ROOT = _TOOL_DIR.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis.core.sweep_analyzer import read_data_file

from classification_store import (
    ReviewLabelStore,
    VALID_USER_LABELS,
    device_group_key_from_filename,
    load_results,
    parse_sweep_index,
)
from paths import DATASETS, DEFAULT_DATASET, dataset_paths

LABEL_CHOICES = [l for l in VALID_USER_LABELS if l != "skip"]
FILTERS = [
    "Not reviewed (priority)",
    "High review priority",
    "Non-conductive / noise",
    "Predicted: memristive (rectifying)",
    "Promising yield (forming+)",
    "Low confidence (<40%)",
    "Uncertain",
    "Borderline memristivity (40-65)",
    "I disagreed",
    "Needs manual label (flash N)",
    "I agreed",
    "Predicted: memristive",
    "Predicted: capacitive",
    "Predicted: ohmic",
    "Predicted: conductive",
    "Predicted: non_conductive",
    "Predicted: memristive (rectifying)",
    "All",
]


class ClassificationReviewApp:
    def __init__(self, root: tk.Tk, *, dataset: str = DEFAULT_DATASET) -> None:
        self.root = root
        self.dataset = dataset
        self.paths = dataset_paths(dataset)
        self.root.title(f"Classification Review — {dataset}")
        self.root.geometry("1300x950")

        self.label_store = ReviewLabelStore(
            path=self.paths["corrections_json"],
            dataset=self.dataset,
            legacy_path=self.paths["labels_json"],
        )
        self.records: List[Dict[str, Any]] = []
        self.device_summaries: Dict[str, Dict[str, Any]] = {}
        self.device_records: Dict[str, List[Dict[str, Any]]] = {}
        self.filtered: List[Dict[str, Any]] = []
        self.current_index = 0
        self._file_cache: Dict[str, tuple] = {}
        self._timeline_device_key: Optional[str] = None
        self._timeline_data: List[tuple] = []
        self._timeline_lines: Dict[str, Any] = {}
        self._timeline_drawn_key: Optional[str] = None
        self._sel_annotation = None

        self._build_ui()
        self._load_results()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Dataset:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(12, 4))
        self.dataset_var = tk.StringVar(value=self.dataset)
        ds_box = ttk.Combobox(
            top, textvariable=self.dataset_var, values=list(DATASETS.keys()), state="readonly", width=14
        )
        ds_box.pack(side=tk.LEFT)
        ds_box.bind("<<ComboboxSelected>>", lambda e: self._switch_dataset())

        ttk.Label(top, text="Filter:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(12, 6))
        self.filter_var = tk.StringVar(value=FILTERS[0])
        filt = ttk.Combobox(top, textvariable=self.filter_var, values=FILTERS, state="readonly", width=32)
        filt.pack(side=tk.LEFT)
        filt.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        ttk.Button(top, text="Refresh", command=self._reload).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Export CSV", command=self._export_corrections).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="Flash review", command=self._open_flash_review).pack(side=tk.LEFT, padx=2)
        self.stats_var = tk.StringVar(value="No data loaded")
        ttk.Label(top, textvariable=self.stats_var, foreground="blue").pack(side=tk.LEFT, padx=12)
        self.save_status_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.save_status_var, foreground="green").pack(side=tk.LEFT, padx=4)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(paned, width=360)
        paned.add(left, weight=1)

        ttk.Label(left, text="Sweeps", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(list_frame, yscrollcommand=sb.set, font=("Consolas", 9))
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_select())

        nav = ttk.Frame(left)
        nav.pack(fill=tk.X, pady=4)
        ttk.Button(nav, text="◀ Prev", command=self._prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav, text="Next ▶", command=self._next).pack(side=tk.LEFT, padx=2)

        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        info = ttk.LabelFrame(right, text="Prediction", padding=8)
        info.pack(fill=tk.X, pady=(0, 6))
        self.info_text = tk.Text(info, height=8, font=("Consolas", 10), wrap=tk.WORD)
        self.info_text.pack(fill=tk.X)
        self.info_text.config(state=tk.DISABLED)

        scores_frame = ttk.LabelFrame(right, text="Class scores", padding=6)
        scores_frame.pack(fill=tk.X, pady=(0, 6))
        self.score_labels: Dict[str, ttk.Label] = {}
        row = ttk.Frame(scores_frame)
        row.pack(fill=tk.X)
        for dtype in ("memristive", "capacitive", "conductive", "ohmic"):
            col = ttk.Frame(row)
            col.pack(side=tk.LEFT, expand=True)
            ttk.Label(col, text=dtype, font=("Arial", 8, "bold")).pack()
            lbl = ttk.Label(col, text="—", font=("Arial", 11))
            lbl.pack()
            self.score_labels[dtype] = lbl

        plot_frame = ttk.LabelFrame(right, text="I–V plots", padding=4)
        plot_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.fig, (self.ax, self.ax_timeline) = plt.subplots(
            2, 1, figsize=(6, 7), height_ratios=[1, 1.15], constrained_layout=True
        )
        self._colorbar = None
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, plot_frame)

        review = ttk.LabelFrame(right, text="Your review", padding=8)
        review.pack(fill=tk.X)
        ttk.Label(review, text="If wrong, correct label:").pack(side=tk.LEFT, padx=4)
        self.user_label_var = tk.StringVar()
        ttk.Combobox(
            review, textvariable=self.user_label_var, values=LABEL_CHOICES, width=14, state="readonly"
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(review, text="✓ Agree", command=self._agree, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(review, text="✗ Disagree", command=self._disagree, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(review, text="Skip", command=self._skip, width=8).pack(side=tk.LEFT, padx=2)
        self.review_status = ttk.Label(review, text="", foreground="green")
        self.review_status.pack(side=tk.LEFT, padx=12)

        metrics = ttk.LabelFrame(self.root, text="Review progress / saved corrections", padding=8)
        metrics.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.metrics_text = tk.Text(metrics, height=4, font=("Consolas", 9), wrap=tk.WORD)
        self.metrics_text.pack(fill=tk.X)
        self.metrics_text.config(state=tk.DISABLED)

    def _switch_dataset(self) -> None:
        name = self.dataset_var.get()
        if name == self.dataset:
            return
        self.dataset = name
        self.paths = dataset_paths(name)
        self.label_store = ReviewLabelStore(
            path=self.paths["corrections_json"],
            dataset=self.dataset,
            legacy_path=self.paths["labels_json"],
        )
        self._file_cache.clear()
        self._timeline_device_key = None
        self._timeline_data = []
        self._timeline_lines.clear()
        self._timeline_drawn_key = None
        self._sel_annotation = None
        self.root.title(f"Classification Review — {name}")
        self._load_results()

    def _load_results(self) -> None:
        self.records = load_results(dataset=self.dataset)
        self.device_summaries = {}
        device_yield = self.paths["device_yield_json"]
        if device_yield.exists():
            try:
                payload = json.loads(device_yield.read_text(encoding="utf-8"))
                self.device_summaries = payload.get("devices", {})
            except Exception:
                pass
        if not self.records:
            messagebox.showwarning(
                "No results",
                f"No classification results for dataset '{self.dataset}'.\n\n"
                f"1. python tools/data_consolidation/consolidate.py --dataset \"{self.dataset}\"\n"
                f"2. python tools/data_consolidation/batch_classify.py --dataset \"{self.dataset}\"",
            )
            return
        self._build_device_index()
        self._apply_filter()
        self._update_metrics_panel()

    def _build_device_index(self) -> None:
        """Group records by device_key, sorted by numeric sweep index."""
        from collections import defaultdict

        by_device: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rec in self.records:
            row = rec.get("row", {})
            key = row.get("device_group_key") or device_group_key_from_filename(rec.get("filename", ""))
            if key:
                by_device[key].append(rec)
        self.device_records = {
            key: sorted(
                recs,
                key=lambda r: (parse_sweep_index(r.get("filename", "")), r.get("filename", "")),
            )
            for key, recs in by_device.items()
        }

    def _reload(self) -> None:
        self.label_store.load()
        self._load_results()
        self.save_status_var.set("Reloaded saved corrections from disk")

    def _export_corrections(self) -> None:
        n = self.label_store.export_csv(self.paths["corrections_csv"])
        messagebox.showinfo(
            "Exported",
            f"Saved {n} correction(s) to:\n{self.paths['corrections_csv']}",
        )

    def _open_flash_review(self) -> None:
        import subprocess

        script = _TOOL_DIR / "launch_flash_review.py"
        subprocess.Popen(
            [sys.executable, str(script), "--dataset", self.dataset],
            cwd=str(_ROOT),
        )

    def _correction_stats(self) -> Dict[str, int]:
        filenames = [r.get("filename", "") for r in self.records]
        return self.label_store.match_stats(filenames)

    def _update_stats_bar(self) -> None:
        stats = self._correction_stats()
        filt = self.filter_var.get()
        self.stats_var.set(
            f"Showing {len(self.filtered)} / {len(self.records)}  |  "
            f"saved {stats['matched']} corrections  |  filter: {filt}"
        )
        save_path = self.paths["corrections_json"].name
        extra = ""
        if stats["orphaned"]:
            extra = f"  ({stats['orphaned']} saved for files no longer in results)"
        self.save_status_var.set(f"Persistent file: {save_path}{extra}")

    def _apply_filter(self) -> None:
        filt = self.filter_var.get()
        self.filtered = []
        for rec in self.records:
            row = rec.get("row", {})
            fn = rec.get("filename", "")
            lab = self.label_store.get(fn)
            if not self._passes_filter(filt, row, lab):
                continue
            self.filtered.append(rec)

        self.listbox.delete(0, tk.END)
        for rec in self.filtered:
            row = rec["row"]
            fn = rec["filename"]
            lab = self.label_store.get(fn)
            reviewed = "✓" if lab else " "
            agree = "Y" if lab and lab.get("agrees_with_prediction") else ("N" if lab else " ")
            line = f"{reviewed}{agree} {row['predicted_type'][:4]:4s} {row['confidence_pct']:4.0f}% {fn[:48]}"
            self.listbox.insert(tk.END, line)

        self._update_stats_bar()
        if self.filtered:
            self.listbox.selection_set(0)
            self.current_index = 0
            self._show_record(self.filtered[0])
        self._update_metrics_panel()

    def _passes_filter(self, filt: str, row: dict, lab: Optional[dict]) -> bool:
        if filt == "All":
            return True
        if filt == "Not reviewed (priority)":
            return lab is None
        if filt == "High review priority":
            return row.get("review_priority") == "high"
        if filt == "Non-conductive / noise":
            return (
                row.get("predicted_type") == "non_conductive"
                or row.get("is_noisy") is True
                or row.get("is_noisy") == "True"
            )
        if filt == "Predicted: memristive (rectifying)":
            return (
                row.get("rectifying_character") is True
                or row.get("rectifying_character") == "True"
                or row.get("weak_rectifying") is True
                or row.get("weak_rectifying") == "True"
            )
        if filt == "Promising yield (forming+)":
            key = row.get("device_group_key") or device_group_key_from_filename(row.get("filename", ""))
            dev = self.device_summaries.get(key, {})
            return dev.get("yield_promising") == 1
        if filt == "Low confidence (<40%)":
            return float(row.get("confidence", 0)) < 0.4
        if filt == "Uncertain":
            return row.get("predicted_type") == "uncertain"
        if filt == "Borderline memristivity (40-65)":
            ms = row.get("memristivity_score")
            return ms != "" and ms is not None and 40 <= float(ms) <= 65
        if filt == "I disagreed":
            return lab is not None and not lab.get("agrees_with_prediction")
        if filt == "Needs manual label (flash N)":
            return lab is not None and lab.get("needs_manual_label") is True
        if filt == "I agreed":
            return lab is not None and lab.get("agrees_with_prediction")
        if filt.startswith("Predicted: "):
            return row.get("predicted_type") == filt.replace("Predicted: ", "")
        return True

    def _record_passes_filter(self, rec: dict, lab: Optional[dict]) -> bool:
        return self._passes_filter(self.filter_var.get(), rec.get("row", {}), lab)

    def _on_select(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        self.current_index = sel[0]
        self._show_record(self.filtered[self.current_index])

    def _show_record(self, rec: dict) -> None:
        row = rec["row"]
        clf = rec.get("analysis", {}).get("classification", {})
        fn = rec["filename"]

        lines = [
            f"File: {fn}",
            f"Device: {row.get('device_key', '')}  |  Sample {row.get('sample_id', '')}"
            + (f"  |  Material: {row.get('material')}" if row.get("material") else "")
            + (f"  |  From: {row.get('origin_dataset')}" if row.get("origin_dataset") else ""),
            f"Predicted: {row.get('predicted_type', '?')}"
            + ("  [rectifying character]" if row.get("rectifying_character") in (True, "True") else "")
            + f"  ({row.get('confidence_pct', 0)}% confidence)",
            f"Forming stage: {row.get('forming_stage', '—')}  |  Yield bucket: {row.get('yield_bucket', '—')}",
            f"Rectifying tier: {row.get('rectifying_tier', '—')}",
            f"Memristivity score: {row.get('memristivity_score', '—')}",
            f"Features: hysteresis={row.get('has_hysteresis')} pinched={row.get('pinched_hysteresis')} "
            f"double_x={row.get('double_zero_crossing')} switching={row.get('switching_behavior')} "
            f"weak_rect={row.get('weak_rectifying', False)}",
            f"Noise: is_noisy={row.get('is_noisy')}  ({row.get('noise_reason', '')})",
            f"Ron={row.get('ron_mean', '—')}  Roff={row.get('roff_mean', '—')}  ratio={row.get('switching_ratio', '—')}",
        ]
        dev_key = row.get("device_group_key") or device_group_key_from_filename(fn)
        if dev_key and dev_key in self.device_summaries:
            dev = self.device_summaries[dev_key]
            type_bits = ", ".join(f"{k}:{v}" for k, v in sorted(dev.get("type_counts", {}).items()))
            lines.insert(
                3,
                f"Device timeline: {dev.get('device_forming_stage', '—')} "
                f"({dev.get('sweep_count', 0)} sweeps) tier={dev.get('yield_tier', '—')} | types: {type_bits}",
            )
        lab = self.label_store.get(fn)
        if lab:
            review_note = "agree" if lab["agrees_with_prediction"] else "DISAGREE"
            if lab.get("needs_manual_label"):
                review_note += " — pick correct label"
            lines.append(f"Your review: {lab['user_label']}  ({review_note})")

        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.config(state=tk.DISABLED)

        breakdown = clf.get("breakdown", {}) or {}
        for dtype, lbl in self.score_labels.items():
            val = breakdown.get(dtype, row.get(f"score_{dtype}", ""))
            lbl.config(text=f"{val:.0f}" if isinstance(val, (int, float)) else str(val or "—"))

        self._plot_iv(rec.get("file_path", ""), fn)
        self._plot_device_timeline(dev_key, fn)
        self.canvas.draw_idle()

        if lab:
            self.review_status.config(
                text=f"Reviewed: {lab['user_label']}",
                foreground="green" if lab["agrees_with_prediction"] else "red",
            )
        else:
            self.review_status.config(text="Not reviewed yet", foreground="gray")

        pred = row.get("predicted_type", "")
        if pred in LABEL_CHOICES:
            self.user_label_var.set(pred)

    def _read_cached(self, file_path: str) -> Optional[tuple]:
        """Read a data file with caching to avoid redundant disk I/O."""
        if file_path in self._file_cache:
            return self._file_cache[file_path]
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            result = read_data_file(file_path)
            vi = (result[0], result[1])
            self._file_cache[file_path] = vi
            return vi
        except Exception:
            return None

    def _plot_iv(self, file_path: str, filename: str = "") -> None:
        self.ax.clear()
        vi = self._read_cached(file_path)
        if vi is None:
            self.ax.text(0.5, 0.5, "File not found", ha="center", va="center", transform=self.ax.transAxes)
            return  # canvas.draw_idle() called by _show_record
        try:
            v, i = vi
            scale, unit = self._current_scale_unit([np.max(np.abs(i))])
            sweep_n = parse_sweep_index(filename or Path(file_path).name)
            self.ax.plot(v, i * scale, "b-", linewidth=1.5)
            self.ax.set_xlabel("Voltage (V)")
            self.ax.set_ylabel(f"Current ({unit})")
            title = Path(file_path).name
            if sweep_n:
                title = f"sweep #{sweep_n} — {title}"
            self.ax.set_title(title, fontsize=9)
            self.ax.grid(True, alpha=0.3)
        except Exception as exc:
            self.ax.text(0.5, 0.5, str(exc), ha="center", va="center", fontsize=8, transform=self.ax.transAxes)

    def _current_scale_unit(self, max_abs_values: List[float]) -> tuple[float, str]:
        peak = max(max_abs_values) if max_abs_values else 0.0
        if peak < 1e-9:
            return 1e12, "pA"
        if peak < 1e-6:
            return 1e9, "nA"
        if peak < 1e-3:
            return 1e6, "µA"
        return 1e3, "mA"

    def _load_timeline_data(self, device_key: str) -> None:
        """Load and cache all sweep data for a device (only when device changes)."""
        if device_key == self._timeline_device_key:
            return
        self._timeline_device_key = device_key
        self._timeline_data = []

        sweeps = self.device_records.get(device_key, [])
        for rec in sweeps:
            fp = rec.get("file_path", "")
            vi = self._read_cached(fp)
            if vi is None:
                continue
            v, i = vi
            self._timeline_data.append((rec, v, i, float(np.max(np.abs(i)))))

    def _plot_device_timeline(self, device_key: str, current_filename: str) -> None:
        self._load_timeline_data(device_key)
        plotted = self._timeline_data

        if not plotted:
            if self._timeline_drawn_key != "__empty__":
                self.ax_timeline.clear()
                if self._colorbar is not None:
                    self._colorbar.remove()
                    self._colorbar = None
                self._timeline_drawn_key = "__empty__"
                self._timeline_lines.clear()
                self.ax_timeline.text(
                    0.5, 0.5, "No sweeps for this device", ha="center", va="center",
                    transform=self.ax_timeline.transAxes,
                )
            return

        need_full_redraw = (device_key != self._timeline_drawn_key)

        if need_full_redraw:
            self.ax_timeline.clear()
            if self._colorbar is not None:
                self._colorbar.remove()
                self._colorbar = None
            self._timeline_lines.clear()

            peaks = [peak for _, _, _, peak in plotted]
            scale, unit = self._current_scale_unit(peaks)
            cmap = plt.cm.viridis
            sweep_nums = [parse_sweep_index(rec["filename"]) for rec, _, _, _ in plotted]
            smin, smax = min(sweep_nums), max(sweep_nums)
            norm = plt.Normalize(
                vmin=smin if smin != smax else smin - 0.5,
                vmax=smax if smin != smax else smax + 0.5,
            )

            for rec, v, i, _ in plotted:
                fn = rec.get("filename", "")
                sweep_n = parse_sweep_index(fn)
                color = cmap(norm(sweep_n))
                is_current = fn == current_filename
                lw = 2.4 if is_current else 0.9
                alpha = 1.0 if is_current else 0.5
                (line,) = self.ax_timeline.plot(v, i * scale, color=color, linewidth=lw, alpha=alpha)
                self._timeline_lines[fn] = line

            self.ax_timeline.set_xlabel("Voltage (V)")
            self.ax_timeline.set_ylabel(f"Current ({unit})")
            self.ax_timeline.set_title(
                f"Device timeline: {device_key} ({len(plotted)} sweeps)", fontsize=9
            )
            self.ax_timeline.grid(True, alpha=0.3)

            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            self._colorbar = self.fig.colorbar(sm, ax=self.ax_timeline, fraction=0.03, pad=0.02)
            self._colorbar.set_label("Sweep #")
            self._timeline_drawn_key = device_key
        else:
            for fn, line in self._timeline_lines.items():
                if fn == current_filename:
                    line.set_linewidth(2.4)
                    line.set_alpha(1.0)
                else:
                    line.set_linewidth(0.9)
                    line.set_alpha(0.5)

        if hasattr(self, "_sel_annotation") and self._sel_annotation is not None:
            try:
                self._sel_annotation.remove()
            except Exception:
                pass
            self._sel_annotation = None

        if current_filename:
            cur_n = parse_sweep_index(current_filename)
            cur_type = ""
            for rec, _, _, _ in plotted:
                if rec.get("filename") == current_filename:
                    cur_type = rec.get("row", {}).get("predicted_type", "")
                    break
            self._sel_annotation = self.ax_timeline.text(
                0.02,
                0.98,
                f"Selected: #{cur_n} {cur_type}",
                transform=self.ax_timeline.transAxes,
                va="top",
                fontsize=8,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )

    def _agree(self) -> None:
        rec = self._current_record()
        if not rec:
            return
        pred = rec["row"]["predicted_type"]
        dev_key = rec["row"].get("device_group_key") or device_group_key_from_filename(rec["filename"])
        self.label_store.set_review(
            rec["filename"],
            user_label=pred,
            agrees_with_prediction=True,
            predicted_type=pred,
            device_group_key=dev_key,
        )
        self._after_review(saved_label=pred)

    def _disagree(self) -> None:
        rec = self._current_record()
        if not rec:
            return
        user = self.user_label_var.get().strip().lower()
        if not user:
            messagebox.showwarning("Label required", "Select the correct device type.")
            return
        pred = rec["row"]["predicted_type"]
        dev_key = rec["row"].get("device_group_key") or device_group_key_from_filename(rec["filename"])
        self.label_store.set_review(
            rec["filename"],
            user_label=user,
            agrees_with_prediction=False,
            predicted_type=pred,
            device_group_key=dev_key,
        )
        self._after_review(saved_label=user)

    def _skip(self) -> None:
        rec = self._current_record()
        if not rec:
            return
        dev_key = rec["row"].get("device_group_key") or device_group_key_from_filename(rec["filename"])
        self.label_store.set_review(
            rec["filename"],
            user_label="skip",
            agrees_with_prediction=True,
            predicted_type=rec["row"]["predicted_type"],
            device_group_key=dev_key,
        )
        self._after_review(saved_label="skip", advance=True)

    def _after_review(self, *, saved_label: str = "", advance: bool = True) -> None:
        rec = self._current_record()
        if not rec:
            return

        fn = rec["filename"]
        lab = self.label_store.get(fn)
        still_visible = lab is not None and self._record_passes_filter(rec, lab)

        if still_visible and 0 <= self.current_index < len(self.filtered):
            row = rec["row"]
            reviewed = "✓" if lab else " "
            agree = "Y" if lab and lab.get("agrees_with_prediction") else ("N" if lab else " ")
            line = f"{reviewed}{agree} {row['predicted_type'][:4]:4s} {row['confidence_pct']:4.0f}% {fn[:48]}"
            self.listbox.delete(self.current_index)
            self.listbox.insert(self.current_index, line)
            if advance:
                self._next()
        else:
            if 0 <= self.current_index < len(self.filtered):
                self.filtered.pop(self.current_index)
                self.listbox.delete(self.current_index)
            if self.current_index >= len(self.filtered) and self.filtered:
                self.current_index = len(self.filtered) - 1
            if self.filtered:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(self.current_index)
                self.listbox.see(self.current_index)
                self._show_record(self.filtered[self.current_index])

        self._update_stats_bar()
        self._update_metrics_panel()
        total = self.label_store.count()
        self.save_status_var.set(
            f"Saved '{saved_label}' → {self.paths['corrections_json'].name} ({total} total)"
        )

    def _current_record(self) -> Optional[dict]:
        if not self.filtered or self.current_index >= len(self.filtered):
            return None
        return self.filtered[self.current_index]

    def _prev(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_index)
            self._show_record(self.filtered[self.current_index])

    def _next(self) -> None:
        if self.filtered and self.current_index < len(self.filtered) - 1:
            self.current_index += 1
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.current_index)
            self.listbox.see(self.current_index)
            self._show_record(self.filtered[self.current_index])

    def _update_metrics_panel(self) -> None:
        reviewed = []
        for rec in self.records:
            fn = rec["filename"]
            lab = self.label_store.get(fn)
            if not lab or lab.get("user_label") == "skip":
                continue
            reviewed.append((rec["row"]["predicted_type"], lab["user_label"], lab["agrees_with_prediction"]))

        lines = [
            f"Reviewed: {len(reviewed)} / {len(self.records)}",
            f"Saved to: {self.paths['corrections_json']}",
            "Re-running batch_classify does NOT erase these corrections.",
        ]
        stats = self._correction_stats()
        if stats["orphaned"]:
            lines.append(
                f"Note: {stats['orphaned']} saved correction(s) are for filenames no longer in results "
                f"(e.g. after re-consolidation with renamed files)."
            )
        if reviewed:
            agree = sum(1 for *_, a in reviewed if a)
            lines.append(f"Agree with classifier: {agree} ({100*agree/len(reviewed):.1f}%)")
            disagree = len(reviewed) - agree
            lines.append(f"Disagree (misclassifications found): {disagree}")
            if disagree:
                pairs = Counter((p, u) for p, u, a in reviewed if not a)
                lines.append("Top prediction → your correction:")
                for (pred, user), n in pairs.most_common(8):
                    lines.append(f"  {pred} → {user}: {n}")

        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete("1.0", tk.END)
        self.metrics_text.insert("1.0", "\n".join(lines))
        self.metrics_text.config(state=tk.DISABLED)


def main(dataset: str = DEFAULT_DATASET) -> None:
    root = tk.Tk()
    ClassificationReviewApp(root, dataset=dataset)
    root.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default=DEFAULT_DATASET)
    args = parser.parse_args()
    main(dataset=args.dataset)
