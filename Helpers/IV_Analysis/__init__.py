"""
IV Analysis Module
==================

This module provides comprehensive analysis tools for IV sweep data, including
data extraction and optional LLM-powered insights.

Main Components:
- sing_file_analyser: Core analysis engine (analyze_single_file class)
- IVSweepAnalyzer: Fast data extraction wrapper with metadata support
- IVSweepLLMAnalyzer: Adds LLM insights (optional, slower)

Quick Start - After a Sweep:
    # Simplest way - just pass voltage and current arrays:
    from Helpers.IV_Analysis import quick_analyze
    
    voltages, currents = run_your_sweep()  # Your sweep function
    results = quick_analyze(voltages, currents)
    print(results['classification']['device_type'])
    
    # With metadata:
    results = quick_analyze(
        voltages, currents,
        metadata={'led_on': True, 'led_type': 'UV', 'temperature': 25.0}
    )

Other Options:
    # From file:
    from Helpers.IV_Analysis import analyze_sweep
    data = analyze_sweep(file_path="sweep.txt")
    
    # With LLM insights (slower, optional):
    from Helpers.IV_Analysis import IVSweepLLMAnalyzer
    llm_analyzer = IVSweepLLMAnalyzer(llm_backend='ollama', llm_model='llama2')
    result = llm_analyzer.analyze_with_insights(voltage=voltages, current=currents)
"""

from .iv_sweep_analyzer import IVSweepAnalyzer, analyze_sweep, quick_analyze
from .iv_sweep_llm_analyzer import IVSweepLLMAnalyzer

__all__ = ['IVSweepAnalyzer', 'IVSweepLLMAnalyzer', 'analyze_sweep', 'quick_analyze']

