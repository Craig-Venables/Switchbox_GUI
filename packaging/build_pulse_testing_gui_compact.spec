# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Pulse Testing GUI — compact layout (windowed, onedir).

Build from repository root::

    python packaging/build_pulse_testing_gui.py --compact

Output::

    dist/Pulse_Testing_GUI_Compact/Pulse_Testing_GUI_Compact.exe
"""
import os

block_cipher = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

hiddenimports = [
    "matplotlib.backends.backend_tkagg",
    "PIL._tkinter_finder",
    "pyvisa",
    "pyvisa_py",
    "serial",
    "serial.tools.list_ports",
    "serial.tools.list_ports_common",
    "gui.pulse_testing_gui.ui.layout_classic",
    "gui.pulse_testing_gui.ui.layout_compact",
    "gui.pulse_testing_gui.ui.connection_compact",
    "gui.pulse_testing_gui.ui.manual_test_sections",
    "gui.sample_gui.config",
]

datas = [
    (os.path.join(REPO_ROOT, "Json_Files"), "Json_Files"),
]

a = Analysis(
    [os.path.join(REPO_ROOT, "Pulse_Testing_GUI_compact.py")],
    pathex=[REPO_ROOT],
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
    name="Pulse_Testing_GUI_Compact",
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
    name="Pulse_Testing_GUI_Compact",
)
