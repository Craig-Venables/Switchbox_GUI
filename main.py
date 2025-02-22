import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import json

# Load sample configuration from JSON file
sample_config = {
    "Cross_bar": {
        "sections": {"A": True, "B": True, "C": False, "D": True, "E": True, "F": False, "G": True, "H": True,
                     "I": True, "J": True, "K": True, "L": True},
        "devices": [str(i) for i in range(1, 11)]
    }

}

# Load device mapping
with open("mapping.json", "r") as f:
    device_mapping = json.load(f)


class SampleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Device Viewer")
        self.root.geometry("650x600")

        #list of all devices
        self.device_mapping = device_mapping  # Dictionary of devices
        self.device_list = list(device_mapping.keys())  # Ordered list of device names
        self.current_index = 0  # Index of currently selected device

        # Sample Type Dropdown
        tk.Label(root, text="Sample type").grid(row=0, column=0, sticky='w')
        self.sample_type_var = tk.StringVar()
        self.sample_dropdown = ttk.Combobox(root, textvariable=self.sample_type_var, values=list(sample_config.keys()))
        self.sample_dropdown.grid(row=0, column=1)
        self.sample_dropdown.bind("<<ComboboxSelected>>", self.update_dropdowns)

        # Section Dropdown
        tk.Label(root, text="Section").grid(row=1, column=0, sticky='w')
        self.section_var = tk.StringVar()
        self.section_dropdown = ttk.Combobox(root, textvariable=self.section_var)
        self.section_dropdown.grid(row=1, column=1)

        # Device Number Dropdown
        tk.Label(root, text="Device Number").grid(row=2, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(root, textvariable=self.device_var)
        self.device_dropdown.grid(row=2, column=1)

        # Information Box
        self.info_box = tk.Label(root, text="Current Device: None", relief=tk.SUNKEN, width=30)
        self.info_box.grid(row=3, column=0, columnspan=2, pady=10)

        # Navigation Buttons
        self.prev_button = tk.Button(root, text="<", command=self.prev_device)
        self.prev_button.grid(row=4, column=0, pady=2)

        self.clear_button = tk.Button(root, text="Clear", command=self.clear_canvas)
        self.clear_button.grid(row=5, column=1, pady=2)

        self.change_button = tk.Button(root, text="Go", command=self.change_relays)
        self.change_button.grid(row=5, column=0, pady=2)

        self.next_button = tk.Button(root, text=">", command=self.next_device)
        self.next_button.grid(row=4, column=1,pady=2)

        # Canvas for Image
        self.canvas = tk.Canvas(root, width=400, height=400, bg="white", highlightbackground="black")
        self.canvas.grid(row=0, column=2, rowspan=5, padx=10)
        self.canvas.bind("<Button-1>", self.canvas_click)


        # Terminal Output
        self.terminal_output = tk.Text(root, height=5, width=80, state=tk.DISABLED)
        self.terminal_output.grid(row=6, column=0, columnspan=3, pady=10)

        # Bind section and device selection to update_info_box
        self.section_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)
        self.device_dropdown.bind("<<ComboboxSelected>>", self.update_info_box)

        self.device = ""

        # Placeholder for clicked points
        #self.electrode_points = []
        # Load image


    def load_image(self,sample):
        """ Load imgae into canvas set up to add others later simply """

        if sample == 'Cross_bar':
            sample = "Sample_images/memristor.png"
            self.original_image = Image.open(sample)
            img = self.original_image.resize((400, 400))

            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        if sample == 'Sample 2':
            self.log_terminal("no image for selection")
            # clear image?




    def update_dropdowns(self, event):
        sample = self.sample_type_var.get()
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
            #self.Change_image(sample)

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
        #print(event)

        orig_width, orig_height = self.original_image.size
        scaled_width, scaled_height = 400, 400
        # Compute the scaling factors
        scale_x = orig_width / scaled_width
        scale_y = orig_height / scaled_height


        #for device, bounds in device_mapping.items():
        for i, (device, bounds) in enumerate(device_mapping.items()):


            # Scale down the bounding box coordinates to match canvas size
            x_min_scaled = bounds["x_min"] / scale_x
            x_max_scaled = bounds["x_max"] / scale_x
            y_min_scaled = bounds["y_min"] / scale_y
            y_max_scaled = bounds["y_max"] / scale_y

            # debugging when not devices not working once clicked
            #print(event.x, event.y)
            #print(event.x*scale_x,event.y*scale_y)

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
                #self.device = device


    def update_highlight(self, device):
        # Clear any existing highlights
        self.canvas.delete("highlight")

        # Get the device bounds
        bounds = device_mapping.get(device, None)
        if bounds:
            scale_x = 1198 / 400  # Adjust based on your scaling factor
            scale_y = 1199 / 400

            x_min = bounds["x_min"] / scale_x
            x_max = bounds["x_max"] / scale_x
            y_min = bounds["y_min"] / scale_y
            y_max = bounds["y_max"] / scale_y

            # Draw a new rectangle
            self.canvas.create_rectangle(x_min, y_min, x_max, y_max, outline="red", width=2, tags="highlight")



    def update_info_box(self, event=None):
        selected_sample = self.sample_type_var.get()
        selected_section = self.section_var.get()
        selected_device = self.device_var.get()
        device_text = f"Current Device: {selected_sample} - {selected_section} - {selected_device}"
        self.info_box.config(text=device_text)

    def change_relays(self):
        self.log_terminal("changing relays too")
        self.log_terminal(self.device_list[self.current_index])


        self.log_terminal(self.section_var.get()+self.device_var.get())

    def clear_canvas(self):
        self.canvas.delete("all")
        #self.electrode_points.clear()
        self.log_terminal("Canvas cleared")

    def log_terminal(self, message):
        self.terminal_output.config(state=tk.NORMAL)
        self.terminal_output.insert(tk.END, message + "\n")
        self.terminal_output.config(state=tk.DISABLED)
        self.terminal_output.see(tk.END)


    def Change_image(self,sample):
        self.log_terminal("change image sample")



if __name__ == "__main__":
    root = tk.Tk()
    app = SampleGUI(root)
    root.mainloop()
