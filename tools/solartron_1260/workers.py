"""QThread workers for non-blocking Solartron sweeps."""

from __future__ import annotations

from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from engine import SweepConfig, SweepEngine


class SweepWorker(QThread):
    """Run one sweep role on a background thread."""

    progress = pyqtSignal(int, int, dict)  # current, total, point
    finished_ok = pyqtSignal(object)  # SweepResult
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(
        self,
        engine: SweepEngine,
        config: SweepConfig,
        role: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.config = config
        self.role = role

    def run(self) -> None:
        try:
            self.status.emit(
                f"Starting {self.role} sweep at VB={self.config.dc_bias_v:+.3f} V…"
            )
            result = self.engine.run_sweep(
                self.config,
                self.role,
                progress=lambda cur, tot, pt: self.progress.emit(cur, tot, pt),
            )
            self.finished_ok.emit(result)
        except InterruptedError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))

    def request_cancel(self) -> None:
        self.engine.request_cancel()


class BiasSeriesWorker(QThread):
    """Run frequency sweeps at each DC bias voltage."""

    progress = pyqtSignal(int, int, dict)  # point progress within current bias
    bias_progress = pyqtSignal(int, int, float)  # bias index, n_bias, bias_v
    finished_ok = pyqtSignal(object)  # List[SweepResult]
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(
        self,
        engine: SweepEngine,
        config: SweepConfig,
        biases_v: List[float],
        role: str = "device_only",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.config = config
        self.biases_v = list(biases_v)
        self.role = role

    def run(self) -> None:
        try:
            self.status.emit(
                f"Bias series: {len(self.biases_v)} levels "
                f"({self.biases_v[0]:+.3g} … {self.biases_v[-1]:+.3g} V)"
            )
            results = self.engine.run_bias_series(
                self.config,
                self.biases_v,
                role=self.role,
                progress=lambda cur, tot, pt: self.progress.emit(cur, tot, pt),
                bias_progress=lambda i, n, b: self.bias_progress.emit(i, n, b),
            )
            self.finished_ok.emit(results)
        except InterruptedError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))

    def request_cancel(self) -> None:
        self.engine.request_cancel()


class ConnectWorker(QThread):
    """Open the instrument on a background thread."""

    finished_ok = pyqtSignal(list)  # resource list
    failed = pyqtSignal(str)

    def __init__(self, engine: SweepEngine, config: SweepConfig, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.config = config

    def run(self) -> None:
        try:
            resources = self.engine.connect(self.config)
            self.finished_ok.emit(resources)
        except Exception as exc:
            self.failed.emit(str(exc))
