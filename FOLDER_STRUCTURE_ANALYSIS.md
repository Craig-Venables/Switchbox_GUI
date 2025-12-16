# Folder Structure Analysis & Simplification Proposal

## Current Structure (Too Complex)

```
Data_folder/
└── SampleName/
    ├── A/                          # Section folders
    │   ├── 1/                      # Device folders
    │   │   ├── *.txt               # Raw measurement files
    │   │   ├── sweep_analysis/     # Per-sweep analysis text files
    │   │   └── All_graphs_*.png    # Device-level graphs
    │   └── 2/
    │       └── ...
    ├── B/
    │   └── ...
    ├── device_tracking/             # ❌ Separate folder
    │   ├── Sample_A_1_history.json
    │   └── Sample_A_2_history.json
    ├── device_research/             # ❌ Separate folder (only for memristive)
    │   ├── Sample_A_1/
    │   │   └── *_research.json
    │   └── Sample_A_2/
    ├── device_summaries/            # ❌ Separate folder (now in sample_analysis/)
    │   └── Sample_A_1_*_summary.txt/json
    ├── sample_analysis/             # ✅ Good - unified output
    │   ├── plots/
    │   ├── origin_data/
    │   └── device_summaries/
    └── graphs/                      # ❌ Section/sample graphs (from data_saver)
        └── ...
```

## Problems

1. **Too many top-level folders**: `device_tracking`, `device_research`, `device_summaries`, `sample_analysis`, `graphs`
2. **Redundant data**: Tracking and research data could be combined
3. **Hard to find**: Data scattered across multiple locations
4. **Inconsistent**: Some data at sample level, some at device level

## Proposed Simplified Structure

```
Data_folder/
└── SampleName/
    ├── A/                          # Section folders (keep for raw data)
    │   ├── 1/                      # Device folders
    │   │   └── *.txt               # Raw measurement files only
    │   └── 2/
    │       └── ...
    ├── B/
    │   └── ...
    └── analysis/                    # ✅ SINGLE unified analysis folder
        ├── sweeps/                  # Per-sweep analysis files
        │   ├── Sample_A_1/           # Organized by device
        │   │   ├── 1-FS-2v-..._analysis.txt
        │   │   └── 2-FS-3v-..._analysis.txt
        │   └── Sample_A_2/
        │       └── ...
        ├── devices/                 # All device-level analysis
        │   ├── Sample_A_1.json      # Combined: tracking + research + summaries
        │   └── Sample_A_2.json
        ├── plots/                   # Sample-level plots
        │   ├── overall/             # Overall sample plots
        │   └── {code_name}/         # Code-specific plots
        ├── origin_data/             # Origin export files
        │   ├── overall/
        │   └── {code_name}/
        └── README.txt               # Structure documentation
```

## Consolidation Plan

### Option 1: Fully Unified (Recommended)
- **Single `analysis/` folder** at sample level
- **`sweeps/` subfolder** with per-sweep analysis files organized by device
- **`devices/` subfolder** with one JSON per device containing:
  - Tracking history (all measurements)
  - Research data (if memristive)
  - Sequence summaries (embedded or referenced)
- **`plots/` subfolder** for all sample-level plots
- **`origin_data/` subfolder** for CSV exports

### Option 2: Minimal Change (Easier Migration)
- Keep `device_tracking/` but merge `device_research/` into it
- Move `device_summaries/` into `sample_analysis/` (already done)
- Remove separate `graphs/` folder, use `sample_analysis/plots/`

## Benefits

1. **Easier navigation**: One `analysis/` folder instead of 4-5 folders
2. **Better organization**: All analysis data in one place
3. **Easier backup**: Single folder to backup for analysis data
4. **Clearer structure**: Raw data (device folders) vs analysis (analysis folder)
5. **Less duplication**: Combined JSON files instead of separate tracking/research

## Migration Strategy

1. **Phase 1**: Update save methods to use new structure
2. **Phase 2**: Create migration script to consolidate existing data
3. **Phase 3**: Update all read methods to use new structure
4. **Phase 4**: Remove old folder creation code

## Implementation Details

### Combined Device JSON Structure
```json
{
  "device_id": "Sample_A_1",
  "created": "2024-01-01T00:00:00",
  "updated": "2024-01-15T12:00:00",
  "measurements": [
    {
      "timestamp": "...",
      "classification": {...},
      "resistance": {...},
      "analysis_level": "classification"
    }
  ],
  "research_data": {
    "measurement_1": {...},
    "measurement_2": {...}
  },
  "sequence_summaries": {
    "Sdt_V2": {...},
    "Forming_Protocol": {...}
  }
}
```

### File Locations
- **Raw data**: `{sample}/{section}/{device}/*.txt` (unchanged)
- **Per-sweep analysis**: `{sample}/analysis/sweeps/{device_id}/*_analysis.txt` (MOVED from device folder)
- **Device tracking**: `{sample}/analysis/devices/{device_id}.json` (NEW)
- **Sample plots**: `{sample}/analysis/plots/` (NEW)
- **Origin data**: `{sample}/analysis/origin_data/` (NEW)
