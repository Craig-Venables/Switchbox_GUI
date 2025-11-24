# Building Your Executable - Simple Explanation

## What is the spec file?

The `build_exe.spec` file is **just a configuration file** - it tells PyInstaller how to build your exe. It does NOT get included in the final executable. Think of it like a recipe - you use it to cook, but you don't eat the recipe!

## What Will Be Included?

✅ **Included in the exe:**
- All your Python code (except Helpers folder)
- All dependencies (matplotlib, numpy, etc.)
- Equipment drivers and managers
- GUI code

✅ **Included as external files (editable):**
- `Json_Files/` folder - You can edit these JSON files after building
- `Documents/` folder - Documentation files

❌ **NOT included:**
- `Helpers/` folder - Completely excluded
- `Equipment/Moku/` folder - Excluded (work in progress)
- Test files
- The spec file itself

## How to Build

1. **Install PyInstaller:**
   ```bash
   pip install pyinstaller
   ```

2. **Build the exe:**
   ```bash
   python build_exe.py
   ```

3. **Find your exe:**
   - Location: `dist/Switchbox_GUI/Switchbox_GUI.exe`
   - Next to it you'll find:
     - `Json_Files/` folder (editable!)
     - `Documents/` folder

## After Building

The `dist/Switchbox_GUI/` folder will contain:
```
Switchbox_GUI/
├── Switchbox_GUI.exe          ← Your executable
├── Json_Files/                 ← Editable JSON configs
│   ├── mapping.json
│   ├── system_configs.json
│   └── ... (all your JSONs)
├── Documents/                  ← Documentation
│   ├── README.md
│   └── ... (all your docs)
└── [other files needed to run]
```

**You can edit the JSON files directly** - they're not bundled inside the exe, so changes take effect immediately!

## Distribution

To give your exe to someone else:
1. Zip the entire `dist/Switchbox_GUI/` folder
2. They extract it and run `Switchbox_GUI.exe`
3. They can edit JSON files as needed

