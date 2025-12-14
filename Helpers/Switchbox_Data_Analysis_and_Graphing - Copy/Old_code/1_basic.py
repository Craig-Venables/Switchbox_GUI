import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import pandas as pd
import seaborn as sns

from Old_code import dataanalyzer


class SampleAnalyzer:
    def __init__(self, top_level_path):
        self.top_level_path = Path(top_level_path)
        self.sections = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']
        self.quality_metrics = {}

    def analyze_sample(self, sample_name):
        """Analyze entire sample across all sections"""
        sample_path = self.top_level_path / sample_name
        if not sample_path.exists():
            print(f"Sample {sample_name} not found")
            return

        # Create a summary directory for the sample
        summary_dir = sample_path / 'sample_summary'
        summary_dir.mkdir(exist_ok=True)

        # Initialize DataAnalyzer for detailed analysis
        analyzer = dataanalyzer.DataAnalyzer(self.top_level_path)

        # Analyze each section
        for section in self.sections:
            section_path = sample_path / section
            if section_path.exists():
                print(f"Analyzing section {section}")

                # Run detailed analysis
                analyzer.analyze_section_sweeps(sample_name, section)

                # Calculate quality metrics for this section
                self.calculate_section_metrics(sample_name, section)

                # Analyze individual devices in section
                for device_num in range(1, 11):
                    device_path = section_path / str(device_num)
                    if device_path.exists():
                        analyzer.analyze_single_device(sample_name, section, device_num)

        # Generate summary reports and visualizations
        self.generate_sample_summary(sample_name, summary_dir)

    def calculate_section_metrics(self, sample_name, section):
        """Calculate quality metrics for a section"""
        section_path = self.top_level_path / sample_name / section
        metrics = {
            'devices': [],
            'sweep1_current_range': [],
            'resistance_uniformity': [],
            'device_consistency': [],
            'working_devices': 0
        }

        # Analyze first sweep of each device
        for device_num in range(1, 11):
            device_path = section_path / str(device_num)
            if device_path.exists():
                sweep1_files = list(device_path.glob('1_*.txt'))
                sweep1_files = [f for f in sweep1_files if f.name != 'log.txt']

                if sweep1_files:
                    voltage, current, _ = self.read_data_file(sweep1_files[0])
                    if voltage is not None and current is not None:
                        # Calculate metrics
                        current_range = np.max(np.abs(current)) - np.min(np.abs(current))
                        resistance = np.mean(np.abs(voltage / current))

                        metrics['devices'].append(device_num)
                        metrics['sweep1_current_range'].append(current_range)
                        metrics['resistance_uniformity'].append(resistance)
                        metrics['working_devices'] += 1

        # Calculate section-wide metrics
        if metrics['devices']:
            self.quality_metrics[f"{sample_name}_{section}"] = {
                'working_devices': metrics['working_devices'],
                'current_range_std': np.std(metrics['sweep1_current_range']),
                'resistance_std': np.std(metrics['resistance_uniformity']),
                'overall_score': self.calculate_overall_score(metrics)
            }

    def calculate_overall_score(self, metrics):
        """Calculate an overall quality score (0-100)"""
        if not metrics['devices']:
            return 0

        # Normalize metrics to 0-1 range
        working_ratio = metrics['working_devices'] / 10
        current_uniformity = 1 - min(1,
                                     np.std(metrics['sweep1_current_range']) / np.mean(metrics['sweep1_current_range']))
        resistance_uniformity = 1 - min(1, np.std(metrics['resistance_uniformity']) / np.mean(
            metrics['resistance_uniformity']))

        # Weight the components
        score = (working_ratio * 40 +
                 current_uniformity * 30 +
                 resistance_uniformity * 30)

        return score

    def generate_sample_summary(self, sample_name, summary_dir):
        """Generate summary visualizations and reports"""
        # Create summary DataFrame
        summary_data = pd.DataFrame.from_dict(self.quality_metrics, orient='index')

        # Save numerical summary
        summary_data.to_csv(summary_dir / 'quality_metrics.csv')

        # Create heatmap of quality scores
        plt.figure(figsize=(15, 10))
        scores_matrix = np.zeros((2, 5))  # 2x5 grid for A,B,D,E,F and G,H,I,K,L
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

        # Create bar plot of working devices per section
        plt.figure(figsize=(15, 6))
        working_devices = [self.quality_metrics.get(f"{sample_name}_{section}", {}).get('working_devices', 0)
                           for section in self.sections]
        plt.bar(self.sections, working_devices)
        plt.title(f'Working Devices per Section - {sample_name}')
        plt.ylabel('Number of Working Devices')
        plt.savefig(summary_dir / 'working_devices.png')
        plt.close()

        # Generate HTML report
        self.generate_html_report(sample_name, summary_dir)

    def generate_html_report(self, sample_name, summary_dir):
        """Generate an HTML summary report"""
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
                    <p>Resistance Std: {metrics['resistance_std']:.2e}</p>
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

    def read_data_file(self, file_path):
        try:
            data = np.loadtxt(file_path, skiprows=1)
            voltage = data[:, 0]
            current = data[:, 1]
            time = data[:, 2]
            return voltage, current, time
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None, None, None


def main():
    sample_analyzer = SampleAnalyzer('C:\\Users\\Craig-Desktop\\Desktop\\test_data\\Data_save_loc')
    sample_name = 'D80'  # or whatever your sample name is
    sample_analyzer.analyze_sample(sample_name)


if __name__ == "__main__":
    main()