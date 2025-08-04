import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import json
from Measurement_GUI import MeasurementGUI
from Equipment_Classes.Multiplexer.Multiplexer_Class import MultiplexerController

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]},
    "Multiplexer": {
        "sections": {"A": True},
        "devices": [str(i) for i in range(1, 11)]}}

multiplexer_types = {'Pyswitchbox': {}, 'Electronic_Mpx': {}}


# Function to load device mapping from JSON file
def load_device_mapping(filename="Json_Files\pin_mapping.json"):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Error: JSON file not found.")
        return {}
    except json.JSONDecodeError:
        print("Error: JSON file is not formatted correctly.")
        return {}


pin_mapping = load_device_mapping()

# Load device mapping
with open("Json_Files/mapping.json", "r") as f:
    device_maps = json.load(f)


class SampleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Device Viewer")
        self.root.geometry("1000x650")

        # Defaults
        self.multiplexer_type = "Pyswitchbox"
        self.current_device_map = "Cross_bar"
        self.pyswitchbox = True
        self.Electronic_Mpx = False
        self.update_device_type(self.current_device_map)
        self.current_index = 0  # Index of currently selected device

        # Selected devices tracking
        self.selected_devices = set()  # Store selected device names
        self.selected_indices = []  # Store indices of selected devices
        self.current_selected_index = 0  # Index within selected devices

        # Flags
        self.pyswitchbox = True
        self.Electronic_Mpx = False
        self.measurement_window = False

        # print(self.device_maps_list)
        # print(self.device_list)

        # initialise switchbox
        # self.switchbox = pySwitchbox.Switchbox()

        # Multiplexer Type Dropdown
        tk.Label(root, text="Multiplexer").grid(row=0, column=0, sticky='w')
        self.Multiplexer_type_var = tk.StringVar()
        self.Multiplexer_dropdown = ttk.Combobox(root, textvariable=self.Multiplexer_type_var,
                                                 values=list(multiplexer_types.keys()))
        self.Multiplexer_dropdown.grid(row=0, column=1)
        self.Multiplexer_dropdown.bind("<<ComboboxSelected>>", self.update_multiplexer)

        # Sample Type Dropdown
        tk.Label(root, text="Sample type").grid(row=1, column=0, sticky='w')
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(root, textvariable=self.sample_type_var, values=list(sample_config.keys()))
        self.sample_dropdown.grid(row=1, column=1)
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)

        # Section Dropdown
        tk.Label(root, text="Section").grid(row=2, column=0, sticky='w')
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(root, textvariable=self.section_var)
        self.section_dropdown.grid(row=2, column=1)
        # Section Entry
        # tk.Label(root, text="Section").grid(row=2, column=0, sticky='w')
        # self.section_var = tk.StringVar()
        # self.section_entry = tk.Entry(root, textvariable=self.section_var)
        # self.section_entry.grid(row=2, column=1)

        # Device Number Dropdown
        tk.Label(root, text="Device Number").grid(row=3, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(root, textvariable=self.device_var)
        self.device_dropdown.grid(row=3, column=1)

        # Information Box
        self.info_box = tk.Label(root, text="Current Device: None", relief=tk.SUNKEN, width=30)
        self.info_box.grid(row=4, column=0, columnspan=2, pady=10)

        # Navigation Buttons
        self.prev_button = tk.Button(root, text="<", command=self.prev_device)
        self.prev_button.grid(row=5, column=0, pady=2)

        self.clear_button = tk.Button(root, text="Clear", command=self.clear_canvas)
        self.clear_button.grid(row=6, column=1, pady=2)

        self.change_button = tk.Button(root, text="Go", command=self.change_relays)
        self.change_button.grid(row=6, column=0, pady=2)

        self.next_button = tk.Button(root, text=">", command=self.next_device)
        self.next_button.grid(row=5, column=1, pady=2)

        # Canvas for Image
        self.canvas = tk.Canvas(root, width=400, height=400, bg="white", highlightbackground="black")
        self.canvas.grid(row=0, column=2, rowspan=5, padx=10)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Control-Button-1>", self.canvas_ctrl_click)  # Ctrl+Click for selection

        # Device Selection Frame
        self.create_device_selection_frame()

        # Terminal Output
        self.terminal_output = tk.Text(root, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=7, column=0, columnspan=4, pady=10)

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        # Measurement Button
        self.measure_button = tk.Button(root, text="Measure Devices", command=self.open_measurement_window)
        self.measure_button.grid(row=8, column=0, columnspan=2, pady=10)

        # Placeholder for clicked points
        # self.electrode_points = []

    def create_device_selection_frame(self):
        """Create a frame with checkboxes for device selection"""
        # Main frame for device selection
        selection_frame = tk.LabelFrame(self.root, text="Device Selection", padx=5, pady=5)
        selection_frame.grid(row=0, column=3, rowspan=6, padx=10, sticky='nsew')

        # Buttons frame
        button_frame = tk.Frame(selection_frame)
        button_frame.pack(fill='x', pady=(0, 5))

        tk.Button(button_frame, text="Select All", command=self.select_all_devices).pack(side='left', padx=2)
        tk.Button(button_frame, text="Deselect All", command=self.deselect_all_devices).pack(side='left', padx=2)
        tk.Button(button_frame, text="Invert", command=self.invert_selection).pack(side='left', padx=2)

        # Scrollable frame for checkboxes
        canvas = tk.Canvas(selection_frame, width=150, height=300)
        scrollbar = ttk.Scrollbar(selection_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.device_checkboxes = {}
        self.checkbox_vars = {}

        # Status label
        self.selection_status = tk.Label(selection_frame, text="Selected: 0/0")
        self.selection_status.pack(pady=5)

        self.scrollable_frame = scrollable_frame

    def update_device_checkboxes(self):
        """Update the device checkboxes based on current device list"""
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.device_checkboxes.clear()
        self.checkbox_vars.clear()

        # Create new checkboxes
        for i, device in enumerate(self.device_list):
            var = tk.BooleanVar(value=True)  # Default to selected
            cb = tk.Checkbutton(self.scrollable_frame, text=device, variable=var,
                                command=self.update_selected_devices)
            cb.grid(row=i, column=0, sticky='w')

            self.device_checkboxes[device] = cb
            self.checkbox_vars[device] = var
            self.selected_devices.add(device)

        self.update_selected_devices()

    def select_all_devices(self):
        """Select all devices"""
        for var in self.checkbox_vars.values():
            var.set(True)
        self.update_selected_devices()

    def deselect_all_devices(self):
        """Deselect all devices"""
        for var in self.checkbox_vars.values():
            var.set(False)
        self.update_selected_devices()

    def invert_selection(self):
        """Invert device selection"""
        for var in self.checkbox_vars.values():
            var.set(not var.get())
        self.update_selected_devices()

    def update_selected_devices(self):
        """Update the list of selected devices"""
        self.selected_devices.clear()
        self.selected_indices.clear()

        for device, var in self.checkbox_vars.items():
            if var.get():
                self.selected_devices.add(device)
                # Find index of device in device_list
                if device in self.device_list:
                    self.selected_indices.append(self.device_list.index(device))

        # Sort indices
        self.selected_indices.sort()

        # Update status
        total = len(self.device_list)
        selected = len(self.selected_devices)
        self.selection_status.config(text=f"Selected: {selected}/{total}")

        # Update canvas highlights
        self.update_canvas_selection_highlights()

        # Log selection
        self.log_terminal(f"Selected devices: {', '.join(sorted(self.selected_devices))}")

    def update_canvas_selection_highlights(self):
        """Update visual indicators on canvas for selected devices"""
        # Remove existing selection highlights
        self.canvas.delete("selection")

        if hasattr(self, 'original_image'):
            orig_width, orig_height = self.original_image.size
            scale_x = orig_width / 400
            scale_y = orig_height / 400

            for device, bounds in self.device_mapping.items():
                if device in self.selected_devices:
                    x_min = bounds["x_min"] / scale_x
                    x_max = bounds["x_max"] / scale_x
                    y_min = bounds["y_min"] / scale_y
                    y_max = bounds["y_max"] / scale_y

                    # Draw green rectangle for selected devices
                    self.canvas.create_rectangle(
                        x_min, y_min, x_max, y_max,
                        outline="green", width=1, tags="selection"
                    )

    def canvas_ctrl_click(self, event):
        """Handle Ctrl+Click for device selection toggle"""
        if hasattr(self, 'original_image'):
            orig_width, orig_height = self.original_image.size
            scale_x = orig_width / 400
            scale_y = orig_height / 400

            for device, bounds in self.device_mapping.items():
                x_min = bounds["x_min"] / scale_x
                x_max = bounds["x_max"] / scale_x
                y_min = bounds["y_min"] / scale_y
                y_max = bounds["y_max"] / scale_y

                if x_min <= event.x <= x_max and y_min <= event.y <= y_max:
                    # Toggle device selection
                    if device in self.checkbox_vars:
                        current_value = self.checkbox_vars[device].get()
                        self.checkbox_vars[device].set(not current_value)
                        self.update_selected_devices()
                    break

    def update_multiplexer(self, event):
        self.multiplexer_type = self.Multiplexer_type_var.get()
        print("Multiplexer set to:", self.multiplexer_type)
        if self.multiplexer_type == "Pyswitchbox":
            # initialise switchbox
            # self.switchbox = pySwitchbox.Switchbox()
            print("Initiating Py Switch box")
        elif self.multiplexer_type == "Electronic_Mpx":
            print("initialising Electronic_Mpx")
            self.mpx = MultiplexerController()
        else:
            print("please check input")

    def load_image(self, sample):
        """ Load image into canvas set up to add others later simply """
        if sample == 'Cross_bar':
            sample = "Sample_Infomation/memristor.png"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        if sample == 'Multiplexer':
            sample = "Sample_Infomation/Multiplexer.jpg"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        # Redraw selection highlights
        self.update_canvas_selection_highlights()

    def update_device_type(self, current_device_map):
        # all maps from dict
        self.current_map_name = current_device_map
        self.device_mapping = device_maps[current_device_map]
        self.current_map_map = device_maps[current_device_map]
        self.device_maps_list = list(device_maps.keys())
        self.device_list = list(device_maps[current_device_map].keys())  # Dictionary of devices
        # Update device checkboxes when device type changes
        if hasattr(self, 'device_checkboxes'):
            self.update_device_checkboxes()

    def update_dropdowns(self, event):
        sample = self.sample_type_var.get()
        print("Sample chosen:", sample)
        self.update_device_type(sample)

        if sample in sample_config:
            sections = sample_config[sample]["sections"]
            self.section_dropdown["values"] = list(sections.keys())
            self.section_dropdown.set("")

            # Disable certain sections (keeping them visible)
            self.section_dropdown["state"] = "readonly"

            # Update device numbers
            self.device_dropdown["values"] = sample_config[sample]["devices"]
            self.device_dropdown.set("")

            # Call do_something when sample changes
            self.load_image(sample)
            self.device = self.device_var.get()

    def prev_device(self):
        """Move to the previous device in the selected devices list"""
        if not self.selected_indices:
            self.log_terminal("No devices selected")
            return

        # Find current device's position in selected devices
        current_device = self.device_list[self.current_index]
        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            # Move to previous selected device
            idx_in_selected = (idx_in_selected - 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            # If current device is not selected, move to first selected device
            self.current_index = self.selected_indices[0] if self.selected_indices else 0

        new_device = self.device_list[self.current_index]
        self.log_terminal(f"Previous device: {new_device}")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def next_device(self):
        """Move to the next device in the selected devices list"""
        if not self.selected_indices:
            self.log_terminal("No devices selected")
            return

        # Find current device's position in selected devices
        current_device = self.device_list[self.current_index]
        if self.current_index in self.selected_indices:
            idx_in_selected = self.selected_indices.index(self.current_index)
            # Move to next selected device
            idx_in_selected = (idx_in_selected + 1) % len(self.selected_indices)
            self.current_index = self.selected_indices[idx_in_selected]
        else:
            # If current device is not selected, move to first selected device
            self.current_index = self.selected_indices[0] if self.selected_indices else 0

        new_device = self.device_list[self.current_index]
        self.log_terminal(f"Next device: {new_device}")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def canvas_click(self, event):
        mapname = self.current_map_name
        #print(mapname)
        #print(self.current_map_map)

        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 400, 400
        # Compute the scaling factors
        scale_x = orig_width / scaled_width
        scale_y = orig_height / scaled_height

        for i, (device, bounds) in enumerate(self.device_mapping.items()):
            # Scale down the bounding box coordinates to match canvas size
            x_min_scaled = bounds["x_min"] / scale_x
            x_max_scaled = bounds["x_max"] / scale_x
            y_min_scaled = bounds["y_min"] / scale_y
            y_max_scaled = bounds["y_max"] / scale_y

            if x_min_scaled <= event.x <= x_max_scaled and y_min_scaled <= event.y <= y_max_scaled:
                # Remove previous highlights
                self.canvas.delete("highlight")

                # Update index
                self.current_index = i  # Now it holds the current index of the device

                self.device_var.set(device)
                self.sample_type_var.set(bounds["sample"])
                self.section_var.set(bounds["section"])
                self.info_box.config(text=f"Current Device: {device}")

                # Draw a rectangle around the clicked device
                self.canvas.create_rectangle(
                    x_min_scaled, y_min_scaled, x_max_scaled, y_max_scaled,
                    outline="red", width=2, tags="highlight"
                )

    def update_highlight(self, device):
        # Clear any existing highlights
        self.canvas.delete("highlight")

        # Get the device bounds
        bounds = self.device_mapping.get(device, None)
        if bounds:
            orig_width, orig_height = self.original_image.size
            scaled_width, scaled_height = 400, 400
            # Compute the scaling factors
            scale_x = orig_width / scaled_width
            scale_y = orig_height / scaled_height

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            # Draw a new rectangle
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="red", width=2, tags="highlight")

    def open_measurement_window(self):
        if not self.measurement_window:
            sample_type = self.sample_type_var.get()
            section = self.section_var.get()

            # Pass only selected devices to measurement window
            selected_device_list = [self.device_list[i] for i in self.selected_indices]

            if not selected_device_list:
                messagebox.showwarning("Warning", "No devices selected for measurement.")
                return

            self.change_relays()
            print("")
            print("Selected devices:")
            print(selected_device_list)
            print("")
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, selected_device_list, self)
            self.measurement_window = True
        else:
            self.measuremnt_gui.bring_to_top()

    def update_info_box(self, event=None):
        selected_sample = self.sample_type_var.get()
        selected_section = self.section_var.get()
        selected_device = self.device_var.get()
        device_text = f"Current Device: {selected_sample} - {selected_section} - {selected_device}"
        self.info_box.config(text=device_text)

    def change_relays(self):
        """Change relays for the current device"""
        current_device = self.device_list[self.current_index]

        # Check if current device is in selected devices
        if current_device not in self.selected_devices:
            self.log_terminal(f"Warning: Device {current_device} is not selected")
            response = messagebox.askyesno("Device Not Selected",
                                           f"Device {current_device} is not in the selected list. Continue anyway?")
            if not response:
                return

        if self.multiplexer_type == "Pyswitchbox":
            def get_device_pins(device_name):
                if device_name in pin_mapping:
                    return pin_mapping[device_name]["pins"]
                else:
                    print(f"Warning: {device_name} not found in mapping.")
                    return None

            self.log_terminal("changing relays to")
            self.log_terminal(self.device_list[self.current_index])
            # gives pins in array
            pins_arr = get_device_pins(self.device_list[self.current_index])
            # self.switchbox.activate(pins_arr)

            self.log_terminal(self.section_var.get() + self.device_var.get())
            if self.measurement_window:
                self.measuremnt_gui.current_index = self.current_index
                self.measuremnt_gui.update_variables()

        elif self.multiplexer_type == "Electronic_Mpx":
            self.log_terminal("changing multiplexer to")
            self.log_terminal(self.device_list[self.current_index])
            device_number = self.current_index + 1
            self.mpx.select_channel(device_number)

            print("Electronic_Mpx")
        elif self.multiplexer_type == "Multiplexer":
            print("Multiplexer")

    def clear_canvas(self):
        self.canvas.delete("all")
        self.log_terminal("Canvas cleared")
        # Reload the image and selection highlights
        if hasattr(self, 'sample_type_var'):
            sample = self.sample_type_var.get()
            if sample:
                self.load_image(sample)

    def log_terminal(self, message):
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, message + "\n")
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

    def Change_image(self, sample):
        self.log_terminal("change image sample")

    def get_selected_devices(self):
        """Return list of currently selected devices"""
        return [self.device_list[i] for i in self.selected_indices]

    def cycle_through_selected_devices(self):
        """Generator to cycle through only selected devices"""
        if not self.selected_indices:
            self.log_terminal("No devices selected for cycling")
            return

        while True:
            for idx in self.selected_indices:
                device = self.device_list[idx]
                self.current_index = idx
                self.device_var.set(device)
                self.info_box.config(text=f"Current Device: {device}")
                self.info_box.config(text=f"Current Device: {device}")
                self.update_highlight(device)
                self.change_relays()
                yield device


# Main execution
if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
