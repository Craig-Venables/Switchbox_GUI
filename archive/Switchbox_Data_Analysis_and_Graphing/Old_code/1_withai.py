import tensorflow as tf  # (commented out until model is ready)
import numpy as np
import matplotlib.pyplot as plt
from enum import Enum
import seaborn as sns
import pandas as pd
from pathlib import Path
from Old_code import dataanalyzer
from matplotlib.colors import LinearSegmentedColormap

#model = tf.keras.models.load_model('models/memristor_classifier.keras')

class DeviceType(Enum):
    OHMIC = "Ohmic"
    CONDUCTIVE = "Conductive"
    CAPACITIVE = "Capacitive"
    MEMRISTIVE = "Memristive"

class DeviceClassifier:
    def __init__(self):
        self.check_model_files()
        try:
            # Load the trained model and scaler
            self.model = tf.keras.models.load_model('memristor_classifier.keras')
            self.scaler = np.load('../scaler.npy', allow_pickle=True)
            print("Model and scaler loaded successfully")
        except Exception as e:
            print(f"Error loading model or scaler: {str(e)}")
            self.model = None
            self.scaler = None

    def check_model_files(self):
        model_path = Path('../memristor_classifier.keras')
        scaler_path = Path('../scaler.npy')

        print("\nChecking model files:")
        print(f"Looking for model at: {model_path.absolute()}")
        print(f"Looking for scaler at: {scaler_path.absolute()}")

        if not model_path.exists():
            print("❌ Model file not found!")
        else:
            print("✓ Model file found")

        if not scaler_path.exists():
            print("❌ Scaler file not found!")
        else:
            print("✓ Scaler file found")

    def extract_features(self, voltage, current):
        """Extract same features as training"""
        try:
            # Remove any zero current values to avoid division by zero
            non_zero_mask = current != 0
            voltage_nz = voltage[non_zero_mask]
            current_nz = current[non_zero_mask]

            features = {
                'max_current': np.max(np.abs(current)),
                'min_current': np.min(np.abs(current_nz)),
                'current_range': np.max(current) - np.min(current),
                'hysteresis': np.abs(np.trapz(current, voltage)),
                'resistance_at_max_v': voltage[np.argmax(np.abs(voltage))] / current[np.argmax(np.abs(voltage))],
                'avg_resistance': np.mean(np.abs(voltage_nz / current_nz)),
                'positive_area': np.trapz(current[voltage > 0], voltage[voltage > 0]),
                'negative_area': np.trapz(current[voltage < 0], voltage[voltage < 0]),
                'symmetry': np.std(np.diff(current) / np.diff(voltage))
            }

            # Convert dictionary to list in same order as training
            feature_list = [
                features['max_current'],
                features['min_current'],
                features['current_range'],
                features['hysteresis'],
                features['resistance_at_max_v'],
                features['avg_resistance'],
                features['positive_area'],
                features['negative_area'],
                features['symmetry']
            ]

            return feature_list

        except Exception as e:
            print(f"Error extracting features: {str(e)}")
            return None

    def classify_device(self, voltage, current):
        """Classify device using trained model"""
        if self.model is None or self.scaler is None:
            print("Model or scaler not loaded properly")
            return DeviceType.OHMIC, 0.0  # Changed default return

        try:
            # Extract features
            features = self.extract_features(voltage, current)
            if features is None:
                return DeviceType.OHMIC, 0.0  # Changed default return

            # Scale features
            features_scaled = self.scaler.transform([features])

            # Get prediction probabilities
            probs = self.model.predict(features_scaled, verbose=0)

            # Get class and confidence
            predicted_class = np.argmax(probs)
            confidence = probs[0][predicted_class]

            # Map class index to DeviceType (make sure order matches training)
            device_types = [
                DeviceType.OHMIC,  # Changed from NO_CONDUCTION
                DeviceType.CONDUCTIVE,
                DeviceType.CAPACITIVE,
                DeviceType.MEMRISTIVE
            ]

            # Add some debugging information
            print(f"Classification probabilities: {probs[0]}")
            print(f"Predicted class: {device_types[predicted_class].value}")
            print(f"Confidence: {confidence:.2f}")

            return device_types[predicted_class], confidence

        except Exception as e:
            print(f"Error during classification: {str(e)}")
            return DeviceType.OHMIC, 0.0  # Changed default return

        except Exception as e:
            print(f"Error during classification: {str(e)}")
            return DeviceType.NO_CONDUCTION, 0.0

    def analyze_device_characteristics(self, voltage, current, device_type):
        """Additional analysis for classified devices"""
        try:
            characteristics = {}
            features = self.extract_features(voltage, current)

            if features is not None:
                if device_type == DeviceType.MEMRISTIVE:
                    # Calculate memristive characteristics
                    characteristics.update({
                        'on_off_ratio': features[0] / features[1],  # max_current / min_current
                        'hysteresis': features[3],  # hysteresis area
                        'symmetry': features[8]  # symmetry measure
                    })

                elif device_type == DeviceType.CAPACITIVE:
                    # Calculate capacitive characteristics
                    characteristics.update({
                        'symmetry': np.abs(features[6] / features[7]),  # positive_area / negative_area
                        'phase_lag': np.arctan2(features[3], features[5])  # approximation of phase lag
                    })

                elif device_type == DeviceType.CONDUCTIVE:
                    # Calculate conductive characteristics
                    characteristics.update({
                        'resistance': features[5],  # avg_resistance
                        'linearity': 1 / features[8] if features[8] != 0 else float('inf')  # inverse of symmetry
                    })

                elif device_type == DeviceType.OHMIC:
                    # Calculate ohmic characteristics
                    characteristics.update({
                        'resistance': features[5],  # avg_resistance
                        'linearity': 1 / features[8] if features[8] != 0 else float('inf'),  # inverse of symmetry
                        'r_squared': self.calculate_r_squared(voltage, current)  # linear fit quality
                    })

            return characteristics

        except Exception as e:
            print(f"Error analyzing characteristics: {str(e)}")
            return {}

    def calculate_r_squared(self, voltage, current):
        """Calculate R-squared value for linear fit (useful for ohmic devices)"""
        try:
            # Linear regression
            slope, intercept = np.polyfit(voltage, current, 1)
            y_pred = slope * voltage + intercept

            # R-squared calculation
            ss_tot = np.sum((current - np.mean(current)) ** 2)
            ss_res = np.sum((current - y_pred) ** 2)
            r_squared = 1 - (ss_res / ss_tot)

            return r_squared
        except:
            return 0.0

    # def classify_device(self, voltage, current):
    #     # Placeholder function - replace with actual neural network classification
    #     # For now, return random classification with confidence
    #     device_types = list(DeviceType)
    #     random_type = np.random.choice(device_types)
    #     confidence = np.random.uniform(0.6, 0.99)
    #     return random_type, confidence


class MemristiveAnalyzer:
    @staticmethod
    def calculate_on_off_ratio(voltage, current):
        abs_current = np.abs(current)
        on_current = np.max(abs_current)
        off_current = np.min(abs_current[abs_current > 0])  # Avoid zero
        return on_current / off_current

    @staticmethod
    def analyze_hysteresis(voltage, current):
        # Calculate area within I-V loop as measure of hysteresis
        return np.abs(np.trapz(current, voltage))


class DeviceLayout:
    def __init__(self):
        # Define the physical layout of sections
        self.section_layout = {
            'A': (0, 0), 'B': (0, 1), 'D': (0, 2), 'E': (0, 3), 'F': (0, 4),
            'G': (1, 0), 'H': (1, 1), 'I': (1, 2), 'K': (1, 3), 'L': (1, 4)
        }

        # Define device positions within each section
        self.device_positions = {
            1: (0, 4), 2: (0, 3), 3: (0, 2), 4: (0, 1), 5: (0, 0),
            10: (4, 4), 9: (4, 3), 8: (4, 2), 7: (4, 1), 6: (4, 0)
        }



    def create_sample_heatmap(self, sample_metrics, metric_type='classification'):
        """
        Create heatmap for entire sample
        Size will be (10 x 25) - (2 sections high x 5 sections wide, each section 5x5)
        """
        # Initialize the full heatmap array
        heatmap_data = np.zeros((10, 25))  # 2 rows of sections × 5 devices, 5 columns of sections × 5 devices

        # Map device types to numerical values
        type_values = {
            DeviceType.MEMRISTIVE: 1.0,
            DeviceType.CAPACITIVE: 0.7,
            DeviceType.CONDUCTIVE: 0.4,
            DeviceType.NO_CONDUCTION: 0.1
        }

        # Fill the heatmap
        for section, (section_row, section_col) in self.section_layout.items():
            # Calculate base position for this section
            base_row = section_row * 5
            base_col = section_col * 5

            # Fill in device data for this section
            for device_num, (dev_row, dev_col) in self.device_positions.items():
                metrics_key = f"{section}_{device_num}"
                if metrics_key in sample_metrics:
                    device_data = sample_metrics[metrics_key]
                    if device_data:
                        if metric_type == 'classification':
                            device_type = device_data.get('type', DeviceType.NO_CONDUCTION)
                            value = type_values.get(device_type, 0)
                        else:  # performance
                            value = device_data.get('performance_score', 0)

                        heatmap_data[base_row + dev_row, base_col + dev_col] = value

        return heatmap_data

class SampleAnalyzer:
    def __init__(self, top_level_path):
        self.top_level_path = Path(top_level_path)
        self.sections = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'K', 'L']
        self.quality_metrics = {}
        self.device_classifier = DeviceClassifier()
        self.memristive_analyzer = MemristiveAnalyzer()
        self.device_layout = DeviceLayout()

    def generate_sample_heatmaps(self, sample_name, summary_dir):
        """Generate heatmaps for the entire sample"""
        try:
            # Prepare metrics dictionary for the whole sample
            sample_metrics = {}
            for section in self.sections:
                for device_num in range(1, 11):
                    key = f"{section}_{device_num}"
                    metrics = self.quality_metrics.get(f"{sample_name}_{section}_{device_num}")
                    if metrics:
                        sample_metrics[key] = metrics

            # Create classification heatmap
            plt.figure(figsize=(20, 8))
            class_data = self.device_layout.create_sample_heatmap(sample_metrics, 'classification')

            # Custom colormap for device types
            colors = ['gray', 'green', 'blue', 'red']  # NO_CONDUCTION to MEMRISTIVE
            cmap = LinearSegmentedColormap.from_list('device_types', colors)

            sns.heatmap(class_data,
                        cmap=cmap,
                        annot=True,
                        fmt='.2f',
                        cbar_kws={'label': 'Device Type'},
                        xticklabels=False,
                        yticklabels=False)

            # Add section labels
            for section, (row, col) in self.device_layout.section_layout.items():
                plt.text(col * 5 + 2.5, row * 5 + 2.5, section,
                         horizontalalignment='center',
                         verticalalignment='center',
                         fontsize=12,
                         fontweight='bold')

            plt.title(f'Sample {sample_name} Device Classification Map')
            plt.savefig(summary_dir / 'sample_classification_map.png', bbox_inches='tight', dpi=300)
            plt.close()

            # Create performance heatmap
            plt.figure(figsize=(20, 8))
            perf_data = self.device_layout.create_sample_heatmap(sample_metrics, 'performance')
            sns.heatmap(perf_data,
                        cmap='RdYlGn',
                        annot=True,
                        fmt='.2f',
                        cbar_kws={'label': 'Performance Score'},
                        xticklabels=False,
                        yticklabels=False)

            # Add section labels
            for section, (row, col) in self.device_layout.section_layout.items():
                plt.text(col * 5 + 2.5, row * 5 + 2.5, section,
                         horizontalalignment='center',
                         verticalalignment='center',
                         fontsize=12,
                         fontweight='bold')

            plt.title(f'Sample {sample_name} Performance Map')
            plt.savefig(summary_dir / 'sample_performance_map.png', bbox_inches='tight', dpi=300)
            plt.close()

        except Exception as e:
            print(f"Error generating sample heatmaps: {str(e)}")

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
        data_analyzer = dataanalyzer.DataAnalyzer(self.top_level_path)

        # Analyze each section
        for section in self.sections:
            section_path = sample_path / section
            if section_path.exists():
                print(f"Analyzing section {section}")

                # Run detailed analysis
                data_analyzer.analyze_section_sweeps(sample_name, section)

                # Calculate quality metrics for this section
                self.calculate_section_metrics(sample_name, section)

                # Store device metrics for this section
                section_device_metrics = {}

                # Analyze individual devices in section
                for device_num in range(1, 11):
                    device_path = section_path / str(device_num)
                    if device_path.exists():
                        # Original device analysis
                        data_analyzer.analyze_single_device(sample_name, section, device_num)

                        # New device classification and analysis
                        device_metrics = self.analyze_device_data(sample_name, section, device_num)
                        section_device_metrics[device_num] = device_metrics

                # Generate physical layout heatmaps for this section
                #self.generate_physical_heatmaps(sample_name, section, section_device_metrics, summary_dir)
                # After analyzing all sections, generate sample-wide heatmaps

        self.generate_sample_heatmaps(sample_name, summary_dir)

        # Generate comprehensive summary reports and visualizations
        self.generate_sample_summary(sample_name, summary_dir)

    def analyze_device_data(self, sample_name, section, device_num):
        """Analyze individual device including classification"""
        device_path = self.top_level_path / sample_name / section / str(device_num)

        try:
            # Get first sweep data for initial classification
            sweep1_files = list(device_path.glob('1_*.txt'))
            sweep1_files = [f for f in sweep1_files if f.name != 'log.txt']

            if sweep1_files:
                voltage, current, _ = self.read_data_file(sweep1_files[0])
                if voltage is not None and current is not None:
                    # Classify device
                    device_type, confidence = self.device_classifier.classify_device(voltage, current)

                    # Get additional characteristics
                    characteristics = self.device_classifier.analyze_device_characteristics(
                        voltage, current, device_type
                    )

                    metrics = {
                        'type': device_type,
                        'confidence': confidence,
                        'characteristics': characteristics
                    }

                    # Store metrics
                    self.quality_metrics[f"{sample_name}_{section}_{device_num}"] = metrics
                    return metrics

        except Exception as e:
            print(f"Error analyzing device {device_num} in section {section}: {str(e)}")

        return None
    #
    # def analyze_device_data(self, sample_name, section, device_num):
    #     """Analyze individual device including classification"""
    #     device_path = self.top_level_path / sample_name / section / str(device_num)
    #
    #     # Initialize default metrics
    #     default_metrics = {
    #         'type': DeviceType.NO_CONDUCTION,
    #         'confidence': 0.0,
    #         'performance_score': 0.0
    #     }
    #
    #     try:
    #         # Get first sweep data for initial classification
    #         sweep1_files = list(device_path.glob('1_*.txt'))
    #         sweep1_files = [f for f in sweep1_files if f.name != 'log.txt']
    #
    #         if sweep1_files:
    #             voltage, current, _ = self.read_data_file(sweep1_files[0])
    #             if voltage is not None and current is not None:
    #                 # Classify device
    #                 device_type, confidence = self.device_classifier.classify_device(voltage, current)
    #
    #                 metrics = {
    #                     'type': device_type,
    #                     'confidence': confidence,
    #                     'performance_score': 0.0
    #                 }
    #
    #                 # Additional analysis for memristive devices
    #                 if device_type == DeviceType.MEMRISTIVE:
    #                     metrics.update({
    #                         'on_off_ratio': self.memristive_analyzer.calculate_on_off_ratio(voltage, current),
    #                         'hysteresis': self.memristive_analyzer.analyze_hysteresis(voltage, current)
    #                     })
    #
    #                 # Store metrics in quality_metrics dictionary
    #                 self.quality_metrics[f"{sample_name}_{section}_{device_num}"] = metrics
    #                 return metrics
    #
    #         # If we get here, return default metrics
    #         self.quality_metrics[f"{sample_name}_{section}_{device_num}"] = default_metrics
    #         return default_metrics
    #
    #     except Exception as e:
    #         print(f"Error analyzing device {device_num} in section {section}: {str(e)}")
    #         self.quality_metrics[f"{sample_name}_{section}_{device_num}"] = default_metrics
    #         return default_metrics

    def calculate_section_metrics(self, sample_name, section):
        """Calculate quality metrics for a section"""
        section_path = self.top_level_path / sample_name / section
        metrics = {
            'devices': [],
            'sweep1_current_range': [],
            'resistance_uniformity': [],
            'device_consistency': [],
            'working_devices': 0,
            'memristive_devices': 0,
            'average_on_off_ratio': 0
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
                        # Calculate basic metrics
                        current_range = np.max(np.abs(current)) - np.min(np.abs(current))
                        resistance = np.mean(np.abs(voltage / current))

                        metrics['devices'].append(device_num)
                        metrics['sweep1_current_range'].append(current_range)
                        metrics['resistance_uniformity'].append(resistance)
                        metrics['working_devices'] += 1

                        # Check device classification
                        device_metrics = self.quality_metrics.get(f"{sample_name}_{section}_{device_num}", {})
                        if device_metrics.get('type') == DeviceType.MEMRISTIVE:
                            metrics['memristive_devices'] += 1
                            metrics['average_on_off_ratio'] += device_metrics.get('on_off_ratio', 0)

        # Calculate section-wide metrics
        if metrics['memristive_devices'] > 0:
            metrics['average_on_off_ratio'] /= metrics['memristive_devices']

        if metrics['devices']:
            self.quality_metrics[f"{sample_name}_{section}"] = {
                'working_devices': metrics['working_devices'],
                'memristive_devices': metrics['memristive_devices'],
                'average_on_off_ratio': metrics['average_on_off_ratio'],
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

    def generate_sample_summary(self, sample_name, summary_dir):
        """Generate comprehensive summary visualizations and reports"""
        # Create summary DataFrame
        summary_data = pd.DataFrame.from_dict(self.quality_metrics, orient='index')

        # Save numerical summary
        summary_data.to_csv(summary_dir / 'quality_metrics.csv')

        # Create overall sample heatmap
        plt.figure(figsize=(15, 10))
        section_scores = np.zeros((2, 5))  # 2x5 grid for sections
        for idx, section in enumerate(self.sections):
            key = f"{sample_name}_{section}"
            if key in self.quality_metrics:
                row = idx // 5
                col = idx % 5
                section_scores[row, col] = self.quality_metrics[key]['overall_score']

        sns.heatmap(section_scores,
                    annot=True,
                    fmt='.1f',
                    cmap='RdYlGn',
                    xticklabels=['A/G', 'B/H', 'D/I', 'E/K', 'F/L'],
                    yticklabels=['Top', 'Bottom'])
        plt.title(f'Section Quality Scores - {sample_name}')
        plt.savefig(summary_dir / 'section_quality_heatmap.png')
        plt.close()

        # Create memristive device distribution plot
        plt.figure(figsize=(15, 6))
        memristive_counts = [self.quality_metrics.get(f"{sample_name}_{section}", {}).get('memristive_devices', 0)
                             for section in self.sections]
        plt.bar(self.sections, memristive_counts)
        plt.title(f'Memristive Devices per Section - {sample_name}')
        plt.ylabel('Number of Memristive Devices')
        plt.savefig(summary_dir / 'memristive_distribution.png')
        plt.close()

        # Generate enhanced HTML report
        self.generate_html_report(sample_name, summary_dir)

    def generate_physical_heatmaps(self, sample_name, section, device_metrics, summary_dir):
        """Generate physical layout heatmaps for device classification and performance"""
        try:
            # Classification heatmap
            plt.figure(figsize=(10, 8))
            class_data = self.device_layout.create_physical_heatmap(device_metrics, 'classification')
            sns.heatmap(class_data,
                        cmap='RdYlBu_r',
                        annot=True,
                        fmt='.2f',
                        cbar_kws={'label': 'Device Type'})
            plt.title(f'Device Classification Map - {sample_name} Section {section}')
            plt.savefig(summary_dir / f'physical_classification_map_{section}.png')
            plt.close()

            # Performance heatmap
            plt.figure(figsize=(10, 8))
            perf_data = self.device_layout.create_physical_heatmap(device_metrics, 'performance')
            sns.heatmap(perf_data,
                        cmap='RdYlGn',
                        annot=True,
                        fmt='.2f',
                        cbar_kws={'label': 'Performance Score'})
            plt.title(f'Device Performance Map - {sample_name} Section {section}')
            plt.savefig(summary_dir / f'physical_performance_map_{section}.png')
            plt.close()
        except Exception as e:
            print(f"Error generating heatmaps for section {section}: {str(e)}")

    def generate_html_report(self, sample_name, summary_dir):
        """Generate comprehensive HTML report"""
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
                .device-info {{ display: flex; flex-wrap: wrap; }}
                .device-card {{ width: 300px; margin: 10px; padding: 10px; border: 1px solid #ddd; }}
                .section-summary {{ margin: 20px 0; }}
                .visualization {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Sample {sample_name} Analysis Report</h1>
            
            <h2>Sample Overview</h2>
            <h2>Section Quality Metrics</h2>
            <div class="metrics">
            
            <div class="visualization">
                <h3>Full Sample Heatmaps</h3>
                <img src="sample_classification_map.png" alt="Sample Classification Map">
                <img src="sample_performance_map.png" alt="Sample Performance Map">
            </div>
        """

        # Add section summaries
        for section in self.sections:
            section_metrics = self.quality_metrics.get(f"{sample_name}_{section}", {})
            if section_metrics:
                html_content += f"""
                <div class="section-summary">
                    <h2>Section {section}</h2>
                    <p>Working Devices: {section_metrics.get('working_devices', 0)}/10</p>
                    <p>Memristive Devices: {section_metrics.get('memristive_devices', 0)}</p>
                    <p>Average On/Off Ratio: {section_metrics.get('average_on_off_ratio', 0):.2f}</p>
                    <p>Overall Score: {section_metrics.get('overall_score', 0):.1f}/100</p>

                    <div class="visualization">
                        <img src="physical_classification_map_{section}.png" alt="Classification Map">
                        <img src="physical_performance_map_{section}.png" alt="Performance Map">
                    </div>

                    <div class="device-info">
                """

                # Add device-specific information
                for device_num in range(1, 11):
                    device_metrics = self.quality_metrics.get(f"{sample_name}_{section}_{device_num}", {})
                    if device_metrics:
                        device_type = device_metrics.get('type', DeviceType.NO_CONDUCTION)
                        html_content += f"""
                        <div class="device-card">
                            <h3>Device {device_num}</h3>
                            <p>Type: {device_type.value}</p>
                            <p>Confidence: {device_metrics.get('confidence', 0):.2f}</p>
                        """

                        if device_type == DeviceType.MEMRISTIVE:
                            html_content += f"""
                            <p>On/Off Ratio: {device_metrics.get('on_off_ratio', 'N/A'):.2f}</p>
                            <p>Hysteresis: {device_metrics.get('hysteresis', 'N/A'):.2e}</p>
                            """

                        html_content += "</div>"

                # Add heatmaps
                html_content += f"""
                    <div class="heatmaps">
                        <img src="physical_classification_map_{section}.png" alt="Classification Map">
                        <img src="physical_performance_map_{section}.png" alt="Performance Map">
                    </div>
                    """

        html_content += """
        </body>
        </html>
        """

        with open(summary_dir / 'report.html', 'w') as f:
            f.write(html_content)


def main():
    sample_analyzer = SampleAnalyzer('C:\\Users\\Craig-Desktop\\Desktop\\test_data\\Data_save_loc')
    sample_name = 'D82'  # or whatever your sample name is
    sample_analyzer.analyze_sample(sample_name)


if __name__ == "__main__":
    main()