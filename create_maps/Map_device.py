import cv2
import json

################################################################

# when mapping always go from left to right up to down
# e.g., max values to min values, or it may cause errors
# if onnly some are mapped and noth otheres but it all looks okay this may be the reason

################################################################



# Global variables
refPt = []
cropping = False
device_counter = 1
device_mapping = {}

# Load image
image_path = "../Sample_Infomation/Multiplexer.jpg"
image = cv2.imread(image_path)
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
        with open("device_mapping_multiplexer.json", "w") as f:
            json.dump(device_mapping, f, indent=4)
        print("Mappings saved!")

    # Press 'q' to quit and save
    elif key == ord("q"):
        with open("device_mapping_multiplexer.json", "w") as f:
            json.dump(device_mapping, f, indent=4)
        print("Final mappings saved! Exiting.")
        break

cv2.destroyAllWindows()
