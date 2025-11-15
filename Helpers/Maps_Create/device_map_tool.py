"""
Device Map Creator - User-Friendly GUI Tool
===========================================

A simple, user-friendly tool for creating and checking device maps.
No coding knowledge required!

Features:
- Visual device mapping by clicking and dragging on images
- Real-time preview of mapped devices
- Automatic validation and error checking
- Easy to use for non-programmers

Usage:
    python device_map_tool.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageTk

# Get project root for relative paths
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DeviceMapCreator:
    """User-friendly GUI for creating and checking device maps."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Device Map Creator")
        self.root.geometry("1000x700")
        
        # Variables
        self.image_path = tk.StringVar()
        self.json_path = tk.StringVar(value=str(_PROJECT_ROOT / "Json_Files" / "mapping.json"))
        self.sample_type = tk.StringVar(value="Cross_bar")
        self.section = tk.StringVar(value="A")
        self.device_counter = 1
        self.device_mapping = {}
        self.current_image = None
        self.display_image = None
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Create the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Device Map Creator",
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Instructions
        instructions = (
            "Instructions:\n"
            "1. Select an image file of your device layout\n"
            "2. (Optional) Load existing mapping or start new\n"
            "3. Enter sample type and section name\n"
            "4. Click and drag on the image to map each device\n"
            "5. Use 'Check Mapping' to verify your work\n"
            "6. Save when finished"
        )
        info_text = tk.Text(
            main_frame,
            height=7,
            width=50,
            wrap=tk.WORD,
            font=("Arial", 9)
        )
        info_text.grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        info_text.insert("1.0", instructions)
        info_text.config(state=tk.DISABLED)
        
        # File selection section
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Image file
        ttk.Label(file_frame, text="Image File:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(file_frame, textvariable=self.image_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_image).grid(row=0, column=2, padx=5)
        
        # JSON file
        ttk.Label(file_frame, text="Mapping JSON:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.json_path, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_json).grid(row=1, column=2, padx=5)
        
        # Sample configuration
        config_frame = ttk.LabelFrame(main_frame, text="Sample Configuration", padding="10")
        config_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(config_frame, text="Sample Type:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(config_frame, textvariable=self.sample_type, width=20).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        ttk.Label(config_frame, text="Section:").grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Entry(config_frame, textvariable=self.section, width=10).grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Existing Mapping", command=self.load_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="New Mapping", command=self.new_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Check Mapping", command=self.check_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Mapping", command=self.save_mapping).pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready - Select an image to begin", foreground="blue")
        self.status_label.grid(row=5, column=0, columnspan=3, pady=10)
        
        # Image display area (will be created when image is loaded)
        self.image_label = None
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
    def browse_image(self):
        """Browse for image file."""
        filename = filedialog.askopenfilename(
            title="Select Device Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.image_path.set(filename)
            
    def browse_json(self):
        """Browse for JSON file."""
        filename = filedialog.askopenfilename(
            title="Select Mapping JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(_PROJECT_ROOT / "Json_Files")
        )
        if filename:
            self.json_path.set(filename)
            
    def load_image(self):
        """Load and display the image for mapping."""
        img_path = self.image_path.get()
        if not img_path or not os.path.exists(img_path):
            messagebox.showerror("Error", "Please select a valid image file.")
            return
            
        try:
            # Read image with OpenCV for mapping
            self.current_image = cv2.imread(img_path)
            if self.current_image is None:
                raise ValueError("Could not read image file")
                
            # Create display copy
            self.display_image = self.current_image.copy()
            
            # Show image in new window for mapping
            cv2.namedWindow("Device Mapping - Click and Drag to Map Devices", cv2.WINDOW_NORMAL)
            cv2.setMouseCallback("Device Mapping - Click and Drag to Map Devices", self.mouse_callback)
            
            # Initialize state for mouse callback
            self.refPt = []
            self.cropping = False
            
            # Start keyboard handler
            self.root.after(100, self.check_window_keys)
            
            cv2.imshow("Device Mapping - Click and Drag to Map Devices", self.display_image)
            
            # Show instructions
            self.show_mapping_instructions()
            
            self.status_label.config(
                text=f"Image loaded! Use the image window to map devices. Devices mapped: {len(self.device_mapping)}",
                foreground="green"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image: {str(e)}")
            
    def show_mapping_instructions(self):
        """Show mapping instructions in a popup."""
        instructions = (
            "HOW TO MAP DEVICES:\n\n"
            "1. Click and hold at the TOP-LEFT corner of a device\n"
            "2. Drag to the BOTTOM-RIGHT corner\n"
            "3. Release the mouse button\n"
            "4. The device will be automatically numbered\n\n"
            "IMPORTANT:\n"
            "- Always drag from LEFT to RIGHT, TOP to BOTTOM\n"
            "- Make sure each device has a proper rectangle\n"
            "- Green boxes = valid mappings\n"
            "- Red boxes = invalid mappings (need fixing)\n\n"
            "KEYBOARD SHORTCUTS:\n"
            "- Press 'S' to save current progress\n"
            "- Press 'Q' to quit (auto-saves)\n"
            "- Press 'R' to reset current device\n"
            "- Press 'U' to undo last device"
        )
        messagebox.showinfo("Mapping Instructions", instructions)
        
    def mouse_callback(self, event, x, y, flags, param):
        """OpenCV mouse callback wrapper."""
        self.click_and_crop(event, x, y, flags, param)
        
    def check_window_keys(self):
        """Check for keyboard input in OpenCV window."""
        if self.display_image is not None:
            key = cv2.waitKey(1) & 0xFF
            
            # Press 's' to save
            if key == ord("s"):
                self.save_mapping()
            # Press 'q' to quit
            elif key == ord("q"):
                if len(self.device_mapping) > 0:
                    self.save_mapping()
                cv2.destroyAllWindows()
                self.display_image = None
                return
            # Press 'r' to reset current device (if cropping)
            elif key == ord("r"):
                self.cropping = False
                self.refPt = []
                print("Reset current device")
            # Press 'u' to undo last device
            elif key == ord("u"):
                if self.device_mapping:
                    last_key = list(self.device_mapping.keys())[-1]
                    del self.device_mapping[last_key]
                    self.device_counter -= 1
                    print(f"Undid {last_key}")
                    # Redraw image
                    self.display_image = self.current_image.copy()
                    for dev_name, bounds in self.device_mapping.items():
                        x_min, y_min = bounds["x_min"], bounds["y_min"]
                        x_max, y_max = bounds["x_max"], bounds["y_max"]
                        cv2.rectangle(self.display_image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
                        cv2.putText(self.display_image, dev_name, (x_min, y_min - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    cv2.imshow("Device Mapping - Click and Drag to Map Devices", self.display_image)
                    self.status_label.config(
                        text=f"Undid last device. Total devices: {len(self.device_mapping)}",
                        foreground="orange"
                    )
                    
            # Continue checking
            self.root.after(100, self.check_window_keys)
            
    def click_and_crop(self, event, x, y, flags, param):
        """Handle mouse clicks for device mapping."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.refPt = [(x, y)]
            self.cropping = True
            
        elif event == cv2.EVENT_MOUSEMOVE and self.cropping:
            # Draw temporary rectangle while dragging
            temp_image = self.display_image.copy()
            cv2.rectangle(temp_image, self.refPt[0], (x, y), (0, 255, 0), 2)
            cv2.imshow("Device Mapping - Click and Drag to Map Devices", temp_image)
            
        elif event == cv2.EVENT_LBUTTONUP:
            self.refPt.append((x, y))
            self.cropping = False
            
            # Ensure min/max values are correct (left to right, top to bottom)
            x_min = min(self.refPt[0][0], self.refPt[1][0])
            x_max = max(self.refPt[0][0], self.refPt[1][0])
            y_min = min(self.refPt[0][1], self.refPt[1][1])
            y_max = max(self.refPt[0][1], self.refPt[1][1])
            
            # Validate rectangle
            if x_max - x_min < 5 or y_max - y_min < 5:
                messagebox.showwarning(
                    "Invalid Rectangle",
                    "Rectangle is too small. Please draw a larger rectangle."
                )
                return
                
            # Save device mapping
            device_name = f"device_{self.device_counter}"
            self.device_mapping[device_name] = {
                "x_min": x_min,
                "y_min": y_min,
                "x_max": x_max,
                "y_max": y_max,
                "sample": self.sample_type.get(),
                "section": self.section.get()
            }
            
            # Draw the rectangle on display image
            cv2.rectangle(self.display_image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
            cv2.putText(
                self.display_image,
                device_name,
                (x_min, y_min - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )
            
            cv2.imshow("Device Mapping - Click and Drag to Map Devices", self.display_image)
            
            print(f"✓ Mapped {device_name}: ({x_min}, {y_min}) to ({x_max}, {y_max})")
            self.device_counter += 1
            
            self.status_label.config(
                text=f"Device {device_name} mapped! Total devices: {len(self.device_mapping)}",
                foreground="green"
            )
            
    def load_mapping(self):
        """Load existing mapping from JSON file."""
        json_path = self.json_path.get()
        if not json_path or not os.path.exists(json_path):
            messagebox.showerror("Error", "Please select a valid JSON file.")
            return
            
        try:
            with open(json_path, 'r') as f:
                full_mapping = json.load(f)
                
            # Extract mapping for current sample type
            sample_type = self.sample_type.get()
            if sample_type in full_mapping:
                self.device_mapping = full_mapping[sample_type].copy()
                
                # Find highest device number
                max_num = 0
                for device_name in self.device_mapping.keys():
                    if device_name.startswith("device_"):
                        try:
                            num = int(device_name.split("_")[1])
                            max_num = max(max_num, num)
                        except:
                            pass
                self.device_counter = max_num + 1
                
                self.status_label.config(
                    text=f"Loaded {len(self.device_mapping)} devices from mapping file",
                    foreground="green"
                )
                messagebox.showinfo("Success", f"Loaded {len(self.device_mapping)} devices for sample type '{sample_type}'")
            else:
                messagebox.showinfo("Info", f"No mapping found for sample type '{sample_type}'. Starting new mapping.")
                self.device_mapping = {}
                self.device_counter = 1
                
        except json.JSONDecodeError:
            messagebox.showerror("Error", "JSON file is not valid. Please check the file format.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load mapping: {str(e)}")
            
    def new_mapping(self):
        """Start a new mapping."""
        if len(self.device_mapping) > 0:
            if not messagebox.askyesno("Confirm", "This will clear all current mappings. Continue?"):
                return
                
        self.device_mapping = {}
        self.device_counter = 1
        self.display_image = self.current_image.copy() if self.current_image is not None else None
        
        if self.display_image is not None:
            cv2.imshow("Device Mapping - Click and Drag to Map Devices", self.display_image)
            
        self.status_label.config(text="Started new mapping. Ready to map devices.", foreground="blue")
        messagebox.showinfo("New Mapping", "Started fresh mapping. Begin mapping devices by clicking and dragging on the image.")
        
    def check_mapping(self):
        """Check and validate the current mapping."""
        if len(self.device_mapping) == 0:
            messagebox.showinfo("Info", "No devices mapped yet. Map some devices first.")
            return
            
        # Validation
        errors = []
        warnings = []
        
        for device_name, bounds in self.device_mapping.items():
            # Check for required keys
            required_keys = ["x_min", "y_min", "x_max", "y_max"]
            missing = [key for key in required_keys if key not in bounds]
            if missing:
                errors.append(f"{device_name}: Missing keys {missing}")
                continue
                
            x_min, y_min = bounds["x_min"], bounds["y_min"]
            x_max, y_max = bounds["x_max"], bounds["y_max"]
            
            # Check min/max values
            if x_min >= x_max:
                errors.append(f"{device_name}: x_min ({x_min}) >= x_max ({x_max})")
            if y_min >= y_max:
                errors.append(f"{device_name}: y_min ({y_min}) >= y_max ({y_max})")
                
            # Check rectangle size
            width = x_max - x_min
            height = y_max - y_min
            if width < 5 or height < 5:
                warnings.append(f"{device_name}: Very small rectangle ({width}x{height})")
                
            # Check sample and section
            if "sample" not in bounds or not bounds["sample"]:
                warnings.append(f"{device_name}: Missing sample type")
            if "section" not in bounds or not bounds["section"]:
                warnings.append(f"{device_name}: Missing section")
                
        # Fix auto-fixable issues
        fixed = 0
        for device_name, bounds in self.device_mapping.items():
            if "x_min" in bounds and "x_max" in bounds:
                if bounds["x_min"] > bounds["x_max"]:
                    bounds["x_min"], bounds["x_max"] = bounds["x_max"], bounds["x_min"]
                    fixed += 1
            if "y_min" in bounds and "y_max" in bounds:
                if bounds["y_min"] > bounds["y_max"]:
                    bounds["y_min"], bounds["y_max"] = bounds["y_max"], bounds["y_min"]
                    fixed += 1
                    
        # Report results
        message = f"Validation Results:\n\n"
        message += f"✓ Total devices: {len(self.device_mapping)}\n"
        if fixed > 0:
            message += f"✓ Auto-fixed {fixed} issues\n"
        if warnings:
            message += f"⚠ {len(warnings)} warnings\n"
        if errors:
            message += f"❌ {len(errors)} errors\n"
            
        if errors:
            message += "\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n... and {len(errors) - 10} more"
                
        if warnings:
            message += "\n\nWarnings:\n" + "\n".join(warnings[:10])
            if len(warnings) > 10:
                message += f"\n... and {len(warnings) - 10} more"
                
        if not errors and not warnings:
            message += "\n✓ All devices are valid!"
            messagebox.showinfo("Validation Complete", message)
        elif errors:
            messagebox.showerror("Validation Failed", message)
        else:
            messagebox.showwarning("Validation Complete", message)
            
        self.status_label.config(
            text=f"Validation complete. Devices: {len(self.device_mapping)}, Errors: {len(errors)}, Warnings: {len(warnings)}",
            foreground="green" if not errors else "red"
        )
        
    def save_mapping(self):
        """Save mapping to JSON file."""
        if len(self.device_mapping) == 0:
            messagebox.showwarning("Warning", "No devices mapped. Nothing to save.")
            return
            
        json_path = self.json_path.get()
        if not json_path:
            messagebox.showerror("Error", "Please specify a JSON file path.")
            return
            
        try:
            # Load existing file or create new structure
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    full_mapping = json.load(f)
            else:
                full_mapping = {}
                
            # Update mapping for current sample type
            sample_type = self.sample_type.get()
            if sample_type not in full_mapping:
                full_mapping[sample_type] = {}
                
            full_mapping[sample_type].update(self.device_mapping)
            
            # Save with proper formatting
            with open(json_path, 'w') as f:
                json.dump(full_mapping, f, indent=2, separators=(",", ": "))
                
            messagebox.showinfo(
                "Success",
                f"Saved {len(self.device_mapping)} devices to {json_path}\n"
                f"Sample type: {sample_type}"
            )
            
            self.status_label.config(
                text=f"Saved {len(self.device_mapping)} devices successfully!",
                foreground="green"
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not save mapping: {str(e)}")
            

def main():
    """Main entry point."""
    root = tk.Tk()
    app = DeviceMapCreator(root)
    root.mainloop()


if __name__ == "__main__":
    main()

