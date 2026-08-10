"""
analysis.aux — Pulse + Solartron analysis parallel to IV.

Folder conventions
------------------
{sample}/{section}/{device}/Pulse_measurements/*.txt
{sample}/{section}/{device}/Solartron_1260/<run>/origin_data/*.csv

Outputs (beside source)
-----------------------
Pulse_measurements/analysis/{metrics.csv, files_summary.json, llm_brief.md, plots/}
Solartron_1260/analysis/{spectra_metrics.csv, runs_summary.json, llm_brief.md, plots/}
sample_analysis/aux_index.json  (when running sample-wide)

Python
------
from analysis.aux import analyze_sample_aux, analyze_pulse_folder
result = analyze_sample_aux(r"C:\\...\\D114")
print(result["brief"])

CLI
---
python -m analysis.aux.cli --sample "C:\\...\\D114"
"""
