"""
SIMPLE LAUNCHER - Interactive Weight Adjustment GUI

Use this if run_validation_tool.py has encoding errors.
"""

import sys
import os

# Navigate to project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

print("="*60)
print("Classification Validation Tool")
print("Interactive Weight Adjustment")
print("="*60)
print()

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    
    # Import our components
    from Helpers.Classification_Validation.validation_tool import ClassificationValidator
    from Helpers.Classification_Validation.gui.review_panel import ReviewPanel
    
    print("✓ Modules loaded successfully")
    print()
    print("Creating GUI...")
    
    # Create simple window
    root = tk.Tk()
    root.title("Classification Validation - Interactive Weight Tuning")
    root.geometry("1200x800")
    
    # Create validator
    validator = ClassificationValidator()
    
    # Create main frame
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create notebook for tabs
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # File browser tab
    browser_frame = ttk.Frame(notebook)
    notebook.add(browser_frame, text="Load Data")
    
    # Instructions
    ttk.Label(browser_frame, text="Load IV Sweep Data", 
             font=("Arial", 14, "bold")).pack(pady=20)
    ttk.Label(browser_frame, text="Select a folder containing .txt IV sweep files",
             font=("Arial", 10)).pack(pady=10)
    
    status_var = tk.StringVar(value="No data loaded")
    status_label = ttk.Label(browser_frame, textvariable=status_var, 
                            font=("Arial", 10), foreground="blue")
    status_label.pack(pady=10)
    
    def load_directory():
        directory = filedialog.askdirectory(title="Select IV Sweep Folder")
        if directory:
            status_var.set(f"Loading from: {directory}...")
            root.update()
            
            try:
                results = validator.load_data(directory)
                count = len([r for r in results if r.get('analysis')])
                status_var.set(f"✓ Loaded {count} devices from {directory}")
                review_panel.refresh()
                notebook.select(1)  # Switch to review tab
            except Exception as e:
                status_var.set(f"✗ Error: {str(e)}")
                messagebox.showerror("Load Error", str(e))
    
    load_btn = ttk.Button(browser_frame, text="📁 Select Folder", 
                         command=load_directory, width=20)
    load_btn.pack(pady=20)
    
    # Review tab (main interactive panel)
    review_tab_frame = ttk.Frame(notebook)
    notebook.add(review_tab_frame, text="Review & Adjust Weights")
    
    review_panel = ReviewPanel(review_tab_frame, validator)
    
    # Instructions tab
    help_frame = ttk.Frame(notebook)
    notebook.add(help_frame, text="Instructions")
    
    help_text = tk.Text(help_frame, wrap=tk.WORD, font=("Consolas", 10), padx=20, pady=20)
    help_text.pack(fill=tk.BOTH, expand=True)
    
    instructions = """
QUICK START GUIDE
═════════════════

1. LOAD DATA
   • Click "Load Data" tab
   • Click "Select Folder"  
   • Choose folder with .txt IV sweep files
   
2. REVIEW DEVICES
   • Go to "Review & Adjust Weights" tab
   • Click a device in the list (left side)
   • See classification scores for all 4 types
   • View I-V plot
   
3. PROVIDE FEEDBACK
   • Click "ℹ️ Help" for weight explanations
   • If classification is correct: Click "✓ Correct"
   • If classification is wrong:
     - Select actual type from dropdown
     - Click "✗ Incorrect"
   • Watch scores update in real-time!
   
4. ITERATE
   • Continue reviewing devices
   • Weights improve with each feedback
   • Check "Re-analyze all" to see global impact
   
WHAT HAPPENS?
═════════════
When you click Correct/Incorrect, the system:
• Adjusts classification weights automatically
• Re-analyzes the device with new weights
• Shows updated classification immediately
• Saves weights to data/config.json

TIPS
════
• Start with devices you're confident about
• Watch how close the scores are (e.g., 75 vs 70)
• Review 10-15 devices for best results
• Weights persist between sessions
    """
    
    help_text.insert('1.0', instructions)
    help_text.config(state='disabled')
    
    print("✓ GUI created")
    print()
    print("INSTRUCTIONS:")
    print("1. Click 'Load Data' tab")
    print("2. Select your IV sweep folder")
    print("3. Go to 'Review & Adjust Weights' tab")
    print("4. Start providing feedback!")
    print()
    print("Starting main loop...")
    print()
    
    root.mainloop()
    
except ImportError as e:
    print(f"✗ Import Error: {e}")
    print()
    print("This might be due to encoding issues in existing files.")
    print("The new files created (weight_adjuster.py, updated validation_tool.py")
    print("and review_panel.py) should work, but some original files have")
    print("UTF-16LE encoding.")
    print()
    input("Press Enter to exit...")
    sys.exit(1)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()
    input("Press Enter to exit...")
    sys.exit(1)
