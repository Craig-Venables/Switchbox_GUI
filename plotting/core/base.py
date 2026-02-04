from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt


class PlotManager:
    """Small helper for consistent saving and directory handling."""

    def __init__(self, save_dir: Optional[Path] = None, auto_close: bool = True):
        self.save_dir = Path(save_dir) if save_dir else None
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        self.auto_close = auto_close

    def save(self, fig: plt.Figure, name: str, subdir: Optional[str] = None) -> Path:
        if self.save_dir is None:
            raise ValueError("save_dir not set for PlotManager")
        target_dir = self.save_dir / subdir if subdir else self.save_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / name
        if path.suffix == "":
            path = path.with_suffix(".png")
        fig.savefig(path, bbox_inches="tight")
        if self.auto_close:
            plt.close(fig)
        return path
