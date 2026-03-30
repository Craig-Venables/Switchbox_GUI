"""
Sample-level analysis orchestrator for memristor device measurements.

This module provides the SampleAnalyzer class which coordinates analysis across
multiple sections of a sample/substrate. It aggregates section-level results
and generates sample-wide summary reports and visualizations.

The module is designed to be integrated into larger analysis systems and can
process data from predesigned sweep configurations.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import seaborn as sns
import data_analyzer


class SampleAnalyzer:
    """
    Orchestrates analysis of an entire sample/substrate across multiple sections.
    
    This class coordinates section-level analysis, aggregates results, and generates
    sample-wide summary reports. It is designed to work with predesigned sweep
    configurations and can be integrated into larger analysis pipelines.
    
    Attributes:
        top_level_path (Path): Root directory containing sample data
        sections (list): List of section identifiers to analyze (default: A,B,D,E,F,G,H,I,K,L)
        quality_metrics (dict): Aggregated quality metrics across all sections
        sample_metrics (dict): Sample-level metrics organized by section
        device_stats (dict): Device statistics organized by section
    """
    
    def __init__(self, top_level_path, sections=None):
        """
        Initialize the sample analyzer.
        
        Parameters:
        -----------
        top_level_path : str or Path
            Root directory path containing sample data. Expected structure:
            <top_level_path>/<sample_name>/<section>/<device_number>/<sweep_files>
        sections : list, optional
            List of section identifiers to analyze. If None, defaults to
            ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']
        """
        self.top_level_path = Path(top_level_path)
        self.sections = sections if sections is not None else ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']
        self.quality_metrics = {}
        self.sample_metrics = {}
        self.device_stats = {}

    def analyze_sample(self, sample_name):
        """
        Analyze entire sample across all sections.
        
        This method orchestrates the analysis workflow:
        1. Validates sample path exists
        2. Analyzes each section using DataAnalyzer
        3. Generates individual device plots
        4. Aggregates results and generates sample-level summaries
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample/substrate to analyze
            
        Returns:
        --------
        None
            Results are written to disk in the sample_summary directory
        """
        sample_path = self.top_level_path / sample_name
        if not sample_path.exists():
            print(f"Sample {sample_name} not found at {sample_path}")
            return

        # Create a summary directory for the sample
        summary_dir = sample_path / 'sample_summary'
        summary_dir.mkdir(exist_ok=True)

        # Dictionary to store all device stats
        self.device_stats = {section: {} for section in self.sections}

        # Analyze each section
        for section in self.sections:
            section_path = sample_path / section
            if section_path.exists():
                print(f"Analyzing section {section}")

                # Initialize DataAnalyzer for detailed analysis for each section
                analyzer = data_analyzer.DataAnalyzer(self.top_level_path, section, sample_name)

                # Analyze the current section, plots graphs etc
                stats, metrics, self.quality_metrics = analyzer.analyze_section_sweeps(
                    sample_name, section, self.quality_metrics
                )

                # Store quality metrics for this section
                self.device_stats[section] = stats
                self.sample_metrics[section] = metrics

                # Generate individual device plots
                for device_num in range(1, 11):
                    device_path = section_path / str(device_num)
                    if device_path.exists():
                        analyzer.analyze_single_device(sample_name, section, device_num)

        # Generate summary reports and visualizations
        self.generate_sample_summary(sample_name, summary_dir)


    def generate_sample_summary(self, sample_name, summary_dir):
        """
        Generate sample-level summary visualizations and reports.
        
        Creates:
        - Quality metrics CSV file
        - Section comparison plots
        - Quality heatmap
        - Working devices plot
        - HTML summary report
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample being analyzed
        summary_dir : Path
            Directory where summary files will be saved
        """
        # Create summary DataFrame
        summary_data = pd.DataFrame.from_dict(self.quality_metrics, orient='index')

        # Save numerical summary
        summary_data.to_csv(summary_dir / 'quality_metrics.csv')

        # Create section comparison visualizations
        self.create_section_comparison_plots(summary_dir)

        # Original heatmap and working devices plots...
        self.create_quality_heatmap(sample_name, summary_dir)
        self.create_working_devices_plot(sample_name, summary_dir)

        # Generate HTML report
        self.generate_html_report(sample_name, summary_dir)

    def create_section_comparison_plots(self, summary_dir):
        """
        Create comparison plots for device statistics across sections.
        
        Generates box plots for key metrics and a correlation matrix showing
        relationships between metrics across all sections.
        
        Parameters:
        -----------
        summary_dir : Path
            Directory where plots will be saved
        """
        # Key metrics to compare
        metrics = [
            'mean_ron', 'mean_roff', 'mean_on_off_ratio',
            'avg_normalized_area', 'mean_r_02V', 'mean_r_05V'
        ]

        # Create comparison plots for each metric
        for metric in metrics:
            plt.figure(figsize=(15, 6))

            # Prepare data for boxplot
            data = []
            labels = []

            for section in self.sections:
                if section in self.device_stats:
                    values = [stats[metric] for stats in self.device_stats[section].values()
                              if metric in stats and stats[metric] is not None]
                    if values:
                        data.append(values)
                        labels.append(section)

            if data:
                plt.boxplot(data, tick_labels=labels)
                plt.title(f'{metric} Comparison Across Sections')
                plt.ylabel(metric)
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig(summary_dir / f'{metric}_comparison.png')
            plt.close()

        # Create correlation matrix for key metrics
        self.create_correlation_matrix(summary_dir, metrics)

    def create_correlation_matrix(self, summary_dir, metrics):
        """
        Create correlation matrix heatmap for key device metrics.
        
        Parameters:
        -----------
        summary_dir : Path
            Directory where the correlation matrix plot will be saved
        metrics : list
            List of metric names to include in the correlation analysis
        """
        # Prepare data for correlation analysis
        all_data = []
        for section in self.sections:
            if section in self.device_stats:
                for device_stats in self.device_stats[section].values():
                    metric_values = [device_stats.get(metric) for metric in metrics]
                    if all(v is not None for v in metric_values):
                        all_data.append(metric_values)

        if all_data:
            correlation_df = pd.DataFrame(all_data, columns=metrics)
            plt.figure(figsize=(10, 8))
            sns.heatmap(correlation_df.corr(), annot=True, cmap='coolwarm',
                        xticklabels=metrics, yticklabels=metrics)
            plt.title('Correlation Matrix of Device Metrics')
            plt.tight_layout()
            plt.savefig(summary_dir / 'metric_correlations.png')
            plt.close()

    def create_quality_heatmap(self, sample_name, summary_dir):
        """
        Create heatmap visualization of quality scores across sections.
        
        Arranges sections in a 2x5 grid layout (Top: A,B,D,E,F; Bottom: G,H,I,K,L)
        with color-coded quality scores.
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample
        summary_dir : Path
            Directory where the heatmap will be saved
        """
        plt.figure(figsize=(15, 10))
        scores_matrix = np.zeros((2, 5))
        for idx, section in enumerate(self.sections):
            key = f"{sample_name}_{section}"
            if key in self.quality_metrics:
                row = idx // 5
                col = idx % 5
                scores_matrix[row, col] = self.quality_metrics[key]['overall_score']

        sns.heatmap(scores_matrix,
                    annot=True,
                    fmt='.1f',
                    cmap='RdYlGn',
                    xticklabels=['A/G', 'B/H', 'D/I', 'E/K', 'F/L'],
                    yticklabels=['Top', 'Bottom'])
        plt.title(f'Quality Scores Heatmap - {sample_name}')
        plt.savefig(summary_dir / 'quality_heatmap.png')
        plt.close()

    def create_working_devices_plot(self, sample_name, summary_dir):
        """
        Create bar plot showing number of working devices per section.
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample
        summary_dir : Path
            Directory where the plot will be saved
        """
        plt.figure(figsize=(15, 6))
        working_devices = [self.quality_metrics.get(f"{sample_name}_{section}", {}).get('working_devices', 0)
                           for section in self.sections]
        plt.bar(self.sections, working_devices)
        plt.title(f'Working Devices per Section - {sample_name}')
        plt.ylabel('Number of Working Devices')
        plt.savefig(summary_dir / 'working_devices.png')
        plt.close()


    def generate_html_report(self, sample_name, summary_dir):
        """
        Generate an HTML summary report with quality metrics and visualizations.
        
        Creates a styled HTML report with:
        - Section quality metrics with color-coded scores
        - Embedded visualizations (heatmap and working devices plot)
        
        Parameters:
        -----------
        sample_name : str
            Name of the sample
        summary_dir : Path
            Directory where the HTML report will be saved
        """
        html_content = f"""
        <html>
        <head>
            <title>Sample {sample_name} Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ margin: 10px; padding: 10px; border: 1px solid #ddd; }}
                .good {{ background-color: #90EE90; }}
                .medium {{ background-color: #FFE4B5; }}
                .poor {{ background-color: #FFB6C6; }}
            </style>
        </head>
        <body>
            <h1>Sample {sample_name} Analysis Report</h1>

            <h2>Section Quality Metrics</h2>
            <div class="metrics">
        """

        for section in self.sections:
            key = f"{sample_name}_{section}"
            if key in self.quality_metrics:
                metrics = self.quality_metrics[key]
                score_class = 'good' if metrics['overall_score'] >= 70 else 'medium' if metrics[
                                                                                            'overall_score'] >= 40 else 'poor'

                html_content += f"""
                <div class="metric {score_class}">
                    <h3>Section {section}</h3>
                    <p>Overall Score: {metrics['overall_score']:.1f}/100</p>
                    <p>Working Devices: {metrics['working_devices']}/10</p>
                    <p>Current Range Std: {metrics['current_range_std']:.2e}</p>
                    <p>Resistance_0.2V_std: {metrics['resistance_0_2V_std']:.2e}</p>
                    <p>Resistance_0.5V_std: {metrics['resistance_0_5V_std']:.2e}</p>
                </div>
                """

        html_content += """
            </div>
            <h2>Visualizations</h2>
            <img src="quality_heatmap.png" alt="Quality Heatmap">
            <img src="working_devices.png" alt="Working Devices">
        </body>
        </html>
        """

        with open(summary_dir / 'report.html', 'w') as f:
            f.write(html_content)

def main():
    """
    Example main function demonstrating usage of SampleAnalyzer.
    
    This function should be customized for your specific use case.
    For integration into other systems, instantiate SampleAnalyzer directly
    and call analyze_sample() with appropriate parameters.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Analyze memristor sample data across multiple sections'
    )
    parser.add_argument(
        'top_level_path',
        type=str,
        help='Root directory containing sample data'
    )
    parser.add_argument(
        'sample_name',
        type=str,
        help='Name of the sample/substrate to analyze'
    )
    parser.add_argument(
        '--sections',
        type=str,
        nargs='+',
        default=None,
        help='List of sections to analyze (default: A,B,D,E,F,G,H,I,K,L)'
    )
    
    args = parser.parse_args()
    
    sample_analyzer = SampleAnalyzer(args.top_level_path, sections=args.sections)
    sample_analyzer.analyze_sample(args.sample_name)


if __name__ == "__main__":
    main()