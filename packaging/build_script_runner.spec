# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Switchbox_ScriptRunner (console, onefile).

Runs bundled ``.py`` tools via ``runpy`` when the main GUI is frozen.
Build as part of the v6 release: ``python packaging/build_release_v6.py --build``.
"""
import os

block_cipher = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

a = Analysis(
    [os.path.join(REPO_ROOT, "packaging", "script_runner.py")],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        "matplotlib.backends.backend_tkagg",
        "PIL._tkinter_finder",
        "runpy",
    ],
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
    name="Switchbox_ScriptRunner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
