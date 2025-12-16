# Classification Validation & Refinement Tool

A comprehensive tool for testing, validating, and refining the memristivity scoring and classification system using your own data.

## Overview

This tool allows you to:
- **Batch process** raw IV curve files (.txt format)
- **Manually label** devices with ground truth (memristive/ohmic/capacitive/conductive)
- **Compare** predictions vs labels to see accuracy
- **Adjust scoring weights** (pinched hysteresis, switching behavior, etc.)
- **Tune thresholds** (memristive minimum score, etc.)
- **See real-time impact** of parameter changes on accuracy
- **Generate metrics** (accuracy, confusion matrix, per-class statistics)

## Quick Start

### Launch the Tool

```bash
python Helpers/Classification_Validation/run_validation_tool.py
```

Or from Python:
```python
from Helpers.Classification_Validation.gui.main_window import ValidationToolGUI
app = ValidationToolGUI()
app.run()
```

## Usage Workflow

### 1. Load Data

1. Open the **"Load Data"** tab
2. Click **"Browse..."** and select a directory containing IV .txt files
3. Choose options:
   - Scan subdirectories (recommended: Yes)
   - File pattern (default: `*.txt`)
4. Click **"Process Files"**
5. Wait for processing to complete

### 2. Review & Label

1. Go to the **"Review & Label"** tab
2. Use the filter dropdown to view:
   - All devices
   - Unlabeled devices (start here!)
   - Labeled devices
   - Devices by predicted type
3. Click a device in the list to see:
   - IV curve plot
   - Prediction details
   - Score breakdown
4. Set the ground truth label using the dropdown:
   - memristive
   - ohmic
   - capacitive
   - conductive
5. Click **"Save Label"**
6. Repeat for all devices you want to label

### 3. Check Metrics

1. Go to the **"Metrics"** tab
2. Click **"Refresh Metrics"** to see:
   - Overall accuracy
   - Per-class precision/recall/F1
   - Confusion matrix
   - Score distribution plots
   - Threshold optimization suggestions

### 4. Tune Parameters

1. Go to the **"Tune Parameters"** tab
2. Adjust scoring weights using sliders:
   - Pinched Hysteresis (default: 30)
   - Hysteresis Quality (default: 20)
   - Switching Behavior (default: 20)
   - Memory Window Quality (default: 15)
   - Nonlinearity (default: 10)
   - Polarity Dependence (default: 5)
3. Adjust thresholds:
   - Memristive Minimum Score (default: 60)
   - High Confidence Minimum (default: 70)
4. Click **"Apply Changes"** to recalculate all predictions
5. Check the **"Metrics"** tab to see if accuracy improved
6. Click **"Save Configuration"** to persist your tuned parameters

### 5. Export Results

Use the validator programmatically to export:

```python
from Helpers.Classification_Validation import ClassificationValidator

validator = ClassificationValidator()
validator.load_data("path/to/iv/files")
# ... label devices, tune parameters ...

# Export to JSON
validator.export_results("results.json", format='json')

# Export to CSV
validator.export_results("results.csv", format='csv')
```

## File Structure

```
Helpers/Classification_Validation/
├── __init__.py
├── validation_tool.py          # Main orchestrator
├── batch_processor.py          # Batch analysis of IV files
├── label_manager.py            # Ground truth label storage
├── parameter_tuner.py          # Weight/threshold adjustment
├── metrics_calculator.py       # Accuracy metrics
├── run_validation_tool.py     # Main entry point
├── gui/
│   ├── __init__.py
│   ├── main_window.py         # Main GUI window
│   ├── file_browser.py        # File selection interface
│   ├── review_panel.py        # Review predictions and label
│   ├── tuning_panel.py        # Adjust weights/thresholds
│   └── metrics_panel.py       # View statistics
└── data/
    ├── labels.json             # Ground truth labels (auto-created)
    └── config.json             # Current weights/thresholds (auto-created)
```

## Data Format

### Input Files

IV data files should be .txt format with columns:
- Column 1: Voltage (V)
- Column 2: Current (A)
- Column 3: Time (s) - optional

Example:
```
Voltage Current Time
0.0     1e-9    0.0
0.1     2e-9    0.1
...
```

### Labels File (`data/labels.json`)

```json
{
  "test_sample_A_1": "memristive",
  "test_sample_A_2": "ohmic",
  "test_sample_B_1": "memristive"
}
```

### Configuration File (`data/config.json`)

```json
{
  "weights": {
    "pinched_hysteresis": 30.0,
    "hysteresis_quality": 20.0,
    "switching_behavior": 20.0,
    "memory_window": 15.0,
    "nonlinearity": 10.0,
    "polarity_dependence": 5.0
  },
  "thresholds": {
    "memristive_min_score": 60.0,
    "high_confidence_min": 70.0
  }
}
```

## Programmatic Usage

You can also use the tool programmatically without the GUI:

```python
from Helpers.Classification_Validation import ClassificationValidator

# Initialize
validator = ClassificationValidator()

# Load and process files
validator.load_data("path/to/iv/files", recursive=True)

# Label devices
validator.label_manager.set_label("device_A_1", "memristive")
validator.label_manager.save()

# Adjust weights
validator.update_parameters(
    weights={'pinched_hysteresis': 35.0, 'switching_behavior': 25.0}
)

# Get metrics
metrics = validator.get_metrics()
print(f"Accuracy: {metrics['accuracy']['accuracy_percent']:.1f}%")

# Export results
validator.export_results("validation_results.json")
```

## Tips for Refinement

1. **Start with a small dataset**: Label 20-30 devices first to get initial metrics
2. **Focus on misclassified devices**: Look at confusion matrix to see where errors occur
3. **Adjust weights incrementally**: Change one weight at a time to see its impact
4. **Use threshold optimization**: The tool suggests optimal thresholds based on your data
5. **Check score distributions**: See if correct/incorrect predictions have different score ranges
6. **Save configurations**: Save different configurations for different device types

## Integration with Main System

Once you've refined the weights and thresholds:

1. The configuration is saved in `data/config.json`
2. You can load it in your main analysis:

```python
from Helpers.Classification_Validation.parameter_tuner import ParameterTuner

tuner = ParameterTuner()
weights = tuner.get_weights()
thresholds = tuner.get_thresholds()

# Use in your analysis
from Helpers.IV_Analysis import quick_analyze
results = quick_analyze(voltage, current, custom_weights=weights)
```

## Troubleshooting

**"No files found"**: Check that your directory contains .txt files and the pattern matches

**"Analysis failed"**: Check that IV files have correct format (voltage, current columns)

**"No labels available"**: Go to Review tab and label some devices first

**GUI doesn't start**: Make sure tkinter is installed: `pip install tk`

## Requirements

- Python 3.7+
- tkinter (usually included with Python)
- numpy
- matplotlib
- pandas (for CSV export)
- seaborn (optional, for better confusion matrix plots)

All dependencies should already be in your requirements.txt.
