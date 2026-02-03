"""

Main GUI Window for Classification Validation Tool.

"""



import tkinter as tk

from tkinter import ttk, filedialog, messagebox

from typing import Optional, Callable

import threading



try:

    from ..validation_tool import ClassificationValidator

    from .file_browser import FileBrowserPanel

    from .review_panel import ReviewPanel

    from .tuning_panel import TuningPanel

    from .metrics_panel import MetricsPanel

except ImportError:

    # Handle relative imports

    import sys

    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from tools.classification_validation.validation_tool import ClassificationValidator

    from tools.classification_validation.gui.file_browser import FileBrowserPanel

    from tools.classification_validation.gui.review_panel import ReviewPanel

    from tools.classification_validation.gui.tuning_panel import TuningPanel

    from tools.classification_validation.gui.metrics_panel import MetricsPanel





class ValidationToolGUI:

    """Main GUI window for classification validation and refinement."""

    

    def __init__(self, root: Optional[tk.Tk] = None):

        """

        Initialize GUI.

        

        Args:

            root: Tkinter root window. If None, creates new one.

        """

        if root is None:

            self.root = tk.Tk()

            self.root.title("Classification Validation & Refinement Tool")

        else:

            self.root = root

        

        self.validator = ClassificationValidator()

        

        # Create notebook for tabs

        self.notebook = ttk.Notebook(self.root)

        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        

        # Create tabs

        self.file_browser_tab = FileBrowserPanel(self.notebook, self.validator, self._on_data_loaded)

        self.review_tab = ReviewPanel(self.notebook, self.validator, self._on_labels_updated)

        self.tuning_tab = TuningPanel(self.notebook, self.validator, self._on_parameters_updated)

        self.metrics_tab = MetricsPanel(self.notebook, self.validator)

        

        # Add tabs to notebook

        self.notebook.add(self.file_browser_tab.frame, text="Load Data")

        self.notebook.add(self.review_tab.frame, text="Review & Label")

        self.notebook.add(self.tuning_tab.frame, text="Tune Parameters")

        self.notebook.add(self.metrics_tab.frame, text="Metrics")

        

        # Status bar

        self.status_var = tk.StringVar(value="Ready")

        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)

        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    

    def _on_data_loaded(self):

        """Callback when data is loaded."""

        self.status_var.set("Data loaded. Go to Review tab to label devices.")

        # Refresh other tabs

        self.review_tab.refresh()

        self.metrics_tab.refresh()

    

    def _on_labels_updated(self):

        """Callback when labels are updated."""

        self.status_var.set("Labels updated. Check Metrics tab for accuracy.")

        self.metrics_tab.refresh()
        self.tuning_tab.refresh()

    

    def _on_parameters_updated(self):

        """Callback when parameters are updated."""

        self.status_var.set("Parameters updated. Recalculating predictions...")

        # Refresh all tabs

        self.review_tab.refresh()

        self.metrics_tab.refresh()

        self.status_var.set("Recalculation complete. Check Metrics tab for new accuracy.")

    

    def run(self):

        """Start GUI main loop."""

        self.root.mainloop()





if __name__ == "__main__":

    app = ValidationToolGUI()

    app.run()

