import os
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re

""" this works the best"""


class DataAnalyzer:
    def __init__(self, top_level_path):
        self.top_level_path = Path(top_level_path)

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

    def parse_filename(self, filename):
        try:
            # Remove the .txt extension first
            filename = filename.replace('.txt', '')
            parts = re.split('[_-]', filename)
            return {
                'sweep_num': int(parts[0]),
                'sweep_type': parts[1],
                'voltage': float(parts[2].replace('v', '')),
                'step_voltage': float(parts[3].replace('sv', '')),
                'step_delay': float(parts[4].replace('sd', '')),
                'test_type': parts[5],
                'num_sweeps': int(parts[6])
            }
        except Exception as e:
            print(f"Error parsing filename {filename}: {str(e)}")
            return None

    def create_subplot(self, title):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        fig.suptitle(title)
        ax2.set_yscale('log')
        return fig, ax1, ax2

    def plot_data(self, voltage, current, label, ax1, ax2):
        if voltage is not None and current is not None and len(voltage) > 0:
            ax1.plot(voltage, current, 'o-', label=label, markersize=2)
            ax2.plot(voltage, np.abs(current), 'o-', label=label, markersize=2)
            ax1.set_xlabel('Voltage (V)')
            ax1.set_ylabel('Current (A)')
            ax2.set_xlabel('Voltage (V)')
            ax2.set_ylabel('|Current| (A)')

            # Only add legend if there's data
            if len(ax1.get_lines()) > 0:
                ax1.legend()
            if len(ax2.get_lines()) > 0:
                ax2.legend()

    def analyze_section_sweeps(self, substrate, section):
        section_path = self.top_level_path / substrate / section
        plots_dir = section_path / 'plots_combined'
        plots_dir.mkdir(exist_ok=True)

        # Get all device folders
        device_folders = [d for d in section_path.glob('[1-9]*') if d.is_dir()]

        # Find maximum sweep number
        max_sweep = 0
        for device in device_folders:
            files = list(device.glob('*.txt'))
            for file in files:
                # Skip log.txt
                if file.name == 'log.txt':
                    continue
                sweep_num = int(file.name.split('_')[0])
                max_sweep = max(max_sweep, sweep_num)

        # Plot each sweep combination
        for sweep_num in range(1, max_sweep + 1):
            fig, ax1, ax2 = self.create_subplot(f"{substrate} section {section} sweep {sweep_num} combined")

            for device in device_folders:
                sweep_files = list(device.glob(f'{sweep_num}_*.txt'))
                if sweep_files:
                    # Skip log.txt
                    sweep_file = [f for f in sweep_files if f.name != 'log.txt']
                    if sweep_file:
                        voltage, current, _ = self.read_data_file(sweep_file[0])
                        if voltage is not None:
                            label = f"{section}{device.name} (Sweep {sweep_num})"
                            self.plot_data(voltage, current, label, ax1, ax2)

            ax1.legend()
            ax2.legend()
            plt.savefig(plots_dir / f'sweep_{sweep_num}_combined.png')
            plt.close()

    def analyze_single_device(self, substrate, section, device_num):
        device_path = self.top_level_path / substrate / section / str(device_num)
        images_dir = device_path / 'images'
        images_dir.mkdir(exist_ok=True)

        # Define sweep combinations
        sweep_combinations = [
            (1, 19), (2, 18), (3, 17), (4, 16), (5, 15), (6, 14), (7, 13), (8, 12), (9, 11),(10,),
            (12,), (20, 21, 22, 23), (24, 25, 26), (27, 28, 29), (30, 31, 32)
        ]

        # Process each combination
        for combo in sweep_combinations:
            fig, ax1, ax2 = self.create_subplot(f"{substrate} {section}{device_num} sweeps {combo}")

            for sweep_num in combo:
                sweep_files = list(device_path.glob(f'{sweep_num}_*.txt'))
                # Skip log.txt
                sweep_files = [f for f in sweep_files if f.name != 'log.txt']
                if sweep_files:
                    voltage, current, _ = self.read_data_file(sweep_files[0])
                    if voltage is not None:
                        file_info = self.parse_filename(sweep_files[0].name)
                        if file_info:
                            label = f"Sweep {sweep_num}"
                            if len(combo) >= 3:  # For combinations of 3 or more
                                label += f" (V={file_info['voltage']}, SD={file_info['step_delay']})"
                            self.plot_data(voltage, current, label, ax1, ax2)

            ax1.legend()
            ax2.legend()
            plt.savefig(images_dir / f'sweeps_{"_".join(map(str, combo))}.png')
            plt.close()

        # Plot individual sweeps (20-23 and any others)
        all_files = list(device_path.glob('*.txt'))
        # Skip log.txt
        all_files = [f for f in all_files if f.name != 'log.txt']
        for file in all_files:
            sweep_num = int(file.name.split('_')[0])
            if sweep_num in [20, 21, 22, 23] or not any(sweep_num in combo for combo in sweep_combinations):
                fig, ax1, ax2 = self.create_subplot(f"{substrate} {section}{device_num} sweep {sweep_num}")
                voltage, current, _ = self.read_data_file(file)
                if voltage is not None:
                    self.plot_data(voltage, current, f"Sweep {sweep_num}", ax1, ax2)
                ax1.legend()
                ax2.legend()
                plt.savefig(images_dir / f'sweep_{sweep_num}.png')
                plt.close()


def main():
    analyzer = DataAnalyzer('C:\\Users\\Craig-Desktop\\Desktop\\test_data\\Data_save_loc')
    substrate = 'D80'
    section = 'H'

    try:
        # Analyze section sweeps
        analyzer.analyze_section_sweeps(substrate, section)

        # Analyze individual devices
        for device_num in range(1, 11):
            device_path = analyzer.top_level_path / substrate / section / str(device_num)
            if device_path.exists():
                analyzer.analyze_single_device(substrate, section, device_num)

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()




