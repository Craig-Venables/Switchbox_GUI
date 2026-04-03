# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Switchbox_GUI (windowed, onedir).

Repository root should be the current working directory when you run:
    pyinstaller build_exe.spec
or:
    python build_exe.py

Module / data inventory: Documents/build/BUILD_MODULES.md
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

SPECDIR = os.path.dirname(os.path.abspath(SPEC))


def _safe_collect_submodules(package: str) -> list:
    try:
        return collect_submodules(package)
    except Exception:
        return []


# Root-level plotting shims (plotting.sample_plots, etc.) log deprecation on import;
# skip them as hiddenimports — real code uses plotting.sample, plotting.device, etc.
_SKIP_PLOTTING_ROOT_SHIMS = frozenset(
    {"sample_plots", "endurance_plots", "section_plots", "device_combined_plots"}
)


def _modules_from_pkg_path(pkg_name: str, relative_folder: str) -> list:
    """
    List import paths (e.g. analysis.core.sweep_analyzer) by walking .py files.
    Avoids ``import analysis`` at spec time (that package pulls scipy immediately).
    PyInstaller still follows imports inside those files to bundle scipy, etc.
    """
    root = Path(SPECDIR) / relative_folder
    if not root.is_dir():
        return []
    out: list = []
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root)
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if pkg_name == "plotting" and len(parts) == 1 and parts[0] in _SKIP_PLOTTING_ROOT_SHIMS:
            continue
        if not parts:
            out.append(pkg_name)
        else:
            out.append(pkg_name + "." + ".".join(parts))
    return sorted(set(out))


# Prefer import tracing from ``main.py`` for large trees (``Equipment``, ``Pulse_Testing``,
# ``Notifications``) to avoid PyInstaller spending minutes on optional / broken subpackages
# and to reduce edge-case modulegraph failures. Extend this list if runtime misses a submodule.
_pkg_roots = (
    "gui",
    "Measurements",
)

hiddenimports: list = []
# ``collect_submodules`` for gui/measurements can pull in thousands of modules and, on some
# PyInstaller 6.x + Python 3.10 environments, trigger modulegraph ``IndexError`` during bytecode
# scan. Rely on static analysis from ``main.py`` first; re-enable if the frozen app misses code.
# for _pkg in _pkg_roots:
#     hiddenimports.extend(_safe_collect_submodules(_pkg))
#
# Optional: bundle all analysis/plotting modules without ``import analysis`` at spec time:
# hiddenimports.extend(_modules_from_pkg_path("analysis", "analysis"))
# hiddenimports.extend(_modules_from_pkg_path("plotting", "plotting"))

# Lazy importlib / backends (see Documents/build/BUILD_MODULES.md)
hiddenimports += [
    "Equipment.SMU_AND_PMU.4200A.C_Code_with_python_scripts.A_Iv_Sweep.run_smu_vi_sweep",
    "matplotlib.backends.backend_tkagg",
    "PIL._tkinter_finder",
]

datas = [
    (os.path.join(SPECDIR, "Json_Files"), "Json_Files"),
    (os.path.join(SPECDIR, "Documents"), "Documents"),
]

a = Analysis(
    [os.path.join(SPECDIR, "main.py")],
    pathex=[SPECDIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Switchbox_GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Switchbox_GUI",
)
