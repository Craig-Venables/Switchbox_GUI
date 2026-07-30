"""Background workers for scan and report generation."""

from __future__ import annotations

from typing import Optional, Sequence

from PyQt5.QtCore import QThread, pyqtSignal

from ..config import AppConfig
from ..import_pipeline import scan_and_update_cache
from ..report import generate_report


class ScanWorker(QThread):
    progress = pyqtSignal(str, float)
    finished_ok = pyqtSignal(object)  # ScanSummary
    failed = pyqtSignal(str)

    def __init__(self, config: AppConfig, rebuild: bool = False, parent=None):
        super().__init__(parent)
        self.config = config
        self.rebuild = rebuild

    def run(self) -> None:
        try:
            summary = scan_and_update_cache(
                self.config,
                rebuild=self.rebuild,
                progress=lambda msg, frac: self.progress.emit(msg, float(frac)),
            )
            self.finished_ok.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))


class ReportWorker(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object)  # ReportResult
    failed = pyqtSignal(str)

    def __init__(
        self,
        config: AppConfig,
        *,
        sample_ids: Optional[Sequence[str]] = None,
        polymers: Optional[Sequence[str]] = None,
        bottom_electrodes: Optional[Sequence[str]] = None,
        top_electrodes: Optional[Sequence[str]] = None,
        polymer_percents: Optional[Sequence[float]] = None,
        np_types: Optional[Sequence[str]] = None,
        min_sample_number: Optional[int] = None,
        max_sample_number: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.sample_ids = sample_ids
        self.polymers = polymers
        self.bottom_electrodes = bottom_electrodes
        self.top_electrodes = top_electrodes
        self.polymer_percents = polymer_percents
        self.np_types = np_types
        self.min_sample_number = min_sample_number
        self.max_sample_number = max_sample_number

    def run(self) -> None:
        try:
            self.progress.emit("Generating report from cache…")
            result = generate_report(
                self.config,
                sample_ids=self.sample_ids,
                polymers=self.polymers,
                bottom_electrodes=self.bottom_electrodes,
                top_electrodes=self.top_electrodes,
                polymer_percents=self.polymer_percents,
                np_types=self.np_types,
                min_sample_number=self.min_sample_number,
                max_sample_number=self.max_sample_number,
                log_fn=lambda m: self.progress.emit(m),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
