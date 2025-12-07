"""
IV Sweep LLM Analyzer - LLM-Powered Insights
=============================================

This module extends IVSweepAnalyzer to add LLM-powered insights generation.
Use this when you want natural language analysis of your IV sweep data.

Note: LLM analysis is slower than data extraction. For fast analysis, use
IVSweepAnalyzer directly. Use this class when you need interpretable insights.

Purpose:
- Generate natural language insights from IV sweep data
- Support multiple LLM backends (Ollama, llama-cpp-python, transformers)
- Format comprehensive prompts with all extracted metrics
- Provide measurement-specific analysis requests

Example Usage:
    # Analyze with LLM insights
    from Helpers.IV_Analysis import IVSweepLLMAnalyzer
    
    analyzer = IVSweepLLMAnalyzer(
        analysis_level='full',
        llm_backend='ollama',
        llm_model='llama2'
    )
    
    # Get data + insights in one call
    result = analyzer.analyze_with_insights(file_path="sweep.txt")
    print(result['llm_insights'])
    
    # Or extract data first, then get insights separately
    data = analyzer.analyze_sweep(file_path="sweep.txt")
    insights = analyzer.get_llm_insights()  # Uses extracted data
"""

import numpy as np
from typing import Dict, List, Optional, Union, Any
from .iv_sweep_analyzer import IVSweepAnalyzer


class IVSweepLLMAnalyzer(IVSweepAnalyzer):
    """
    Extended analyzer that adds LLM-powered insights to IV sweep analysis.
    
    Inherits from IVSweepAnalyzer for fast data extraction, then adds
    optional LLM processing for natural language insights. LLM analysis
    is separate and can be called only when needed.
    
    Example:
        >>> # Initialize with LLM backend
        >>> analyzer = IVSweepLLMAnalyzer(
        ...     analysis_level='full',
        ...     llm_backend='ollama',
        ...     llm_model='llama2'
        ... )
        >>> 
        >>> # Extract data (fast)
        >>> data = analyzer.analyze_sweep(file_path="sweep.txt")
        >>> print(data['classification']['device_type'])
        memristive
        >>> 
        >>> # Get LLM insights (slower, optional)
        >>> insights = analyzer.get_llm_insights()
        >>> print(insights)
    """
    
    def __init__(self, 
                 analysis_level: str = 'full',
                 llm_backend: str = 'ollama',
                 llm_model: Optional[str] = None,
                 llm_config: Optional[Dict] = None):
        """
        Initialize the IV Sweep LLM Analyzer.
        
        Parameters:
        -----------
        analysis_level : str, default='full'
            Analysis depth: 'basic', 'classification', 'full', or 'research'
        llm_backend : str, default='ollama'
            LLM backend: 'ollama', 'llama_cpp', 'transformers', or 'custom'
        llm_model : str, optional
            Model name/path for the LLM
        llm_config : dict, optional
            Additional configuration for the LLM backend
        
        Example:
            >>> # Using Ollama (recommended)
            >>> analyzer = IVSweepLLMAnalyzer(
            ...     llm_backend='ollama',
            ...     llm_model='llama2'
            ... )
            >>> 
            >>> # Using llama-cpp-python
            >>> analyzer = IVSweepLLMAnalyzer(
            ...     llm_backend='llama_cpp',
            ...     llm_model='/path/to/model.gguf'
            ... )
        """
        super().__init__(analysis_level=analysis_level)
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.llm_config = llm_config or {}
    
    def format_for_llm(self, extracted_data: Optional[Dict] = None) -> str:
        """
        Format extracted data into a comprehensive prompt for LLM analysis.
        
        Creates a detailed prompt with all metrics, metadata, and measurement-
        specific analysis requests. This is called automatically by get_llm_insights()
        but can be called separately to inspect or modify the prompt.
        
        Parameters:
        -----------
        extracted_data : dict, optional
            Extracted data (uses last analysis if not provided)
        
        Returns:
        --------
        str : Formatted prompt text ready for LLM
        
        Example:
            >>> analyzer = IVSweepLLMAnalyzer()
            >>> data = analyzer.analyze_sweep(file_path="sweep.txt")
            >>> prompt = analyzer.format_for_llm()
            >>> print(prompt[:200])  # First 200 chars
        """
        if extracted_data is None:
            extracted_data = self.extracted_data
        
        if extracted_data is None:
            raise ValueError("No extracted data available. Run analyze_sweep() first.")
        
        # Add metadata section
        metadata = extracted_data['device_info'].get('metadata', {})
        metadata_section = ""
        if metadata:
            metadata_section = "\n### Measurement Conditions:\n"
            if metadata.get('led_on') is not None:
                metadata_section += f"- LED Status: {'ON' if metadata['led_on'] else 'OFF'}\n"
            if metadata.get('led_type'):
                metadata_section += f"- LED Type: {metadata['led_type']}\n"
            if metadata.get('led_wavelength'):
                metadata_section += f"- LED Wavelength: {metadata['led_wavelength']} nm\n"
            if metadata.get('temperature') is not None:
                metadata_section += f"- Temperature: {metadata['temperature']} °C\n"
            if metadata.get('humidity') is not None:
                metadata_section += f"- Humidity: {metadata['humidity']}%\n"
            if metadata.get('bias_voltage') is not None:
                metadata_section += f"- Bias Voltage: {metadata['bias_voltage']} V\n"
            if metadata.get('sweep_rate') is not None:
                metadata_section += f"- Sweep Rate: {metadata['sweep_rate']} V/s\n"
            if metadata.get('notes'):
                metadata_section += f"- Notes: {metadata['notes']}\n"
            # Add any other custom metadata fields
            for key, value in metadata.items():
                if key not in ['led_on', 'led_type', 'led_wavelength', 'temperature', 'humidity', 
                              'bias_voltage', 'sweep_rate', 'notes']:
                    metadata_section += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        prompt = f"""# IV Sweep Analysis Report

## Device Information
- Device Name: {extracted_data['device_info'].get('name', 'Unknown')}
- Analysis Level: {extracted_data['device_info']['analysis_level']}
- Measurement Type: {extracted_data['device_info']['measurement_type']}
- Number of Loops: {extracted_data['device_info']['num_loops']}
{metadata_section}

## Device Classification
- **Device Type**: {extracted_data['classification']['device_type']}
- **Confidence**: {extracted_data['classification']['confidence']:.1%}
- **Conduction Mechanism**: {extracted_data['classification']['conduction_mechanism']}
- **Model Fit Quality (R²)**: {extracted_data['classification']['model_r2']:.3f}

### Classification Features:
"""
        
        # Add classification features
        features = extracted_data['classification'].get('features', {})
        for key, value in features.items():
            if isinstance(value, bool):
                prompt += f"- {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}\n"
            elif isinstance(value, (int, float)):
                prompt += f"- {key.replace('_', ' ').title()}: {value:.3f}\n"
            else:
                prompt += f"- {key.replace('_', ' ').title()}: {value}\n"
        
        prompt += f"""
## Resistance Characteristics
- **Ron (ON resistance)**: {extracted_data['resistance_metrics']['ron_mean']:.2e} Ω (σ = {extracted_data['resistance_metrics']['ron_std']:.2e} Ω)
- **Roff (OFF resistance)**: {extracted_data['resistance_metrics']['roff_mean']:.2e} Ω (σ = {extracted_data['resistance_metrics']['roff_std']:.2e} Ω)
- **Switching Ratio (Roff/Ron)**: {extracted_data['resistance_metrics']['switching_ratio_mean']:.1f} ± {extracted_data['resistance_metrics'].get('switching_ratio_std', 0):.1f}
- **ON/OFF Ratio**: {extracted_data['resistance_metrics']['on_off_ratio_mean']:.2f}
- **Window Margin**: {extracted_data['resistance_metrics']['window_margin_mean']:.2f}

## Voltage Characteristics
- **Von (ON voltage)**: {extracted_data['voltage_metrics']['von_mean']:.3f} V
- **Voff (OFF voltage)**: {extracted_data['voltage_metrics']['voff_mean']:.3f} V
- **Voltage Range**: {extracted_data['voltage_metrics']['min_voltage']:.3f} V to {extracted_data['voltage_metrics']['max_voltage']:.3f} V

## Hysteresis Analysis
- **Normalized Hysteresis Area**: {extracted_data['hysteresis_metrics']['normalized_area_mean']:.6f} ± {extracted_data['hysteresis_metrics'].get('normalized_area_std', 0):.6f}
- **Total Hysteresis Area**: {extracted_data['hysteresis_metrics']['total_area']:.6e}
- **Has Hysteresis**: {'Yes' if extracted_data['hysteresis_metrics']['has_hysteresis'] else 'No'}
- **Pinched Hysteresis**: {'Yes' if extracted_data['hysteresis_metrics']['pinched_hysteresis'] else 'No'}

## Performance Metrics
- **Retention Score**: {extracted_data['performance_metrics']['retention_score']:.3f} (1.0 = perfect, <0.3 = poor)
- **Endurance Score**: {extracted_data['performance_metrics']['endurance_score']:.3f} (1.0 = perfect, <0.3 = poor)
- **Rectification Ratio**: {extracted_data['performance_metrics']['rectification_ratio_mean']:.2f} (1.0 = symmetric, >10 = diode-like)
- **Nonlinearity Factor**: {extracted_data['performance_metrics']['nonlinearity_mean']:.3f} (0 = linear, 1 = highly nonlinear)
- **Asymmetry Factor**: {extracted_data['performance_metrics']['asymmetry_mean']:.3f} (0 = symmetric, 1 = asymmetric)
- **Power Consumption**: {extracted_data['performance_metrics']['power_consumption_mean'] * 1e6:.2f} μW
- **Energy per Switch**: {extracted_data['performance_metrics']['energy_per_switch_mean'] * 1e12:.2f} pJ
"""
        
        if extracted_data['performance_metrics']['compliance_current'] is not None:
            prompt += f"- **Compliance Current**: {extracted_data['performance_metrics']['compliance_current']:.2f} μA\n"
        else:
            prompt += "- **Compliance Current**: Not detected\n"
        
        # Add research diagnostics if available
        if 'research_diagnostics' in extracted_data:
            prompt += "\n## Research-Level Diagnostics\n"
            diag = extracted_data['research_diagnostics']
            if diag.get('switching_polarity'):
                prompt += f"- **Switching Polarity**: {diag['switching_polarity']}\n"
            if diag.get('ndr_index') is not None:
                prompt += f"- **NDR Index**: {diag['ndr_index']:.3f}\n"
            if diag.get('hysteresis_direction'):
                prompt += f"- **Hysteresis Direction**: {diag['hysteresis_direction']}\n"
            if diag.get('kink_voltage') is not None:
                prompt += f"- **Kink Voltage**: {diag['kink_voltage']:.3f} V\n"
            if diag.get('loop_similarity_score') is not None:
                prompt += f"- **Loop Similarity Score**: {diag['loop_similarity_score']:.3f}\n"
        
        # Add measurement-specific metrics
        measurement_type = extracted_data['device_info']['measurement_type']
        if measurement_type == 'endurance' and hasattr(self, 'analyzer') and self.analyzer:
            if hasattr(self.analyzer, 'state_degradation') and self.analyzer.state_degradation:
                prompt += "\n## Endurance Characteristics\n"
                deg = self.analyzer.state_degradation
                if deg.get('ron_degradation') is not None:
                    prompt += f"- **Ron Degradation**: {deg['ron_degradation'] * 100:.1f}%\n"
                if deg.get('roff_degradation') is not None:
                    prompt += f"- **Roff Degradation**: {deg['roff_degradation'] * 100:.1f}%\n"
                if deg.get('window_degradation') is not None:
                    prompt += f"- **Window Degradation**: {deg['window_degradation'] * 100:.1f}%\n"
                if deg.get('cycles_to_50_percent'):
                    prompt += f"- **Projected 50% Lifetime**: {deg['cycles_to_50_percent']} cycles\n"
        
        if measurement_type == 'retention' and hasattr(self, 'analyzer') and self.analyzer:
            if hasattr(self.analyzer, 'state_degradation') and self.analyzer.state_degradation:
                prompt += "\n## Retention Characteristics\n"
                ret = self.analyzer.state_degradation
                if ret.get('initial_resistance') is not None:
                    prompt += f"- **Initial Resistance**: {ret['initial_resistance']:.2e} Ω\n"
                if ret.get('decay_rate') is not None:
                    prompt += f"- **Decay Rate**: {ret['decay_rate']:.6f}\n"
                if ret.get('retention_time_90_percent'):
                    prompt += f"- **90% Retention Time**: {ret['retention_time_90_percent']} s\n"
        
        if measurement_type == 'pulse' and hasattr(self, 'analyzer') and self.analyzer:
            if hasattr(self.analyzer, 'set_times') and self.analyzer.set_times:
                prompt += "\n## Pulse Characteristics\n"
                if self.analyzer.set_times:
                    prompt += f"- **Mean Set Time**: {np.mean(self.analyzer.set_times) * 1e9:.1f} ns\n"
                if self.analyzer.reset_times:
                    prompt += f"- **Mean Reset Time**: {np.mean(self.analyzer.reset_times) * 1e9:.1f} ns\n"
                if self.analyzer.set_voltages:
                    prompt += f"- **Mean Set Voltage**: {np.mean(self.analyzer.set_voltages):.2f} V\n"
        
        # Add validation results if available
        if 'validation' in extracted_data:
            prompt += "\n## Memristor Behavior Validation\n"
            validation = extracted_data['validation']
            for key, value in validation.items():
                if isinstance(value, bool):
                    prompt += f"- {key.replace('_', ' ').title()}: {'Pass' if value else 'Fail'}\n"
                elif isinstance(value, (int, float)):
                    prompt += f"- {key.replace('_', ' ').title()}: {value:.3f}\n"
        
        # Customize analysis request based on measurement type
        if measurement_type == 'endurance':
            analysis_request = """
## Analysis Request

Please provide a comprehensive analysis of this endurance measurement. Include:

1. **Device Stability**: How stable is the device over multiple cycles?
2. **Degradation Analysis**: What is the rate and nature of device degradation?
3. **Lifetime Projection**: Based on the data, what is the expected device lifetime?
4. **Failure Mechanisms**: What might be causing any observed degradation?
5. **Optimization Suggestions**: How could the device be improved for better endurance?
6. **Comparison**: How does this compare to typical memristor endurance performance?

Please be specific and reference the numerical values provided above.
"""
        elif measurement_type == 'retention':
            analysis_request = """
## Analysis Request

Please provide a comprehensive analysis of this retention measurement. Include:

1. **State Stability**: How well does the device retain its state over time?
2. **Decay Analysis**: What is the nature and rate of state decay?
3. **Retention Time**: How long can the device maintain its state?
4. **Physical Mechanisms**: What physical processes might be causing state loss?
5. **Optimization Suggestions**: How could retention be improved?
6. **Comparison**: How does this compare to typical memristor retention performance?

Please be specific and reference the numerical values provided above.
"""
        elif measurement_type == 'pulse':
            analysis_request = """
## Analysis Request

Please provide a comprehensive analysis of this pulse measurement. Include:

1. **Switching Speed**: How fast does the device switch between states?
2. **Switching Characteristics**: What are the key features of the switching behavior?
3. **Energy Efficiency**: How energy-efficient is the switching process?
4. **Switching Mechanism**: What might be the underlying switching mechanism?
5. **Optimization Suggestions**: How could switching be improved?
6. **Comparison**: How does this compare to typical memristor switching performance?

Please be specific and reference the numerical values provided above.
"""
        else:
            analysis_request = """
## Analysis Request

Please provide a comprehensive analysis of this IV sweep data. Include:

1. **Device Interpretation**: What type of device is this based on the characteristics?
2. **Key Observations**: What are the most notable features or behaviors?
3. **Performance Assessment**: How does this device perform compared to typical memristors?
4. **Potential Applications**: What applications might this device be suitable for?
5. **Recommendations**: Any suggestions for further characterization or optimization?
6. **Physical Insights**: What can we infer about the underlying physical mechanisms?

Please be specific and reference the numerical values provided above.
"""
        
        prompt += analysis_request
        
        return prompt
    
    def get_llm_insights(self, 
                        prompt: Optional[str] = None,
                        custom_prompt: Optional[str] = None) -> str:
        """
        Get insights from a local LLM based on the extracted data.
        
        This method formats the extracted data into a prompt and queries
        the configured LLM backend. Can be slow for large models or data.
        Only call this when you need LLM insights.
        
        Parameters:
        -----------
        prompt : str, optional
            Pre-formatted prompt (uses format_for_llm() if not provided)
        custom_prompt : str, optional
            Custom prompt to use instead of the default formatted prompt
        
        Returns:
        --------
        str : LLM-generated insights
        
        Example:
            >>> analyzer = IVSweepLLMAnalyzer(llm_backend='ollama', llm_model='llama2')
            >>> data = analyzer.analyze_sweep(file_path="sweep.txt")
            >>> # Get insights (this is the slow part)
            >>> insights = analyzer.get_llm_insights()
            >>> print(insights)
        """
        if custom_prompt:
            final_prompt = custom_prompt
        elif prompt:
            final_prompt = prompt
        else:
            final_prompt = self.format_for_llm()
        
        # Route to appropriate LLM backend
        if self.llm_backend == 'ollama':
            return self._query_ollama(final_prompt)
        elif self.llm_backend == 'llama_cpp':
            return self._query_llama_cpp(final_prompt)
        elif self.llm_backend == 'transformers':
            return self._query_transformers(final_prompt)
        elif self.llm_backend == 'custom':
            return self._query_custom(final_prompt)
        else:
            raise ValueError(f"Unknown LLM backend: {self.llm_backend}")
    
    def analyze_with_insights(self,
                              voltage: Optional[np.ndarray] = None,
                              current: Optional[np.ndarray] = None,
                              time: Optional[np.ndarray] = None,
                              file_path: Optional[str] = None,
                              measurement_type: Optional[str] = None,
                              device_name: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None,
                              custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete analysis pipeline: extract data AND generate LLM insights.
        
        This runs both data extraction (fast) and LLM analysis (slow) in one call.
        For faster analysis, use analyze_sweep() first, then get_llm_insights() separately.
        
        Parameters:
        -----------
        voltage : array-like, optional
            Voltage data (required if file_path not provided)
        current : array-like, optional
            Current data (required if file_path not provided)
        time : array-like, optional
            Time data for pulse/retention measurements
        file_path : str, optional
            Path to data file (alternative to providing voltage/current directly)
        measurement_type : str, optional
            Type of measurement (auto-detected if not provided)
        device_name : str, optional
            Device identifier
        metadata : dict, optional
            Additional metadata (LED state, LED type, etc.)
        custom_prompt : str, optional
            Custom LLM prompt
        
        Returns:
        --------
        dict : Complete analysis including extracted data and LLM insights
        
        Example:
            >>> analyzer = IVSweepLLMAnalyzer(llm_backend='ollama', llm_model='llama2')
            >>> result = analyzer.analyze_with_insights(file_path="sweep.txt")
            >>> print(result['classification']['device_type'])  # Fast data
            memristive
            >>> print(result['llm_insights'])  # LLM insights (slower)
        """
        # Extract all information (fast)
        extracted = self.analyze_sweep(
            voltage=voltage,
            current=current,
            time=time,
            file_path=file_path,
            measurement_type=measurement_type,
            device_name=device_name,
            metadata=metadata
        )
        
        # Generate LLM insights (slow, optional)
        try:
            insights = self.get_llm_insights(custom_prompt=custom_prompt)
            extracted['llm_insights'] = insights
        except Exception as e:
            extracted['llm_insights'] = f"Error generating insights: {str(e)}"
            extracted['llm_error'] = str(e)
        
        return extracted
    
    def _query_ollama(self, prompt: str) -> str:
        """Query Ollama API for insights."""
        try:
            import ollama
            model = self.llm_model or self.llm_config.get('model', 'llama2')
            response = ollama.generate(model=model, prompt=prompt, **self.llm_config)
            return response.get('response', 'No response generated')
        except ImportError:
            raise ImportError("Ollama not installed. Install with: pip install ollama")
        except Exception as e:
            return f"Error querying Ollama: {str(e)}"
    
    def _query_llama_cpp(self, prompt: str) -> str:
        """Query llama-cpp-python for insights."""
        try:
            from llama_cpp import Llama
            model_path = self.llm_model or self.llm_config.get('model_path')
            if model_path is None:
                raise ValueError("llm_model or llm_config['model_path'] must be provided for llama_cpp backend")
            
            llm = Llama(model_path=model_path, **self.llm_config)
            response = llm(prompt, max_tokens=self.llm_config.get('max_tokens', 512), stop=["\n\n"], echo=False)
            return response['choices'][0]['text']
        except ImportError:
            raise ImportError("llama-cpp-python not installed. Install with: pip install llama-cpp-python")
        except Exception as e:
            return f"Error querying llama-cpp: {str(e)}"
    
    def _query_transformers(self, prompt: str) -> str:
        """Query Hugging Face transformers for insights."""
        try:
            from transformers import pipeline
            model_name = self.llm_model or self.llm_config.get('model_name', 'gpt2')
            generator = pipeline('text-generation', model=model_name, **self.llm_config)
            response = generator(prompt, max_length=self.llm_config.get('max_length', 512), num_return_sequences=1)
            return response[0]['generated_text'][len(prompt):]
        except ImportError:
            raise ImportError("transformers not installed. Install with: pip install transformers")
        except Exception as e:
            return f"Error querying transformers: {str(e)}"
    
    def _query_custom(self, prompt: str) -> str:
        """Query custom LLM backend."""
        custom_func = self.llm_config.get('query_function')
        if custom_func is None:
            raise ValueError("llm_config['query_function'] must be provided for custom backend")
        return custom_func(prompt)

