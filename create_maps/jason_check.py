import json

# checks jason file for problems and fixes them

# Load the mapping.json file
with open("../Json_Files/mapping.json", "r") as file:
    device_mapping = json.load(file)

# Iterate through each device and fix incorrect min/max values
for device, bounds in device_mapping.items():
    if bounds["x_min"] > bounds["x_max"]:
        bounds["x_min"], bounds["x_max"] = bounds["x_max"], bounds["x_min"]

    if bounds["y_min"] > bounds["y_max"]:
        bounds["y_min"], bounds["y_max"] = bounds["y_max"], bounds["y_min"]

# Save the corrected file with proper formatting
with open("../Json_Files/mapping.json", "w") as file:
    json.dump(device_mapping, file, indent=2, separators=(",", ": "))

print("Mapping file checked and corrected. Saved as mapping.json.")
