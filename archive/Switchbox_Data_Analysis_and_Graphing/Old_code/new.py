# def calculate_sweep_metrics(self, section_path, sweep_num):
#     """Calculate metrics for a specific sweep number"""
#     metrics_main_sweep = {
#         'devices': [],
#         'current_range': [],
#         'resistance_uniformity': [],
#         'device_consistency': [],
#         'working_devices': 0,
#         'resistance_at_0_2V': [],
#         'resistance_at_0_5V': [],
#         'on_off_ratio': []
#     }
#
#     # Your existing sweep 1 analysis code here
#     for device_num in range(1, 11):
#         device_path = section_path / str(device_num)
#         if device_path.exists():
#             sweep_files = list(device_path.glob(f'{sweep_num}-*.txt'))
#             sweep_files = [f for f in sweep_files if f.name != 'log.txt']
#
#             if sweep_files:
#                 voltage, current, _ = self.read_data_file(sweep_files[0])
#                 if voltage is not None and current is not None:
#                     # Your existing metrics calculations...
#                     current_range = np.max(np.abs(current)) - np.min(np.abs(current))
#                     resistance = np.mean(np.abs(voltage / current))
#
#                     def get_resistance_at_voltage(target_voltage):
#                         idx = np.abs(voltage - target_voltage).argmin()
#                         if abs(voltage[idx] - target_voltage) < 0.01:
#                             return abs(voltage[idx] / current[idx])
#                         return None
#
#                     r_0_2V = get_resistance_at_voltage(0.2)
#                     r_0_5V = get_resistance_at_voltage(0.5)
#
#                     metrics_main_sweep['devices'].append(device_num)
#                     metrics_main_sweep['sweep1_current_range'].append(current_range)
#                     metrics_main_sweep['resistance_uniformity'].append(resistance)
#                     if r_0_2V is not None:
#                         metrics_main_sweep['resistance_at_0_2V'].append(r_0_2V)
#                     if r_0_5V is not None:
#                         metrics_main_sweep['resistance_at_0_5V'].append(r_0_5V)
#                     metrics_main_sweep['working_devices'] += 1
#
#     # Calculate aggregate metrics
#     if metrics_main_sweep['devices']:
#         return {
#             'working_devices': metrics_main_sweep['working_devices'],
#             'current_range_std': np.std(metrics_main_sweep['sweep1_current_range']),
#             'resistance_std': np.std(metrics_main_sweep['resistance_uniformity']),
#             'resistance_0_2V_mean': np.mean(metrics_main_sweep['resistance_at_0_2V']) if metrics_main_sweep[
#                 'resistance_at_0_2V'] else None,
#             'resistance_0_2V_std': np.std(metrics_main_sweep['resistance_at_0_2V']) if metrics_main_sweep[
#                 'resistance_at_0_2V'] else None,
#             'resistance_0_5V_mean': np.mean(metrics_main_sweep['resistance_at_0_5V']) if metrics_main_sweep[
#                 'resistance_at_0_5V'] else None,
#             'resistance_0_5V_std': np.std(metrics_main_sweep['resistance_at_0_5V']) if metrics_main_sweep[
#                 'resistance_at_0_5V'] else None,
#             'overall_score': self.calculate_overall_score(metrics_main_sweep)
#         }
#     return {}