import json
from pathlib import Path

import cv2

"""
Interactive tool for drawing rectangular ROIs on the multiplexer image.
The script displays the reference photo, lets a user select regions left-to-
right/top-to-bottom, and writes the coordinates into a JSON map for the GUI.
"""

# when mapping always go from left to right up to down
# e.g., max values to min values, or it may cause errors
# if onnly some are mapped and noth otheres but it all looks okay this may be the reason


# Global variables
refPt = []
cropping = False
device_counter = 1
device_mapping = {}

# Load image safely
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_IMAGE = SCRIPT_DIR / "memristor.png"
image_path = Path(DEFAULT_IMAGE)

# Output file path (save in Maps_Create directory, one level up from script)
OUTPUT_DIR = SCRIPT_DIR.parent
OUTPUT_FILE = OUTPUT_DIR / "test.json"

if not image_path.is_file():
    raise FileNotFoundError(
        f"Expected reference image at {image_path}. Update the path or copy the "
        "photo into this directory before running the mapper."
    )

image = cv2.imread(str(image_path))
if image is None:
    raise RuntimeError(
        f"OpenCV could not read {image_path}. Check file integrity or format."
    )
clone = image.copy()


def click_and_crop(event, x, y, flags, param):
    global refPt, cropping, device_counter, device_mapping

    if event == cv2.EVENT_LBUTTONDOWN:
        refPt = [(x, y)]
        cropping = True

    elif event == cv2.EVENT_LBUTTONUP:
        refPt.append((x, y))
        cropping = False

        # Draw the rectangle
        cv2.rectangle(image, refPt[0], refPt[1], (0, 255, 0), 2)
        cv2.imshow("Image", image)

        # Save device mapping
        x_min, y_min = refPt[0]
        x_max, y_max = refPt[1]
        device_mapping[f"device_{device_counter}"] = {
            "x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max
        }
        print(f"Saved device_{device_counter}: {refPt}")
        device_counter += 1


cv2.namedWindow("Image")
cv2.setMouseCallback("Image", click_and_crop)

while True:
    cv2.imshow("Image", image)
    key = cv2.waitKey(1) & 0xFF

    # Press 's' to save the current mappings
    if key == ord("s"):
        with open(OUTPUT_FILE, "w") as f:
            json.dump(device_mapping, f, indent=4)
        print(f"Mappings saved to: {OUTPUT_FILE}")

    # Press 'q' to quit and save
    elif key == ord("q"):
        with open(OUTPUT_FILE, "w") as f:
            json.dump(device_mapping, f, indent=4)
        print(f"Final mappings saved to: {OUTPUT_FILE}")
        break

cv2.destroyAllWindows()
