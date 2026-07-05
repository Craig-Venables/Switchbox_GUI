"""
Fast flash review: big predicted type on screen, Y/N keyboard shortcuts.

Quick yes/no on whether the classifier got it right. Disagreements are saved
for full manual labelling later in review_classifications.py (filter: I disagreed).

Usage:
    python tools/data_consolidation/launch_flash_review.py
    python tools/data_consolidation/launch_flash_review.py --dataset "All combined"
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

_TOOL_DIR = Path(__file__).resolve().parent
_ROOT = _TOOL_DIR.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from analysis.core.sweep_analyzer import read_data_file

from classification_store import ReviewLabelStore, device_group_key_from_filename, load_results, parse_sweep_index
from paths import DATASETS, DEFAULT_DATASET, dataset_paths

FLASH_TYPE_CHOICES = [
    "memristive",
    "rectifying",
    "uncertain",
    "ohmic",
    "non_conductive",
    "capacitive",
    "conductive",
    "all types",
]

TYPE_COLORS = {
    "memristive": "#1a7f37",
    "rectifying": "#bf5700",
    "uncertain": "#6e40c9",
    "ohmic": "#0969da",
    "non_conductive": "#57606a",
    "capacitive": "#8250df",
    "conductive": "#0550ae",
}


class FlashReviewApp:
    """Minimal UI for rapid Y/N validation of predicted classifications."""

    def __init__(self, root: tk.Tk, *, dataset: str = DEFAULT_DATASET) -> None:
        self.root = root
        self.dataset = dataset
        self.paths = dataset_paths(dataset)
        self.root.title(f"Flash Review — {dataset}")
        self.root.geometry("1100x820")

        self.label_store = ReviewLabelStore(
            path=self.paths["corrections_json"],
            dataset=self.dataset,
            legacy_path=self.paths["labels_json"],
        )
        self.records: List[Dict[str, Any]] = []
        self.queue: List[Dict[str, Any]] = []
        self.index = 0
        self._file_cache: Dict[str, tuple] = {}

        self._build_ui()
        self._bind_keys()
        self._load_results()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Dataset:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(4, 4))
        self.dataset_var = tk.StringVar(value=self.dataset)
        ds_box = ttk.Combobox(
            top, textvariable=self.dataset_var, values=list(DATASETS.keys()), state="readonly", width=14
        )
        ds_box.pack(side=tk.LEFT)
        ds_box.bind("<<ComboboxSelected>>", lambda e: self._on_dataset_change())

        ttk.Label(top, text="Predicted type:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(16, 4))
        self.type_var = tk.StringVar(value="memristive")
        type_box = ttk.Combobox(
            top, textvariable=self.type_var, values=FLASH_TYPE_CHOICES, state="readonly", width=16
        )
        type_box.pack(side=tk.LEFT)
        type_box.bind("<<ComboboxSelected>>", lambda e: self._rebuild_queue())

        self.skip_reviewed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, text="Skip already reviewed", variable=self.skip_reviewed_var, command=self._rebuild_queue
        ).pack(side=tk.LEFT, padx=12)

        ttk.Button(top, text="Reload", command=self._reload).pack(side=tk.LEFT, padx=4)

        self.progress_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.progress_var, foreground="blue").pack(side=tk.LEFT, padx=12)

        flash_frame = ttk.Frame(self.root, padding=(12, 8))
        flash_frame.pack(fill=tk.X)

        ttk.Label(flash_frame, text="Is this classification correct?", font=("Arial", 14)).pack()
        self.flash_label = tk.Label(
            flash_frame,
            text="—",
            font=("Arial", 52, "bold"),
            fg="#1a7f37",
            pady=8,
        )
        self.flash_label.pack()
        self.sub_label = tk.Label(flash_frame, text="", font=("Arial", 12), fg="#444")
        self.sub_label.pack()
        self.file_label = tk.Label(flash_frame, text="", font=("Consolas", 9), fg="#666")
        self.file_label.pack(pady=(4, 0))

        plot_frame = ttk.LabelFrame(self.root, text="I–V curve", padding=4)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.fig, self.ax = plt.subplots(figsize=(7, 4.5), constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        actions = ttk.Frame(self.root, padding=10)
        actions.pack(fill=tk.X)

        yes_btn = tk.Button(
            actions,
            text="Yes  (Y)",
            font=("Arial", 16, "bold"),
            bg="#1a7f37",
            fg="white",
            activebackground="#116329",
            activeforeground="white",
            width=12,
            height=2,
            command=self._yes,
        )
        yes_btn.pack(side=tk.LEFT, padx=20, expand=True)
        no_btn = tk.Button(
            actions,
            text="No  (N)",
            font=("Arial", 16, "bold"),
            bg="#cf222e",
            fg="white",
            activebackground="#a40e26",
            activeforeground="white",
            width=12,
            height=2,
            command=self._no,
        )
        no_btn.pack(side=tk.LEFT, padx=20, expand=True)
        skip_btn = tk.Button(
            actions,
            text="Skip  (S)",
            font=("Arial", 12),
            width=10,
            height=2,
            command=self._skip,
        )
        skip_btn.pack(side=tk.LEFT, padx=20, expand=True)

        ttk.Label(
            self.root,
            text="Keys: Y = correct  |  N = wrong (label later in full review)  |  S = skip  |  ← → = prev/next",
            font=("Arial", 9),
            foreground="#555",
        ).pack(pady=(0, 8))

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self.status_var, foreground="green").pack(pady=(0, 6))

    def _bind_keys(self) -> None:
        for key in ("y", "Y", "n", "N", "s", "S", "Left", "Right"):
            self.root.bind(f"<{key}>", self._on_key)

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym in ("y", "Y"):
            self._yes()
        elif event.keysym in ("n", "N"):
            self._no()
        elif event.keysym in ("s", "S"):
            self._skip()
        elif event.keysym == "Left":
            self._prev()
        elif event.keysym == "Right":
            self._next_preview()

    def _on_dataset_change(self) -> None:
        name = self.dataset_var.get()
        if name == self.dataset or name not in DATASETS:
            return
        self.dataset = name
        self.paths = dataset_paths(name)
        self.label_store = ReviewLabelStore(
            path=self.paths["corrections_json"],
            dataset=self.dataset,
            legacy_path=self.paths["labels_json"],
        )
        self._file_cache.clear()
        self.root.title(f"Flash Review — {name}")
        self._load_results()

    def _reload(self) -> None:
        self.label_store.load()
        self._load_results()
        self.status_var.set("Reloaded corrections from disk")

    def _load_results(self) -> None:
        self.records = load_results(dataset=self.dataset)
        if not self.records:
            messagebox.showwarning(
                "No results",
                f"No classification results for '{self.dataset}'.\nRun batch_classify first.",
            )
            return
        self._rebuild_queue()

    def _rebuild_queue(self) -> None:
        type_filter = self.type_var.get()
        skip_reviewed = self.skip_reviewed_var.get()
        self.queue = []
        for rec in self.records:
            row = rec.get("row", {})
            pred = row.get("predicted_type", "")
            if type_filter != "all types" and pred != type_filter:
                continue
            fn = rec.get("filename", "")
            if skip_reviewed and self.label_store.get(fn):
                continue
            self.queue.append(rec)
        self.index = 0
        self._show_current()

    def _current(self) -> Optional[Dict[str, Any]]:
        if not self.queue or self.index >= len(self.queue):
            return None
        return self.queue[self.index]

    def _show_current(self) -> None:
        rec = self._current()
        if rec is None:
            self.flash_label.config(text="Done!", fg="#57606a")
            self.sub_label.config(text="Change predicted type or turn off 'Skip already reviewed' for more.")
            self.file_label.config(text="")
            self.ax.clear()
            self.ax.text(0.5, 0.5, "Queue empty", ha="center", va="center", transform=self.ax.transAxes)
            self.canvas.draw_idle()
            self.progress_var.set(f"0 remaining  |  saved {self.label_store.count()} corrections")
            return

        row = rec["row"]
        pred = row.get("predicted_type", "?")
        conf = row.get("confidence_pct", 0)
        fn = rec.get("filename", "")

        color = TYPE_COLORS.get(pred, "#333")
        self.flash_label.config(text=pred.upper(), fg=color)
        self.sub_label.config(
            text=f"{conf}% confidence  |  memristivity {row.get('memristivity_score', '—')}"
        )
        self.file_label.config(text=fn)
        self.progress_var.set(
            f"{self.index + 1} / {len(self.queue)}  |  "
            f"type={self.type_var.get()}  |  saved {self.label_store.count()} corrections"
        )
        self._plot_iv(rec.get("file_path", ""), fn)
        self.status_var.set("")

    def _read_cached(self, file_path: str) -> Optional[tuple]:
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

    def _plot_iv(self, file_path: str, filename: str) -> None:
        self.ax.clear()
        vi = self._read_cached(file_path)
        if vi is None:
            self.ax.text(0.5, 0.5, "File not found", ha="center", va="center", transform=self.ax.transAxes)
            self.canvas.draw_idle()
            return
        v, i = vi
        peak = float(np.max(np.abs(i)))
        if peak < 1e-9:
            scale, unit = 1e12, "pA"
        elif peak < 1e-6:
            scale, unit = 1e9, "nA"
        elif peak < 1e-3:
            scale, unit = 1e6, "µA"
        else:
            scale, unit = 1e3, "mA"
        sweep_n = parse_sweep_index(filename)
        self.ax.plot(v, i * scale, "b-", linewidth=1.8)
        self.ax.set_xlabel("Voltage (V)")
        self.ax.set_ylabel(f"Current ({unit})")
        title = filename if len(filename) < 60 else filename[:57] + "..."
        if sweep_n:
            title = f"sweep #{sweep_n} — {title}"
        self.ax.set_title(title, fontsize=9)
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw_idle()

    def _save_and_advance(self, *, agree: bool, saved_label: str, needs_manual: bool = False) -> None:
        rec = self._current()
        if not rec:
            return
        row = rec["row"]
        pred = row.get("predicted_type", "")
        fn = rec.get("filename", "")
        dev_key = row.get("device_group_key") or device_group_key_from_filename(fn)
        self.label_store.set_review(
            fn,
            user_label=saved_label,
            agrees_with_prediction=agree,
            predicted_type=pred,
            device_group_key=dev_key,
            review_mode="flash",
            needs_manual_label=needs_manual,
            notes="Flash review: needs manual label" if needs_manual else "Flash review",
        )
        if self.skip_reviewed_var.get():
            self.queue.pop(self.index)
            if self.index >= len(self.queue) and self.queue:
                self.index = len(self.queue) - 1
        else:
            self.index += 1
        total = self.label_store.count()
        self.status_var.set(
            f"Saved → {self.paths['corrections_json'].name} ({total} total)"
            + (" — label later in full review" if needs_manual else "")
        )
        self._show_current()

    def _yes(self) -> None:
        rec = self._current()
        if not rec:
            return
        pred = rec["row"]["predicted_type"]
        self._save_and_advance(agree=True, saved_label=pred)

    def _no(self) -> None:
        rec = self._current()
        if not rec:
            return
        pred = rec["row"]["predicted_type"]
        # Placeholder label; full review GUI picks the correct type (filter: I disagreed)
        self._save_and_advance(agree=False, saved_label="uncertain", needs_manual=True)

    def _skip(self) -> None:
        rec = self._current()
        if not rec:
            return
        row = rec["row"]
        fn = rec.get("filename", "")
        dev_key = row.get("device_group_key") or device_group_key_from_filename(fn)
        self.label_store.set_review(
            fn,
            user_label="skip",
            agrees_with_prediction=True,
            predicted_type=row.get("predicted_type", ""),
            device_group_key=dev_key,
            review_mode="flash",
            notes="Flash review skip",
        )
        if self.skip_reviewed_var.get():
            self.queue.pop(self.index)
            if self.index >= len(self.queue) and self.queue:
                self.index = len(self.queue) - 1
        else:
            self.index += 1
        self._show_current()

    def _prev(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._show_current()

    def _next_preview(self) -> None:
        if self.index < len(self.queue) - 1:
            self.index += 1
            self._show_current()


def main(dataset: str = DEFAULT_DATASET) -> None:
    root = tk.Tk()
    FlashReviewApp(root, dataset=dataset)
    root.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fast flash review with Y/N shortcuts.")
    parser.add_argument("--dataset", choices=list(DATASETS.keys()), default=DEFAULT_DATASET)
    args = parser.parse_args()
    main(dataset=args.dataset)
