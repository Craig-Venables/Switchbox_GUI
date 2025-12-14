# enhanced_analyzer.py
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import seaborn as sns
from single_file_metrics import analyze_single_file
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from datetime import datetime
from scipy import stats
import warnings

warnings.filterwarnings('ignore')


# not sure this is any good 


class ComprehensiveDeviceAnalyzer:
    """
    Analyzes all sweeps for a device to provide comprehensive characterization
    """

    def __init__(self, device_path, sample_name, section, device_num):
        self.device_path = Path(device_path)
        self.sample_name = sample_name
        self.section = section
        self.device_num = device_num
        self.sweep_analyses = {}
        self.device_evolution = {}
        self.classification_history = []

    def analyze_all_sweeps(self):
        """Analyze all sweeps for this device"""
        sweep_files = sorted([f for f in self.device_path.glob('*.txt')
                              if f.name != 'log.txt'],
                             key=lambda x: int(x.name.split('-')[0]))

        results = {
            'sweep_analyses': {},
            'evolution_metrics': {},
            'device_classification': {},
            'performance_summary': {}
        }

        # Analyze each sweep
        for sweep_file in sweep_files:
            sweep_num = int(sweep_file.name.split('-')[0])
            # print(sweep_file)
            voltage, current, time = self.read_data_file(sweep_file)

            if voltage is not None and current is not None:
                # Use your analyze_single_file class
                analyzer = analyze_single_file(voltage, current, time)

                # Store comprehensive analysis
                results['sweep_analyses'][sweep_num] = {
                    'summary_stats': analyzer.get_summary_stats(),
                    'performance_metrics': analyzer.get_memristor_performance_metrics(),
                    'classification': {
                        'device_type': analyzer.device_type,
                        'confidence': analyzer.classification_confidence,
                        'conduction_mechanism': analyzer.conduction_mechanism
                    },
                    'neuromorphic_metrics': analyzer.get_neuromorphic_metrics() if analyzer.device_type == 'memristive' else None
                }

                # Track classification evolution
                self.classification_history.append({
                    'sweep': sweep_num,
                    'type': analyzer.device_type,
                    'confidence': analyzer.classification_confidence
                })

        # Analyze device evolution
        results['evolution_metrics'] = self._analyze_device_evolution(results['sweep_analyses'])

        # Determine overall device classification
        results['device_classification'] = self._classify_device_overall_improved()
        # print(sweep_file)
        # print(results['device_classification'])
        # Generate performance summary
        results['performance_summary'] = self._generate_performance_summary(results)

        return results

    def _analyze_device_evolution(self, sweep_analyses):
        """Track how device parameters evolve over sweeps"""
        evolution = {
            'ron_evolution': [],
            'roff_evolution': [],
            'switching_ratio_evolution': [],
            'von_evolution': [],
            'voff_evolution': [],
            'retention_evolution': [],
            'endurance_evolution': [],
            'classification_stability': []
        }

        for sweep_num in sorted(sweep_analyses.keys()):
            analysis = sweep_analyses[sweep_num]
            stats = analysis['summary_stats']
            metrics = analysis['performance_metrics']

            if stats and metrics:
                evolution['ron_evolution'].append(stats.get('mean_ron', np.nan))
                evolution['roff_evolution'].append(stats.get('mean_roff', np.nan))
                evolution['switching_ratio_evolution'].append(metrics.get('switching_ratio', np.nan))
                evolution['von_evolution'].append(stats.get('mean_von', np.nan))
                evolution['voff_evolution'].append(stats.get('mean_voff', np.nan))
                evolution['retention_evolution'].append(metrics.get('retention_score', np.nan))
                evolution['endurance_evolution'].append(metrics.get('endurance_score', np.nan))

        # Calculate evolution statistics
        evolution['trends'] = self._calculate_trends(evolution)
        evolution['stability_scores'] = self._calculate_stability_scores(evolution)

        return evolution

    # def _classify_device_overall(self):
    #     """Determine overall device classification based on all sweeps"""
    #     if not self.classification_history:
    #         return {'type': 'unknown', 'confidence': 0, 'consistency': 0}
    #
    #     # Count device type occurrences
    #     type_counts = {}
    #     total_confidence = 0
    #
    #     for classification in self.classification_history:
    #         device_type = classification['type']
    #         confidence = classification['confidence']
    #
    #         if device_type not in type_counts:
    #             type_counts[device_type] = {'count': 0, 'confidence_sum': 0}
    #
    #         type_counts[device_type]['count'] += 1
    #         type_counts[device_type]['confidence_sum'] += confidence
    #         total_confidence += confidence
    #
    #     # Determine dominant type
    #     dominant_type = max(type_counts.items(),
    #                         key=lambda x: x[1]['count'] * x[1]['confidence_sum'])[0]
    #
    #     # Calculate consistency score
    #     consistency = type_counts[dominant_type]['count'] / len(self.classification_history)
    #
    #     # Calculate average confidence for dominant type
    #     avg_confidence = (type_counts[dominant_type]['confidence_sum'] /
    #                       type_counts[dominant_type]['count'])
    #
    #     return {
    #         'type': dominant_type,
    #         'confidence': avg_confidence,
    #         'consistency': consistency,
    #         'type_distribution': {k: v['count'] for k, v in type_counts.items()},
    #         'memristive_percentage': (type_counts.get('memristive', {}).get('count', 0) /
    #                                   len(self.classification_history) * 100)
    #     }

    def _classify_device_overall_improved(self):
        """Enhanced device classification with temporal analysis"""
        if not self.classification_history:
            return {'type': 'unknown', 'confidence': 0, 'consistency': 0}

        #todo something in here needs sorting to detrmin memristive devices and stuff not sure how yet
        
        # Temporal analysis - check if device behavior changes over time
        early_sweeps = self.classification_history[:len(self.classification_history) // 3]
        late_sweeps = self.classification_history[-len(self.classification_history) // 3:]

        early_types = [s['type'] for s in early_sweeps]
        late_types = [s['type'] for s in late_sweeps]

        # Check for evolution
        evolution = {
            'early_dominant': max(set(early_types), key=early_types.count) if early_types else 'unknown',
            'late_dominant': max(set(late_types), key=late_types.count) if late_types else 'unknown',
            'evolved': False
        }

        if evolution['early_dominant'] != evolution['late_dominant']:
            evolution['evolved'] = True
            pass

        # Weight recent sweeps more heavily
        weighted_scores = {}
        for i, classification in enumerate(self.classification_history):
            weight = 1 + (i / len(self.classification_history))  # Linear increase
            device_type = classification['type']
            confidence = classification['confidence']

            if device_type not in weighted_scores:
                weighted_scores[device_type] = 0
            weighted_scores[device_type] += weight * confidence

        # Determine final type
        dominant_type = max(weighted_scores.items(), key=lambda x: x[1])[0]

        # Calculate metrics
        type_counts = {}
        for clf in self.classification_history:
            type_counts[clf['type']] = type_counts.get(clf['type'], 0) + 1

        return {
            'type': dominant_type,
            'confidence': weighted_scores[dominant_type] / sum(weighted_scores.values()),
            'consistency': type_counts.get(dominant_type, 0) / len(self.classification_history),
            'type_distribution': type_counts,
            'memristive_percentage': (type_counts.get('memristive', 0) /
                                      len(self.classification_history) * 100),
            'evolution': evolution
        }

    def _calculate_trends(self, evolution):
        """Calculate trends in device parameters"""
        trends = {}

        for param, values in evolution.items():
            if param.endswith('_evolution') and values:
                clean_values = [v for v in values if not np.isnan(v)]
                if len(clean_values) > 1:
                    # Linear regression for trend
                    x = np.arange(len(clean_values))
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, clean_values)

                    trends[param] = {
                        'slope': slope,
                        'r_squared': r_value ** 2,
                        'p_value': p_value,
                        'trend': 'increasing' if slope > 0 else 'decreasing',
                        'significant': p_value < 0.05
                    }

        return trends

    def _calculate_stability_scores(self, evolution):
        """Calculate stability scores for key parameters"""
        stability_scores = {}

        for param, values in evolution.items():
            if param.endswith('_evolution') and values:
                clean_values = [v for v in values if not np.isnan(v)]
                if len(clean_values) > 1:
                    # Coefficient of variation as stability metric
                    cv = np.std(clean_values) / np.mean(clean_values) if np.mean(clean_values) != 0 else np.inf
                    stability_scores[param] = {
                        'cv': cv,
                        'stability': 1 / (1 + cv),  # Convert to 0-1 score
                        'std': np.std(clean_values),
                        'mean': np.mean(clean_values)
                    }

        return stability_scores

    def _generate_performance_summary(self, results):
        """Generate comprehensive performance summary"""
        summary = {
            'device_id': f"{self.section}-{self.device_num}",
            'total_sweeps': len(results['sweep_analyses']),
            'memristive_sweeps': sum(1 for s in results['sweep_analyses'].values()
                                     if s['classification']['device_type'] == 'memristive'),
            'overall_classification': results['device_classification'],
            'key_metrics': {},
            'quality_score': 0
        }

        # Extract key metrics from memristive sweeps only
        memristive_analyses = [s for s in results['sweep_analyses'].values()
                               if s['classification']['device_type'] == 'memristive']

        if memristive_analyses:
            # Aggregate metrics
            ron_values = [s['summary_stats'].get('mean_ron', np.nan) for s in memristive_analyses]
            roff_values = [s['summary_stats'].get('mean_roff', np.nan) for s in memristive_analyses]
            ratio_values = [s['performance_metrics'].get('switching_ratio', np.nan) for s in memristive_analyses]

            summary['key_metrics'] = {
                'ron': {
                    'mean': np.nanmean(ron_values),
                    'std': np.nanstd(ron_values),
                    'min': np.nanmin(ron_values),
                    'max': np.nanmax(ron_values)
                },
                'roff': {
                    'mean': np.nanmean(roff_values),
                    'std': np.nanstd(roff_values),
                    'min': np.nanmin(roff_values),
                    'max': np.nanmax(roff_values)
                },
                'switching_ratio': {
                    'mean': np.nanmean(ratio_values),
                    'std': np.nanstd(ratio_values),
                    'min': np.nanmin(ratio_values),
                    'max': np.nanmax(ratio_values)
                }
            }

            # Calculate quality score
            summary['quality_score'] = self._calculate_quality_score(summary, results)

        return summary

    def _calculate_quality_score(self, summary, results):
        """Calculate overall device quality score (0-100)"""
        scores = []

        # Memristive percentage score (0-40 points)
        memristive_pct = results['device_classification']['memristive_percentage']
        scores.append(memristive_pct * 0.4)

        # Switching ratio score (0-30 points)
        if 'switching_ratio' in summary['key_metrics']:
            mean_ratio = summary['key_metrics']['switching_ratio']['mean']
            ratio_score = min(30, (np.log10(mean_ratio) / 3) * 30) if mean_ratio > 1 else 0
            scores.append(ratio_score)

        # Stability score (0-30 points)
        evolution = results['evolution_metrics']
        if 'stability_scores' in evolution:
            stability_values = [s['stability'] for s in evolution['stability_scores'].values()
                                if 'stability' in s]
            if stability_values:
                avg_stability = np.mean(stability_values)
                scores.append(avg_stability * 30)

        return sum(scores)

    def read_data_file(self, file_path):
        """Read data file with error handling"""
        try:
            data = np.loadtxt(file_path, skiprows=1)
            return data[:, 0], data[:, 1], data[:, 2] if data.shape[1] > 2 else None
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None, None, None


class EnhancedSectionAnalyzer:
    """Enhanced section analyzer with comprehensive multi-sweep analysis"""

    def __init__(self, section_path, sample_name, section):
        self.section_path = Path(section_path)
        self.sample_name = sample_name
        self.section = section
        self.device_results = {}

    # def analyze_section_comprehensive(self):
    #     """Analyze all devices in section with full sweep analysis"""
    #     results = {
    #         'device_analyses': {},
    #         'section_statistics': {},
    #         'quality_metrics': {},
    #         'comparative_analysis': {}
    #     }
    #
    #     # Get all device folders
    #     device_folders = sorted([d for d in self.section_path.glob('[1-9]*')
    #                              if d.is_dir()],
    #                             key=lambda x: int(x.name))
    #
    #     # TEMPORARY: Disable parallel processing for debugging
    #     DEBUG = True  # Set to False to re-enable parallel processing
    #
    #     if DEBUG:
    #         # Sequential processing for debugging
    #         for device_folder in device_folders:
    #             device_num = int(device_folder.name)
    #             print(f"Analyzing device {device_num} at {device_folder}")
    #             try:
    #                 analyzer = ComprehensiveDeviceAnalyzer(
    #                     device_folder, self.sample_name, self.section, device_num
    #                 )
    #                 device_results = analyzer.analyze_all_sweeps()
    #                 results['device_analyses'][device_num] = device_results
    #             except Exception as e:
    #                 print(f"Error analyzing device {device_num} at path {device_folder}")
    #                 import traceback
    #                 traceback.print_exc()
    #                 # Still add minimal results
    #                 results['device_analyses'][device_num] = {
    #                     # ... minimal error results as above ...
    #                 }
    #     else:
    #
    #         # Analyze each device using parallel processing
    #         with ProcessPoolExecutor(max_workers=4) as executor:
    #             future_to_device_info = {}  # Store both device_num and device_folder
    #
    #             for device_folder in device_folders:
    #                 device_num = int(device_folder.name)
    #                 analyzer = ComprehensiveDeviceAnalyzer(
    #                     device_folder, self.sample_name, self.section, device_num
    #                 )
    #                 future = executor.submit(analyzer.analyze_all_sweeps)
    #                 # Store both device number and folder path
    #                 future_to_device_info[future] = (device_num, device_folder)
    #
    #             # Collect results
    #             for future in as_completed(future_to_device_info):
    #                 device_num, device_folder = future_to_device_info[future]  # Get both values
    #                 try:
    #                     device_results = future.result()
    #                     results['device_analyses'][device_num] = device_results
    #                 except Exception as e:
    #                     print(f"Error analyzing device {device_num} at path {device_folder}: {e}")
    #                     # Add a minimal result for failed devices
    #                     results['device_analyses'][device_num] = {
    #                         'sweep_analyses': {},
    #                         'evolution_metrics': {},
    #                         'device_classification': {
    #                             'type': 'error',
    #                             'confidence': 0,
    #                             'consistency': 0,
    #                             'type_distribution': {},
    #                             'memristive_percentage': 0
    #                         },
    #                         'performance_summary': {
    #                             'device_id': f"{self.section}-{device_num}",
    #                             'total_sweeps': 0,
    #                             'memristive_sweeps': 0,
    #                             'overall_classification': {'type': 'error', 'confidence': 0},
    #                             'key_metrics': {},
    #                             'quality_score': 0,
    #                             'error': str(e)
    #                         }
    #                     }
    #
    #         # Generate section-level statistics (handle empty or error results)
    #         if results['device_analyses']:
    #             results['section_statistics'] = self._generate_section_statistics(results['device_analyses'])
    #             results['quality_metrics'] = self._calculate_section_quality_metrics(results)
    #             results['comparative_analysis'] = self._perform_comparative_analysis(results['device_analyses'])
    #         else:
    #             # Provide default values if no devices were successfully analyzed
    #             results['section_statistics'] = {
    #                 'total_devices': len(device_folders),
    #                 'working_devices': 0,
    #                 'memristive_devices': 0,
    #                 'device_type_distribution': {},
    #                 'performance_statistics': {},
    #                 'evolution_patterns': {},
    #                 'quality_score_distribution': {
    #                     'mean': 0,
    #                     'std': 0,
    #                     'median': 0,
    #                     'min': 0,
    #                     'max': 0
    #                 }
    #             }
    #             results['quality_metrics'] = {
    #                 'yield': 0,
    #                 'memristive_yield': 0,
    #                 'uniformity_scores': {},
    #                 'reliability_scores': {},
    #                 'overall_section_score': 0
    #             }
    #             results['comparative_analysis'] = {
    #                 'performance_correlations': {},
    #                 'device_clustering': {},
    #                 'outlier_analysis': {},
    #                 'trend_analysis': {}
    #             }
    #
    #         return results

    def analyze_section_comprehensive(self):
        """Analyze all devices in section with full sweep analysis"""
        # Initialize results with default structure
        results = {
            'device_analyses': {},
            'section_statistics': {
                'total_devices': 0,
                'working_devices': 0,
                'memristive_devices': 0,
                'device_type_distribution': {},
                'performance_statistics': {},
                'evolution_patterns': {},
                'quality_score_distribution': {
                    'mean': 0,
                    'std': 0,
                    'median': 0,
                    'min': 0,
                    'max': 0
                }
            },
            'quality_metrics': {
                'yield': 0,
                'memristive_yield': 0,
                'uniformity_scores': {},
                'reliability_scores': {},
                'overall_section_score': 0
            },
            'comparative_analysis': {
                'performance_correlations': {},
                'device_clustering': {},
                'outlier_analysis': {},
                'trend_analysis': {}
            }
        }

        try:
            # Get all device folders
            device_folders = sorted([d for d in self.section_path.glob('[1-9]*')
                                     if d.is_dir()],
                                    key=lambda x: int(x.name))

            if not device_folders:
                print(f"No device folders found in section {self.section}")
                return results  # Return default structure

            # Update total devices count
            results['section_statistics']['total_devices'] = len(device_folders)

            # Analyze each device using parallel processing
            with ProcessPoolExecutor(max_workers=4) as executor:
                future_to_device_info = {}

                for device_folder in device_folders:
                    device_num = int(device_folder.name)
                    analyzer = ComprehensiveDeviceAnalyzer(
                        device_folder, self.sample_name, self.section, device_num
                    )
                    future = executor.submit(analyzer.analyze_all_sweeps)
                    future_to_device_info[future] = (device_num, device_folder)

                # Collect results
                for future in as_completed(future_to_device_info):
                    device_num, device_folder = future_to_device_info[future]
                    try:
                        device_results = future.result()
                        if device_results:  # Only add if we got valid results
                            results['device_analyses'][device_num] = device_results
                    except Exception as e:
                        print(f"Error analyzing device {device_num} at path {device_folder}: {e}")
                        # Continue without adding failed device

            # Generate section-level statistics only if we have device analyses
            if results['device_analyses']:
                try:
                    results['section_statistics'] = self._generate_section_statistics(results['device_analyses'])
                except Exception as e:
                    print(f"Error generating section statistics: {e}")
                    # Keep default statistics

                try:
                    results['quality_metrics'] = self._calculate_section_quality_metrics(results)
                except Exception as e:
                    print(f"Error calculating quality metrics: {e}")
                    # Keep default metrics

                try:
                    results['comparative_analysis'] = self._perform_comparative_analysis(results['device_analyses'])
                except Exception as e:
                    print(f"Error performing comparative analysis: {e}")
                    # Keep default analysis
            else:
                print(f"No devices successfully analyzed in section {self.section}")

            return results

        except Exception as e:
            print(f"Critical error in analyze_section_comprehensive: {e}")
            import traceback
            traceback.print_exc()
            return results  # Return default structure even on critical error


    def _generate_section_statistics(self, device_analyses):
        """Generate statistics across all devices in section"""
        stats = {
            'total_devices': len(device_analyses),
            'working_devices': 0,
            'memristive_devices': 0,
            'device_type_distribution': {},
            'performance_statistics': {},
            'evolution_patterns': {}
        }

        # Collect data from all devices
        all_ron = []
        all_roff = []
        all_ratios = []
        all_quality_scores = []

        for device_num, analysis in device_analyses.items():
            # Count working devices
            if analysis['performance_summary']['total_sweeps'] > 0:
                stats['working_devices'] += 1

            # Count memristive devices
            if analysis['device_classification']['type'] == 'memristive':
                stats['memristive_devices'] += 1

            # Track device type distribution
            device_type = analysis['device_classification']['type']
            if device_type not in stats['device_type_distribution']:
                stats['device_type_distribution'][device_type] = 0
            stats['device_type_distribution'][device_type] += 1

            # Collect performance metrics
            if 'key_metrics' in analysis['performance_summary']:
                metrics = analysis['performance_summary']['key_metrics']
                if 'ron' in metrics and 'mean' in metrics['ron']:
                    if not np.isnan(metrics['ron']['mean']):
                        all_ron.append(metrics['ron']['mean'])
                if 'roff' in metrics and 'mean' in metrics['roff']:
                    if not np.isnan(metrics['roff']['mean']):
                        all_roff.append(metrics['roff']['mean'])
                if 'switching_ratio' in metrics and 'mean' in metrics['switching_ratio']:
                    if not np.isnan(metrics['switching_ratio']['mean']):
                        all_ratios.append(metrics['switching_ratio']['mean'])

            all_quality_scores.append(analysis['performance_summary']['quality_score'])

        # Calculate section-wide statistics with CV
        if all_ron:
            mean_ron = np.nanmean(all_ron)
            std_ron = np.nanstd(all_ron)
            stats['performance_statistics']['ron'] = {
                'mean': mean_ron,
                'std': std_ron,
                'median': np.nanmedian(all_ron),
                'cv': std_ron / abs(mean_ron) if mean_ron != 0 else float('inf')
            }

        if all_roff:
            mean_roff = np.nanmean(all_roff)
            std_roff = np.nanstd(all_roff)
            stats['performance_statistics']['roff'] = {
                'mean': mean_roff,
                'std': std_roff,
                'median': np.nanmedian(all_roff),
                'cv': std_roff / abs(mean_roff) if mean_roff != 0 else float('inf')
            }

        if all_ratios:
            mean_ratio = np.nanmean(all_ratios)
            std_ratio = np.nanstd(all_ratios)
            stats['performance_statistics']['switching_ratio'] = {
                'mean': mean_ratio,
                'std': std_ratio,
                'median': np.nanmedian(all_ratios),
                'min': np.nanmin(all_ratios),
                'max': np.nanmax(all_ratios),
                'cv': std_ratio / abs(mean_ratio) if mean_ratio != 0 else float('inf')
            }

        stats['quality_score_distribution'] = {
            'mean': np.mean(all_quality_scores),
            'std': np.std(all_quality_scores),
            'median': np.median(all_quality_scores),
            'min': np.min(all_quality_scores) if all_quality_scores else 0,
            'max': np.max(all_quality_scores) if all_quality_scores else 0
        }

        return stats

    def _calculate_section_quality_metrics(self, results):
        """Calculate comprehensive quality metrics for the section"""
        metrics = {
            'yield': results['section_statistics']['working_devices'] / results['section_statistics'][
                'total_devices'] * 100 if results['section_statistics']['total_devices'] > 0 else 0,
            'memristive_yield': results['section_statistics']['memristive_devices'] / results['section_statistics'][
                'total_devices'] * 100 if results['section_statistics']['total_devices'] > 0 else 0,
            'uniformity_scores': {},
            'reliability_scores': {},
            'overall_section_score': 0
        }

        # Calculate uniformity scores
        perf_stats = results['section_statistics']['performance_statistics']

        for param in ['ron', 'roff', 'switching_ratio']:
            if param in perf_stats:
                # Check if 'cv' exists, if not calculate it
                if 'cv' in perf_stats[param]:
                    cv = perf_stats[param]['cv']
                else:
                    # Calculate CV from mean and std if available
                    mean_val = perf_stats[param].get('mean', 0)
                    std_val = perf_stats[param].get('std', 0)
                    if mean_val != 0:
                        cv = std_val / abs(mean_val)
                    else:
                        cv = float('inf')

                # Convert CV to uniformity score (0-1, where 1 is perfectly uniform)
                metrics['uniformity_scores'][param] = 1 / (1 + cv)

        # Calculate reliability scores based on device evolution
        reliability_scores = []
        for device_analysis in results['device_analyses'].values():
            evolution = device_analysis.get('evolution_metrics', {})
            if 'stability_scores' in evolution:
                stability_values = []
                for score_data in evolution['stability_scores'].values():
                    if isinstance(score_data, dict) and 'stability' in score_data:
                        stability_values.append(score_data['stability'])

                if stability_values:
                    device_reliability = np.mean(stability_values)
                    reliability_scores.append(device_reliability)

        if reliability_scores:
            metrics['reliability_scores'] = {
                'mean': np.mean(reliability_scores),
                'std': np.std(reliability_scores),
                'min': np.min(reliability_scores),
                'max': np.max(reliability_scores)
            }

        # Calculate overall section score
        score_components = []

        # Yield component (30%)
        if results['section_statistics']['total_devices'] > 0:
            score_components.append(metrics['yield'] * 0.3)

        # Memristive yield component (30%)
        if results['section_statistics']['total_devices'] > 0:
            score_components.append(metrics['memristive_yield'] * 0.3)

        # Uniformity component (20%)
        if metrics['uniformity_scores']:
            uniformity_avg = np.mean(list(metrics['uniformity_scores'].values()))
            score_components.append(uniformity_avg * 100 * 0.2)

        # Reliability component (20%)
        if 'reliability_scores' in metrics and 'mean' in metrics['reliability_scores']:
            score_components.append(metrics['reliability_scores']['mean'] * 100 * 0.2)

        metrics['overall_section_score'] = sum(score_components)

        return metrics

    def _perform_comparative_analysis(self, device_analyses):
        """Perform comparative analysis across devices"""
        comparative = {
            'performance_correlations': {},
            'device_clustering': {},
            'outlier_analysis': {},
            'trend_analysis': {}
        }

        # Create performance matrix for correlation analysis
        device_nums = sorted(device_analyses.keys())
        performance_matrix = []

        for device_num in device_nums:
            device_data = device_analyses[device_num]
            if 'key_metrics' in device_data['performance_summary']:
                metrics = device_data['performance_summary']['key_metrics']
                row = [
                    metrics.get('ron', {}).get('mean', np.nan),
                    metrics.get('roff', {}).get('mean', np.nan),
                    metrics.get('switching_ratio', {}).get('mean', np.nan),
                    device_data['performance_summary']['quality_score']
                ]
                performance_matrix.append(row)

        if performance_matrix:
            # Calculate correlations
            perf_df = pd.DataFrame(performance_matrix,
                                   columns=['ron', 'roff', 'switching_ratio', 'quality_score'])
            comparative['performance_correlations'] = perf_df.corr().to_dict()

            # Identify outliers using IQR method
            for col in perf_df.columns:
                Q1 = perf_df[col].quantile(0.25)
                Q3 = perf_df[col].quantile(0.75)
                IQR = Q3 - Q1
                outliers = perf_df[(perf_df[col] < Q1 - 1.5 * IQR) | (perf_df[col] > Q3 + 1.5 * IQR)]
                if not outliers.empty:
                    comparative['outlier_analysis'][col] = {
                        'outlier_devices': [device_nums[i] for i in outliers.index],
                        'outlier_values': outliers[col].tolist()
                    }

        return comparative


class ComprehensiveSampleAnalyzer:
    """Main analyzer for complete sample analysis with PDF reporting"""

    def __init__(self, top_level_path):
        self.top_level_path = Path(top_level_path)
        self.sections = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']
        self.sample_results = {}

    def analyze_sample_comprehensive(self, sample_name):
        """Perform comprehensive analysis of entire sample"""
        sample_path = self.top_level_path / sample_name
        if not sample_path.exists():
            print(f"Sample {sample_name} not found")
            return None

        # Create output directory
        output_dir = sample_path / 'comprehensive_analysis'
        output_dir.mkdir(exist_ok=True)

        results = {
            'sample_name': sample_name,
            'analysis_timestamp': datetime.now().isoformat(),
            'section_analyses': {},
            'sample_statistics': {},
            'comparative_analysis': {},
            'quality_assessment': {}
        }

        try:
            # Analyze each section
            for section in self.sections:
                section_path = sample_path / section
                if section_path.exists():
                    print(f"Analyzing section {section}...")
                    try:
                        analyzer = EnhancedSectionAnalyzer(section_path, sample_name, section)
                        section_results = analyzer.analyze_section_comprehensive()
                        results['section_analyses'][section] = section_results
                    except Exception as e:
                        print(f"Error analyzing section {section}: {e}")
                        continue

            # Only proceed with aggregated analysis if we have section data
            if results['section_analyses']:
                # Generate sample-level statistics
                results['sample_statistics'] = self._generate_sample_statistics(results['section_analyses'])

                # Perform cross-section analysis
                results['comparative_analysis'] = self._perform_cross_section_analysis(results['section_analyses'])

                # Generate quality assessment
                results['quality_assessment'] = self._generate_quality_assessment(results)
            else:
                # Provide default values if no sections were analyzed
                results['sample_statistics'] = {
                    'total_sections_analyzed': 0,
                    'total_devices': 0,
                    'total_working_devices': 0,
                    'total_memristive_devices': 0,
                    'overall_sample_score': 0
                }
                results['quality_assessment'] = {
                    'overall_grade': 'F - No data available',
                    'strengths': [],
                    'weaknesses': ['No sections could be analyzed'],
                    'recommendations': ['Check data availability'],
                    'suitability_scores': {
                        'neuromorphic_computing': 0,
                        'memory_applications': 0,
                        'logic_applications': 0,
                        'analog_computing': 0
                    }
                }

            # Generate comprehensive PDF report
            try:
                self._generate_pdf_report(results, output_dir / f'{sample_name}_comprehensive_report.pdf')
            except Exception as e:
                print(f"Error generating PDF report: {e}")

            # Save raw results
            try:
                with open(output_dir / 'analysis_results.json', 'w') as f:
                    json_safe_results = self._convert_to_json_serializable(results)
                    json.dump(json_safe_results, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not save JSON file: {e}")
                try:
                    import pickle
                    with open(output_dir / 'analysis_results.pkl', 'wb') as f:
                        pickle.dump(results, f)
                    print("Saved results as pickle file instead")
                except Exception as e2:
                    print(f"Could not save results file: {e2}")

            return results

        except Exception as e:
            print(f"Critical error in analysis: {e}")
            import traceback
            traceback.print_exc()

            # Return minimal results
            return {
                'sample_name': sample_name,
                'analysis_timestamp': datetime.now().isoformat(),
                'section_analyses': {},
                'sample_statistics': {
                    'total_sections_analyzed': 0,
                    'total_devices': 0,
                    'total_working_devices': 0,
                    'total_memristive_devices': 0,
                    'overall_sample_score': 0
                },
                'quality_assessment': {
                    'overall_grade': 'F - Analysis failed',
                    'strengths': [],
                    'weaknesses': ['Analysis failed'],
                    'recommendations': ['Debug the analysis code'],
                    'suitability_scores': {
                        'neuromorphic_computing': 0,
                        'memory_applications': 0,
                        'logic_applications': 0,
                        'analog_computing': 0
                    }
                },
                'comparative_analysis': {},
                'error': str(e)
            }

    def _generate_sample_statistics(self, section_analyses):
        """Generate sample-wide statistics"""
        stats = {
            'total_sections_analyzed': 0,
            'total_devices': 0,
            'total_working_devices': 0,
            'total_memristive_devices': 0,
            'section_performance': {},
            'best_section': None,
            'worst_section': None,
            'overall_sample_score': 0
        }

        section_scores = {}

        for section, analysis in section_analyses.items():
            # Skip if analysis is None or invalid
            if analysis is None:
                print(f"Warning: Section {section} analysis is None, skipping")
                continue

            # Validate that analysis has required keys
            if not isinstance(analysis, dict):
                print(f"Warning: Section {section} analysis is not a dictionary, skipping")
                continue

            if 'section_statistics' not in analysis:
                print(f"Warning: Section {section} missing section_statistics, skipping")
                continue

            section_stats = analysis['section_statistics']

            # Check if section_stats is valid
            if section_stats is None or not isinstance(section_stats, dict):
                print(f"Warning: Section {section} has invalid section_statistics, skipping")
                continue

            # Now safely process the statistics
            stats['total_sections_analyzed'] += 1
            stats['total_devices'] += section_stats.get('total_devices', 0)
            stats['total_working_devices'] += section_stats.get('working_devices', 0)
            stats['total_memristive_devices'] += section_stats.get('memristive_devices', 0)

            # Get quality metrics
            if 'quality_metrics' in analysis and analysis['quality_metrics']:
                quality_metrics = analysis['quality_metrics']
                section_score = quality_metrics.get('overall_section_score', 0)
                section_scores[section] = section_score

                stats['section_performance'][section] = {
                    'score': section_score,
                    'yield': quality_metrics.get('yield', 0),
                    'memristive_yield': quality_metrics.get('memristive_yield', 0),
                    'mean_quality_score': section_stats.get('quality_score_distribution', {}).get('mean', 0)
                }
            else:
                # Default values if quality metrics missing
                stats['section_performance'][section] = {
                    'score': 0,
                    'yield': 0,
                    'memristive_yield': 0,
                    'mean_quality_score': 0
                }
                section_scores[section] = 0

        # Identify best and worst sections only if we have valid scores
        if section_scores:
            stats['best_section'] = max(section_scores.items(), key=lambda x: x[1])
            stats['worst_section'] = min(section_scores.items(), key=lambda x: x[1])
            stats['overall_sample_score'] = np.mean(list(section_scores.values()))
        else:
            print("Warning: No valid section scores found")
            stats['overall_sample_score'] = 0

        return stats

    def _perform_cross_section_analysis(self, section_analyses):
        """Analyze patterns across sections"""
        analysis = {
            'parameter_variations': {},
            'section_correlations': {},
            'spatial_patterns': {}
        }

        # Collect metrics from all sections
        section_metrics = {}
        for section, section_analysis in section_analyses.items():
            if 'performance_statistics' in section_analysis['section_statistics']:
                perf_stats = section_analysis['section_statistics']['performance_statistics']
                section_metrics[section] = {
                    'ron_mean': perf_stats.get('ron', {}).get('mean', np.nan),
                    'roff_mean': perf_stats.get('roff', {}).get('mean', np.nan),
                    'ratio_mean': perf_stats.get('switching_ratio', {}).get('mean', np.nan),
                    'yield': section_analysis['quality_metrics']['yield']
                }

        # Calculate variations
        if section_metrics:
            metrics_df = pd.DataFrame.from_dict(section_metrics, orient='index')

            for column in metrics_df.columns:
                values = metrics_df[column].dropna()
                if len(values) > 1:
                    analysis['parameter_variations'][column] = {
                        'cv': values.std() / values.mean() if values.mean() != 0 else np.inf,
                        'range': values.max() - values.min(),
                        'std': values.std()
                    }

            # Calculate correlations between sections
            analysis['section_correlations'] = metrics_df.corr().to_dict()

        # Analyze spatial patterns (top vs bottom rows)
        top_sections = ['A', 'B', 'D', 'E', 'F']
        bottom_sections = ['G', 'H', 'I', 'K', 'L']

        top_scores = [section_analyses[s]['quality_metrics']['overall_section_score']
                      for s in top_sections if s in section_analyses]
        bottom_scores = [section_analyses[s]['quality_metrics']['overall_section_score']
                         for s in bottom_sections if s in section_analyses]

        if top_scores and bottom_scores:
            analysis['spatial_patterns'] = {
                'top_mean_score': np.mean(top_scores),
                'bottom_mean_score': np.mean(bottom_scores),
                'spatial_uniformity': 1 - abs(np.mean(top_scores) - np.mean(bottom_scores)) / 100
            }

        return analysis

    def _generate_quality_assessment(self, results):
        """Generate overall quality assessment"""
        assessment = {
            'overall_grade': '',
            'strengths': [],
            'weaknesses': [],
            'recommendations': [],
            'suitability_scores': {}
        }

        try:
            # Determine overall grade
            overall_score = results['sample_statistics'].get('overall_sample_score', 0)
            if overall_score >= 80:
                assessment['overall_grade'] = 'A - Excellent'
            elif overall_score >= 70:
                assessment['overall_grade'] = 'B - Good'
            elif overall_score >= 60:
                assessment['overall_grade'] = 'C - Satisfactory'
            elif overall_score >= 50:
                assessment['overall_grade'] = 'D - Fair'
            else:
                assessment['overall_grade'] = 'F - Poor'

            # Identify strengths
            stats = results['sample_statistics']
            total_devices = stats.get('total_devices', 1)

            if total_devices > 0:
                memristive_ratio = stats.get('total_memristive_devices', 0) / total_devices
                if memristive_ratio > 0.7:
                    assessment['strengths'].append('High memristive device yield')

            best_section = stats.get('best_section')
            if best_section and len(best_section) > 1 and best_section[1] > 80:
                assessment['strengths'].append(f'Excellent performance in section {best_section[0]}')

            # Identify weaknesses
            worst_section = stats.get('worst_section')
            if worst_section and len(worst_section) > 1 and worst_section[1] < 50:
                assessment['weaknesses'].append(f'Poor performance in section {worst_section[0]}')

            variations = results.get('comparative_analysis', {}).get('parameter_variations', {})
            if variations:
                for param, var_stats in variations.items():
                    if isinstance(var_stats, dict) and 'cv' in var_stats:
                        cv = var_stats['cv']
                        if not np.isnan(cv) and not np.isinf(cv) and cv > 0.5:
                            assessment['weaknesses'].append(f'High variability in {param}')

            # Generate recommendations
            if total_devices > 0 and stats.get('total_memristive_devices', 0) / total_devices < 0.5:
                assessment['recommendations'].append('Optimize fabrication process to increase memristive yield')

            if variations.get('switching_ratio', {}).get('cv', 0) > 0.3:
                assessment['recommendations'].append('Improve process uniformity to reduce switching ratio variations')

            # Calculate suitability scores with error handling
            try:
                assessment['suitability_scores']['neuromorphic_computing'] = self._calculate_neuromorphic_suitability(
                    results)
            except Exception as e:
                print(f"Error calculating neuromorphic suitability: {e}")
                assessment['suitability_scores']['neuromorphic_computing'] = 0

            try:
                assessment['suitability_scores']['memory_applications'] = self._calculate_memory_suitability(results)
            except Exception as e:
                print(f"Error calculating memory suitability: {e}")
                assessment['suitability_scores']['memory_applications'] = 0

            try:
                assessment['suitability_scores']['logic_applications'] = self._calculate_logic_suitability(results)
            except Exception as e:
                print(f"Error calculating logic suitability: {e}")
                assessment['suitability_scores']['logic_applications'] = 0

            try:
                assessment['suitability_scores']['analog_computing'] = self._calculate_analog_suitability(results)
            except Exception as e:
                print(f"Error calculating analog suitability: {e}")
                assessment['suitability_scores']['analog_computing'] = 0

        except Exception as e:
            print(f"Error in quality assessment generation: {e}")
            # Return default assessment
            assessment = {
                'overall_grade': 'F - Assessment Error',
                'strengths': [],
                'weaknesses': ['Quality assessment failed'],
                'recommendations': ['Debug assessment code'],
                'suitability_scores': {
                    'neuromorphic_computing': 0,
                    'memory_applications': 0,
                    'logic_applications': 0,
                    'analog_computing': 0
                }
            }

        return assessment

    def _calculate_neuromorphic_suitability(self, results):
        """Calculate suitability score for neuromorphic applications"""
        score = 0
        weights = {
            'analog_switching': 0.3,
            'retention': 0.2,
            'endurance': 0.2,
            'low_power': 0.2,
            'uniformity': 0.1
        }

        # Check for analog switching behavior
        analog_devices = 0
        total_memristive = 0

        for section_analysis in results['section_analyses'].values():
            if section_analysis is None or 'device_analyses' not in section_analysis:
                continue

            for device_analysis in section_analysis['device_analyses'].values():
                if device_analysis is None:
                    continue

                if device_analysis.get('device_classification', {}).get('type') == 'memristive':
                    total_memristive += 1
                    # Check if device shows gradual switching (multiple resistance states)
                    sweep_analyses = device_analysis.get('sweep_analyses', {})
                    resistance_states = set()

                    for sweep in sweep_analyses.values():
                        if sweep is None or 'summary_stats' not in sweep:
                            continue

                        summary_stats = sweep.get('summary_stats', {})
                        if summary_stats:
                            ron = summary_stats.get('mean_ron')
                            if ron is not None and not np.isnan(ron) and ron > 0:
                                try:
                                    # Round to significant figures
                                    if ron >= 1:
                                        # For values >= 1, round to nearest order of magnitude
                                        order = int(np.log10(ron))
                                        rounded = round(ron, -order + 1)
                                    else:
                                        # For values < 1, round to 3 significant figures
                                        rounded = round(ron, 3)
                                    resistance_states.add(rounded)
                                except (ValueError, OverflowError):
                                    # Skip problematic values
                                    continue

                    if len(resistance_states) > 3:  # Multiple distinct states
                        analog_devices += 1

        if total_memristive > 0:
            score += weights['analog_switching'] * (analog_devices / total_memristive) * 100

        # Add other scoring components based on available metrics
        overall_quality = results['sample_statistics'].get('overall_sample_score', 0)
        score += weights['uniformity'] * overall_quality * 0.01

        # Estimate other components (would need more specific metrics in real implementation)
        score += weights['retention'] * 50  # Placeholder
        score += weights['endurance'] * 50  # Placeholder
        score += weights['low_power'] * 50  # Placeholder

        return min(100, score)

    def _calculate_memory_suitability(self, results):
        """Calculate suitability score for memory applications"""
        score = 0
        weights = {
            'switching_ratio': 0.4,
            'retention': 0.3,
            'endurance': 0.2,
            'uniformity': 0.1
        }

        # High switching ratio is crucial for memory
        all_ratios = []
        for section_analysis in results['section_analyses'].values():
            if section_analysis is None:
                continue

            perf_stats = section_analysis.get('section_statistics', {}).get('performance_statistics', {})
            if 'switching_ratio' in perf_stats:
                mean_ratio = perf_stats['switching_ratio'].get('mean')
                if mean_ratio is not None and not np.isnan(mean_ratio) and mean_ratio > 0:
                    all_ratios.append(mean_ratio)

        if all_ratios:
            avg_ratio = np.mean(all_ratios)
            # Score based on log scale (ratio of 100 = 50 points, 1000 = 75 points, 10000 = 100 points)
            try:
                ratio_score = min(100, 25 * np.log10(max(1, avg_ratio)))
            except (ValueError, OverflowError):
                ratio_score = 0
            score += weights['switching_ratio'] * ratio_score

        # Uniformity
        variations = results.get('comparative_analysis', {}).get('parameter_variations', {})
        if variations and 'switching_ratio' in variations:
            cv = variations['switching_ratio'].get('cv', float('inf'))
            if not np.isnan(cv) and not np.isinf(cv):
                uniformity_score = 100 * (1 / (1 + cv))
                score += weights['uniformity'] * uniformity_score

        # Placeholder for retention and endurance
        score += weights['retention'] * 50
        score += weights['endurance'] * 50

        return min(100, score)

    def _calculate_logic_suitability(self, results):
        """Calculate suitability score for logic applications"""
        # Logic applications need fast, reliable switching
        score = 0

        # High yield is important
        total_devices = results['sample_statistics'].get('total_devices', 1)
        memristive_devices = results['sample_statistics'].get('total_memristive_devices', 0)

        if total_devices > 0:
            yield_score = (memristive_devices / total_devices) * 100
            score += yield_score * 0.5

        # Low variability is crucial
        variations = results.get('comparative_analysis', {}).get('parameter_variations', {})
        if variations:
            cv_values = []
            for var_data in variations.values():
                if isinstance(var_data, dict) and 'cv' in var_data:
                    cv = var_data['cv']
                    if not np.isnan(cv) and not np.isinf(cv):
                        cv_values.append(cv)

            if cv_values:
                avg_cv = np.mean(cv_values)
                variability_score = 100 * (1 / (1 + avg_cv))
                score += variability_score * 0.5

        return min(100, score)

    def _calculate_analog_suitability(self, results):
        """Calculate suitability score for analog computing"""
        # Similar to neuromorphic but with emphasis on linearity
        base_score = self._calculate_neuromorphic_suitability(results)

        # Adjust based on linearity metrics if available
        # For now, just scale down the neuromorphic score
        return base_score * 0.8

    def _generate_pdf_report(self, results, output_path):
        """Generate comprehensive PDF report"""
        with PdfPages(output_path) as pdf:
            # Title page
            self._create_title_page(pdf, results)

            # Executive summary
            self._create_executive_summary(pdf, results)

            # Sample overview
            self._create_sample_overview(pdf, results)

            # Section-by-section analysis
            for section in sorted(results['section_analyses'].keys()):
                self._create_section_analysis_pages(pdf, section, results['section_analyses'][section])

            # Comparative analysis
            self._create_comparative_analysis_pages(pdf, results)

            # Quality assessment and recommendations
            self._create_quality_assessment_page(pdf, results)

            # Detailed device summaries (appendix)
            self._create_device_summary_appendix(pdf, results)

    def _create_title_page(self, pdf, results):
        """Create title page for PDF report"""
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.5, 0.7, f"Comprehensive Memristor Analysis Report",
                 ha='center', va='center', fontsize=24, weight='bold')
        fig.text(0.5, 0.6, f"Sample: {results['sample_name']}",
                 ha='center', va='center', fontsize=18)
        fig.text(0.5, 0.5, f"Analysis Date: {results['analysis_timestamp'][:10]}",
                 ha='center', va='center', fontsize=14)

        # Add key metrics box
        stats = results['sample_statistics']
        metrics_text = f"""
            Total Devices Analyzed: {stats['total_devices']}
            Working Devices: {stats['total_working_devices']}
            Memristive Devices: {stats['total_memristive_devices']}
            Overall Quality Score: {stats['overall_sample_score']:.1f}/100
            Grade: {results['quality_assessment']['overall_grade']}
            """

        fig.text(0.5, 0.3, metrics_text, ha='center', va='center', fontsize=12,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray"))

        plt.axis('off')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_executive_summary(self, pdf, results):
        """Create executive summary page"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Executive Summary', fontsize=16, weight='bold')

        # 1. Section scores heatmap
        sections = sorted(results['section_analyses'].keys())
        scores = [results['section_analyses'][s]['quality_metrics']['overall_section_score']
                  for s in sections]

        # Reshape for 2x5 grid
        score_matrix = np.zeros((2, 5))
        section_map = {
            'A': (0, 0), 'B': (0, 1), 'D': (0, 2), 'E': (0, 3), 'F': (0, 4),
            'G': (1, 0), 'H': (1, 1), 'I': (1, 2), 'K': (1, 3), 'L': (1, 4)
        }

        for section, score in zip(sections, scores):
            if section in section_map:
                row, col = section_map[section]
                score_matrix[row, col] = score

        sns.heatmap(score_matrix, annot=True, fmt='.1f', cmap='RdYlGn',
                    vmin=0, vmax=100, ax=ax1,
                    xticklabels=['A/G', 'B/H', 'D/I', 'E/K', 'F/L'],
                    yticklabels=['Top', 'Bottom'])
        ax1.set_title('Section Quality Scores')

        # 2. Device type distribution
        type_counts = {}
        for section_analysis in results['section_analyses'].values():
            for device in section_analysis['device_analyses'].values():
                device_type = device['device_classification']['type']
                type_counts[device_type] = type_counts.get(device_type, 0) + 1

        if type_counts:
            ax2.pie(type_counts.values(), labels=type_counts.keys(), autopct='%1.1f%%')
            ax2.set_title('Device Type Distribution')

        # 3. Performance metrics comparison
        metrics_data = []
        metric_names = ['Ron', 'Roff', 'Ratio']

        for section in sections:
            perf_stats = results['section_analyses'][section]['section_statistics'].get('performance_statistics', {})
            if perf_stats:
                metrics_data.append([
                    perf_stats.get('ron', {}).get('mean', 0),
                    perf_stats.get('roff', {}).get('mean', 0),
                    perf_stats.get('switching_ratio', {}).get('mean', 0)
                ])

        if metrics_data:
            metrics_array = np.array(metrics_data).T
            x = np.arange(len(sections))
            width = 0.25

            for i, (metric_values, metric_name) in enumerate(zip(metrics_array, metric_names)):
                ax3.bar(x + i * width, metric_values, width, label=metric_name)

            ax3.set_xlabel('Section')
            ax3.set_xticks(x + width)
            ax3.set_xticklabels(sections)
            ax3.set_ylabel('Value')
            ax3.set_yscale('log')
            ax3.legend()
            ax3.set_title('Key Performance Metrics by Section')

        # 4. Application suitability scores
        suitability = results['quality_assessment']['suitability_scores']
        applications = list(suitability.keys())
        scores = list(suitability.values())

        ax4.barh(applications, scores)
        ax4.set_xlim(0, 100)
        ax4.set_xlabel('Suitability Score')
        ax4.set_title('Application Suitability Assessment')

        for i, (app, score) in enumerate(zip(applications, scores)):
            ax4.text(score + 1, i, f'{score:.1f}', va='center')

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_sample_overview(self, pdf, results):
        """Create sample overview visualizations"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Sample Overview', fontsize=16, weight='bold')

        # 1. Yield comparison across sections
        sections = sorted(results['section_analyses'].keys())
        yields = []
        mem_yields = []

        for section in sections:
            yields.append(results['section_analyses'][section]['quality_metrics']['yield'])
            mem_yields.append(results['section_analyses'][section]['quality_metrics']['memristive_yield'])

        x = np.arange(len(sections))
        width = 0.35

        ax1.bar(x - width / 2, yields, width, label='Working Devices')
        ax1.bar(x + width / 2, mem_yields, width, label='Memristive Devices')
        ax1.set_xlabel('Section')
        ax1.set_ylabel('Yield (%)')
        ax1.set_title('Device Yield by Section')
        ax1.set_xticks(x)
        ax1.set_xticklabels(sections)
        ax1.legend()
        ax1.set_ylim(0, 100)

        # 2. Quality score distribution
        all_quality_scores = []
        for section_analysis in results['section_analyses'].values():
            for device in section_analysis['device_analyses'].values():
                all_quality_scores.append(device['performance_summary']['quality_score'])

        ax2.hist(all_quality_scores, bins=20, edgecolor='black')
        ax2.set_xlabel('Quality Score')
        ax2.set_ylabel('Number of Devices')
        ax2.set_title('Device Quality Score Distribution')
        ax2.axvline(np.mean(all_quality_scores), color='red', linestyle='--',
                    label=f'Mean: {np.mean(all_quality_scores):.1f}')
        ax2.legend()

        # 3. Parameter variations across sample
        variations = results['comparative_analysis']['parameter_variations']
        if variations:
            params = list(variations.keys())
            cvs = [variations[p]['cv'] for p in params]

            ax3.bar(params, cvs)
            ax3.set_ylabel('Coefficient of Variation')
            ax3.set_title('Parameter Uniformity Across Sample')
            ax3.set_ylim(0, max(cvs) * 1.2)
            for i, cv in enumerate(cvs):
                ax3.text(i, cv + 0.01, f'{cv:.2f}', ha='center')

            # 4. Evolution trends summary
        trend_summary = {'improving': 0, 'degrading': 0, 'stable': 0}

        for section_analysis in results['section_analyses'].values():
            for device in section_analysis['device_analyses'].values():
                if 'trends' in device['evolution_metrics']:
                    for param, trend_data in device['evolution_metrics']['trends'].items():
                        if trend_data['significant']:
                            if trend_data['slope'] > 0.01:
                                trend_summary['improving'] += 1
                            elif trend_data['slope'] < -0.01:
                                trend_summary['degrading'] += 1
                            else:
                                trend_summary['stable'] += 1

        if sum(trend_summary.values()) > 0:
            ax4.pie(trend_summary.values(), labels=trend_summary.keys(), autopct='%1.1f%%')
            ax4.set_title('Device Evolution Trends')

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_section_analysis_pages(self, pdf, section, section_analysis):
        """Create detailed analysis pages for each section"""
        # Page 1: Section overview
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle(f'Section {section} Analysis', fontsize=16, weight='bold')

        # 1. Device performance scatter plot
        device_nums = []
        ron_values = []
        roff_values = []
        quality_scores = []

        for device_num, device_data in section_analysis['device_analyses'].items():
            device_nums.append(device_num)
            metrics = device_data['performance_summary'].get('key_metrics', {})
            ron_values.append(metrics.get('ron', {}).get('mean', np.nan))
            roff_values.append(metrics.get('roff', {}).get('mean', np.nan))
            quality_scores.append(device_data['performance_summary']['quality_score'])

        # Color by quality score
        scatter = ax1.scatter(ron_values, roff_values, c=quality_scores, cmap='viridis', s=100)
        ax1.set_xlabel('Ron (Ω)')
        ax1.set_ylabel('Roff (Ω)')
        ax1.set_xscale('log')
        ax1.set_yscale('log')
        ax1.set_title('Device Resistance States')

        # Add device labels
        for i, device_num in enumerate(device_nums):
            if not np.isnan(ron_values[i]) and not np.isnan(roff_values[i]):
                ax1.annotate(str(device_num), (ron_values[i], roff_values[i]),
                             xytext=(5, 5), textcoords='offset points')

        plt.colorbar(scatter, ax=ax1, label='Quality Score')

        # 2. Device classification breakdown
        type_counts = {}
        for device in section_analysis['device_analyses'].values():
            device_type = device['device_classification']['type']
            type_counts[device_type] = type_counts.get(device_type, 0) + 1

        ax2.bar(type_counts.keys(), type_counts.values())
        ax2.set_xlabel('Device Type')
        ax2.set_ylabel('Count')
        ax2.set_title('Device Classification')

        # 3. Evolution stability heatmap
        stability_matrix = []
        device_labels = []

        for device_num in sorted(section_analysis['device_analyses'].keys()):
            device_data = section_analysis['device_analyses'][device_num]
            if 'stability_scores' in device_data['evolution_metrics']:
                stability_scores = device_data['evolution_metrics']['stability_scores']
                row = []
                for param in ['ron_evolution', 'roff_evolution', 'switching_ratio_evolution']:
                    if param in stability_scores:
                        row.append(stability_scores[param]['stability'])
                    else:
                        row.append(np.nan)
                if row:
                    stability_matrix.append(row)
                    device_labels.append(f'D{device_num}')

        if stability_matrix:
            sns.heatmap(stability_matrix, xticklabels=['Ron', 'Roff', 'Ratio'],
                        yticklabels=device_labels, cmap='RdYlGn', vmin=0, vmax=1,
                        annot=True, fmt='.2f', ax=ax3)
            ax3.set_title('Parameter Stability Scores')

        # 4. Performance metrics distribution
        metrics_df = pd.DataFrame({
            'Device': device_nums,
            'Quality Score': quality_scores,
            'Ron': ron_values,
            'Roff': roff_values
        })

        ax4.boxplot([quality_scores], labels=['Quality Scores'])
        ax4.set_ylabel('Score')
        ax4.set_title(f'Section {section} Quality Distribution')
        ax4.set_ylim(0, 100)

        # Add statistics text
        stats_text = f"""
                Mean: {np.mean(quality_scores):.1f}
                Std: {np.std(quality_scores):.1f}
                Min: {np.min(quality_scores):.1f}
                Max: {np.max(quality_scores):.1f}
                """
        ax4.text(1.3, 50, stats_text, fontsize=10,
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

        # Page 2: Individual device evolution plots
        self._create_device_evolution_page(pdf, section, section_analysis)

    def _create_device_evolution_page(self, pdf, section, section_analysis):
        """Create page showing device evolution trends"""
        num_devices = len(section_analysis['device_analyses'])
        if num_devices == 0:
            return

        # Create grid of subplots
        rows = int(np.ceil(num_devices / 2))
        fig, axes = plt.subplots(rows, 2, figsize=(11, 8.5))
        fig.suptitle(f'Section {section} - Device Evolution', fontsize=16, weight='bold')

        if rows == 1:
            axes = axes.reshape(1, -1)

        device_nums = sorted(section_analysis['device_analyses'].keys())

        for idx, device_num in enumerate(device_nums):
            row = idx // 2
            col = idx % 2
            ax = axes[row, col]

            device_data = section_analysis['device_analyses'][device_num]
            evolution = device_data['evolution_metrics']

            # Plot switching ratio evolution
            if 'switching_ratio_evolution' in evolution:
                ratios = evolution['switching_ratio_evolution']
                valid_ratios = [r for r in ratios if not np.isnan(r)]
                if valid_ratios:
                    ax.plot(range(len(valid_ratios)), valid_ratios, 'o-')
                    ax.set_xlabel('Sweep Number')
                    ax.set_ylabel('Switching Ratio')
                    ax.set_title(f'Device {device_num}')
                    ax.set_yscale('log')

                    # Add trend line if significant
                    if 'trends' in evolution and 'switching_ratio_evolution' in evolution['trends']:
                        trend = evolution['trends']['switching_ratio_evolution']
                        if trend['significant']:
                            x = np.arange(len(valid_ratios))
                            y_trend = trend['slope'] * x + valid_ratios[0]
                            ax.plot(x, y_trend, 'r--', alpha=0.5,
                                    label=f"Trend: {trend['trend']}")
                            ax.legend()

        # Remove empty subplots
        for idx in range(num_devices, rows * 2):
            fig.delaxes(axes.flatten()[idx])

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_comparative_analysis_pages(self, pdf, results):
        """Create comparative analysis visualizations"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Cross-Section Comparative Analysis', fontsize=16, weight='bold')

        # 1. Performance correlation heatmap
        sections = sorted(results['section_analyses'].keys())
        performance_matrix = []

        for section in sections:
            row = []
            stats = results['section_analyses'][section]['section_statistics']
            perf_stats = stats.get('performance_statistics', {})

            row.append(perf_stats.get('ron', {}).get('mean', np.nan))
            row.append(perf_stats.get('roff', {}).get('mean', np.nan))
            row.append(perf_stats.get('switching_ratio', {}).get('mean', np.nan))
            row.append(results['section_analyses'][section]['quality_metrics']['overall_section_score'])

            performance_matrix.append(row)

        if performance_matrix:
            perf_df = pd.DataFrame(performance_matrix,
                                   columns=['Ron', 'Roff', 'Ratio', 'Score'],
                                   index=sections)
            corr_matrix = perf_df.corr()

            sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0,
                        vmin=-1, vmax=1, ax=ax1)
            ax1.set_title('Performance Metrics Correlation')

        # 2. Spatial uniformity analysis
        top_scores = []
        bottom_scores = []

        for section in sections:
            score = results['section_analyses'][section]['quality_metrics']['overall_section_score']
            if section in ['A', 'B', 'D', 'E', 'F']:
                top_scores.append(score)
            else:
                bottom_scores.append(score)

        positions = [1, 2]
        box_data = [top_scores, bottom_scores]
        ax2.boxplot(box_data, positions=positions, labels=['Top Row', 'Bottom Row'])
        ax2.set_ylabel('Quality Score')
        ax2.set_title('Spatial Uniformity Analysis')
        ax2.set_ylim(0, 100)

        # Add statistical test
        if len(top_scores) > 1 and len(bottom_scores) > 1:
            t_stat, p_value = stats.ttest_ind(top_scores, bottom_scores)
            ax2.text(1.5, 90, f'p-value: {p_value:.3f}', ha='center',
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow"))

        # 3. Parameter variation radar chart
        variations = results['comparative_analysis']['parameter_variations']
        if variations:
            categories = list(variations.keys())
            values = [1 / (1 + variations[cat]['cv']) for cat in categories]  # Convert to uniformity score

            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False)
            values = np.concatenate((values, [values[0]]))  # Complete the circle
            angles = np.concatenate((angles, [angles[0]]))

            ax3.plot(angles, values, 'o-', linewidth=2)
            ax3.fill(angles, values, alpha=0.25)
            ax3.set_xticks(angles[:-1])
            ax3.set_xticklabels(categories)
            ax3.set_ylim(0, 1)
            ax3.set_title('Parameter Uniformity Profile')
            ax3.grid(True)

        # 4. Best vs worst section comparison
        best_section = results['sample_statistics']['best_section']
        worst_section = results['sample_statistics']['worst_section']

        if best_section and worst_section:
            best_data = results['section_analyses'][best_section[0]]
            worst_data = results['section_analyses'][worst_section[0]]

            comparison_metrics = {
                'Quality Score': (best_section[1], worst_section[1]),
                'Yield (%)': (
                    best_data['quality_metrics']['yield'],
                    worst_data['quality_metrics']['yield']
                ),
                'Memristive Yield (%)': (
                    best_data['quality_metrics']['memristive_yield'],
                    worst_data['quality_metrics']['memristive_yield']
                )
            }

            x = np.arange(len(comparison_metrics))
            width = 0.35

            best_values = [v[0] for v in comparison_metrics.values()]
            worst_values = [v[1] for v in comparison_metrics.values()]

            ax4.bar(x - width / 2, best_values, width, label=f'Best ({best_section[0]})')
            ax4.bar(x + width / 2, worst_values, width, label=f'Worst ({worst_section[0]})')

            ax4.set_ylabel('Value')
            ax4.set_title('Best vs Worst Section Comparison')
            ax4.set_xticks(x)
            ax4.set_xticklabels(comparison_metrics.keys(), rotation=45, ha='right')
            ax4.legend()

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_quality_assessment_page(self, pdf, results):
        """Create quality assessment and recommendations page"""
        fig = plt.figure(figsize=(8.5, 11))
        fig.suptitle('Quality Assessment & Recommendations', fontsize=16, weight='bold')

        # Create text layout
        assessment = results['quality_assessment']

        y_position = 0.9
        line_height = 0.03

        # Overall grade
        fig.text(0.1, y_position, f"Overall Grade: {assessment['overall_grade']}",
                 fontsize=14, weight='bold')
        y_position -= line_height * 2

        # Strengths
        fig.text(0.1, y_position, "Strengths:", fontsize=12, weight='bold')
        y_position -= line_height

        for strength in assessment['strengths']:
            fig.text(0.15, y_position, f"• {strength}", fontsize=10)
            y_position -= line_height

        y_position -= line_height

        # Weaknesses
        fig.text(0.1, y_position, "Areas for Improvement:", fontsize=12, weight='bold')
        y_position -= line_height

        for weakness in assessment['weaknesses']:
            fig.text(0.15, y_position, f"• {weakness}", fontsize=10)
            y_position -= line_height

        y_position -= line_height

        # Recommendations
        fig.text(0.1, y_position, "Recommendations:", fontsize=12, weight='bold')
        y_position -= line_height

        for i, recommendation in enumerate(assessment['recommendations']):
            fig.text(0.15, y_position, f"{i + 1}. {recommendation}", fontsize=10)
            y_position -= line_height * 1.5

        # Application suitability visualization
        ax = fig.add_subplot(212)

        applications = list(assessment['suitability_scores'].keys())
        scores = list(assessment['suitability_scores'].values())

        # Create horizontal bar chart with color coding
        colors = ['green' if s >= 70 else 'yellow' if s >= 50 else 'red' for s in scores]
        bars = ax.barh(applications, scores, color=colors)

        ax.set_xlim(0, 100)
        ax.set_xlabel('Suitability Score')
        ax.set_title('Application Suitability Assessment')

        # Add score labels
        for bar, score in zip(bars, scores):
            ax.text(score + 1, bar.get_y() + bar.get_height() / 2,
                    f'{score:.1f}', va='center')

        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', label='Highly Suitable (≥70)'),
            Patch(facecolor='yellow', label='Moderately Suitable (50-69)'),
            Patch(facecolor='red', label='Not Suitable (<50)')
        ]
        ax.legend(handles=legend_elements, loc='lower right')

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()

    def _create_device_summary_appendix(self, pdf, results):
        """Create appendix with detailed device summaries"""
        # Create summary table page
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle('Device Summary Table', fontsize=16, weight='bold')

        # Collect all device data
        device_data = []

        for section in sorted(results['section_analyses'].keys()):
            for device_num in sorted(results['section_analyses'][section]['device_analyses'].keys()):
                device_info = results['section_analyses'][section]['device_analyses'][device_num]

                row = {
                    'Section': section,
                    'Device': device_num,
                    'Type': device_info['device_classification']['type'],
                    'Quality Score': f"{device_info['performance_summary']['quality_score']:.1f}",
                    'Memristive %': f"{device_info['device_classification']['memristive_percentage']:.1f}"
                }

                # Add key metrics if available
                if 'key_metrics' in device_info['performance_summary']:
                    metrics = device_info['performance_summary']['key_metrics']
                    if 'ron' in metrics:
                        row['Ron (Ω)'] = f"{metrics['ron']['mean']:.2e}"
                    if 'roff' in metrics:
                        row['Roff (Ω)'] = f"{metrics['roff']['mean']:.2e}"
                    if 'switching_ratio' in metrics:
                        row['Ratio'] = f"{metrics['switching_ratio']['mean']:.1f}"

                device_data.append(row)

        # Create table
        if device_data:
            df = pd.DataFrame(device_data)

            # Calculate number of pages needed
            rows_per_page = 40
            num_pages = int(np.ceil(len(df) / rows_per_page))

            for page in range(num_pages):
                fig = plt.figure(figsize=(11, 8.5))
                ax = fig.add_subplot(111)
                ax.axis('tight')
                ax.axis('off')

                start_idx = page * rows_per_page
                end_idx = min((page + 1) * rows_per_page, len(df))

                page_data = df.iloc[start_idx:end_idx]

                # Create table
                table = ax.table(cellText=page_data.values,
                                 colLabels=page_data.columns,
                                 cellLoc='center',
                                 loc='center')

                table.auto_set_font_size(False)
                table.set_fontsize(8)
                table.scale(1.2, 1.5)

                # Color code by quality score
                for i in range(1, len(page_data) + 1):
                    quality_score = float(page_data.iloc[i - 1]['Quality Score'])
                    if quality_score >= 70:
                        color = 'lightgreen'
                    elif quality_score >= 50:
                        color = 'lightyellow'
                    else:
                        color = 'lightcoral'

                    for j in range(len(page_data.columns)):
                        table[(i, j)].set_facecolor(color)
                        table[(i, j)].set_alpha(0.3)

                plt.title(f'Device Summary Table (Page {page + 1}/{num_pages})',
                          fontsize=14, weight='bold', pad=20)

                pdf.savefig(fig, bbox_inches='tight')
                plt.close()

    def _convert_to_json_serializable(self, obj):
        """Convert numpy types to native Python types for JSON serialization"""
        # Handle None first
        if obj is None:
            return None

        # Handle numpy types
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.float32, np.float64, np.float16)):
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
            return float(obj)
        elif isinstance(obj, (np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
            return float(obj)
        elif isinstance(obj, np.complexfloating):
            return {'real': float(obj.real), 'imag': float(obj.imag)}
        elif isinstance(obj, float):
            # Handle Python float
            if np.isnan(obj):
                return None
            elif np.isinf(obj):
                return str(obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif isinstance(obj, str) or isinstance(obj, int) or isinstance(obj, bool):
            return obj
        else:
            # For any other type, try to convert to string
            try:
                return str(obj)
            except:
                return None

    # Updated main.py


def main():
    """Main function to run comprehensive analysis"""
    # Define paths
    home = 'C:\\Users\\Craig-Desktop\\Desktop\\test_data\\Data_save_loc'
    home2 = 'C:\\Users\\Craig-Desktop\\OneDrive - The University of Nottingham\\Documents\\Phd\\2) Data\\1) Devices\\1) Memristors\\Quantum Dots\\Zn-Cu-In-S(Zns)'
    work = 'C:\\Users\\ppxcv1\\OneDrive - The University of nottingham\\Documents\\Phd\\2) Data\\test_data\\Data_save_loc'

    # Initialize analyzer
    analyzer = ComprehensiveSampleAnalyzer(home)

    # List of samples to analyze
    samples = ['D94-0.1mgml-ITO-PMMA(2%)-Gold-s2']  # Start with one sample

    # Analyze each sample
    for sample_name in samples:
        print(f"\n{'=' * 50}")
        print(f"Analyzing sample: {sample_name}")
        print(f"{'=' * 50}")

        try:
            results = analyzer.analyze_sample_comprehensive(sample_name)

            if results is not None:
                # Print summary to console
                print(f"\nAnalysis Complete!")
                print(f"Overall Grade: {results['quality_assessment']['overall_grade']}")
                print(f"Total Devices: {results['sample_statistics']['total_devices']}")
                print(f"Working Devices: {results['sample_statistics']['total_working_devices']}")
                print(f"Memristive Devices: {results['sample_statistics']['total_memristive_devices']}")
                print(f"Overall Score: {results['sample_statistics']['overall_sample_score']:.1f}/100")

                print("\nSuitability Scores:")
                for app, score in results['quality_assessment']['suitability_scores'].items():
                    print(f"  {app}: {score:.1f}/100")
            else:
                print("Analysis returned no results")

        except Exception as e:
            print(f"Error analyzing sample {sample_name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()