import socket
from datetime import datetime
import time

ARDUINO_IP = '192.168.0.10'
PORT = 5000

def main():
    while True:
        try:
            # Connect to Arduino
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ARDUINO_IP, PORT))
                
                # Send current time as timestamp (first message)
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                s.sendall((now + "\n").encode())
                
                # Read sensor value once
                data = s.recv(1024).decode().strip()
                print(f"{now} -> {data}")
                
            time.sleep(2)  # repeat interval
        except (ConnectionRefusedError, OSError):
            print("Arduino not reachable, retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
