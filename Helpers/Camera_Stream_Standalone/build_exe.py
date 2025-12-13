"""
Build script for creating executable from camera_stream_app.py

Description:
    Builds a standalone executable for the Camera Stream application using PyInstaller.
    The executable will include all dependencies and can run without Python installed.

Usage:
    python build_exe.py
    
This will create a standalone executable using PyInstaller.
"""

import subprocess
import sys
import os

def build_exe():
    """Build executable using PyInstaller."""
    script_name = "camera_stream_app.py"
    exe_name = "CameraStream"
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if not os.path.exists(script_name):
        print(f"Error: {script_name} not found in {script_dir}!")
        return False
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print("PyInstaller found.")
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("PyInstaller installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install PyInstaller: {e}")
            return False
    
    # Build command with proper options
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",              # Single executable file
        "--windowed",             # No console window (GUI app)
        "--name", exe_name,       # Executable name
        "--clean",                # Clean PyInstaller cache
        "--noconfirm",            # Overwrite output without asking
        # Hidden imports (modules that PyInstaller might miss)
        "--hidden-import", "cv2",
        "--hidden-import", "flask",
        "--hidden-import", "numpy",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        # Collect all submodules
        "--collect-all", "cv2",
        "--collect-all", "flask",
        script_name
    ]
    
    print("\n" + "="*60)
    print("Building Camera Stream executable...")
    print("="*60)
    print(f"Script: {script_name}")
    print(f"Output: {exe_name}.exe")
    print(f"Command: {' '.join(cmd)}")
    print("="*60 + "\n")
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "="*60)
        print("Build complete!")
        print("="*60)
        exe_path = os.path.join("dist", f"{exe_name}.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Executable location: {os.path.abspath(exe_path)}")
            print(f"File size: {size_mb:.2f} MB")
        else:
            print(f"Warning: Executable not found at expected location: {exe_path}")
        print("="*60 + "\n")
        return True
    except subprocess.CalledProcessError as e:
        print("\n" + "="*60)
        print(f"Build failed: {e}")
        print("="*60 + "\n")
        return False
    except Exception as e:
        print("\n" + "="*60)
        print(f"Unexpected error: {e}")
        print("="*60 + "\n")
        return False

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)

