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

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from PIL import Image, ImageTk

# Get project root for relative paths
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAX_DISPLAY_SIZE = 1400


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

        # Image / canvas state
        self.pil_image = None
        self.display_scale = 1.0
        self.photo = None
        self.mapping_window = None
        self.canvas = None
        self.ref_pt = None
        self.cropping = False
        self.drag_rect_id = None

        self.setup_ui()

    def setup_ui(self):
        """Create the user interface."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        title_label = ttk.Label(
            main_frame,
            text="Device Map Creator",
            font=("Arial", 16, "bold"),
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))

        instructions = (
            "Instructions:\n"
            "1. Select an image file of your device layout\n"
            "2. (Optional) Load existing mapping or start new\n"
            "3. Enter sample type and section name\n"
            "4. Click 'Load Image', then click and drag on the mapping window\n"
            "5. Use 'Check Mapping' to verify your work\n"
            "6. Save when finished\n\n"
            "In the mapping window: S=save, R=reset drag, U=undo last device"
        )
        info_text = tk.Text(
            main_frame,
            height=8,
            width=50,
            wrap=tk.WORD,
            font=("Arial", 9),
        )
        info_text.grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        info_text.insert("1.0", instructions)
        info_text.config(state=tk.DISABLED)

        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(file_frame, text="Image File:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(file_frame, textvariable=self.image_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_image).grid(row=0, column=2, padx=5)

        ttk.Label(file_frame, text="Mapping JSON:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.json_path, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self.browse_json).grid(row=1, column=2, padx=5)

        config_frame = ttk.LabelFrame(main_frame, text="Sample Configuration", padding="10")
        config_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(config_frame, text="Sample Type:").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Entry(config_frame, textvariable=self.sample_type, width=20).grid(row=0, column=1, padx=5, sticky=tk.W)

        ttk.Label(config_frame, text="Section:").grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Entry(config_frame, textvariable=self.section, width=10).grid(row=0, column=3, padx=5, sticky=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text="Load Image", command=self.load_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Existing Mapping", command=self.load_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="New Mapping", command=self.new_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Check Mapping", command=self.check_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Mapping", command=self.save_mapping).pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(main_frame, text="Ready - Select an image to begin", foreground="blue")
        self.status_label.grid(row=5, column=0, columnspan=3, pady=10)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def browse_image(self):
        filename = filedialog.askopenfilename(
            title="Select Device Image",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self.image_path.set(filename)

    def browse_json(self):
        filename = filedialog.askopenfilename(
            title="Select Mapping JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(_PROJECT_ROOT / "Json_Files"),
        )
        if filename:
            self.json_path.set(filename)

    def _canvas_to_image(self, x, y):
        return int(x / self.display_scale), int(y / self.display_scale)

    def _image_to_canvas(self, x, y):
        return x * self.display_scale, y * self.display_scale

    def _open_mapping_window(self):
        if self.pil_image is None:
            return

        if self.mapping_window is not None and self.mapping_window.winfo_exists():
            self.mapping_window.lift()
            self._redraw_canvas()
            return

        self.mapping_window = tk.Toplevel(self.root)
        self.mapping_window.title("Device Mapping - Click and Drag to Map Devices")
        self.mapping_window.geometry("900x700")

        frame = ttk.Frame(self.mapping_window)
        frame.pack(fill=tk.BOTH, expand=True)

        x_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)

        img_w, img_h = self.pil_image.size
        scale = min(1.0, _MAX_DISPLAY_SIZE / max(img_w, img_h))
        self.display_scale = scale
        display_w = max(1, int(img_w * scale))
        display_h = max(1, int(img_h * scale))

        display_image = self.pil_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(display_image)

        self.canvas = tk.Canvas(
            frame,
            width=min(display_w, 880),
            height=min(display_h, 650),
            scrollregion=(0, 0, display_w, display_h),
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set,
            cursor="cross",
        )
        x_scroll.config(command=self.canvas.xview)
        y_scroll.config(command=self.canvas.yview)

        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo, tags="image")
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.mapping_window.bind("<Key>", self._on_mapping_key)
        self.canvas.focus_set()

        self._redraw_canvas()

    def _redraw_canvas(self):
        if self.canvas is None:
            return

        self.canvas.delete("device")
        for dev_name, bounds in self.device_mapping.items():
            x1, y1 = self._image_to_canvas(bounds["x_min"], bounds["y_min"])
            x2, y2 = self._image_to_canvas(bounds["x_max"], bounds["y_max"])
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00aa00", width=2, tags="device")
            self.canvas.create_text(
                x1 + 2,
                y1 - 2,
                text=dev_name,
                anchor=tk.SW,
                fill="#00aa00",
                font=("Arial", 9),
                tags="device",
            )

    def _clear_drag_preview(self):
        if self.drag_rect_id is not None:
            self.canvas.delete(self.drag_rect_id)
            self.drag_rect_id = None

    def _on_canvas_press(self, event):
        self.ref_pt = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.cropping = True
        self._clear_drag_preview()

    def _on_canvas_drag(self, event):
        if not self.cropping or self.ref_pt is None:
            return

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self._clear_drag_preview()
        self.drag_rect_id = self.canvas.create_rectangle(
            self.ref_pt[0],
            self.ref_pt[1],
            x,
            y,
            outline="#00ff00",
            width=2,
            dash=(4, 2),
            tags="drag",
        )

    def _on_canvas_release(self, event):
        if not self.cropping or self.ref_pt is None:
            return

        end_pt = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.cropping = False
        self._clear_drag_preview()

        x_min, y_min = self._canvas_to_image(min(self.ref_pt[0], end_pt[0]), min(self.ref_pt[1], end_pt[1]))
        x_max, y_max = self._canvas_to_image(max(self.ref_pt[0], end_pt[0]), max(self.ref_pt[1], end_pt[1]))
        self.ref_pt = None

        if x_max - x_min < 5 or y_max - y_min < 5:
            messagebox.showwarning(
                "Invalid Rectangle",
                "Rectangle is too small. Please draw a larger rectangle.",
                parent=self.mapping_window,
            )
            return

        device_name = f"device_{self.device_counter}"
        self.device_mapping[device_name] = {
            "x_min": x_min,
            "y_min": y_min,
            "x_max": x_max,
            "y_max": y_max,
            "sample": self.sample_type.get(),
            "section": self.section.get(),
        }

        print(f"Mapped {device_name}: ({x_min}, {y_min}) to ({x_max}, {y_max})")
        self.device_counter += 1
        self._redraw_canvas()
        self.status_label.config(
            text=f"Device {device_name} mapped! Total devices: {len(self.device_mapping)}",
            foreground="green",
        )

    def _on_mapping_key(self, event):
        key = event.char.lower()
        if key == "s":
            self.save_mapping()
        elif key == "r":
            self.cropping = False
            self.ref_pt = None
            self._clear_drag_preview()
            print("Reset current device")
        elif key == "u":
            if self.device_mapping:
                last_key = list(self.device_mapping.keys())[-1]
                del self.device_mapping[last_key]
                self.device_counter -= 1
                print(f"Undid {last_key}")
                self._redraw_canvas()
                self.status_label.config(
                    text=f"Undid last device. Total devices: {len(self.device_mapping)}",
                    foreground="orange",
                )

    def load_image(self):
        img_path = self.image_path.get()
        if not img_path or not os.path.exists(img_path):
            messagebox.showerror("Error", "Please select a valid image file.")
            return

        try:
            self.pil_image = Image.open(img_path).convert("RGB")
            self.ref_pt = None
            self.cropping = False
            self._open_mapping_window()
            self.status_label.config(
                text=(
                    f"Image loaded - click and drag in the mapping window. "
                    f"S=save, R=reset, U=undo. Devices mapped: {len(self.device_mapping)}"
                ),
                foreground="green",
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image: {str(e)}")

    def load_mapping(self):
        json_path = self.json_path.get()
        if not json_path or not os.path.exists(json_path):
            messagebox.showerror("Error", "Please select a valid JSON file.")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                full_mapping = json.load(f)

            sample_type = self.sample_type.get()
            if sample_type in full_mapping:
                self.device_mapping = full_mapping[sample_type].copy()

                max_num = 0
                for device_name in self.device_mapping.keys():
                    if device_name.startswith("device_"):
                        try:
                            num = int(device_name.split("_")[1])
                            max_num = max(max_num, num)
                        except ValueError:
                            pass
                self.device_counter = max_num + 1

                self._redraw_canvas()
                self.status_label.config(
                    text=f"Loaded {len(self.device_mapping)} devices from mapping file",
                    foreground="green",
                )
                messagebox.showinfo(
                    "Success",
                    f"Loaded {len(self.device_mapping)} devices for sample type '{sample_type}'",
                )
            else:
                messagebox.showinfo(
                    "Info",
                    f"No mapping found for sample type '{sample_type}'. Starting new mapping.",
                )
                self.device_mapping = {}
                self.device_counter = 1
                self._redraw_canvas()

        except json.JSONDecodeError:
            messagebox.showerror("Error", "JSON file is not valid. Please check the file format.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load mapping: {str(e)}")

    def new_mapping(self):
        if len(self.device_mapping) > 0:
            if not messagebox.askyesno("Confirm", "This will clear all current mappings. Continue?"):
                return

        self.device_mapping = {}
        self.device_counter = 1
        self._redraw_canvas()
        self.status_label.config(text="Started new mapping. Ready to map devices.", foreground="blue")
        messagebox.showinfo(
            "New Mapping",
            "Started fresh mapping. Begin mapping devices by clicking and dragging on the image.",
        )

    def check_mapping(self):
        if len(self.device_mapping) == 0:
            messagebox.showinfo("Info", "No devices mapped yet. Map some devices first.")
            return

        errors = []
        warnings = []

        for device_name, bounds in self.device_mapping.items():
            required_keys = ["x_min", "y_min", "x_max", "y_max"]
            missing = [key for key in required_keys if key not in bounds]
            if missing:
                errors.append(f"{device_name}: Missing keys {missing}")
                continue

            x_min, y_min = bounds["x_min"], bounds["y_min"]
            x_max, y_max = bounds["x_max"], bounds["y_max"]

            if x_min >= x_max:
                errors.append(f"{device_name}: x_min ({x_min}) >= x_max ({x_max})")
            if y_min >= y_max:
                errors.append(f"{device_name}: y_min ({y_min}) >= y_max ({y_max})")

            width = x_max - x_min
            height = y_max - y_min
            if width < 5 or height < 5:
                warnings.append(f"{device_name}: Very small rectangle ({width}x{height})")

            if "sample" not in bounds or not bounds["sample"]:
                warnings.append(f"{device_name}: Missing sample type")
            if "section" not in bounds or not bounds["section"]:
                warnings.append(f"{device_name}: Missing section")

        fixed = 0
        for bounds in self.device_mapping.values():
            if "x_min" in bounds and "x_max" in bounds and bounds["x_min"] > bounds["x_max"]:
                bounds["x_min"], bounds["x_max"] = bounds["x_max"], bounds["x_min"]
                fixed += 1
            if "y_min" in bounds and "y_max" in bounds and bounds["y_min"] > bounds["y_max"]:
                bounds["y_min"], bounds["y_max"] = bounds["y_max"], bounds["y_min"]
                fixed += 1

        message = "Validation Results:\n\n"
        message += f"Total devices: {len(self.device_mapping)}\n"
        if fixed > 0:
            message += f"Auto-fixed {fixed} issues\n"
        if warnings:
            message += f"{len(warnings)} warnings\n"
        if errors:
            message += f"{len(errors)} errors\n"

        if errors:
            message += "\nErrors:\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                message += f"\n... and {len(errors) - 10} more"

        if warnings:
            message += "\n\nWarnings:\n" + "\n".join(warnings[:10])
            if len(warnings) > 10:
                message += f"\n... and {len(warnings) - 10} more"

        if not errors and not warnings:
            message += "\nAll devices are valid!"
            messagebox.showinfo("Validation Complete", message)
        elif errors:
            messagebox.showerror("Validation Failed", message)
        else:
            messagebox.showwarning("Validation Complete", message)

        self._redraw_canvas()
        self.status_label.config(
            text=(
                f"Validation complete. Devices: {len(self.device_mapping)}, "
                f"Errors: {len(errors)}, Warnings: {len(warnings)}"
            ),
            foreground="green" if not errors else "red",
        )

    def save_mapping(self):
        if len(self.device_mapping) == 0:
            messagebox.showwarning("Warning", "No devices mapped. Nothing to save.")
            return

        json_path = self.json_path.get()
        if not json_path:
            messagebox.showerror("Error", "Please specify a JSON file path.")
            return

        try:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    full_mapping = json.load(f)
            else:
                full_mapping = {}

            sample_type = self.sample_type.get()
            if sample_type not in full_mapping:
                full_mapping[sample_type] = {}

            full_mapping[sample_type].update(self.device_mapping)

            json_dir = os.path.dirname(os.path.abspath(json_path))
            if json_dir:
                os.makedirs(json_dir, exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(full_mapping, f, indent=2, separators=(",", ": "))

            messagebox.showinfo(
                "Success",
                f"Saved {len(self.device_mapping)} devices to {json_path}\n"
                f"Sample type: {sample_type}",
            )
            self.status_label.config(
                text=f"Saved {len(self.device_mapping)} devices successfully!",
                foreground="green",
            )

        except Exception as e:
            messagebox.showerror("Error", f"Could not save mapping: {str(e)}")


def main():
    root = tk.Tk()
    DeviceMapCreator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
