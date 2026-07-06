"""
Frozen-build helpers for launching tools and Python scripts.

When Switchbox_GUI is packaged with PyInstaller, ``sys.executable`` points at
the main ``.exe`` — not Python — so subprocess launches must use bundled
companion executables (``tools_bin/``) or ``Switchbox_ScriptRunner.exe``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

# tool_id → standalone PyInstaller output name (without .exe)
TOOL_EXE_NAMES: dict[str, str] = {
    "display": "DisplayControl",
    "led_testing": "LEDTesting",
    "camera_stream": "CameraStream",
    "data_analysis_pulse_2450": "TSP_Data_Analysis",
}

SCRIPT_RUNNER_NAME = "Switchbox_ScriptRunner"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Repository root in dev; bundled resource root when frozen."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def app_dir() -> Path:
    """Directory beside the running executable (distributable root when frozen)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _tools_bin_dir() -> Path:
    return app_dir() / "tools_bin"


def resolve_bundled_script(relative_path: str) -> Optional[Path]:
    """Resolve a repo-relative script path (e.g. tools/Display/main.py)."""
    rel = Path(relative_path.replace("/", "\\")) if "\\" in relative_path else Path(relative_path)
    for base in (repo_root(), app_dir()):
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return None


def resolve_tool_exe(tool_id: str) -> Optional[Path]:
    """Return a bundled standalone tool executable, if present."""
    name = TOOL_EXE_NAMES.get(tool_id)
    if not name:
        return None
    exe_name = f"{name}.exe" if sys.platform == "win32" else name
    candidate = _tools_bin_dir() / exe_name
    if candidate.is_file():
        return candidate
    # Allow tools placed directly next to the main onedir folder
    fallback = app_dir().parent / "tools_bin" / exe_name
    if fallback.is_file():
        return fallback
    return None


def resolve_script_runner() -> Optional[Path]:
    exe_name = f"{SCRIPT_RUNNER_NAME}.exe" if sys.platform == "win32" else SCRIPT_RUNNER_NAME
    for base in (_tools_bin_dir(), app_dir()):
        candidate = base / exe_name
        if candidate.is_file():
            return candidate
    return None


def _popen_kwargs(
    *,
    cwd: Optional[Path],
    hide_console: bool,
    new_console: bool,
) -> dict:
    kwargs: dict = {}
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if sys.platform == "win32":
        flags = 0
        if hide_console:
            flags |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        if new_console:
            flags |= subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
        if flags:
            kwargs["creationflags"] = flags
    return kwargs


def launch_argv(
    argv: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    hide_console: bool = False,
    new_console: bool = False,
) -> subprocess.Popen:
    return subprocess.Popen(
        list(argv),
        **_popen_kwargs(cwd=cwd, hide_console=hide_console, new_console=new_console),
    )


def launch_python_script(
    relative_script: str,
    args: Optional[Iterable[str]] = None,
    *,
    cwd: Optional[Path] = None,
    hide_console: bool = False,
    new_console: bool = False,
) -> subprocess.Popen:
    """
    Launch a repo-relative Python script.

    Dev: ``python <script> [args]``
    Frozen: ``Switchbox_ScriptRunner.exe <script> [args]`` (script from bundle)
    """
    script = resolve_bundled_script(relative_script)
    if script is None:
        raise FileNotFoundError(f"Script not found: {relative_script}")

    extra: List[str] = [str(a) for a in (args or [])]
    if is_frozen():
        runner = resolve_script_runner()
        if runner is None:
            raise FileNotFoundError(
                f"{SCRIPT_RUNNER_NAME} not found under {_tools_bin_dir()}. "
                "Rebuild the v6 release package (see packaging/BUILD_RELEASE_V6.md)."
            )
        argv = [str(runner), str(script), *extra]
    else:
        argv = [sys.executable, str(script), *extra]

    return launch_argv(
        argv,
        cwd=cwd,
        hide_console=hide_console,
        new_console=new_console,
    )


def launch_registered_tool(
    tool_id: str,
    *,
    module_path: str,
    cwd: Optional[Path] = None,
) -> subprocess.Popen:
    """
    Launch a hardware tool from Measurement GUI.

    Prefers a standalone ``tools_bin/<Tool>.exe`` when frozen; falls back to
    the Python entry script in development.
    """
    if is_frozen():
        tool_exe = resolve_tool_exe(tool_id)
        if tool_exe is not None:
            return launch_argv([str(tool_exe)], cwd=cwd, new_console=True)
    return launch_python_script(
        module_path,
        cwd=cwd or repo_root(),
        new_console=True,
    )
