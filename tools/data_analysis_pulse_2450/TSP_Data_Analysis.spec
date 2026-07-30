# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for TSP / pulse data analysis tool (windowed, onefile).

Build from repository root::

    python tools/data_analysis_pulse_2450/build_exe.py

Requires PyQt6 in the build environment (see tools/data_analysis_pulse_2450/requirements.txt).
"""
import os

block_cipher = None

TOOL_ROOT = os.path.dirname(os.path.abspath(SPEC))
REPO_ROOT = os.path.dirname(os.path.dirname(TOOL_ROOT))

datas = [
    (os.path.join(TOOL_ROOT, "resources"), "resources"),
    (os.path.join(TOOL_ROOT, "settings.json"), "."),
]

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "matplotlib.backends.backend_qtagg",
    "numpy",
    "pandas",
]

a = Analysis(
    [os.path.join(TOOL_ROOT, "main.py")],
    pathex=[REPO_ROOT, TOOL_ROOT],
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
    a.binaries,
    a.datas,
    [],
    name="TSP_Data_Analysis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
