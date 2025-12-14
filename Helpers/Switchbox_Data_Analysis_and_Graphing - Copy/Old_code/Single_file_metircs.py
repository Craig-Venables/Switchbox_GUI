import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import math


class analyze_single_file:
    """ Class for taking voltage and current data and returning all information from a sample, for later use. """

    def __init__(self, voltage, current):

        self.voltage = np.array(voltage)
        self.current = np.array(current)

        # Initialize lists to store the values for each metric
        self.ps_areas = []
        self.ng_areas = []
        self.areas = []
        self.normalized_areas = []
        self.ron = []
        self.roff = []
        self.von = []
        self.voff = []
        self.on_off = []
        self.r_02V = []  # resistance values at 0.2v
        self.r_05V = []  # resistance values at 0.5v

        # determine number of sweeps
        self.num_loops = self.check_for_loops(voltage)

        # split into single sweeps.
        self.split_v_data, self.split_c_data = self.split_loops(voltage, current)

        # get metrics
        self.calculate_metrics_for_loops(self.split_v_data, self.split_c_data)
        # metrics include R_on, R_off, Areas, Normalised_areas

        # Calculate conductivity
        # calculate device consistancy
        # resistance uniformity
        # current range.

    def get_resistance_at_voltage(self, target_voltage):
        try:
            idx = np.abs(self.voltage - target_voltage).argmin()
            if abs(self.voltage[idx] - target_voltage) < 0.01:
                result = zero_division_check(abs(self.voltage[idx]),abs(self.current[idx]))
                return result
            return None
        except Exception as e:
            print(f"Error calculating resistance at {target_voltage}V: {str(e)}")
            return None

    def export_metrics(self, filename):
        """Export calculated metrics to CSV file."""
        # Basic metrics dictionary
        metrics_dict = {
            'ps_areas': self.ps_areas,
            'ng_areas': self.ng_areas,
            'areas': self.areas,
            'normalized_areas': self.normalized_areas,
            'ron': self.ron,
            'roff': self.roff,
            'von': self.von,
            'voff': self.voff,
            'on_off': self.on_off,
            'r_02V': self.r_02V,
            'r_05V': self.r_05V
        }
        df = pd.DataFrame(metrics_dict)
        df.to_csv(filename, index=False)

    def get_summary_stats(self):
        """
        Return summary statistics of key metrics including means and standard deviations.

        Returns:
            dict: Dictionary containing mean and standard deviation for key metrics
        """
        return {
            # Resistance metrics
            'mean_ron': np.mean(self.ron),
            'std_ron': np.std(self.ron),
            'mean_roff': np.mean(self.roff),
            'std_roff': np.std(self.roff),

            # On/Off ratio metrics
            'mean_on_off_ratio': np.mean(self.on_off),
            'std_on_off_ratio': np.std(self.on_off),

            # Area metrics
            'total_area': np.sum(self.areas),
            'avg_normalized_area': np.mean(self.normalized_areas),
            'std_normalized_area': np.std(self.normalized_areas),

            # Resistance at specific voltages
            'mean_r_02V': np.mean([x for x in self.r_02V if x is not None]),
            'std_r_02V': np.std([x for x in self.r_02V if x is not None]),
            'mean_r_05V': np.mean([x for x in self.r_05V if x is not None]),
            'std_r_05V': np.std([x for x in self.r_05V if x is not None]),

            # General device metrics
            'num_loops': self.num_loops,
            'max_current': np.max(np.abs(self.current)),
            'max_voltage': np.max(np.abs(self.voltage)),

            # Coefficient of variation (CV = std/mean) for key metrics
            'cv_on_off_ratio': np.std(self.on_off) / np.mean(self.on_off) if np.mean(self.on_off) != 0 else None,
            'cv_normalized_area': np.std(self.normalized_areas) / np.mean(self.normalized_areas) if np.mean(
                self.normalized_areas) != 0 else None,
        }

    def calculate_metrics_for_loops(self, split_v_data, split_c_data):
        '''
        Calculate various metrics for each split array of voltage and current data.
        anything that needs completing on loops added in here

        Parameters:
        - split_v_data (list of lists): List containing split voltage arrays
        - split_c_data (list of lists): List containing split current arrays

        Returns:
        - ps_areas (list): List of PS areas for each split array
        - ng_areas (list): List of NG areas for each split array
        - areas (list): List of total areas for each split array
        - normalized_areas (list): List of normalized areas for each split array
        '''

        # Loop through each split array
        for idx in range(len(split_v_data)):
            sub_v_array = split_v_data[idx]
            sub_c_array = split_c_data[idx]

            # Call the area_under_curves function for the current split arrays
            ps_area, ng_area, area, norm_area = self.area_under_curves(sub_v_array, sub_c_array)

            # Append the values to their respective lists
            self.ps_areas.append(ps_area)
            self.ng_areas.append(ng_area)
            self.areas.append(area)
            self.normalized_areas.append(norm_area)

            # caclulate the on and off volatge and resistance
            r_on, r_off, v_on, v_off = self.on_off_values(sub_v_array, sub_c_array)

            self.ron.append(float(r_on))
            self.roff.append(float(r_off))
            self.von.append(float(v_on))
            self.voff.append(float(v_off))
            self.on_off.append(float(r_on - r_off))

            # get resistance values at 0.2V (For conductivity)
            self.r_02V.append(self.get_resistance_at_voltage(0.2))
            self.r_05V.append(self.get_resistance_at_voltage(0.5))

        #return self.ps_areas, self.ng_areas, self.areas, self.normalized_areas, self.ron, self.roff, self.von, self.voff

    def area_under_curves(self, v_data, c_data):
        """
        only run this for an individual sweep
        :return: ps_area_enclosed,ng_area_enclosed,total_area_enclosed
        """

        def area_under_curve(voltage, current):
            """
            Calculate the area under the curve given voltage and current data.
            """

            # print(voltage,current)
            voltage = np.array(voltage)
            current = np.array(current)
            # Calculate the area under the curve using the trapezoidal rule
            area = np.trapezoid(current, voltage)
            return area

        # finds v max and min
        v_max, v_min = self.bounds(v_data)

        # creates dataframe of the sweep in sections
        df_sections = self.split_data_in_sect(v_data, c_data, v_max, v_min)

        # calculate the area under the curve for each section
        sect1_area = abs(area_under_curve(df_sections.get('voltage_ps_sect1'), df_sections.get('current_ps_sect1')))
        sect2_area = abs(area_under_curve(df_sections.get('voltage_ps_sect2'), df_sections.get('current_ps_sect2')))
        sect3_area = abs(area_under_curve(df_sections.get('voltage_ng_sect1'), df_sections.get('current_ng_sect1')))
        sect4_area = abs(area_under_curve(df_sections.get('voltage_ng_sect2'), df_sections.get('current_ng_sect2')))

        # plot to show where each section is on the hysteresis
        # plt.plot(df_sections.get('voltage_ps_sect1'), df_sections.get('current_ps_sect1'),color="blue" )
        # plt.plot(df_sections.get('voltage_ps_sect2'), df_sections.get('current_ps_sect2'),color="green")
        # plt.plot(df_sections.get('voltage_ng_sect1'), df_sections.get('current_ng_sect1'),color="red")
        # plt.plot(df_sections.get('voltage_ng_sect2'), df_sections.get('current_ng_sect2'),color="yellow")
        # plt.legend()
        # plt.show()
        # plt.pause(0.1)

        # blue - green
        # red - yellow

        ps_area_enclosed = abs(sect2_area) - abs(sect1_area)
        ng_area_enclosed = abs(sect3_area) - abs(sect4_area)
        area_enclosed = ps_area_enclosed + ng_area_enclosed
        norm_area_enclosed = area_enclosed / (abs(v_max) + abs(v_min))

        # added nan check as causes issues later if not a value
        if math.isnan(norm_area_enclosed):
            norm_area_enclosed = 0
        if math.isnan(ps_area_enclosed):
            ps_area_enclosed = 0
        if math.isnan(ng_area_enclosed):
            ng_area_enclosed = 0
        if math.isnan(area_enclosed):
            area_enclosed = 0

        return ps_area_enclosed, ng_area_enclosed, area_enclosed, norm_area_enclosed

    def on_off_values(self, voltage_data, current_data):
        """
        Calculates r on off and v on off values for an individual device
        """

        # Convert DataFrame columns to lists
        # voltage_data = voltage_data.flatten()
        # current_data = current_data.flatten()
        # voltage_data = voltage_data.to_numpy()
        # current_data = current_data.to_numpy()

        # Initialize lists to store Ron and Roff values
        resistance_on_value = []
        resistance_off_value = []
        # Initialize default values for on and off voltages
        voltage_on_value = 0
        voltage_off_value = 0

        # Get the maximum voltage value
        max_voltage = round(max(voltage_data), 1)
        # Catch edge case for just negative sweep only
        if max_voltage == 0:
            max_voltage = abs(round(min(voltage_data), 1))

        # Set the threshold value to 0.2 times the maximum voltage
        threshold = round(0.2 * max_voltage, 2)
        # print("threshold,max_voltage")
        # print(threshold,max_voltage)
        # print(len(voltage_data))
        # print(voltage_data)

        # Filter the voltage and current data to include values within the threshold
        filtered_voltage = []
        filtered_current = []
        for index in range(len(voltage_data)):
            # print(index)
            if -threshold < voltage_data[index] < threshold:
                filtered_voltage.append(voltage_data[index])
                filtered_current.append(current_data[index])
        # print(filtered_voltage)

        resistance_magnitudes = []
        for idx in range(len(filtered_voltage)):
            if filtered_voltage[idx] != 0 and filtered_current[idx] != 0:
                resistance_magnitudes.append(abs(filtered_voltage[idx] / filtered_current[idx]))

        if not resistance_magnitudes:
            # Handle the case when the list is empty, e.g., set default values or raise an exception.
            print("Error: No valid resistance values found.")
            return 0, 0, 0, 0

        # # Calculate the resistance magnitude for each filtered data point
        # resistance_magnitudes = []
        # for idx in range(len(filtered_voltage)):
        #     if filtered_voltage[idx] != 0:
        #         resistance_magnitudes.append(abs(filtered_voltage[idx] / filtered_current[idx]))
        # print(resistance_magnitudes)
        # Store the minimum and maximum resistance values
        resistance_off_value = min(resistance_magnitudes)
        resistance_on_value = max(resistance_magnitudes)

        # Calculate the gradients for each data point
        gradients = []
        for idx in range(len(voltage_data)):
            if idx != len(voltage_data) - 1:
                if voltage_data[idx + 1] - voltage_data[idx] != 0:
                    gradients.append(
                        (current_data[idx + 1] - current_data[idx]) / (voltage_data[idx + 1] - voltage_data[idx]))

        # Find the maximum and minimum gradient values
        max_gradient = max(gradients[:(int(len(gradients) / 2))])
        min_gradient = min(gradients)

        # Use the maximum and minimum gradient values to determine the on and off voltages
        for idx in range(len(gradients)):
            if gradients[idx] == max_gradient:
                voltage_off_value = voltage_data[idx]
            if gradients[idx] == min_gradient:
                voltage_on_value = voltage_data[idx]

        # Return the calculated Ron and Roff values and on and off voltages
        return resistance_on_value, resistance_off_value, voltage_on_value, voltage_off_value

    def check_for_loops(self, v_data):
        """
        :param v_data:
        :return: number of loops for given data set
        """

        # looks at max voltage and min voltage if they are seen more than twice it classes it as a loop
        # checks for the number of zeros 3 = single loop
        num_max = 0
        num_min = 0
        num_zero = 0
        max_v, min_v = self.bounds(v_data)
        max_v_2 = max_v / 2
        min_v_2 = min_v / 2

        # 4 per sweep
        for value in v_data:
            if value == max_v_2:
                num_max += 1
            if value == min_v_2:
                num_min += 1
            if value == 0:
                num_zero += 1
        # print(num_min)

        # print("num zero", num_zero)
        if num_max + num_min == 4:
            # print("single sweep")
            return 1
        if num_max + num_min == 2:
            # print("half_sweep", num_max, num_min)
            return 0.5
        else:
            # print("multiloop", (num_max + num_min) / 4)
            loops = (num_max + num_min) / 4
            return loops

    def split_loops(self, v_data, c_data):
        """ splits the looped data and outputs each sweep as another array coppied from data"""

        if self.num_loops != 1:
            total_length = len(v_data)  # Assuming both v_data and c_data have the same length
            size = total_length // self.num_loops  # Calculate the size based on the number of loops

            # Convert size to integer
            size = int(size)

            # Handle the case when the division leaves the remainder
            if total_length % self.num_loops != 0:
                size += 1

            split_v_data = [v_data[i:i + size] for i in range(0, total_length, size)]
            split_c_data = [c_data[i:i + size] for i in range(0, total_length, size)]

            # self.split_v_data = split_v_data
            # self.split_c_data = split_c_data
            return split_v_data, split_c_data
        else:
            return v_data, c_data

    def bounds(self, data):
        """
        :param data:
        :return: max and min values of given array max,min
        """
        max = np.max(data)
        min = np.min(data)
        return max, min

    def split_data_in_sect(self, voltage, current, v_max, v_min):
        # splits the data into sections and clculates the area under the curve for how "memeristive" a device is.
        zipped_data = list(zip(voltage, current))

        positive = [(v, c) for v, c in zipped_data if 0 <= v <= v_max]
        negative = [(v, c) for v, c in zipped_data if v_min <= v <= 0]

        # voltage = np.array(voltage)
        # current = np.array(current)
        #
        # positive_mask = (voltage >= 0) & (voltage <= v_max)
        # negative_mask = (voltage >= v_min) & (voltage <= 0)
        #
        # positive = np.column_stack((voltage[positive_mask], current[positive_mask]))
        # negative = np.column_stack((voltage[negative_mask], current[negative_mask]))

        # Find the maximum length among the four sections
        max_len = max(len(positive), len(negative))

        # Split positive section into two equal parts
        positive1 = positive[:max_len // 2]
        positive2 = positive[max_len // 2:]

        # Split negative section into two equal parts
        negative3 = negative[:max_len // 2]
        negative4 = negative[max_len // 2:]

        # Find the maximum length among the four sections
        max_len = max(len(positive1), len(positive2), len(negative3), len(negative4))

        # Calculate the required padding for each section
        pad_positive1 = max_len - len(positive1)
        pad_positive2 = max_len - len(positive2)
        pad_negative3 = max_len - len(negative3)
        pad_negative4 = max_len - len(negative4)

        # Limit the padding to the length of the last value for each section
        last_positive1 = positive1[-1] if positive1 else (0, 0)
        last_positive2 = positive2[-1] if positive2 else (0, 0)
        last_negative3 = negative3[-1] if negative3 else (0, 0)
        last_negative4 = negative4[-1] if negative4 else (0, 0)

        positive1 += [last_positive1] * pad_positive1
        positive2 += [last_positive2] * pad_positive2
        negative3 += [last_negative3] * pad_negative3
        negative4 += [last_negative4] * pad_negative4

        # Create DataFrame for device
        sections = {
            'voltage_ps_sect1': [v for v, _ in positive1],
            'current_ps_sect1': [c for _, c in positive1],
            'voltage_ps_sect2': [v for v, _ in positive2],
            'current_ps_sect2': [c for _, c in positive2],
            'voltage_ng_sect1': [v for v, _ in negative3],
            'current_ng_sect1': [c for _, c in negative3],
            'voltage_ng_sect2': [v for v, _ in negative4],
            'current_ng_sect2': [c for _, c in negative4],
        }

        df_sections = pd.DataFrame(sections)
        return df_sections


def zero_division_check(x, y):
    try:
        return x / y
    except ZeroDivisionError:  # Specifically catch ZeroDivisionError
        return 0
    except TypeError:  # Handle type errors (non-numeric inputs)
        raise TypeError("Inputs must be numeric")


def read_data_file(file_path):
    try:
        data = np.loadtxt(file_path, skiprows=1)
        voltage = data[:, 0]
        current = data[:, 1]

        return voltage, current
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None, None, None


if __name__ == "__main__":
    voltage, current = read_data_file("G - 10 - 34.txt")
    sfa = analyze_single_file(voltage, current)
