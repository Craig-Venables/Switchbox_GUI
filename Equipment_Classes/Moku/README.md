# Moku Go Installation and Setup Guide

This guide provides step-by-step instructions for installing and configuring the Moku Go software to work with your Python project.

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)
- Virtual environment (recommended)
- Windows/Linux/macOS operating system
- **Moku:Go device connected via USB** (not Ethernet for this setup)

## Step 1: Install Moku Python Package

First, activate your virtual environment (if using one):

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

Install the Moku Python package using pip:

```bash
pip install liquidinstruments-moku
```

Alternatively, if you have a `requirements.txt` file, add the package:

```
liquidinstruments-moku
```

Then install:

```bash
pip install -r requirements.txt
```

### Important: pymoku vs moku Package Issue

**Common Error:** `ModuleNotFoundError: No module named 'pymoku'`

**Problem:** The `pymoku` package is an incomplete/broken package that only contains metadata files with no actual Python modules. This often happens when the wrong package is installed.

**Solution:** Use the correct package name `moku` from `liquidinstruments-moku`:

```bash
# ❌ Wrong - don't use this
pip install pymoku

# ✅ Correct - use this instead
pip install liquidinstruments-moku
```

**In your Python code:**
```python
# ❌ Wrong imports
from pymoku import Moku
from pymoku.instruments import WaveformGenerator

# ✅ Correct imports
from moku import Moku
from moku.instruments import WaveformGenerator
```

**If you already have the wrong package installed:**
```bash
pip uninstall pymoku
pip install liquidinstruments-moku
```

## Step 2: Install Moku CLI

Download and install the Moku CLI from the official Liquid Instruments website:

1. Visit: https://liquidinstruments.com/software/utilities/
2. Download the appropriate installer for your operating system
3. Run the installer and follow the installation prompts
4. Note the installation directory (typically `C:\Program Files\Liquid Instruments\Moku CLI\` on Windows)

### Default Installation Paths

- **Windows**: `C:\Program Files\Liquid Instruments\Moku CLI\`
- **Linux**: `/opt/liquidinstruments/moku-cli/`
- **macOS**: `/Applications/Liquid Instruments/Moku CLI/`

## Step 3: Configure Environment Variables

### Windows (PowerShell)

Set the environment variable for the current session:

```powershell
$env:MOKU_CLI_PATH = "C:\Program Files\Liquid Instruments\Moku CLI\mokucli.exe"
```

Make it permanent for your user:

```powershell
[Environment]::SetEnvironmentVariable('MOKU_CLI_PATH', 'C:\Program Files\Liquid Instruments\Moku CLI\mokucli.exe', 'User')
```

### Linux/macOS (Bash)

Set for current session:

```bash
export MOKU_CLI_PATH="/opt/liquidinstruments/moku-cli/mokucli"
```

Make permanent by adding to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
echo 'export MOKU_CLI_PATH="/opt/liquidinstruments/moku-cli/mokucli"' >> ~/.bashrc
source ~/.bashrc
```

### Alternative: Set Environment Variable System-Wide

#### Windows (System Environment Variables)
1. Right-click on "This PC" or "My Computer"
2. Select "Properties"
3. Click "Advanced system settings"
4. Click "Environment Variables"
5. Under "System variables", click "New"
6. Variable name: `MOKU_CLI_PATH`
7. Variable value: `C:\Program Files\Liquid Instruments\Moku CLI\mokucli.exe`

#### Linux (System-wide)
```bash
sudo sh -c 'echo "export MOKU_CLI_PATH=/opt/liquidinstruments/moku-cli/mokucli" > /etc/profile.d/moku.sh'
```

## Step 4: Set up USB Connection (Critical for Moku:Go)

**Important:** Moku:Go devices connect via USB, not Ethernet. You need to set up a USB proxy to enable communication.

### Method 1: Using Moku CLI Proxy (Recommended)

The Moku CLI can create a local proxy that bridges USB to network:

1. **Find your Moku:Go USB identifier:**
   ```powershell
   # Check connected USB devices
   Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*33E2*" }
   ```
   Look for something like `USB\VID_33E2&PID_0028\936` - the number at the end (936) is your device identifier.

2. **Start the USB proxy:**
   ```powershell
   # Replace '936' with your actual device identifier
   & "path\to\mokucli.exe" proxy usb://MokuGo-936
   ```

3. **Use localhost in your Python code:**
   ```python
   from moku import Moku
   m = Moku("127.0.0.1:8090")  # Default proxy port
   ```

### Method 2: Using Moku Desktop Application

Alternatively, install and run the Moku Desktop Application:

1. Download from: https://liquidinstruments.com/software/
2. Run the application - it will automatically detect USB devices
3. Find your Moku's IP address in the application
4. Use that IP address directly in your Python code

### Method 3: Custom Port for Proxy

If port 8090 conflicts, specify a different port:

```powershell
& "path\to\mokucli.exe" proxy usb://MokuGo-936 --port 9090
```

Then use in Python:
```python
m = Moku("127.0.0.1:9090")
```

## Step 5: Verify Installation

Test that everything is working correctly:

### Test Python Package Import

```python
import moku
print("Moku package imported successfully!")
```

### Test CLI Path

```python
import os
cli_path = os.environ.get('MOKU_CLI_PATH')
if cli_path and os.path.exists(cli_path):
    print(f"Moku CLI found at: {cli_path}")
else:
    print("Moku CLI not found. Please check installation and environment variable.")
```

### Test USB Proxy Connection

First, start the USB proxy in a separate terminal:

```powershell
# Replace '936' with your actual device identifier
& "path\to\mokucli.exe" proxy usb://MokuGo-936
```

Then test the connection:

```python
from moku import Moku
from moku.instruments import WaveformGenerator

try:
    # Connect through the USB proxy
    m = Moku("127.0.0.1:8090")
    i = m.attach_instrument(WaveformGenerator)

    # Generate a test signal
    i.gen_sinewave(1, amplitude=1.0, frequency=1000)
    print("Successfully connected to Moku:Go via USB proxy!")

    m.disconnect()
except Exception as e:
    print(f"Connection failed: {e}")
```

### Alternative: Test Direct USB (if proxy not working)

```python
from moku import Moku
from moku.instruments import WaveformGenerator

try:
    # Direct USB connection (may not work without proper setup)
    m = Moku("usb://MokuGo-936")
    i = m.attach_instrument(WaveformGenerator)
    print("Successfully connected to Moku:Go via direct USB!")
    m.disconnect()
except Exception as e:
    print(f"Direct USB connection failed: {e}")
    print("Try using the USB proxy method instead.")
```

## Step 6: Using the Moku Go Controller

Use the provided `Monku_Go.py` script. **Important:** This script uses USB connection, so you must have the USB proxy running.

### Method 1: Using the USB Proxy (Recommended)

1. **Start the USB proxy in one terminal:**
   ```powershell
   & "path\to\mokucli.exe" proxy usb://MokuGo-936
   ```

2. **Run the script in another terminal:**
   ```python
   python Equipment_Classes/Moku/Monku_Go.py
   ```

### Method 2: Using Direct Connection (if proxy works)

If you have the Moku Desktop Application running:

```python
from moku import Moku
from moku.instruments import WaveformGenerator

# Connect using the IP shown in Moku Desktop App
m = Moku("192.168.X.X")  # Replace with actual IP
i = m.attach_instrument(WaveformGenerator)

# Generate signals
i.gen_sinewave(1, amplitude=1.0, frequency=50e3)
i.gen_squarewave(2, amplitude=1.0, frequency=500)

m.disconnect()
```

## Troubleshooting

### Common Issues

1. **"Can't find mokucli" warning**
   - Ensure `MOKU_CLI_PATH` environment variable is set correctly
   - Verify the mokucli executable exists at the specified path
   - Try using absolute path to mokucli

2. **Import Error: "No module named 'moku'"**
   - Install the package: `pip install liquidinstruments-moku`
   - Ensure you're using the correct Python environment
   - Check if virtual environment is activated

3. **pymoku Import Error: "No module named 'pymoku'"**
   - **This is a very common issue!** See the "pymoku vs moku Package Issue" section above
   - The `pymoku` package is broken/incomplete
   - Uninstall `pymoku` and install `liquidinstruments-moku` instead
   - Update your imports from `from pymoku import Moku` to `from moku import Moku`

4. **USB Connection Issues**
   - **Verify USB device is detected:**
     ```powershell
     Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*33E2*" }
     ```
   - **Start USB proxy:** `& "path\to\mokucli.exe" proxy usb://MokuGo-XXX`
   - **Check proxy is running:** Look for "Running a proxy" message
   - **Use correct port:** Default is 8090, but can be changed with `--port`
   - **Try different USB ports** if connection fails

5. **USB Proxy Errors**
   - **"Unexpected gaierror occurred"**: DNS resolution issue, try restarting the proxy
   - **"Connection forcibly closed"**: Proxy may have crashed, restart it
   - **Port conflicts**: Use `--port` to specify a different port
   - **Permission issues**: Run PowerShell as Administrator

6. **Connection Timeout**
   - Ensure USB proxy is running before starting Python script
   - Check that the device identifier (e.g., '936') matches your device
   - Try different USB ports or cables
   - Restart the Moku device if possible

7. **Permission Error**
   - On Linux/macOS, you might need to run with `sudo`
   - Or adjust permissions: `chmod +x /path/to/mokucli`
   - On Windows, try running PowerShell as Administrator

### Environment Variable Troubleshooting

Check if environment variable is set:

```bash
# Windows PowerShell
echo $env:MOKU_CLI_PATH

# Linux/macOS
echo $MOKU_CLI_PATH
```

Verify mokucli exists:

```bash
# Windows PowerShell
Test-Path "C:\Program Files\Liquid Instruments\Moku CLI\mokucli.exe"

# Linux/macOS
ls -la /opt/liquidinstruments/moku-cli/mokucli
```

## File Structure

```
Equipment_Classes/Moku/
├── Monku_Go.py              # Main Moku Go controller script (USB connection)
├── README.md                # This comprehensive installation guide
├── Moku CLI/                # Moku Command Line Interface
│   ├── mokucli.exe         # Main CLI executable
│   └── _internal/          # CLI dependencies
└── Moku_Go.py              # Alternative implementation (Multiplexer version)
```

## CLI Setup Summary

To get the Moku CLI working for USB connections:

1. **Set the path:**
   ```powershell
   $env:MOKU_CLI_PATH = "C:\path\to\your\project\Equipment_Classes\Moku\Moku CLI\mokucli.exe"
   ```

2. **Test CLI:**
   ```powershell
   & $env:MOKU_CLI_PATH --help
   ```

3. **Find USB device:**
   ```powershell
   Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*33E2*" }
   ```

4. **Start USB proxy:**
   ```powershell
   & $env:MOKU_CLI_PATH proxy usb://MokuGo-936
   ```

5. **Connect in Python:**
   ```python
   from moku import Moku
   m = Moku("127.0.0.1:8090")
   ```

## Additional Resources

- [Liquid Instruments Documentation](https://liquidinstruments.com/docs/)
- [Moku Python API Reference](https://liquidinstruments.com/docs/python/)
- [Moku CLI Documentation](https://liquidinstruments.com/docs/cli/)
- [USB Connection Troubleshooting](https://liquidinstruments.com/docs/troubleshooting/)

## Version Information

- Python: 3.7+
- liquidinstruments-moku: Latest version (not pymoku!)
- Moku CLI: v4.0.1 (bundled in project)
- Connection: USB only (not Ethernet)

---

**Last Updated:** January 2025
**Tested On:** Windows 10/11, Python 3.11+, Moku:Go firmware v2.x+
**Key Discovery:** USB proxy method required for Moku:Go devices
