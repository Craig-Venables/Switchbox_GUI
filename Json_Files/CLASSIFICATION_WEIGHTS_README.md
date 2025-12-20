# Classification Weights Configuration

## Overview
The device classification system uses weighted scoring to determine device types (memristive, capacitive, memcapacitive, conductive, ohmic).

## Configuration File
Location: `Json_Files/classification_weights.json`

## How to Adjust Weights

1. Open `Json_Files/classification_weights.json`
2. Modify the weight values in the `"weights"` section
3. Save the file
4. Restart your application or re-run analysis

## Weight Categories

### Memristive Weights
- `memristive_has_hysteresis`: Score for hysteresis presence (default: 25.0)
- `memristive_pinched_hysteresis`: Score for pinched loop at origin (default: 30.0)
- `memristive_switching_behavior`: Score for switching/memory effect (default: 25.0)
- `memristive_nonlinear_iv`: Score for non-linear I-V (default: 10.0)
- `memristive_polarity_dependent`: Score for polarity dependence (default: 10.0)
- `memristive_penalty_linear_iv`: Penalty if linear I-V detected (default: -20.0)
- `memristive_penalty_ohmic`: Penalty if ohmic behavior detected (default: -30.0)

### Capacitive Weights
- `capacitive_hysteresis_unpinched`: Score for unpinched hysteresis loop (default: 40.0)
- `capacitive_phase_shift`: Score for phase shift >45° (default: 40.0)
- `capacitive_elliptical`: Score for elliptical hysteresis pattern (default: 20.0)

### Memcapacitive Weights
- `memcapacitive_hysteresis_unpinched`: Score for unpinched hysteresis (default: 40.0)
- `memcapacitive_switching_behavior`: Score for switching behavior (default: 30.0)
- `memcapacitive_nonlinear_iv`: Score for non-linearity (default: 20.0)
- `memcapacitive_phase_shift`: Score for phase shift >30° (default: 20.0)
- `memcapacitive_penalty_pinched`: Penalty if pinched loop (default: -20.0)

### Conductive Weights  
(Non-linear, non-ohmic, without hysteresis/switching)
- `conductive_no_hysteresis`: Score for no hysteresis (default: 30.0)
- `conductive_nonlinear_no_switching`: Score for non-linear without switching (default: 40.0)
- `conductive_advanced_mechanism`: Score for advanced conduction models (SCLC, etc.) (default: 30.0)

### Ohmic Weights
- `ohmic_linear_clean`: Score for clean linear I-V (default: 60.0)
- `ohmic_model_fit`: Score for good ohmic model fit (default: 20.0)

## Classification Thresholds
- **Minimum score for classification**: 30 points
- **Total score of 0**: Results in "uncertain" classification
- **Confidence**: Max score / 100

## Tips for Tuning

1. **Increase specificity**: Raise weights for key distinguishing features
2. **Reduce false positives**: Increase penalty weights (make more negative)
3. **Balance classes**: Ensure similar total possible scores across device types
4. **Test changes**: Use the validation tool to see how weight changes affect classification

## Example Adjustments

### Make memristive classification stricter:
```json
"memristive_pinched_hysteresis": 40.0,  // was 30.0
"memristive_penalty_ohmic": -40.0       // was -30.0
```

### Favor capacitive over memcapacitive:
```json
"capacitive_phase_shift": 50.0,           // was 40.0  
"memcapacitive_penalty_pinched": -30.0    // was -20.0
```

## Fallback Behavior
If the JSON file cannot be loaded, the system will use hardcoded default weights and print a warning message.
