"""
Switchbox_GUI v6 release build orchestrator.

Prepare and (optionally) run every PyInstaller target, then assemble
``dist/Switchbox_GUI_v6/`` with the main app, companion exes, and Pulse GUIs.

Usage (from repository root)::

    python packaging/build_release_v6.py              # check env + print plan (default)
    python packaging/build_release_v6.py --check        # same as default
    python packaging/build_release_v6.py --build        # run all builds + assemble
    python packaging/build_release_v6.py --assemble-only  # stitch existing dist/ outputs

See packaging/BUILD_RELEASE_V6.md for prerequisites and handover checklist.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = Path(__file__).with_name("release_v6_config.py")
_spec = importlib.util.spec_from_file_location("release_v6_config", _CONFIG_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_CONFIG_PATH}")
_config = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _config
_spec.loader.exec_module(_config)

BuildTarget = _config.BuildTarget
CopyArtifact = _config.CopyArtifact
RELEASE_DIR_NAME = _config.RELEASE_DIR_NAME
RELEASE_VERSION = _config.RELEASE_VERSION
TOP_BAR_BUILD_KEYS = _config.TOP_BAR_BUILD_KEYS
TOP_BAR_ARTIFACT_KEYS = _config.TOP_BAR_ARTIFACT_KEYS
assembly_artifacts = _config.assembly_artifacts
release_root = _config.release_root
repo_targets = _config.repo_targets


def _check_python_version() -> int | None:
    if sys.version_info[:3] == (3, 10, 0):
        print(
            "Error: Python 3.10.0 breaks PyInstaller analysis.\n"
            "Use Python 3.10.11+ or 3.11+, then recreate your venv.\n"
            "Example:\n"
            "  py -3.11 -m venv .venv-build\n"
            "  .venv-build\\Scripts\\pip install -r requirements.txt pyinstaller\n"
            "  .venv-build\\Scripts\\python packaging/build_release_v6.py --build"
        )
        return 1
    return None


def _ensure_pyinstaller(repo_root: Path) -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            cwd=repo_root,
        )


def _check_requirements(repo_root: Path) -> list[str]:
    warnings: list[str] = []
    req = repo_root / "requirements.txt"
    if not req.is_file():
        warnings.append("Missing requirements.txt")
        return warnings

    core = (
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "PIL",
        "cv2",
        "pyvisa",
        "serial",
    )
    for mod in core:
        if importlib.util.find_spec(mod) is None:
            alt = "pillow" if mod == "PIL" else mod
            if mod == "cv2" and importlib.util.find_spec("opencv_python") is None:
                warnings.append(f"Not installed: {mod} (pip install opencv-python)")
            elif importlib.util.find_spec(alt) is None:
                warnings.append(f"Not installed: {mod}")
    if importlib.util.find_spec("PyInstaller") is None:
        warnings.append("PyInstaller not installed (will auto-install on --build)")
    return warnings


def _resolve_source(repo_root: Path, globs: Iterable[str]) -> Path | None:
    for pattern in globs:
        path = repo_root / pattern
        if path.exists():
            return path
    return None


def _print_plan(targets: list[BuildTarget], artifacts: list[CopyArtifact]) -> None:
    print("\n=== v6 build targets ===")
    for t in targets:
        req = "required" if t.required else f"optional - {t.optional_reason}"
        print(f"  [{t.key}] {t.label} ({req})")
        print(f"       -> {' | '.join(t.output_paths)}")
    print(f"\n=== Assembly -> dist/{RELEASE_DIR_NAME}/ ===")
    for a in artifacts:
        req = "required" if a.required else f"optional - {a.optional_reason}"
        print(f"  [{a.key}] {a.label} ({req})")
        print(f"       {a.source_globs[0]} -> {a.dest_under_release}")


def _run_target(repo_root: Path, target: BuildTarget) -> bool:
    print(f"\n{'=' * 60}\nBuilding: {target.label}\n{'=' * 60}")
    try:
        subprocess.check_call(target.command, cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        print(f"FAILED [{target.key}]: exit {exc.returncode}")
        return False
    missing = [p for p in target.output_paths if not (repo_root / p).exists()]
    if missing:
        print(f"FAILED [{target.key}]: expected outputs missing:")
        for p in missing:
            print(f"  - {p}")
        return False
    print(f"OK [{target.key}]")
    return True


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _assemble(
    repo_root: Path,
    *,
    skip_optional: bool,
    artifacts: list | None = None,
) -> int:
    out_root = release_root(repo_root)
    if out_root.exists():
        print(f"Removing previous {out_root}")
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    errors: list[str] = []
    skipped: list[str] = []

    for artifact in artifacts or assembly_artifacts():
        src = _resolve_source(repo_root, artifact.source_globs)
        if src is None:
            if artifact.required and not skip_optional:
                errors.append(f"Missing required artifact: {artifact.label} ({artifact.source_globs})")
            else:
                skipped.append(f"{artifact.label} (not built)")
            continue

        dest = out_root / artifact.dest_under_release
        print(f"Copy: {src} -> {dest}")
        _copy_tree(src, dest)

    readme = out_root / "README_RELEASE.txt"
    readme.write_text(
        "\n".join(
            [
                f"Switchbox_GUI v{RELEASE_VERSION} release package",
                "=" * (32 + len(RELEASE_VERSION)),
                "",
                "Run the main application:",
                "  Switchbox_GUI\\Switchbox_GUI.exe",
                "",
                "Bundled tool exes (Hardware Tools menu + script runner):",
                "  Switchbox_GUI\\tools_bin\\",
                "",
                "Standalone Pulse Testing GUIs:",
                "  Pulse_Testing_GUI\\Pulse_Testing_GUI.exe",
                "  Pulse_Testing_GUI_Compact\\Pulse_Testing_GUI_Compact.exe",
                "",
                f"Distribute this entire folder (zip {RELEASE_DIR_NAME}).",
                "",
                f"Skipped optional copies: {', '.join(skipped) if skipped else 'none'}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"\nAssembly complete: {out_root}")
    if skipped:
        print("Skipped optional:")
        for line in skipped:
            print(f"  - {line}")
    if errors:
        print("\nAssembly errors:")
        for line in errors:
            print(f"  - {line}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Prepare / build Switchbox_GUI v6 release")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate environment and print build plan (default if no action flags)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Run all PyInstaller targets, then assemble dist/Switchbox_GUI_v6/",
    )
    parser.add_argument(
        "--assemble-only",
        action="store_true",
        help="Only assemble dist/Switchbox_GUI_v6/ from existing build outputs",
    )
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help="Do not fail when optional targets/artifacts are missing",
    )
    parser.add_argument(
        "--main-only",
        action="store_true",
        help="Build main app + ScriptRunner + Display/LED tools (top-bar + Hardware Tools)",
    )
    args = parser.parse_args(argv)

    if not args.build and not args.assemble_only:
        args.check = True

    err = _check_python_version()
    if err:
        return err

    targets = repo_targets(repo_root)
    if args.main_only:
        targets = [t for t in targets if t.key in TOP_BAR_BUILD_KEYS]
    elif args.skip_optional:
        targets = [t for t in targets if t.required]

    artifacts = assembly_artifacts()
    if args.main_only:
        artifacts = [a for a in artifacts if a.key in TOP_BAR_ARTIFACT_KEYS]

    print(f"Repository: {repo_root}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    warnings = _check_requirements(repo_root)
    if warnings:
        print("\nEnvironment notes:")
        for w in warnings:
            print(f"  - {w}")

    _print_plan(targets, artifacts)

    if args.check and not args.build and not args.assemble_only:
        print(
            "\nReady to build. When satisfied, run:\n"
            "  python packaging/build_release_v6.py --build\n"
            "Optional extras (camera, TSP analysis) need their deps; use --skip-optional to omit."
        )
        return 0

    if args.build:
        _ensure_pyinstaller(repo_root)
        failed: list[str] = []
        for target in targets:
            ok = _run_target(repo_root, target)
            if not ok:
                if target.required:
                    failed.append(target.key)
                elif not args.skip_optional:
                    failed.append(target.key)
        if failed:
            print(f"\nBuild stopped — failed targets: {', '.join(failed)}")
            return 1

    return _assemble(
        repo_root,
        skip_optional=args.skip_optional or args.main_only,
        artifacts=artifacts if args.main_only else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
