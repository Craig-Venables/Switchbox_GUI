import re
import os
def extract_number_from_filename(filename):
    # Use regex to find the number at the start of the filename before the first '-'
    match = re.match(r'^(\d+)_', filename)
    if match:
        return int(match.group(1))
    return None


def find_largest_number_in_folder(folder_path):
    largest_number = None

    # Iterate over all files in the folder
    for filename in os.listdir(folder_path):
        print(filename)
        number = extract_number_from_filename(filename)
        if number is not None:
            if largest_number is None or number > largest_number:
                largest_number = number

    return largest_number

path = "C:\\Users\\ppxcv1\\OneDrive - The University of Nottingham\\Documents\\GitHub_labpc1\\Switchbox_GUI\\Data_save_loc\\.!toplevel.!labelframe2.!entry\\Across Ito\\1"
print(find_largest_number_in_folder(path))
