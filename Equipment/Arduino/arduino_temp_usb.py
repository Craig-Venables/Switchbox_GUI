import socket
import serial
import time
import os
from datetime import datetime
import csv

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
    print(f"Sent time sync: {now}")
    ser.flush()  # Ensure data is sent immediately

def read_serial(ser):
    line = ser.readline().decode(errors="ignore").strip()
    return line

def send_time_tcp(sock):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sock.sendall((now + "\n").encode())

def read_tcp(sock):
    sock.sendall(b"\n")  # request latest reading
    data = sock.recv(1024).decode(errors="ignore").strip()
    return data

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
        print(f"Failed to connect to USB: {e}")
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
        print(f"Connection check failed: {e}")
        return False

# -------------------- Main --------------------
def main():
    print("Starting logger...")

    if USE_USB:
        ser = None
        last_sync_time = 0
        
        while True:
            # Check if we need to establish or re-establish connection
            if ser is None:
                print(f"Attempting to connect to USB port {USB_PORT}...")
                ser = try_usb_connection()
                if ser is None:
                    print(f"USB connection failed. Retrying in {RECONNECT_INTERVAL} seconds...")
                    time.sleep(RECONNECT_INTERVAL)
                    continue
                else:
                    print("USB connected successfully!")
                    last_sync_time = time.time()
            
            # Check if connection is still alive
            if not is_connection_alive(ser):
                print("USB connection lost. Closing connection...")
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
                    print("Requesting reading from Arduino...")
                    send_time_serial(ser)
                    last_sync_time = current_time
                    
                    # Wait for response from Arduino
                    response_received = False
                    timeout_start = time.time()
                    
                    while not response_received and (time.time() - timeout_start) < 10:  # 10 second timeout
                        line = read_serial(ser)
                        if line:
                            parts = line.split(',')
                            if len(parts) == 3:
                                arduino_timestamp, temp, hum = parts
                                # Use current system time instead of Arduino timestamp
                                current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                print(f"{current_timestamp}, {temp}, {hum}")
                                write_csv(current_timestamp, temp, hum)
                                response_received = True
                                break
                        time.sleep(0.5)  # Check every 500ms
                    
                    if not response_received:
                        print("No response from Arduino within 10 seconds")
                        
                except (serial.SerialException, OSError) as e:
                    print(f"Error communicating with Arduino: {e}")
                    try:
                        ser.close()
                    except:
                        pass
                    ser = None
                    continue
            
            # Short sleep to prevent busy waiting
            time.sleep(1)
            
    else:
        # TCP connection logic (unchanged)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((TCP_IP, TCP_PORT))
            send_time_tcp(sock)
            print("TCP connected, logging every 60s...")
            while True:
                line = read_tcp(sock)
                if line:
                    parts = line.split(',')
                    if len(parts) == 3:
                        timestamp, temp, hum = parts
                        print(f"{timestamp}, {temp}, {hum}")
                        write_csv(timestamp, temp, hum)
                        time.sleep(60)  # wait one minute

if __name__ == "__main__":
    main()
