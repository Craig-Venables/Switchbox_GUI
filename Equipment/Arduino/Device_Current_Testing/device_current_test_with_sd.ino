/*
 * Arduino Uno - Device Current Testing with SHT45 Sensor (SD Card Version)
 * 
 * Enhanced version with SD card logging for completely independent operation.
 * 
 * This sketch applies 0.2V to multiple devices sequentially and measures the current.
 * Monitors temperature and humidity using SHT45 sensor.
 * Logs all data to SD card without requiring PC connection.
 * 
 * Hardware Requirements:
 * - Arduino Uno
 * - SHT45 sensor
 * - SD card module (SPI)
 * - RTC module (DS1307 or similar) for accurate timestamps
 * - DAC module OR filtered PWM for voltage control
 * - Current sensing circuit
 * 
 * Pin Configuration:
 * - A4 (SDA) -> SHT45 SDA
 * - A5 (SCL) -> SHT45 SCL
 * - Pin 10 -> SD CS
 * - Pin 11 -> SD MOSI
 * - Pin 12 -> SD MISO
 * - Pin 13 -> SD SCK
 * - Digital pins 3,5,6,9 -> PWM/Enable for devices
 * - A0-A3 -> Current sense inputs
 */

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <SensirionI2CSht4x.h>
// #include <RTClib.h>  // Uncomment if using RTC

// ==================== CONFIGURATION ====================
#define NUM_DEVICES 4           // Adjust based on available pins
#define TARGET_VOLTAGE 0.2
#define MEASUREMENT_CYCLE 60000  // 60 seconds between full cycles

// Pin definitions
const int DEVICE_ENABLE_PINS[NUM_DEVICES] = {3, 5, 6, 9};
const int CURRENT_SENSE_PINS[NUM_DEVICES] = {A0, A1, A2, A3};
const int SD_CHIP_SELECT = 10;

// Calibration
float CURRENT_SENSE_SCALE = 0.001;

// ==================== OBJECTS ====================
SensirionI2CSht4x sht4x;
// RTC_DS1307 rtc;  // Uncomment if using RTC

File dataFile;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("============================================");
  Serial.println("Device Current Tester (SD Version)");
  Serial.println("============================================");
  
  // Initialize SD card
  if (!SD.begin(SD_CHIP_SELECT)) {
    Serial.println("SD card initialization failed!");
    Serial.println("Check wiring and SD card formatting.");
    while(1);  // Halt if SD fails
  }
  Serial.println("SD card initialized.");
  
  // Initialize SHT45
  Wire.begin();
  sht4x.begin(Wire, 0x44);
  uint16_t error = sht4x.softReset();
  if (error) {
    Serial.println("SHT45 initialization failed!");
  } else {
    Serial.println("SHT45 initialized.");
  }
  
  // Initialize device pins
  for (int i = 0; i < NUM_DEVICES; i++) {
    pinMode(DEVICE_ENABLE_PINS[i], OUTPUT);
    digitalWrite(DEVICE_ENABLE_PINS[i], LOW);
  }
  
  // Create new data file with timestamp
  String filename = "data_" + getTimestampFilename() + ".csv";
  dataFile = SD.open(filename.c_str(), FILE_WRITE);
  if (dataFile) {
    dataFile.println("Timestamp,Device,Temp(C),Humidity(%),Voltage(V),Current(A)");
    dataFile.close();
    Serial.print("Created file: ");
    Serial.println(filename);
  } else {
    Serial.println("Error creating data file!");
  }
  
  Serial.println("System ready. Starting measurements...");
  Serial.println();
}

// ==================== MAIN LOOP ====================
void loop() {
  static unsigned long lastCycle = 0;
  
  if (millis() - lastCycle >= MEASUREMENT_CYCLE) {
    lastCycle = millis();
    performMeasurements();
  }
  
  delay(10);
}

void performMeasurements() {
  // Read environmental conditions
  float temp = NAN, hum = NAN;
  uint16_t error = sht4x.measureHighPrecision(temp, hum);
  
  // Test each device
  for (int dev = 0; dev < NUM_DEVICES; dev++) {
    digitalWrite(DEVICE_ENABLE_PINS[dev], HIGH);
    analogWrite(DEVICE_ENABLE_PINS[dev], (TARGET_VOLTAGE / 5.0) * 255);
    delay(100);
    
    float current = measureCurrent(dev);
    
    logToSD(dev, temp, hum, TARGET_VOLTAGE, current);
    logToSerial(dev, temp, hum, TARGET_VOLTAGE, current);
    
    digitalWrite(DEVICE_ENABLE_PINS[dev], LOW);
    analogWrite(DEVICE_ENABLE_PINS[dev], 0);
    delay(50);
  }
}

float measureCurrent(int device) {
  int raw = analogRead(CURRENT_SENSE_PINS[device]);
  float voltage = (raw * 5.0) / 1023.0;
  return voltage * CURRENT_SENSE_SCALE;
}

void logToSD(int device, float temp, float hum, float volt, float curr) {
  dataFile = SD.open("data_current.csv", FILE_WRITE);
  if (dataFile) {
    dataFile.print(getTimestamp());
    dataFile.print(",");
    dataFile.print(device);
    dataFile.print(",");
    if (!isnan(temp)) dataFile.print(temp, 2); else dataFile.print("NAN");
    dataFile.print(",");
    if (!isnan(hum)) dataFile.print(hum, 2); else dataFile.print("NAN");
    dataFile.print(",");
    dataFile.print(volt, 3);
    dataFile.print(",");
    dataFile.println(curr, 6);
    dataFile.close();
  }
}

void logToSerial(int device, float temp, float hum, float volt, float curr) {
  Serial.print(getTimestamp());
  Serial.print(", Device");
  Serial.print(device);
  Serial.print(": ");
  if (!isnan(temp)) Serial.print(temp, 1); else Serial.print("N/A");
  Serial.print("°C, ");
  if (!isnan(hum)) Serial.print(hum, 1); else Serial.print("N/A");
  Serial.print("%, ");
  Serial.print(volt, 2);
  Serial.print("V, ");
  Serial.print(curr, 6);
  Serial.println("A");
}

String getTimestamp() {
  unsigned long s = millis() / 1000;
  char buffer[15];
  sprintf(buffer, "%02d:%02d:%02d", (s/3600)%24, (s/60)%60, s%60);
  return String(buffer);
}

String getTimestampFilename() {
  // Simple timestamp for filename
  unsigned long s = millis() / 1000;
  char buffer[20];
  sprintf(buffer, "%06lu", s);
  return String(buffer);
}

