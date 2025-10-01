import socket
import serial
import time
import os
import threading
from datetime import datetime
import csv
import pystray
from PIL import Image
import sys

# -------------------- CONFIG --------------------
USE_USB = True        # Set False to use TCP
USB_PORT = 'COM9'     # Adjust if needed
BAUD = 115200
TCP_IP = '192.168.0.10'  # Arduino IP
TCP_PORT = 5000

# Reconnection settings
RECONNECT_INTERVAL = 30  # seconds to wait before trying to reconnect
POLL_INTERVAL = 5        # seconds to wait between connection checks

SAVE_DIR = r"C:\Users\ppxcv1\OneDrive - The University of Nottingham\Documents\Phd\General\Lab Temp and Humidity"

# Global variables for GUI
tray_icon = None
status_text = "Starting..."
is_running = True
ser = None

# -------------------- Helpers --------------------
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_csv_path():
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    date = now.strftime("%Y-%m-%d")
    
    # Create year/month folder structure
    year_month_dir = os.path.join(SAVE_DIR, year, month)
    ensure_dir(year_month_dir)
    
    return os.path.join(year_month_dir, f"{date}.csv")

def write_csv(timestamp, temp, hum):
    csv_path = get_csv_path()
    new_file = not os.path.exists(csv_path)

    with open(csv_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if new_file:
            writer.writerow(['timestamp', 'temperature', 'humidity'])
        writer.writerow([timestamp, temp, hum])

def send_time_serial(ser):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = now + "\n"
    ser.write(message.encode())
    update_status(f"Sent time sync: {now}")
    ser.flush()  # Ensure data is sent immediately

def read_serial(ser):
    line = ser.readline().decode(errors="ignore").strip()
    return line

def check_usb_connection():
    """Check if USB port is available and can be opened"""
    try:
        with serial.Serial(USB_PORT, BAUD, timeout=1) as test_ser:
            return True
    except (serial.SerialException, OSError):
        return False

def try_usb_connection():
    """Try to establish USB connection, returns serial object or None"""
    try:
        ser = serial.Serial(USB_PORT, BAUD, timeout=1)
        time.sleep(2)  # wait for Arduino reset
        send_time_serial(ser)
        return ser
    except (serial.SerialException, OSError) as e:
        update_status(f"Failed to connect to USB: {e}")
        return None

def is_connection_alive(ser):
    """Check if serial connection is still alive"""
    try:
        # Check if the port is still open
        if not ser.is_open:
            return False
        
        # Try to read with a short timeout to test connection
        original_timeout = ser.timeout
        ser.timeout = 0.1
        ser.readline()
        ser.timeout = original_timeout  # reset timeout
        return True
    except (serial.SerialException, OSError) as e:
        update_status(f"Connection check failed: {e}")
        return False

def update_status(message):
    """Update the status text for the tray icon"""
    global status_text
    status_text = f"{datetime.now().strftime('%H:%M:%S')} - {message}"
    print(status_text)  # Also print to console for debugging

def load_icon():
    """Load the icon from Downloads folder"""
    icon_path = r"C:\Users\ppxcv1\Downloads\cloud_forecast_rain_humidity_weather_icon_228446.ico"
    
    # If the specific file doesn't exist, try with different extensions
    if not os.path.exists(icon_path):
        # Try .png extension
        icon_path = icon_path.replace('.ico', '.png')
        if not os.path.exists(icon_path):
            # Try .jpg extension
            icon_path = icon_path.replace('.png', '.jpg')
            if not os.path.exists(icon_path):
                # Create a simple icon if none found
                return create_simple_icon()
    
    try:
        return Image.open(icon_path)
    except Exception as e:
        print(f"Could not load icon: {e}")
        return create_simple_icon()

def create_simple_icon():
    """Create a simple icon if the provided one can't be loaded"""
    from PIL import ImageDraw
    
    # Create a 64x64 image with transparent background
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw thermometer shape
    draw.ellipse([size//2-8, size-20, size//2+8, size-4], fill=(255, 100, 100), outline=(200, 50, 50), width=2)
    draw.rectangle([size//2-3, 10, size//2+3, size-20], fill=(255, 100, 100), outline=(200, 50, 50), width=2)
    
    for i in range(5):
        y = 15 + i * 8
        draw.line([size//2-6, y, size//2-1, y], fill=(200, 50, 50), width=1)
    
    return img

def show_status():
    """Show current status in a simple message"""
    import tkinter as tk
    from tkinter import messagebox
    
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    messagebox.showinfo("Arduino Temperature Logger", status_text)
    root.destroy()

def open_data_folder():
    """Open the data folder in Windows Explorer"""
    import subprocess
    subprocess.run(['explorer', SAVE_DIR])

def quit_app():
    """Quit the application"""
    global is_running
    is_running = False
    if tray_icon:
        tray_icon.stop()
    sys.exit(0)

def arduino_logging_thread():
    """Main Arduino logging logic running in a separate thread"""
    global ser, status_text
    
    last_sync_time = 0
    
    while is_running:
        try:
            # Check if we need to establish or re-establish connection
            if ser is None:
                update_status(f"Attempting to connect to USB port {USB_PORT}...")
                ser = try_usb_connection()
                if ser is None:
                    update_status(f"USB connection failed. Retrying in {RECONNECT_INTERVAL} seconds...")
                    time.sleep(RECONNECT_INTERVAL)
                    continue
                else:
                    update_status("USB connected successfully!")
                    last_sync_time = time.time()
            
            # Check if connection is still alive
            if not is_connection_alive(ser):
                update_status("USB connection lost. Closing connection...")
                try:
                    ser.close()
                except:
                    pass
                ser = None
                continue
            
            # Check if it's time to sync time and request reading (every 60 seconds)
            current_time = time.time()
            if current_time - last_sync_time >= 60:
                try:
                    update_status("Requesting reading from Arduino...")
                    send_time_serial(ser)
                    last_sync_time = current_time
                    
                    # Wait for response from Arduino
                    response_received = False
                    timeout_start = time.time()
                    
                    while not response_received and (time.time() - timeout_start) < 10 and is_running:
                        line = read_serial(ser)
                        if line:
                            parts = line.split(',')
                            if len(parts) == 3:
                                arduino_timestamp, temp, hum = parts
                                # Use current system time instead of Arduino timestamp
                                current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                update_status(f"Logged: {temp}°C, {hum}%")
                                write_csv(current_timestamp, temp, hum)
                                response_received = True
                                break
                        time.sleep(0.5)  # Check every 500ms
                    
                    if not response_received:
                        update_status("No response from Arduino within 10 seconds")
                        
                except (serial.SerialException, OSError) as e:
                    update_status(f"Error communicating with Arduino: {e}")
                    try:
                        ser.close()
                    except:
                        pass
                    ser = None
                    continue
            
            # Short sleep to prevent busy waiting
            time.sleep(1)
            
        except Exception as e:
            update_status(f"Unexpected error: {e}")
            time.sleep(5)

def main():
    """Main function to set up system tray and start logging"""
    global tray_icon
    
    # Load the icon
    icon_image = load_icon()
    
    # Create menu items
    menu = pystray.Menu(
        pystray.MenuItem("Status", show_status, default=True),
        pystray.MenuItem("Open Data Folder", open_data_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app)
    )
    
    # Create the tray icon
    tray_icon = pystray.Icon(
        "ArduinoTempLogger",
        icon_image,
        "Arduino Temperature Logger",
        menu
    )
    
    # Start the Arduino logging in a separate thread
    logging_thread = threading.Thread(target=arduino_logging_thread, daemon=True)
    logging_thread.start()
    
    # Run the tray icon (this blocks until quit)
    tray_icon.run()

if __name__ == "__main__":
    main()
