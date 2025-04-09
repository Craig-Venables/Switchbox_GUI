import pyvisa
import re
rm = pyvisa.ResourceManager()
print("Available VISA resources:")
print(rm.list_resources())


# Create a VISA resource manager
rm = pyvisa.ResourceManager()

# List all connected VISA resources
resources = rm.list_resources()
print(resources)

# Regex pattern for USB VISA addresses
usb_pattern = re.compile(r"USB\d+::0x[0-9A-Fa-f]{4}::0x[0-9A-Fa-f]{4}::\d+::INSTR")

# Filter and print matching USB VISA addresses
usb_devices = [res for res in resources if usb_pattern.match(res)]

print("Found USB VISA Devices:")
for device in usb_devices:
    print(device)