import socket
import serial
import time
from datetime import datetime
import csv

# -------------------- CONFIG --------------------
USE_USB = True        # Set False to use TCP instead
USB_PORT = 'COM9'     # Your Arduino USB port
BAUD = 115200
TCP_IP = '192.168.0.10'  # Arduino IP
TCP_PORT = 5000
CSV_FILE = 'sensor_log.csv'

# -------------------- Helpers --------------------
def send_time_serial(ser):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ser.write((now + "\n").encode())

def read_serial(ser):
    line = ser.readline().decode().strip()
    return line

def send_time_tcp(sock):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sock.sendall((now + "\n").encode())

def read_tcp(sock):
    sock.sendall(b"\n")  # request latest reading
    data = sock.recv(1024).decode().strip()
    return data

# -------------------- Main Logging --------------------
with open(CSV_FILE, 'a', newline='') as csvfile:
    csvwriter = csv.writer(csvfile)
    
    # Write header if empty
    if csvfile.tell() == 0:
        csvwriter.writerow(['timestamp', 'temperature', 'humidity'])

    if USE_USB:
        with serial.Serial(USB_PORT, BAUD, timeout=1) as ser:
            time.sleep(2)  # wait for Arduino reset
            send_time_serial(ser)
            print("Starting USB logging...")
            while True:
                line = read_serial(ser)
                if line:
                    print(line)
                    parts = line.split(',')
                    if len(parts) == 3:
                        csvwriter.writerow(parts)
                        csvfile.flush()
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((TCP_IP, TCP_PORT))
            send_time_tcp(sock)
            print("Starting TCP logging...")
            while True:
                line = read_tcp(sock)
                if line:
                    print(line)
                    parts = line.split(',')
                    if len(parts) == 3:
                        csvwriter.writerow(parts)
                        csvfile.flush()
