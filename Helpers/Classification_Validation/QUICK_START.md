# Quick Start Guide

## Launch the Tool

```bash
python Helpers/Classification_Validation/run_validation_tool.py
```

## Basic Workflow

1. **Load Data Tab**
   - Browse to directory with IV .txt files
   - Click "Process Files"
   - Wait for processing

2. **Review & Label Tab**
   - Filter to "unlabeled"
   - Click each device
   - Set ground truth label (memristive/ohmic/capacitive/conductive)
   - Click "Save Label"
   - Repeat for all devices

3. **Metrics Tab**
   - Click "Refresh Metrics"
   - See accuracy, confusion matrix, score distributions

4. **Tune Parameters Tab**
   - Adjust weight sliders
   - Click "Apply Changes"
   - Check Metrics tab to see if accuracy improved
   - Click "Save Configuration" when satisfied

## Key Features

- **Real-time weight adjustment**: Change weights → see accuracy change immediately
- **Threshold optimization**: Tool suggests optimal thresholds based on your data
- **Score distribution analysis**: See where correct/incorrect predictions fall
- **Confusion matrix**: Visualize classification errors
- **Export results**: Save predictions, labels, and metrics to JSON/CSV

## Tips

- Start with 20-30 labeled devices to get initial metrics
- Adjust one weight at a time to understand its impact
- Use threshold optimization to find best cutoff for your data
- Save configurations for different device types
