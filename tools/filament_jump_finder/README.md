# Filament Jump Finder

PyQt5 tool to detect large current jumps in IV sweep data — useful for spotting filament formation events across a sample.

## Run

```powershell
# From repo root
python -m tools.filament_jump_finder

# Open a sample folder on startup
python -m tools.filament_jump_finder --sample "C:\path\to\sample"
```

## Features

- Load a sample folder via `device_visualizer` data loader
- Adjustable jump threshold and filtering
- Tables for first occurrence and all occurrences
- Matplotlib plots and CSV export
- Inspect-jumps dialog for per-device detail

## Dependencies

PyQt5, matplotlib, numpy — same stack as `tools/device_visualizer/`.
