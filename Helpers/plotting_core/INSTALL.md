# Installation Guide

## Quick Start

### Option 1: Install as Package (Recommended)

```bash
cd plotting_core
pip install -e .
```

Then use in your code:
```python
from plotting_core import UnifiedPlotter
plotter = UnifiedPlotter(save_dir="output/plots")
plotter.plot_all(voltage, current, device_name="Device_1")
```

### Option 2: Copy Folder Directly

Simply copy the `plotting_core` folder to your project and add to path:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("path/to/plotting_core").parent))

from plotting_core import UnifiedPlotter
```

### Option 3: Use from Repository

If running examples from within the repository:

```bash
cd plotting_core/examples
python basic_usage.py
```

## Requirements

Install dependencies:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install matplotlib numpy pandas seaborn
```

## Testing Installation

Run the basic example:
```bash
python examples/basic_usage.py
```

This should generate plots in `output/plots/` directory.

