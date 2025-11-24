# Building Switchbox_GUI Executable

This guide explains how to build a standalone executable from the Switchbox_GUI project.

## Quick Start

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable:**
   ```bash
   python build_exe.py
   ```
   
   Or directly:
   ```bash
   pyinstaller build_exe.spec
   ```

3. **Find your executable:**
   - Location: `dist/Switchbox_GUI/Switchbox_GUI.exe`
   - The entire `dist/Switchbox_GUI` folder contains everything needed to run the app

## Why PyInstaller Instead of auto-py-to-exe?

**auto-py-to-exe** is a GUI wrapper around PyInstaller that's great for simple projects, but for this complex project with:
- Hardware dependencies (DLLs, C code)
- Multiple entry points
- JSON configuration files
- Complex import structure

**Direct PyInstaller** gives you:
- ✅ Better control over what gets included
- ✅ Scriptable/automated builds
- ✅ Version control friendly (spec file)
- ✅ Easier debugging when things go wrong
- ✅ More reliable for complex projects

## Customization

### Adding Files to the Executable

Edit `build_exe.spec` and add to the `datas` list:
```python
datas = [
    ('path/to/file', 'destination/in/exe'),
]
```

### Adding Hidden Imports

If you get "ModuleNotFoundError" at runtime, add the module to `hiddenimports` in `build_exe.spec`:
```python
hiddenimports = [
    'your_missing_module',
]
```

### Including DLLs

If you need specific DLLs, add them to `binaries`:
```python
binaries = [
    ('path/to/library.dll', '.'),
]
```

### Adding an Icon

1. Create or obtain a `.ico` file
2. In `build_exe.spec`, set:
   ```python
   icon='path/to/your/icon.ico',
   ```

## Troubleshooting

### "ModuleNotFoundError" at Runtime

1. Add the missing module to `hiddenimports` in `build_exe.spec`
2. Rebuild: `python build_exe.py`

### Executable is Too Large

1. Add unnecessary modules to `excludes` in `build_exe.spec`
2. Consider using `--onefile` vs `--onedir` (current setup uses `--onedir` for better compatibility)

### DLL Errors

1. Ensure all required DLLs are included in `binaries` or `datas`
2. Check that DLLs match your Python architecture (32-bit vs 64-bit)

### JSON Config Files Not Found

1. Verify `Json_Files` is in the `datas` list
2. Check that your code uses relative paths to find config files

## Testing the Executable

1. **Test on the build machine first:**
   ```bash
   dist/Switchbox_GUI/Switchbox_GUI.exe
   ```

2. **Test on a clean machine:**
   - Copy the entire `dist/Switchbox_GUI` folder to a machine without Python
   - Run the executable
   - This verifies all dependencies are included

## Distribution

To distribute your application:
1. Build the executable
2. Zip or package the entire `dist/Switchbox_GUI` folder
3. Users can extract and run `Switchbox_GUI.exe` directly

**Note:** The executable is platform-specific. Build on Windows to create a Windows executable.

## Advanced: One-File Executable

If you prefer a single `.exe` file instead of a folder, modify `build_exe.spec`:

Change the `EXE` section to:
```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Switchbox_GUI',
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
    name='Switchbox_GUI',
)
```

Then change the last line to return `coll` instead of `exe`.

