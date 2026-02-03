"""
Analysis Module
===============

Unified analysis module for IV sweep data and sample-level analysis.

This module provides comprehensive analysis tools at multiple levels:
- Core: Fundamental single-sweep analysis (SweepAnalyzer)
- Aggregators: Multi-level analysis (DeviceAnalyzer, SectionAnalyzer, SampleAnalyzer, ComprehensiveAnalyzer)
- API: Public convenience wrappers (quick_analyze, analyze_sweep, etc.)

Quick Start:
    # Simplest way - just pass voltage and current arrays:
    from analysis import quick_analyze
    
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
    from analysis import analyze_sweep
    data = analyze_sweep(file_path="sweep.txt")
    
    # Core analyzer (direct access):
    from analysis import SweepAnalyzer
    analyzer = SweepAnalyzer(voltage, current)
    
    # Sample analysis:
    from analysis import ComprehensiveAnalyzer
    analyzer = ComprehensiveAnalyzer(sample_directory)
    analyzer.run_comprehensive_analysis()
    
    # With LLM insights (slower, optional):
    from analysis import IVSweepLLMAnalyzer
    llm_analyzer = IVSweepLLMAnalyzer(llm_backend='ollama', llm_model='llama2')
    result = llm_analyzer.analyze_with_insights(voltage=voltages, current=currents)
"""

# Core analyzer (fundamental, no aggregation)
from .core import SweepAnalyzer

# Aggregators (combine multiple units)
from .aggregators import DeviceAnalyzer, SectionAnalyzer, SampleAnalysisOrchestrator, ComprehensiveAnalyzer

# API (most commonly used)
from .api import IVSweepAnalyzer, IVSweepLLMAnalyzer, quick_analyze, analyze_sweep

__all__ = [
    # Core (single-unit analysis)
    'SweepAnalyzer',
    # Aggregators (multi-unit analysis)
    'DeviceAnalyzer', 'SectionAnalyzer', 'SampleAnalysisOrchestrator', 'ComprehensiveAnalyzer',
    # API
    'IVSweepAnalyzer', 'IVSweepLLMAnalyzer', 'quick_analyze', 'analyze_sweep'
]

