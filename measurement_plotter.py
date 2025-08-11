import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import threading
import queue
import time
from collections import deque
from datetime import datetime
import gc

# Use threading-safe matplotlib backend
import matplotlib

matplotlib.use('TkAgg')


class MeasurementPlotter:
    """
    Real-time plotting window for measurement data.
    Fixed version with proper threading to prevent freezing.
    """

    def __init__(self, parent, measurement_type="IV Sweep", max_points_displayed=1000):
        """
        Initialize the plotter window.

        Args:
            parent: Parent window
            measurement_type: Type of measurement ("IV Sweep" or "Single Avg Measure")
            max_points_displayed: Maximum points to display per trace (for performance)
        """
        self.parent = parent
        self.measurement_type = measurement_type
        self.max_points_displayed = max_points_displayed

        # Create new window
        self.window = tk.Toplevel(parent)
        self.window.title(f"Real-time Measurement Plot - {measurement_type}")
        self.window.geometry("1000x700")

        # Data storage (thread-safe)
        self.data_lock = threading.Lock()
        self.device_data = {}  # {device_name: {'x': [], 'y': [], 'timestamps': []}}
        self.plot_lines = {}  # {device_name: line_object}
        self.colors = plt.cm.tab10(np.linspace(0, 1, 10))  # Color cycle
        self.device_colors = {}

        # Threading
        self.data_queue = queue.Queue()
        self.plot_queue = queue.Queue()  # Separate queue for plot updates
        self.running = True

        # Performance settings
        self.update_interval = 200  # ms (slower initial update)
        self.points_per_device = {}  # Track total points per device
        self.last_update_time = 0

        # Create GUI
        self.create_widgets()

        # Start update cycle
        self.schedule_update()

        # Window close handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start data processing thread
        self.data_thread = threading.Thread(target=self.process_data_thread, daemon=True)
        self.data_thread.start()

    def create_widgets(self):
        """Create the GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        # Status label
        self.status_label = ttk.Label(control_frame, text="Status: Running")
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Device count label
        self.device_count_label = ttk.Label(control_frame, text="Devices: 0")
        self.device_count_label.pack(side=tk.LEFT, padx=5)

        # Points count label
        self.points_label = ttk.Label(control_frame, text="Points: 0")
        self.points_label.pack(side=tk.LEFT, padx=5)

        # Performance label
        self.performance_label = ttk.Label(control_frame, text="Update: 0ms")
        self.performance_label.pack(side=tk.LEFT, padx=5)

        # Controls
        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        # Pause button
        self.pause_var = tk.BooleanVar(value=False)
        self.pause_button = ttk.Checkbutton(
            control_frame, text="Pause", variable=self.pause_var
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)

        # Clear button
        ttk.Button(
            control_frame, text="Clear All", command=self.clear_all_data
        ).pack(side=tk.LEFT, padx=5)

        # Auto-scale button
        self.autoscale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            control_frame, text="Auto-scale", variable=self.autoscale_var
        ).pack(side=tk.LEFT, padx=5)

        # Save plot button
        ttk.Button(
            control_frame, text="Save Plot", command=self.save_current_plot
        ).pack(side=tk.LEFT, padx=5)

        # Export data button
        ttk.Button(
            control_frame, text="Export Data", command=self.export_data
        ).pack(side=tk.LEFT, padx=5)

        # Plot container
        plot_container = ttk.Frame(main_frame)
        plot_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create matplotlib figure
        self.create_plot(plot_container)

        # Device legend frame
        legend_container = ttk.Frame(main_frame)
        legend_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.create_device_legend(legend_container)

    def create_plot(self, parent):
        """Create the matplotlib plot."""
        # Create figure with subplots based on measurement type
        if self.measurement_type == "IV Sweep":
            self.fig = Figure(figsize=(8, 6), dpi=100, tight_layout=True)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_xlabel('Voltage (V)')
            self.ax.set_ylabel('Current (A)')
            self.ax.set_title('I-V Characteristics')
            self.ax.grid(True, alpha=0.3)

        elif self.measurement_type == "Single Avg Measure":
            self.fig = Figure(figsize=(8, 6), dpi=100, tight_layout=True)

            # Create two subplots
            self.ax = self.fig.add_subplot(211)
            self.ax.set_xlabel('Time (s)')
            self.ax.set_ylabel('Average Current (A)')
            self.ax.set_title('Average Current vs Time')
            self.ax.grid(True, alpha=0.3)

            self.ax2 = self.fig.add_subplot(212)
            self.ax2.set_xlabel('Device')
            self.ax2.set_ylabel('Current (A)')
            self.ax2.set_title('Current Distribution by Device')
            self.ax2.grid(True, alpha=0.3)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Add toolbar
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()

    def create_device_legend(self, parent):
        """Create a scrollable device legend with checkboxes."""
        legend_frame = ttk.LabelFrame(parent, text="Devices", padding="5")
        legend_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable frame
        canvas = tk.Canvas(legend_frame, width=180)
        scrollbar = ttk.Scrollbar(legend_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.device_checkboxes = {}
        self.device_vars = {}

    def add_data_point(self, device_name, x, y, timestamp=None):
        """
        Add a data point to the queue for plotting.
        Thread-safe method.
        """
        if timestamp is None:
            timestamp = time.time()

        self.data_queue.put(('data', device_name, x, y, timestamp))

    def add_batch_data(self, device_name, x_array, y_array, timestamps=None):
        """
        Add multiple data points at once.
        Thread-safe method.
        """
        if timestamps is None:
            timestamps = [time.time()] * len(x_array)

        self.data_queue.put(('batch', device_name, x_array, y_array, timestamps))

    def process_data_thread(self):
        """Background thread to process incoming data."""
        while self.running:
            try:
                # Process data with timeout to allow thread to exit cleanly
                data = self.data_queue.get(timeout=0.1)

                with self.data_lock:
                    if data[0] == 'data':
                        _, device_name, x, y, timestamp = data
                        self._add_single_point_locked(device_name, x, y, timestamp)

                    elif data[0] == 'batch':
                        _, device_name, x_array, y_array, timestamps = data
                        self._add_batch_points_locked(device_name, x_array, y_array, timestamps)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in data processing thread: {e}")

    def _add_single_point_locked(self, device_name, x, y, timestamp):
        """Internal method to add a single data point. Must be called with lock held."""
        if device_name not in self.device_data:
            self._initialize_device_locked(device_name)

        self.device_data[device_name]['x'].append(x)
        self.device_data[device_name]['y'].append(y)
        self.device_data[device_name]['timestamps'].append(timestamp)

        self.points_per_device[device_name] = len(self.device_data[device_name]['x'])

    def _add_batch_points_locked(self, device_name, x_array, y_array, timestamps):
        """Internal method to add batch data points. Must be called with lock held."""
        if device_name not in self.device_data:
            self._initialize_device_locked(device_name)

        self.device_data[device_name]['x'].extend(x_array)
        self.device_data[device_name]['y'].extend(y_array)
        self.device_data[device_name]['timestamps'].extend(timestamps)

        self.points_per_device[device_name] = len(self.device_data[device_name]['x'])

    def _initialize_device_locked(self, device_name):
        """Initialize data storage for a new device. Must be called with lock held."""
        self.device_data[device_name] = {
            'x': deque(maxlen=None),
            'y': deque(maxlen=None),
            'timestamps': deque(maxlen=None)
        }

        # Assign color
        color_idx = len(self.device_colors) % len(self.colors)
        self.device_colors[device_name] = self.colors
        self.device_colors[device_name] = self.colors[color_idx]

        # Queue GUI update for adding device to legend
        self.plot_queue.put(('add_device', device_name))

        self.points_per_device[device_name] = 0

    def add_device_to_legend(self, device_name):
        """Add device checkbox to legend. Must be called from GUI thread."""
        if device_name in self.device_vars:
            return  # Already added

        var = tk.BooleanVar(value=True)
        color = self.device_colors.get(device_name, self.colors[0])

        # Create frame for device entry
        device_frame = ttk.Frame(self.scrollable_frame)
        device_frame.pack(fill=tk.X, padx=2, pady=2)

        # Color indicator
        color_hex = f'#{int(color[0] * 255):02x}{int(color[1] * 255):02x}{int(color[2] * 255):02x}'
        color_label = tk.Label(device_frame, text="■", fg=color_hex, font=('Arial', 12))
        color_label.pack(side=tk.LEFT)

        # Checkbox
        cb = ttk.Checkbutton(
            device_frame, text=device_name, variable=var,
            command=lambda: self.toggle_device_visibility(device_name)
        )
        cb.pack(side=tk.LEFT)

        # Point count
        count_label = ttk.Label(device_frame, text="(0)", font=('Arial', 8))
        count_label.pack(side=tk.RIGHT)

        self.device_checkboxes[device_name] = cb
        self.device_vars[device_name] = var
        self.device_checkboxes[f"{device_name}_count"] = count_label

    def toggle_device_visibility(self, device_name):
        """Toggle visibility of a device's data."""
        if device_name in self.plot_lines and device_name in self.device_vars:
            visible = self.device_vars[device_name].get()
            self.plot_lines[device_name].set_visible(visible)
            self.canvas.draw_idle()

    def schedule_update(self):
        """Schedule the next plot update."""
        if self.running:
            self.update_plot()
            self.window.after(self.update_interval, self.schedule_update)

    def update_plot(self):
        """Update the plot with new data. Runs in GUI thread."""
        if self.pause_var.get():
            return

        start_time = time.time()

        try:
            # Process any GUI updates from the queue
            while not self.plot_queue.empty():
                try:
                    action = self.plot_queue.get_nowait()
                    if action[0] == 'add_device':
                        self.add_device_to_legend(action[1])
                except queue.Empty:
                    break

            # Update plots with thread-safe data copy
            with self.data_lock:
                # Create a shallow copy of data for plotting
                plot_data = {}
                for device_name, data in self.device_data.items():
                    plot_data[device_name] = {
                        'x': list(data['x']),
                        'y': list(data['y']),
                        'timestamps': list(data['timestamps'])
                    }

            # Update main plot (outside of lock)
            if self.measurement_type == "IV Sweep":
                self.update_iv_plot(plot_data)
            elif self.measurement_type == "Single Avg Measure":
                self.update_avg_plot(plot_data)

            # Update statistics
            self.update_statistics()

            # Refresh canvas
            self.canvas.draw_idle()

            # Update performance metric
            update_time = (time.time() - start_time) * 1000
            self.performance_label.config(text=f"Update: {update_time:.1f}ms")

            # Dynamic update interval adjustment
            if update_time > 200:
                self.update_interval = min(1000, self.update_interval + 100)
            elif update_time < 50 and self.update_interval > 200:
                self.update_interval = max(200, self.update_interval - 50)

        except Exception as e:
            print(f"Error updating plot: {e}")
            import traceback
            traceback.print_exc()

    def update_iv_plot(self, plot_data):
        """Update I-V sweep plot."""
        for device_name, data in plot_data.items():
            if len(data['x']) == 0:
                continue

            # Check if device should be visible
            if device_name not in self.device_vars:
                continue

            # Get data arrays
            x_data = np.array(data['x'])
            y_data = np.array(data['y'])

            # Decimate if needed
            if len(x_data) > self.max_points_displayed:
                indices = np.linspace(0, len(x_data) - 1, self.max_points_displayed, dtype=int)
                x_plot = x_data[indices]
                y_plot = y_data[indices]
            else:
                x_plot, y_plot = x_data, y_data

            # Update or create line
            if device_name in self.plot_lines:
                self.plot_lines[device_name].set_data(x_plot, y_plot)
            else:
                color = self.device_colors.get(device_name, 'blue')
                line, = self.ax.plot(
                    x_plot, y_plot,
                    label=device_name,
                    color=color,
                    linewidth=1.5
                )
                self.plot_lines[device_name] = line

            # Update visibility
            if device_name in self.device_vars:
                self.plot_lines[device_name].set_visible(self.device_vars[device_name].get())

        # Auto-scale if enabled
        if self.autoscale_var.get():
            self.ax.relim()
            self.ax.autoscale_view()

    def update_avg_plot(self, plot_data):
        """Update average measurement plots."""
        # Top plot: Current vs Time
        for device_name, data in plot_data.items():
            if len(data['x']) == 0 or device_name not in self.device_vars:
                continue

            # For average measurements, use timestamps
            x_data = np.array(data['timestamps'])
            y_data = np.array(data['y'])

            if len(x_data) > 0:
                # Convert to relative time
                x_data = x_data - x_data[0]

                # Decimate if needed
                if len(x_data) > self.max_points_displayed:
                    indices = np.linspace(0, len(x_data) - 1, self.max_points_displayed, dtype=int)
                    x_plot = x_data[indices]
                    y_plot = y_data[indices]
                else:
                    x_plot, y_plot = x_data, y_data

                # Update or create line
                if device_name in self.plot_lines:
                    self.plot_lines[device_name].set_data(x_plot, y_plot)
                else:
                    color = self.device_colors.get(device_name, 'blue')
                    line, = self.ax.plot(
                        x_plot, y_plot,
                        label=device_name,
                        color=color,
                        marker='o', markersize=4, linewidth=1.5
                    )
                    self.plot_lines[device_name] = line

                # Update visibility
                self.plot_lines[device_name].set_visible(self.device_vars[device_name].get())

        # Bottom plot: Latest current distribution
        self.update_distribution_plot(plot_data)

        # Auto-scale if enabled
        if self.autoscale_var.get():
            self.ax.relim()
            self.ax.autoscale_view()
            if hasattr(self, 'ax2'):
                self.ax2.relim()
                self.ax2.autoscale_view()

    def update_distribution_plot(self, plot_data):
        """Update the distribution plot for average measurements."""
        if not hasattr(self, 'ax2'):
            return

        # Clear previous bars
        self.ax2.clear()
        self.ax2.set_xlabel('Device')
        self.ax2.set_ylabel('Current (A)')
        self.ax2.set_title('Latest Current Values')
        self.ax2.grid(True, alpha=0.3)

        # Get latest values
        devices = []
        currents = []
        colors = []

        for device_name, data in plot_data.items():
            if len(data['y']) > 0 and device_name in self.device_vars:
                if self.device_vars[device_name].get():
                    devices.append(device_name)
                    currents.append(data['y'][-1])  # Latest value
                    colors.append(self.device_colors.get(device_name, 'blue'))

        if devices:
            # Create bar plot
            x_pos = np.arange(len(devices))
            bars = self.ax2.bar(x_pos, currents, color=colors, alpha=0.7, edgecolor='black')

            # Set x-axis labels
            self.ax2.set_xticks(x_pos)
            self.ax2.set_xticklabels(devices, rotation=45, ha='right')

            # Add value labels on bars
            for bar, current in zip(bars, currents):
                height = bar.get_height()
                self.ax2.text(bar.get_x() + bar.get_width() / 2., height,
                              f'{current:.2e}', ha='center', va='bottom', fontsize=8)

    def update_statistics(self):
        """Update statistics labels."""
        with self.data_lock:
            total_devices = len(self.device_data)
            total_points = sum(self.points_per_device.values())

        self.device_count_label.config(text=f"Devices: {total_devices}")
        self.points_label.config(text=f"Points: {total_points:,}")

        # Update device point counts
        for device_name, count in self.points_per_device.items():
            if f"{device_name}_count" in self.device_checkboxes:
                self.device_checkboxes[f"{device_name}_count"].config(text=f"({count})")

    def clear_all_data(self):
        """Clear all measurement data."""
        response = messagebox.askyesno(
            "Clear Data",
            "Are you sure you want to clear all measurement data?"
        )

        if response:
            with self.data_lock:
                # Clear data structures
                self.device_data.clear()
                self.points_per_device.clear()

            # Clear plots
            for line in self.plot_lines.values():
                line.remove()
            self.plot_lines.clear()

            # Clear legend
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.device_checkboxes.clear()
            self.device_vars.clear()

            # Clear axes
            self.ax.clear()
            self.ax.set_xlabel('Voltage (V)' if self.measurement_type == "IV Sweep" else 'Time (s)')
            self.ax.set_ylabel('Current (A)')
            self.ax.grid(True, alpha=0.3)

            if hasattr(self, 'ax2'):
                self.ax2.clear()
                self.ax2.set_xlabel('Device')
                self.ax2.set_ylabel('Current (A)')
                self.ax2.grid(True, alpha=0.3)

            # Redraw
            self.canvas.draw()

            # Force garbage collection
            gc.collect()

    def save_current_plot(self):
        """Save the current plot to file."""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("PDF files", "*.pdf"),
                       ("SVG files", "*.svg"), ("All files", "*.*")]
        )

        if filename:
            self.fig.savefig(filename, dpi=300, bbox_inches='tight')
            messagebox.showinfo("Success", f"Plot saved to {filename}")

    def export_data(self):
        """Export all data to CSV files."""
        from tkinter import filedialog

        directory = filedialog.askdirectory(title="Select Export Directory")
        if not directory:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with self.data_lock:
            # Create a copy of data for export
            export_data = {}
            for device_name, data in self.device_data.items():
                export_data[device_name] = {
                    'x': list(data['x']),
                    'y': list(data['y']),
                    'timestamps': list(data['timestamps'])
                }

        # Export outside of lock
        exported_count = 0
        for device_name, data in export_data.items():
            if len(data['x']) == 0:
                continue

            # Create filename
            safe_name = device_name.replace('/', '_').replace('\\', '_')
            filename = f"{directory}/{safe_name}_{self.measurement_type.replace(' ', '_')}_{timestamp}.csv"

            # Prepare data
            x_data = np.array(data['x'])
            y_data = np.array(data['y'])
            t_data = np.array(data['timestamps'])

            # Save to CSV
            if self.measurement_type == "IV Sweep":
                header = "Voltage(V),Current(A),Timestamp(s)"
            else:
                header = "Time(s),Current(A),Timestamp(s)"

            with open(filename, 'w') as f:
                f.write(header + "\n")
                for x, y, t in zip(x_data, y_data, t_data):
                    f.write(f"{x},{y},{t}\n")

            exported_count += 1

        messagebox.showinfo("Success", f"Exported {exported_count} device datasets to {directory}")

    def on_close(self):
        """Handle window close event."""
        self.running = False

        # Wait for thread to finish
        if hasattr(self, 'data_thread') and self.data_thread.is_alive():
            self.data_thread.join(timeout=1.0)

        # Clear data
        with self.data_lock:
            self.device_data.clear()
            self.plot_lines.clear()

        # Destroy window
        try:
            self.window.destroy()
        except:
            pass


class ThreadSafePlotter:
    """
    Wrapper class for thread-safe plotting operations from measurement threads.
    """

    def __init__(self, plotter):
        self.plotter = plotter

    def add_data(self, device_name, x, y, timestamp=None):
        """Thread-safe method to add data."""
        if self.plotter and self.plotter.running:
            self.plotter.add_data_point(device_name, x, y, timestamp)

    def add_batch(self, device_name, x_array, y_array, timestamps=None):
        """Thread-safe method to add batch data."""
        if self.plotter and self.plotter.running:
            self.plotter.add_batch_data(device_name, x_array, y_array, timestamps)

    def callback_sink(self, device_name):
        """Return a callback that accepts (x, y, t) and forwards to plotter."""
        def cb(x, y, t):
            self.add_data(device_name, x, y, t)
        return cb

    def is_active(self):
        """Check if plotter is still active."""
        return self.plotter and self.plotter.running