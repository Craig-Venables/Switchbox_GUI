"""
Laser FG Scope GUI — Save Manager
==================================
Handles path resolution and writing for Fast Optical Pulse captures.

Save directory structure
------------------------
When launched from Measurement GUI (provider available):
    {base}/{sample}/{letter}/{number}/Fast_Optical_Pulses/

When run standalone with a simple save folder set:
    {simple_folder}/Fast_Optical_Pulses/

File naming:
    {index:03d}-{pulse_width_ns:.0f}ns-{bias_v:+.2f}V-{timestamp}.csv
    {index:03d}-{pulse_width_ns:.0f}ns-{bias_v:+.2f}V-{timestamp}.png  (companion)

CSV format:
    # comment-header lines with experiment metadata (Origin-friendly)
    time_s,voltage_V
    <data rows>
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np


SUBFOLDER = "Fast_Optical_Pulses"


class SaveManager:
    """
    Manages the save location and writing of captured waveform data.

    Usage
    -----
    mgr = SaveManager(provider=measurement_gui_instance)   # or provider=None
    mgr.set_simple_path("/path/to/folder")   # only needed if no provider
    mgr.auto_save = True

    # Called by main.py after each capture:
    path = mgr.save_capture(time_arr, volt_arr, meta, fig)
    """

    def __init__(self, provider: Any = None) -> None:
        self._provider    = provider   # measurement GUI instance or None
        self._simple_path = ""         # user-chosen folder (standalone mode)
        self._auto_save   = False

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def auto_save(self) -> bool:
        return self._auto_save

    @auto_save.setter
    def auto_save(self, val: bool) -> None:
        self._auto_save = bool(val)

    @property
    def simple_path(self) -> str:
        return self._simple_path

    def set_simple_path(self, path: str) -> None:
        self._simple_path = path.strip()

    def set_provider(self, provider: Any) -> None:
        self._provider = provider

    # ── Path resolution ───────────────────────────────────────────────────────

    def get_save_dir(self) -> Optional[Path]:
        """
        Return the full save directory Path, or None if no location is set.
        Creates intermediate directories when returning a valid path.
        """
        d = self._resolve_dir()
        if d:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def _resolve_dir(self) -> Optional[Path]:
        if self._provider:
            return self._provider_dir()
        if self._simple_path:
            return Path(self._simple_path) / SUBFOLDER
        return None

    def _provider_dir(self) -> Optional[Path]:
        try:
            base   = self._provider._get_base_save_path()
            sample = self._get_sample_name()
            letter, number = self._get_device_parts()
            return Path(base) / sample / letter / str(number) / SUBFOLDER
        except Exception as exc:
            print(f"[SaveManager] Could not build provider path: {exc}")
            # Fall back to simple_path if set
            if self._simple_path:
                return Path(self._simple_path) / SUBFOLDER
        return None

    # ── Provider helpers ──────────────────────────────────────────────────────

    def _get_sample_name(self) -> str:
        p = self._provider
        if p is None:
            return "Unknown"
        try:
            if hasattr(p, "sample_name_var"):
                name = p.sample_name_var.get().strip()
                if name:
                    return name
        except Exception:
            pass
        try:
            if hasattr(p, "sample_gui") and hasattr(p.sample_gui, "current_device_name"):
                name = p.sample_gui.current_device_name
                if name and name != "Unknown":
                    return name
        except Exception:
            pass
        return "Unknown"

    def _get_device_parts(self) -> Tuple[str, str]:
        p = self._provider
        if p is None:
            return "X", "0"
        try:
            letter = str(getattr(p, "final_device_letter", None) or "X")
            number = str(getattr(p, "final_device_number", None) or "0")
            return letter, number
        except Exception:
            return "X", "0"

    def get_context_strings(self) -> Tuple[str, str]:
        """Return (sample_name, device_label) for embedding in metadata."""
        if self._provider:
            sample = self._get_sample_name()
            letter, number = self._get_device_parts()
            return sample, f"{letter}{number}"
        return "Unknown", "Unknown"

    # ── Save ──────────────────────────────────────────────────────────────────

    def save_capture(
        self,
        time_arr:  np.ndarray,
        volt_arr:  np.ndarray,
        meta:      Dict[str, Any],
        fig:       Any = None,   # matplotlib Figure or None
    ) -> Optional[str]:
        """
        Write CSV + companion PNG to the configured save directory.

        Returns the full path to the saved CSV file, or None if saving failed
        or no save directory is configured.
        """
        save_dir = self.get_save_dir()
        if save_dir is None:
            return None

        if time_arr is None or volt_arr is None or len(time_arr) < 2:
            return None

        try:
            stem    = self._build_stem(save_dir, meta)
            csv_p   = save_dir / f"{stem}.csv"
            png_p   = save_dir / f"{stem}.png"

            # Enrich meta with sample/device from provider
            sample, device = self.get_context_strings()
            enriched = dict(meta)
            enriched.setdefault("sample_name",  sample)
            enriched.setdefault("device_label", device)

            self._write_csv(csv_p, time_arr, volt_arr, enriched)

            if fig is not None:
                try:
                    fig.savefig(str(png_p), dpi=150, bbox_inches="tight")
                except Exception as exc:
                    print(f"[SaveManager] PNG save failed: {exc}")

            return str(csv_p)

        except Exception as exc:
            print(f"[SaveManager] save_capture failed: {exc}")
            return None

    # ── File naming ───────────────────────────────────────────────────────────

    def _build_stem(self, folder: Path, meta: Dict[str, Any]) -> str:
        index    = self._get_next_index(folder)
        pw_ns    = float(meta.get("pulse_width_ns", 0))
        bias_v   = float(meta.get("bias_v", 0.0))
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{index:03d}-{pw_ns:.0f}ns-{bias_v:+.2f}V-{ts}"

    @staticmethod
    def _get_next_index(folder: Path) -> int:
        """Return 1 + the highest existing numeric prefix in the folder."""
        indices = []
        for f in folder.glob("*.csv"):
            try:
                indices.append(int(f.stem.split("-")[0]))
            except (ValueError, IndexError):
                pass
        return max(indices, default=0) + 1

    # ── CSV writing ───────────────────────────────────────────────────────────

    @staticmethod
    def _write_csv(
        path:     Path,
        time_arr: np.ndarray,
        volt_arr: np.ndarray,
        meta:     Dict[str, Any],
    ) -> None:
        ts = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        with open(str(path), "w", newline="", encoding="utf-8") as fh:
            fh.write("# Laser FG Scope — Fast Optical Pulse Capture\n")
            fh.write(f"# Timestamp:        {ts}\n")
            fh.write(f"# Sample:           {meta.get('sample_name',  'Unknown')}\n")
            fh.write(f"# Device:           {meta.get('device_label', 'Unknown')}\n")
            fh.write(f"# FG Mode:          {meta.get('fg_mode',      'unknown')}\n")
            fh.write(f"# Pulse Width (ns): {meta.get('pulse_width_ns', 0):.1f}\n")
            fh.write(f"# Burst Count:      {meta.get('burst_count',   1)}\n")
            fh.write(f"# Bias (V):         {meta.get('bias_v',        0.0):.4f}\n")
            fh.write(f"# Laser Power (mW): {meta.get('laser_power_mw',0.0):.2f}\n")
            fh.write(f"# Scope Channel:    CH{meta.get('scope_channel', 1)}\n")
            fh.write(f"# Points:           {len(time_arr)}\n")
            fh.write("#\n")
            fh.write("time_s,voltage_V\n")
            writer = csv.writer(fh)
            for t, v in zip(time_arr, volt_arr):
                writer.writerow([f"{t:.12e}", f"{v:.8e}"])
