"""
Emit deprecation warnings and log when old import paths are used, so call sites can be updated.
"""
import inspect
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

# Log file path: CWD by default, or set PLOTTING_DEPRECATION_LOG to override
_LOG_PATH: Optional[Path] = None


def _get_log_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is not None:
        return _LOG_PATH
    env_path = os.environ.get("PLOTTING_DEPRECATION_LOG")
    if env_path:
        _LOG_PATH = Path(env_path)
    else:
        _LOG_PATH = Path.cwd() / "plotting_deprecation.log"
    return _LOG_PATH


def _find_caller_outside_plotting() -> tuple:
    """Return (filepath, line_no) of the first stack frame outside the plotting package."""
    plotting_root = Path(__file__).resolve().parent.parent
    for frame_info in inspect.stack():
        filename = frame_info.filename
        # Skip stdlib / frozen / importlib
        if "<frozen" in filename or "importlib" in filename:
            continue
        try:
            path = Path(filename).resolve()
            try:
                path.relative_to(plotting_root)
                continue  # inside plotting package, skip
            except ValueError:
                pass  # not under plotting_root
            return filename, frame_info.lineno
        except Exception:
            pass
    return "<unknown>", 0


def warn_old_import(old_module: str, new_module: str) -> None:
    """
    Emit a DeprecationWarning and append to the deprecation log when an old import path is used.
    Call this from re-export stub modules at load time.
    """
    caller_file, caller_line = _find_caller_outside_plotting()
    message = (
        f"plotting: {old_module} is a legacy path. Use {new_module} instead. "
        f"Caller: {caller_file}:{caller_line}"
    )
    warnings.warn(message, DeprecationWarning, stacklevel=2)

    try:
        log_path = _get_log_path()
        ts = datetime.now().isoformat(timespec="seconds")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {old_module} -> {new_module} | {caller_file}:{caller_line}\n")
    except OSError:
        pass


def set_deprecation_log_path(path: Optional[Path]) -> None:
    """Set the log file path for deprecation messages (e.g. for tests)."""
    global _LOG_PATH
    _LOG_PATH = path
