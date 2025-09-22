import serial

ser = serial.Serial("COM4", baudrate=38400, timeout=1)

ser.write(b"DL 1\r\n")     # turn emission ON
print(ser.readline().decode().strip())  # should print OK