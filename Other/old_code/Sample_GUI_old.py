import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import json
from Measurement_GUI import MeasurementGUI
from Equipment_Classes.Multiplexer.Multiplexer_Class import MultiplexerController
# import pySwitchbox

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]},
    "Multiplexer": {
            "sections": {"A": True},
            "devices": [str(i) for i in range(1, 11)]}}

multiplexer_types = {'Pyswitchbox':{}, 'Electronic_Mpx':{}}

# Function to load device mapping from JSON file
def load_device_mapping(filename="Json_Files\\pin_mapping.json"):
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
with open("../../Json_Files/mapping.json", "r") as f:
    device_maps = json.load(f)

class SampleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Device Viewer")
        self.root.geometry("650x600")

        # Defaults
        self.multiplexer_type = "Pyswitchbox"
        self.current_device_map = "Cross_bar"
        self.pyswitchbox = True
        self.Electronic_Mpx = False
        self.update_device_type(self.current_device_map)
        self.current_index = 0  # Index of currently selected device


        # Flags
        self.pyswitchbox = True
        self.Electronic_Mpx = False
        self.measurement_window = False

        print(self.device_maps_list)
        print(self.device_list)

        # initialise switchbox
        # self.switchbox = pySwitchbox.Switchbox()

        # Multiplexer Type Dropdown
        tk.Label(root, text="Multiplexer").grid(row=0, column=0, sticky='w')
        self.Multiplexer_type_var = tk.StringVar()
        self.Multiplexer_dropdown = ttk.Combobox(root, textvariable=self.Multiplexer_type_var, values=list(multiplexer_types.keys()))
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

        # Terminal Output
        self.terminal_output = tk.Text(root, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=7, column=0, columnspan=3, pady=10)

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        # Measurement Button
        self.measure_button = tk.Button(root, text="Measure Devices", command=self.open_measurement_window)
        self.measure_button.grid(row=8, column=0, columnspan=2, pady=10)

        # Placeholder for clicked points
        # self.electrode_points = []
        # Load image

    def update_multiplexer(self,event):
        self.multiplexer_type = self.Multiplexer_type_var.get()
        print("multiplexer set too",self.multiplexer_type)
        if self.multiplexer_type == "Pyswitchbox":
            #initialise switchbox
            #self.switchbox = pySwitchbox.Switchbox()
            print("initiating py switch box please wait")
        elif self.multiplexer_type == "Electronic_Mpx":
            print("initialising Electronic_Mpx")
            self.mpx = MultiplexerController()

        else:
            print("please check input")



    def load_image(self, sample):
        """ Load imgae into canvas set up to add others later simply """

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

    def update_device_type(self, current_device_map):
        # all maps from dict
        self.device_mapping = device_maps[current_device_map]
        self.device_maps_list = list(device_maps.keys())
        self.device_list = list(device_maps[current_device_map].keys())  # Dictionary of devices
        # self.device_list = list(device_maps.keys())
    def update_dropdowns(self, event):

        sample = self.sample_type_var.get()
        print("sample chosen" ,sample)
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
            # self.Change_image(sample)

    def prev_device(self):

        # Move to the next device in the list
        self.current_index = (self.current_index - 1) % len(self.device_list)
        new_device = self.device_list[self.current_index]
        self.log_terminal("Previous device")

        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def next_device(self):
        # Move to the next device in the list
        self.current_index = (self.current_index + 1) % len(self.device_list)
        new_device = self.device_list[self.current_index]
        self.log_terminal("Next device")
        # Update the displayed device information
        self.device_var.set(new_device)
        self.info_box.config(text=f"Current Device: {new_device}")

        # Update the highlight
        self.update_highlight(new_device)

    def canvas_click(self, event):
        # print(event)


       #  mapname = self.current_map_name
       #  print(mapname)
       # # self.current_map_map = self.device_numbers[mapname]
       #  print(self.current_map_map)



        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 400, 400
        # Compute the scaling factors
        scale_x = orig_width / scaled_width
        scale_y = orig_height / scaled_height

        # for device, bounds in device_mapping.items():
        for i, (device, bounds) in enumerate(self.device_mapping.items()):

            # Scale down the bounding box coordinates to match canvas size
            x_min_scaled = bounds["x_min"] / scale_x
            x_max_scaled = bounds["x_max"] / scale_x
            y_min_scaled = bounds["y_min"] / scale_y
            y_max_scaled = bounds["y_max"] / scale_y

            # debugging when not devices not working once clicked
            # print(event.x, event.y)
            # print(event.x*scale_x,event.y*scale_y)

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
                # self.device = device

    def update_highlight(self, device):
        # Clear any existing highlights
        self.canvas.delete("highlight")
        #self.device_mapping[self.current_device_map]
        # Get the device bounds
        bounds = self.device_mapping.get(device, None)
        if bounds:
            scale_x = 1198 / 400  # Adjust based on your scaling factor
            scale_y = 1199 / 400

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

            # # Filter devices belonging to the selected sample type
            # selected_devices = [d for d in self.device_list if device_maps[d]["sample"] == sample_type]
            #
            # if not selected_devices:
            #     messagebox.showwarning("Warning", "No devices found for this sample.")
            #     return
            self.measuremnt_gui = MeasurementGUI(self.root, sample_type, section, self.device_list, self)
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
        if self.multiplexer_type == "Pyswitchbox":
            def get_device_pins(device_name):
                if device_name in pin_mapping:
                    # print(device_name,pin_mapping)
                    return pin_mapping[device_name]["pins"]
                else:
                    print(f"Warning: {device_name} not found in mapping.")
                    return None

            self.log_terminal("changing relays too")
            self.log_terminal(self.device_list[self.current_index])
            # gives pins in array
            pins_arr = get_device_pins(self.device_list[self.current_index])
            # self.switchbox.activate(pins_arr)

            self.log_terminal(self.section_var.get() + self.device_var.get())
            if self.measurement_window:
                self.measuremnt_gui.current_index = self.current_index
                self.measuremnt_gui.update_variables()
        elif self.multiplexer_type == "Electronic_Mpx":
            self.log_terminal("changing multiplexer too")
            self.log_terminal(self.device_list[self.current_index])
            device_number = self.current_index + 1
            self.mpx.select_channel(device_number)

            print("Electronic_Mpx")
        elif self.multiplexer_type == "Multiplexer":
            print("Multiplexer")

    def clear_canvas(self):
        self.canvas.delete("all")
        # self.electrode_points.clear()
        self.log_terminal("Canvas cleared")

    def log_terminal(self, message):
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, message + "\n")
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)

def Change_image(self, sample):
    self.log_terminal("change image sample")




