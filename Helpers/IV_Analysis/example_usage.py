"""
Example Usage of IV Analysis Module
===================================

Simple examples showing how to use the IV analysis tools for single sweeps.
"""

from Helpers.IV_Analysis import IVSweepAnalyzer, IVSweepLLMAnalyzer, analyze_sweep


def example_quick_analysis():
    """Quick analysis - just get the data (fast)."""
    print("=" * 60)
    print("Example 1: Quick Data Extraction (Fast)")
    print("=" * 60)
    
    # Simple one-line analysis
    data = analyze_sweep(file_path="G - 10 - 34.txt")
    
    print(f"\nDevice Type: {data['classification']['device_type']}")
    print(f"Confidence: {data['classification']['confidence']:.1%}")
    print(f"Switching Ratio: {data['resistance_metrics']['switching_ratio_mean']:.1f}")
    print(f"Retention Score: {data['performance_metrics']['retention_score']:.3f}")


def example_with_metadata():
    """Analysis with metadata (LED state, temperature, etc.)."""
    print("\n" + "=" * 60)
    print("Example 2: Analysis with Metadata")
    print("=" * 60)
    
    metadata = {
        'led_on': True,
        'led_type': 'UV',
        'led_wavelength': 365,
        'temperature': 25.0,
        'humidity': 45.0,
        'notes': 'First measurement after fabrication'
    }
    
    analyzer = IVSweepAnalyzer(analysis_level='full')
    data = analyzer.analyze_sweep(
        file_path="G - 10 - 34.txt",
        metadata=metadata
    )
    
    print(f"\nDevice: {data['device_info']['name']}")
    print(f"LED Status: {'ON' if data['device_info']['metadata'].get('led_on') else 'OFF'}")
    print(f"LED Type: {data['device_info']['metadata'].get('led_type', 'N/A')}")
    print(f"Temperature: {data['device_info']['metadata'].get('temperature', 'N/A')} °C")


def example_direct_data():
    """Analyze data directly without a file."""
    print("\n" + "=" * 60)
    print("Example 3: Analyze Direct Data (No File)")
    print("=" * 60)
    
    import numpy as np
    
    # Example data
    voltage = np.array([0, 1, 2, 1, 0, -1, -2, -1, 0])
    current = np.array([0, 1e-6, 2e-6, 1.5e-6, 0, -1e-6, -2e-6, -1.5e-6, 0])
    
    analyzer = IVSweepAnalyzer(analysis_level='full')
    data = analyzer.analyze_sweep(voltage=voltage, current=current)
    
    print(f"\nDevice Type: {data['classification']['device_type']}")
    print(f"Number of Loops: {data['device_info']['num_loops']}")


def example_with_llm():
    """Analysis with LLM insights (slower, optional)."""
    print("\n" + "=" * 60)
    print("Example 4: Analysis with LLM Insights (Slower)")
    print("=" * 60)
    
    # Option 1: Get data first, then insights separately (recommended)
    analyzer = IVSweepLLMAnalyzer(
        analysis_level='full',
        llm_backend='ollama',
        llm_model='llama2'
    )
    
    # Fast data extraction
    data = analyzer.analyze_sweep(file_path="G - 10 - 34.txt")
    print(f"\nDevice Type: {data['classification']['device_type']}")
    
    # Slow LLM analysis (only when needed)
    try:
        insights = analyzer.get_llm_insights()
        print("\nLLM Insights:")
        print(insights[:500] + "..." if len(insights) > 500 else insights)
    except Exception as e:
        print(f"\nLLM Error: {e}")
        print("(Make sure Ollama is installed and running)")


def example_separate_steps():
    """Show how to separate data extraction from LLM analysis."""
    print("\n" + "=" * 60)
    print("Example 5: Separate Data Extraction and LLM Analysis")
    print("=" * 60)
    
    # Step 1: Fast data extraction (always do this first)
    analyzer = IVSweepLLMAnalyzer(analysis_level='full')
    data = analyzer.analyze_sweep(file_path="G - 10 - 34.txt")
    
    print("\nExtracted Data:")
    print(f"  Device Type: {data['classification']['device_type']}")
    print(f"  Switching Ratio: {data['resistance_metrics']['switching_ratio_mean']:.1f}")
    
    # Step 2: Optional LLM analysis (only if needed, slower)
    # Configure LLM backend
    analyzer.llm_backend = 'ollama'
    analyzer.llm_model = 'llama2'
    
    try:
        insights = analyzer.get_llm_insights()
        print("\nLLM Insights:")
        print(insights[:300] + "..." if len(insights) > 300 else insights)
    except Exception as e:
        print(f"\nSkipping LLM analysis: {e}")


if __name__ == "__main__":
    # Run examples
    try:
        example_quick_analysis()
    except Exception as e:
        print(f"Example 1 failed: {e}")
    
    try:
        example_with_metadata()
    except Exception as e:
        print(f"Example 2 failed: {e}")
    
    try:
        example_direct_data()
    except Exception as e:
        print(f"Example 3 failed: {e}")
    
    # LLM examples (may fail if Ollama not set up)
    try:
        example_with_llm()
    except Exception as e:
        print(f"Example 4 failed: {e}")
    
    try:
        example_separate_steps()
    except Exception as e:
        print(f"Example 5 failed: {e}")

