/*
 * SHT45 Simple Test Sketch
 * 
 * This is a minimal test program to verify SHT45 sensor is working correctly.
 * Upload this first to test your sensor before using the full device testing system.
 */

#include <Wire.h>
#include <SensirionI2CSht4x.h>

// Create SHT45 object
SensirionI2CSht4x sht4x;

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(2000);  // Wait for serial monitor to open
  
  Serial.println("============================================");
  Serial.println("SHT45 Sensor Test");
  Serial.println("============================================");
  
  // Initialize I2C communication
  Wire.begin();
  
  // Initialize SHT45 sensor
  sht4x.begin(Wire, 0x44);  // Default I2C address for SHT45
  
  // Perform software reset
  uint16_t error;
  char errorMessage[256];
  
  error = sht4x.softReset();
  if (error) {
    Serial.print("Error during reset: ");
    errorToString(error, errorMessage, 256);
    Serial.println(errorMessage);
  } else {
    Serial.println("SHT45 reset successful");
  }
  
  delay(1000);
  
  Serial.println("\nReading sensor data every 2 seconds...\n");
  Serial.println("Timestamp       Temperature(°C)  Humidity(%)");
  Serial.println("--------------------------------------------");
}

void loop() {
  float temperature = NAN;
  float humidity = NAN;
  uint16_t error;
  char errorMessage[256];
  
  // Read temperature and humidity
  error = sht4x.measureHighPrecision(temperature, humidity);
  
  if (error) {
    Serial.print("Error reading sensor: ");
    errorToString(error, errorMessage, 256);
    Serial.println(errorMessage);
  } else {
    // Print timestamp
    printTimestamp();
    Serial.print("  ");
    
    // Print temperature
    Serial.print(temperature, 2);
    Serial.print("            ");
    
    // Print humidity
    Serial.print(humidity, 2);
    Serial.println();
    
    // Also print in CSV format
    Serial.print("CSV: ");
    Serial.print(temperature, 2);
    Serial.print(",");
    Serial.print(humidity, 2);
    Serial.println();
  }
  
  delay(2000);  // Wait 2 seconds before next reading
}

void printTimestamp() {
  unsigned long seconds = millis() / 1000;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  
  seconds = seconds % 60;
  minutes = minutes % 60;
  
  char buffer[15];
  sprintf(buffer, "%02d:%02d:%02d", hours % 24, minutes, seconds);
  Serial.print(buffer);
}

/*
 * TROUBLESHOOTING:
 * 
 * If you get errors:
 * 1. Check I2C wiring:
 *    - SDA to A4
 *    - SCL to A5
 *    - VCC to 5V or 3.3V
 *    - GND to GND
 * 
 * 2. Add pull-up resistors (4.7kΩ) if not on module:
 *    - SDA to VCC via 4.7kΩ
 *    - SCL to VCC via 4.7kΩ
 * 
 * 3. Try different I2C address:
 *    - Some SHT45 may use 0x45 instead of 0x44
 * 
 * 4. Check serial monitor baud rate:
 *    - Must be set to 115200
 * 
 * 5. Verify SHT45 library is installed:
 *    - Sketch → Include Library → Manage Libraries
 *    - Search: "SensirionI2CSht4x"
 *    - Install by Sensirion AG
 */

