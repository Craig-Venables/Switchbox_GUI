# IV Analysis Module

Fast and comprehensive analysis tools for IV sweep measurements with optional LLM-powered insights.

## Quick Start - After a Sweep (Simplest!)

**Just pass your voltage and current arrays - that's it!**

```python
from Helpers.IV_Analysis import quick_analyze

# Your sweep returns voltage and current arrays
voltages, currents = run_your_sweep()

# One line - get all analysis results
results = quick_analyze(voltages, currents)

# Access results
print(results['classification']['device_type'])
print(results['resistance_metrics']['switching_ratio_mean'])
print(results['resistance_metrics']['ron_mean'])
```

**With metadata (LED state, temperature, etc.):**
```python
results = quick_analyze(
    voltages, currents,
    metadata={'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
)
```

### Alternative: From File

```python
from Helpers.IV_Analysis import analyze_sweep

# One-line analysis - get all data back
data = analyze_sweep(file_path="sweep.txt")

print(data['classification']['device_type'])
print(data['resistance_metrics']['switching_ratio_mean'])
```

### With Metadata

```python
from Helpers.IV_Analysis import IVSweepAnalyzer

analyzer = IVSweepAnalyzer(analysis_level='full')

metadata = {
    'led_on': True,
    'led_type': 'UV',
    'led_wavelength': 365,
    'temperature': 25.0
}

data = analyzer.analyze_sweep(
    file_path="sweep.txt",
    metadata=metadata
)
```

### With LLM Insights (Optional, Slower)

```python
from Helpers.IV_Analysis import IVSweepLLMAnalyzer

# Initialize with LLM backend
analyzer = IVSweepLLMAnalyzer(
    analysis_level='full',
    llm_backend='ollama',
    llm_model='llama2'
)

# Extract data (fast)
data = analyzer.analyze_sweep(file_path="sweep.txt")

# Get LLM insights (slower, optional)
insights = analyzer.get_llm_insights()
print(insights)
```

## Architecture

The module is split into two classes:

1. **IVSweepAnalyzer** - Fast data extraction (always use this first)
2. **IVSweepLLMAnalyzer** - Extends IVSweepAnalyzer with LLM insights (optional)

This design allows you to:
- Extract data quickly without LLM overhead
- Add LLM insights only when needed
- Reuse extracted data for multiple LLM queries

## Key Features

- **Fast Data Extraction**: Extract all metrics without LLM processing
- **Flexible Input**: Accept file paths OR direct voltage/current data
- **Metadata Support**: Include LED state, temperature, humidity, etc.
- **Multiple Measurement Types**: IV sweeps, pulse, endurance, retention
- **Optional LLM Insights**: Add natural language analysis when needed
- **Comprehensive Metrics**: All metrics from analyze_single_file

## Analysis Levels Explained

The `analysis_level` parameter controls how much detail is extracted. Choose based on your needs:

### `'basic'` - Fast Core Metrics
**Speed**: Fastest (~1-2 seconds)  
**Use when**: You just need basic resistance values quickly

**Provides**:
- **Resistance Metrics**: Ron, Roff (mean and std)
- **Voltage Metrics**: Von, Voff, voltage ranges
- **Hysteresis Metrics**: Normalized area, total area, has hysteresis
- **Basic Performance**: Retention score, endurance score
- **Summary Statistics**: Basic statistical summaries

**Missing**: Device classification, conduction mechanisms, advanced diagnostics

---

### `'classification'` - Device Type Identification
**Speed**: Fast (~2-3 seconds)  
**Use when**: You need to know what type of device it is

**Provides**: Everything from `'basic'` PLUS:
- **Device Classification**: Device type (memristive, capacitive, conductive, ohmic)
- **Classification Confidence**: How confident the classification is (0-1)
- **Classification Features**: Key features used for classification
- **Classification Explanation**: Why it was classified this way

**Missing**: Conduction mechanism models, advanced diagnostics

---

### `'full'` - Comprehensive Analysis (Recommended)
**Speed**: Moderate (~3-5 seconds)  
**Use when**: You want complete analysis for most use cases (default)

**Provides**: Everything from `'classification'` PLUS:
- **Conduction Mechanism**: Identified mechanism (Ohmic, Schottky, Poole-Frenkel, etc.)
- **Model Fit Quality**: R² value for conduction model fitting
- **Advanced Performance Metrics**:
  - Rectification ratio
  - Nonlinearity factor
  - Asymmetry factor
  - Power consumption
  - Energy per switch
  - Compliance current
- **Window Margin**: Resistance window stability
- **Detailed Performance**: Additional performance metrics
- **Validation Results**: Memristor behavior validation checks

**Missing**: Research-level diagnostics

---

### `'research'` - Maximum Detail
**Speed**: Slower (~5-10 seconds)  
**Use when**: You need every possible metric for research/publication

**Provides**: Everything from `'full'` PLUS:
- **Research Diagnostics**:
  - Switching polarity (bipolar/unipolar)
  - NDR (Negative Differential Resistance) index
  - Hysteresis direction
  - Kink voltage (if present)
  - Loop similarity score
  - Pinch offset
  - Noise floor
- **Advanced Degradation Metrics**: (for endurance/retention)
  - Degradation rates
  - Lifetime projections
  - Decay analysis

---

## Quick Comparison Table

| Feature | basic | classification | full | research |
|---------|-------|----------------|------|----------|
| Ron, Roff | ✅ | ✅ | ✅ | ✅ |
| Device Type | ❌ | ✅ | ✅ | ✅ |
| Conduction Mechanism | ❌ | ❌ | ✅ | ✅ |
| Performance Metrics | Basic | Basic | Full | Full |
| Research Diagnostics | ❌ | ❌ | ❌ | ✅ |
| Speed | Fastest | Fast | Moderate | Slower |

## Recommendation

- **Most use cases**: Use `'full'` (default) - best balance of speed and detail
- **Quick checks**: Use `'basic'` for fastest results
- **Research/publication**: Use `'research'` for maximum detail
- **Batch processing**: Use `'classification'` or `'basic'` for speed

## Performance

- **Data Extraction**: Fast (~seconds for typical sweeps)
  - `basic`: ~1-2 seconds
  - `classification`: ~2-3 seconds
  - `full`: ~3-5 seconds
  - `research`: ~5-10 seconds
- **LLM Analysis**: Slower (depends on model size, ~10-60 seconds)

**Recommendation**: Always extract data first, then optionally get LLM insights.

## Examples

See `example_usage.py` for complete examples.

