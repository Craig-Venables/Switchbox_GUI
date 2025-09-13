import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

# Load the image
image_path = "../Sample_Infomation/memristor.png"  # Replace with the actual image filename
image = Image.open(image_path)

mapping_file = "../../Json_Files/mapping.json"  # Replace with actual mapping JSON fil


# Load the image and resize it to 400x400
original_image = Image.open(image_path)
image = original_image.resize((400, 400))  # Resize to 400x400
orig_width, orig_height = original_image.size
scaled_width, scaled_height = 400, 400

# Compute the scaling factors
scale_x = orig_width / scaled_width
scale_y = orig_height / scaled_height

# Load the mapping JSON file
with open(mapping_file, "r") as f:
    device_mapping = json.load(f)

# Create the plot
fig, ax = plt.subplots(figsize=(6, 6))
ax.imshow(image)

# Iterate through each device and plot a rectangle
for device, bounds in device_mapping.items():
    # Apply scaling factor to mapping values
    x_min, x_max = bounds["x_min"] / scale_x, bounds["x_max"] / scale_x
    y_min, y_max = bounds["y_min"] / scale_y, bounds["y_max"] / scale_y

    # Check if bounding box is invalid (missing values, zero size, etc.)
    if x_min == x_max or y_min == y_max:
        print(f"⚠️ WARNING: Device {device} has invalid bounds ({x_min}, {y_min}, {x_max}, {y_max})")
        rect_color = "red"  # Highlight problematic devices in red
    else:
        rect_color = "green"

    # Create rectangle
    rect = patches.Rectangle(
        (x_min, y_min), x_max - x_min, y_max - y_min, linewidth=2, edgecolor=rect_color, facecolor="none"
    )
    ax.add_patch(rect)

    # Add label for each device
    ax.text(x_min, y_min - 5, device, fontsize=6, color=rect_color, fontweight="bold")

# Show the image with overlays
plt.title("Scaled Device Mapping Overlay")
plt.axis("off")  # Hide axes for clarity
plt.show()
