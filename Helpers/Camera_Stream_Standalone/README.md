# Camera Stream Standalone Application

Standalone application that displays camera feed locally and streams it over IP network.

## Features

- **Local Display**: Shows camera feed in OpenCV window
- **IP Streaming**: Streams camera feed over HTTP/MJPEG (accessible via web browser)
- **Camera Controls**: Adjust exposure, frame rate, brightness, contrast, and gain
- **Click-to-Mark**: Click on the camera window to place markers (red dots with crosshairs)
- **Configurable**: Set camera index, IP address, port, and resolution
- **Standalone**: Can be converted to executable (.exe) for easy distribution

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Run as Python Script

```bash
python camera_stream_app.py
```

### Configuration

1. **Camera Index**: Select which camera to use (usually 0 for default)
2. **Stream IP Address** (Usually leave as default):
   - **`0.0.0.0` (Recommended)**: Streams on all network interfaces
     - Makes the stream accessible from any device on your network
     - Also accessible locally via `localhost`
     - **This is what you want 99% of the time!**
   - **Specific IP**: Only streams on that specific network interface
     - Only use if you have multiple network adapters and want to restrict access
3. **Stream Port**: Port number for HTTP streaming (default: 8080 is fine)
4. **Resolution**: Select camera resolution

**Quick Answer**: You don't need to change the IP address! Just leave it as `0.0.0.0` and it will work perfectly. The application will show you the exact URLs to access the stream after you start it.

### Camera Controls

**Auto Mode (Default)**: The camera automatically controls exposure, brightness, contrast, and gain when you first start it. This is the recommended mode for most use cases.

**Manual Mode**: You can take manual control by:
1. Adjusting the sliders or entering values for exposure, brightness, contrast, or gain
2. Clicking "Apply Manual Settings" to apply your changes
3. The camera will then use your manual settings instead of auto mode

**Controls**:
- **Frame Rate**: Set frames per second (default: 30) - always applies
- **Exposure**: Adjust exposure time (negative values = auto exposure, default: -6.0)
- **Brightness**: Adjust brightness (-100 to 100, default: 0)
- **Contrast**: Adjust contrast (-100 to 100, default: 0)
- **Gain**: Adjust gain (0 to 100, default: 0)

**Reset to Auto**: Click "Reset to Auto" to return to automatic camera control.

**Note**: Settings only apply when you click "Apply Manual Settings". Moving sliders doesn't change the camera until you click the button.

### Click-to-Mark Feature

- **Move Marker**: Click anywhere on the camera display window to move the marker to that position
- **Single Marker**: Only one marker exists at a time - clicking a new location moves it there
- **Clear Marker**: 
  - Click the "Clear Marker" button in the GUI
  - Or press 'C' key while the camera window is focused
- Marker appears as a red circle with crosshairs and is visible in both local display and stream

### Accessing the Stream

Once started, access the stream via web browser:

- **Local access**: `http://localhost:8080/stream`
- **Network access**: `http://<your-ip-address>:8080/stream`
- **Full page viewer**: `http://<your-ip-address>:8080/`

The application will display your local IP address in the status message.

## Converting to Executable

### Using PyInstaller

1. Install PyInstaller:
```bash
pip install pyinstaller
```

2. Create executable:
```bash
pyinstaller --onefile --windowed --name CameraStream camera_stream_app.py
```

Or with icon:
```bash
pyinstaller --onefile --windowed --icon=icon.ico --name CameraStream camera_stream_app.py
```

The executable will be in the `dist/` folder.

### Using cx_Freeze

1. Install cx_Freeze:
```bash
pip install cx_Freeze
```

2. Create `setup.py`:
```python
from cx_Freeze import setup, Executable

setup(
    name="CameraStream",
    version="1.0",
    description="Camera Stream Application",
    executables=[Executable("camera_stream_app.py", base="Win32GUI")]
)
```

3. Build:
```bash
python setup.py build
```

## Troubleshooting

### Camera Not Opening

- Check camera index (try 0, 1, 2, etc.)
- Ensure camera is not being used by another application
- On Windows, check Device Manager for camera availability

### Stream Not Accessible

- Check firewall settings (allow port 8080)
- Ensure IP address is correct
- Try `0.0.0.0` to stream on all interfaces
- Check that Flask is installed: `pip install flask`

### Performance Issues

- Lower resolution for better performance
- Reduce FPS if needed
- Close other applications using the camera

## Network Access

To access the stream from another device on the same network:

1. Find your computer's IP address (shown in status message)
2. On the other device, open web browser
3. Navigate to: `http://<your-ip>:8080/stream`

## Controls

- **Start Camera & Stream**: Start the camera and begin streaming
- **Pause/Resume**: Temporarily pause the camera feed (stops capturing new frames but keeps connection alive)
- **Stop**: Completely stop the camera and close all connections
- **Clear Marker**: Remove the marker from the display

## Keyboard Shortcuts

- **'q'**: Quit the application (in camera window)
- **'c'**: Clear the marker (in camera window)

## Notes

- Press 'q' in the OpenCV window to quit
- Press 'c' in the camera window to clear all markers
- The application uses MJPEG streaming for low latency
- Flask server runs in background thread
- Camera capture runs in separate thread for smooth performance
- The marker moves to the clicked position and appears in both local display and stream
- Camera settings can be adjusted in real-time using sliders or entry fields

