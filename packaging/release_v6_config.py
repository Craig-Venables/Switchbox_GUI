"""
Release v6 manifest — targets, paths, and assembly layout.

Used by ``packaging/build_release_v6.py``. Do not run PyInstaller from here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BuildTarget:
    """One PyInstaller build step."""

    key: str
    label: str
    command: list[str]  # argv relative to repo root (python packaging/...)
    output_paths: list[str]  # repo-relative paths to verify after build
    required: bool = True
    optional_reason: str = ""


@dataclass(frozen=True)
class CopyArtifact:
    """File or directory to copy into the v6 release folder."""

    key: str
    label: str
    source_globs: list[str]  # repo-relative; first existing match wins per glob
    dest_under_release: str  # relative to dist/Switchbox_GUI_v6/
    required: bool = True
    optional_reason: str = ""


RELEASE_VERSION = "6.1"
RELEASE_DIR_NAME = f"Switchbox_GUI_v{RELEASE_VERSION}"

# Main app + everything needed for Measurement GUI top-bar buttons (Hardware Tools exes).
TOP_BAR_BUILD_KEYS = ("main", "script_runner", "display", "led_testing")
TOP_BAR_ARTIFACT_KEYS = (
    "main_app",
    "tools_bin_runner",
    "tools_bin_display",
    "tools_bin_led",
)


def repo_targets(repo_root: Path) -> list[BuildTarget]:
    py = _python_executable()

    return [
        BuildTarget(
            key="main",
            label="Switchbox_GUI (main app, onedir)",
            command=[py, "packaging/build_exe.py"],
            output_paths=["dist/Switchbox_GUI/Switchbox_GUI.exe"],
            required=True,
        ),
        BuildTarget(
            key="script_runner",
            label="Switchbox_ScriptRunner (console helper for bundled .py tools)",
            command=[
                py,
                "-m",
                "PyInstaller",
                "packaging/build_script_runner.spec",
                "--clean",
                "--noconfirm",
            ],
            output_paths=["dist/Switchbox_ScriptRunner.exe"],
            required=True,
        ),
        BuildTarget(
            key="pulse_classic",
            label="Pulse Testing GUI - classic layout",
            command=[py, "packaging/build_pulse_testing_gui.py"],
            output_paths=["dist/Pulse_Testing_GUI/Pulse_Testing_GUI.exe"],
            required=True,
        ),
        BuildTarget(
            key="pulse_compact",
            label="Pulse Testing GUI - compact layout",
            command=[py, "packaging/build_pulse_testing_gui.py", "--compact"],
            output_paths=["dist/Pulse_Testing_GUI_Compact/Pulse_Testing_GUI_Compact.exe"],
            required=True,
        ),
        BuildTarget(
            key="display",
            label="Display Control (ST7789 Arduino tool)",
            command=[py, "tools/Display/build_exe.py"],
            output_paths=["tools/Display/dist/DisplayControl.exe"],
            required=True,
        ),
        BuildTarget(
            key="led_testing",
            label="LED Testing (Arduino tool)",
            command=[py, "tools/LED_testing/build_exe.py"],
            output_paths=["tools/LED_testing/dist/LEDTesting.exe"],
            required=True,
        ),
        BuildTarget(
            key="camera_stream",
            label="Camera Stream standalone",
            command=[py, "tools/camera_stream_standalone/build_exe.py"],
            output_paths=["tools/camera_stream_standalone/dist/CameraStream.exe"],
            required=False,
            optional_reason="OpenCV/Flask stack; skip with --skip-optional",
        ),
        BuildTarget(
            key="tsp_data_analysis",
            label="TSP Data Analysis (PyQt6)",
            command=[py, "tools/data_analysis_pulse_2450/build_exe.py"],
            output_paths=["tools/data_analysis_pulse_2450/dist/TSP_Data_Analysis.exe"],
            required=False,
            optional_reason="Requires PyQt6; skip with --skip-optional",
        ),
    ]


def assembly_artifacts() -> list[CopyArtifact]:
    return [
        CopyArtifact(
            key="main_app",
            label="Main Switchbox_GUI onedir",
            source_globs=["dist/Switchbox_GUI"],
            dest_under_release="Switchbox_GUI",
            required=True,
        ),
        CopyArtifact(
            key="tools_bin_runner",
            label="Script runner",
            source_globs=["dist/Switchbox_ScriptRunner.exe"],
            dest_under_release="Switchbox_GUI/tools_bin/Switchbox_ScriptRunner.exe",
            required=True,
        ),
        CopyArtifact(
            key="tools_bin_display",
            label="Display Control exe",
            source_globs=["tools/Display/dist/DisplayControl.exe"],
            dest_under_release="Switchbox_GUI/tools_bin/DisplayControl.exe",
            required=True,
        ),
        CopyArtifact(
            key="tools_bin_led",
            label="LED Testing exe",
            source_globs=["tools/LED_testing/dist/LEDTesting.exe"],
            dest_under_release="Switchbox_GUI/tools_bin/LEDTesting.exe",
            required=True,
        ),
        CopyArtifact(
            key="tools_bin_camera",
            label="Camera Stream exe",
            source_globs=["tools/camera_stream_standalone/dist/CameraStream.exe"],
            dest_under_release="Switchbox_GUI/tools_bin/CameraStream.exe",
            required=False,
            optional_reason="Built only when camera_stream target succeeds",
        ),
        CopyArtifact(
            key="tools_bin_tsp_analysis",
            label="TSP Data Analysis exe",
            source_globs=["tools/data_analysis_pulse_2450/dist/TSP_Data_Analysis.exe"],
            dest_under_release="Switchbox_GUI/tools_bin/TSP_Data_Analysis.exe",
            required=False,
            optional_reason="Built only when tsp_data_analysis target succeeds",
        ),
        CopyArtifact(
            key="pulse_classic",
            label="Pulse Testing GUI classic",
            source_globs=["dist/Pulse_Testing_GUI"],
            dest_under_release="Pulse_Testing_GUI",
            required=True,
        ),
        CopyArtifact(
            key="pulse_compact",
            label="Pulse Testing GUI compact",
            source_globs=["dist/Pulse_Testing_GUI_Compact"],
            dest_under_release="Pulse_Testing_GUI_Compact",
            required=True,
        ),
        CopyArtifact(
            key="moku_cli",
            label="Moku CLI vendor bundle",
            source_globs=["Equipment/Moku/Moku CLI"],
            dest_under_release="Equipment/Moku/Moku CLI",
            required=False,
            optional_reason="Install Moku CLI locally before build to include (not in git)",
        ),
    ]


def _python_executable() -> str:
    import sys

    return sys.executable


def release_root(repo_root: Path) -> Path:
    return repo_root / "dist" / RELEASE_DIR_NAME
