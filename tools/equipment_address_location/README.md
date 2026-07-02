# Equipment address discovery

Quick scripts to list VISA and serial ports when configuring `Json_Files/system_configs.json`.

## Run

```powershell
# List all VISA resources (USB instruments)
python tools/equipment_address_location/find_visa.py

# List serial/COM ports
python tools/equipment_address_location/find_serial.py
```

Copy the address you need into the appropriate instrument entry in `Json_Files/system_configs.json`.
