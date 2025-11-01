/*
 * Arduino Uno - Device Current Testing with SHT45 Sensor
 * 
 * This sketch applies 0.2V to multiple devices sequentially and measures the current flowing through each.
 * Simultaneously monitors temperature and humidity using an SHT45 sensor.
 * 
 * Features:
 * - PWM-based voltage application (using low-pass filter or external DAC)
 * - Current measurement via analog pins
 * - Environmental monitoring with SHT45
 * - Data logging with timestamps
 * - Independent operation without PC connection
 * 
 * Hardware Requirements:
 * - Arduino Uno
 * - SHT45 sensor (I2C)
 * - DAC module (MCP4725 or similar) OR low-pass filter for PWM-to-analog
 * - Current sensing circuit (shunt resistor + op-amp OR INA219 module)
 * - Multiple device connections
 * 
 * Pin Configuration:
 * - A4 (SDA) -> SHT45 SDA
 * - A5 (SCL) -> SHT45 SCL
 * - A0-A5 -> Analog inputs for current measurement (one per device)
 * - Digital pins 3,5,6,9,10,11 -> PWM outputs for voltage control OR device selection
 */

#include <Wire.h>
#include <SensirionI2CSht4x.h>  // SHT4x library (works for SHT45)

// ==================== CONFIGURATION ====================
#define NUM_DEVICES 6           // Number of devices to test
#define TARGET_VOLTAGE 0.2      // Target voltage in volts
#define MEASUREMENT_DELAY 1000  // Delay between measurements in ms
#define CYCLE_INTERVAL 60000    // Full cycle interval in ms (60 seconds)

// Pin mapping for device control and current measurement
// Adjust these based on your hardware setup
const int DEVICE_ENABLE_PINS[NUM_DEVICES] = {3, 5, 6, 9, 10, 11};
const int CURRENT_SENSE_PINS[NUM_DEVICES] = {A0, A1, A2, A3, A4, A5};

// Calibration parameters (adjust based on your circuit)
float CURRENT_SENSE_SCALE = 0.001;  // mV to A conversion factor
int PWM_VALUE = 0;                  // Will be calculated for 0.2V

// I2C address for SHT45 (default is 0x44)
#define SHT45_I2C_ADDRESS 0x44

// ==================== OBJECT INITIALIZATION ====================
SensirionI2CSht4x sht4x;

// ==================== GLOBAL VARIABLES ====================
unsigned long lastMeasurement = 0;
unsigned long lastCycle = 0;
bool sensorAvailable = false;

// ==================== SETUP ====================
void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("============================================");
  Serial.println("Device Current Testing System");
  Serial.println("============================================");
  
  // Initialize I2C for SHT45
  Wire.begin();
  sht4x.begin(Wire, SHT45_I2C_ADDRESS);
  
  // Check SHT45 connection
  uint16_t error;
  char errorMessage[256];
  error = sht4x.softReset();
  if (error) {
    Serial.print("SHT45 Error: ");
    errorToString(error, errorMessage, 256);
    Serial.println(errorMessage);
    sensorAvailable = false;
  } else {
    Serial.println("SHT45 initialized successfully");
    sensorAvailable = true;
  }
  
  // Calculate PWM value for 0.2V output
  // For 5V Arduino: PWM 8-bit = 0-255
  // For 0.2V: (0.2 / 5.0) * 255 = 10.2 -> 10
  PWM_VALUE = (TARGET_VOLTAGE / 5.0) * 255;
  
  Serial.print("PWM value for ");
  Serial.print(TARGET_VOLTAGE);
  Serial.print("V: ");
  Serial.println(PWM_VALUE);
  
  // Initialize device enable pins as outputs
  for (int i = 0; i < NUM_DEVICES; i++) {
    pinMode(DEVICE_ENABLE_PINS[i], OUTPUT);
    digitalWrite(DEVICE_ENABLE_PINS[i], LOW);  // Start with all disabled
    pinMode(CURRENT_SENSE_PINS[i], INPUT);
  }
  
  Serial.print("Monitoring ");
  Serial.print(NUM_DEVICES);
  Serial.println(" devices");
  Serial.println("============================================");
  
  // Print CSV header
  Serial.println("\nCSV Format:");
  Serial.println("Timestamp,Device,Temp(C),Humidity(%),Voltage(V),Current(A)");
  
  delay(2000);
}

// ==================== MAIN LOOP ====================
void loop() {
  unsigned long currentTime = millis();
  
  // Perform measurement cycle
  if (currentTime - lastCycle >= CYCLE_INTERVAL) {
    lastCycle = currentTime;
    performMeasurements();
  }
  
  // Short delay to prevent CPU spinning
  delay(10);
}

// ==================== MEASUREMENT FUNCTIONS ====================
void performMeasurements() {
  Serial.println("\n--- Starting Measurement Cycle ---");
  Serial.print("Timestamp: ");
  Serial.println(getTimestamp());
  
  // Read environmental conditions once per cycle
  float temperature = NAN;
  float humidity = NAN;
  
  if (sensorAvailable) {
    uint16_t error;
    char errorMessage[256];
    
    error = sht4x.measureHighPrecision(temperature, humidity);
    if (error) {
      errorToString(error, errorMessage, 256);
      Serial.print("SHT45 Error: ");
      Serial.println(errorMessage);
    } else {
      Serial.print("Environment: ");
      Serial.print(temperature);
      Serial.print("°C, ");
      Serial.print(humidity);
      Serial.println("%");
    }
  }
  
  // Test each device
  for (int device = 0; device < NUM_DEVICES; device++) {
    // Enable device
    digitalWrite(DEVICE_ENABLE_PINS[device], HIGH);
    
    // Apply voltage using PWM
    analogWrite(DEVICE_ENABLE_PINS[device], PWM_VALUE);
    
    // Wait for stabilization
    delay(100);
    
    // Measure current
    float current = measureCurrent(device);
    
    // Read voltage (optional, if you have a voltage divider)
    float measuredVoltage = measureVoltage(device);
    
    // Log data
    logData(device, temperature, humidity, measuredVoltage, current);
    
    // Disable device
    digitalWrite(DEVICE_ENABLE_PINS[device], LOW);
    analogWrite(DEVICE_ENABLE_PINS[device], 0);
    
    // Short delay before next device
    delay(50);
  }
  
  Serial.println("--- End of Measurement Cycle ---\n");
}

// ==================== SENSOR READING FUNCTIONS ====================
float measureCurrent(int device) {
  // Read analog value (0-1023 for 0-5V)
  int rawValue = analogRead(CURRENT_SENSE_PINS[device]);
  
  // Convert to voltage (assuming 5V reference)
  float voltage = (rawValue * 5.0) / 1023.0;
  
  // Convert voltage to current using your calibration
  // This assumes a current-to-voltage conversion circuit
  // Adjust CURRENT_SENSE_SCALE based on your hardware
  float current = voltage * CURRENT_SENSE_SCALE;
  
  return current;
}

float measureVoltage(int device) {
  // If you have a voltage monitoring circuit, implement it here
  // For now, return the target voltage
  return TARGET_VOLTAGE;
}

// ==================== DATA LOGGING ====================
void logData(int device, float temp, float hum, float voltage, float current) {
  // Print in CSV format for easy data extraction
  Serial.print(getTimestamp());
  Serial.print(",");
  Serial.print(device);
  Serial.print(",");
  
  if (!isnan(temp)) {
    Serial.print(temp, 2);
  } else {
    Serial.print("NAN");
  }
  Serial.print(",");
  
  if (!isnan(hum)) {
    Serial.print(hum, 2);
  } else {
    Serial.print("NAN");
  }
  Serial.print(",");
  
  Serial.print(voltage, 3);
  Serial.print(",");
  Serial.print(current, 6);
  Serial.println();
  
  // Also print human-readable format
  Serial.print("Device ");
  Serial.print(device);
  Serial.print(": V=");
  Serial.print(voltage, 3);
  Serial.print("V, I=");
  Serial.print(current, 6);
  Serial.println("A");
}

// ==================== UTILITY FUNCTIONS ====================
String getTimestamp() {
  // Create a timestamp string
  // Since Arduino Uno doesn't have RTC, use elapsed time
  unsigned long seconds = millis() / 1000;
  unsigned long minutes = seconds / 60;
  unsigned long hours = minutes / 60;
  
  seconds = seconds % 60;
  minutes = minutes % 60;
  
  char buffer[20];
  sprintf(buffer, "%02lu:%02lu:%02lu", hours, minutes, seconds);
  return String(buffer);
}

// ==================== NOTES ====================
/*
 * IMPORTANT HARDWARE CONSIDERATIONS:
 * 
 * 1. Voltage Application (0.2V):
 *    Option A: Use external DAC (MCP4725) via I2C
 *    Option B: Use PWM + Low-pass filter (RC filter: R=10kΩ, C=10µF)
 *    Option C: Use voltage divider circuit
 *    
 *    Using only PWM without filtering will give you a square wave, not DC voltage.
 * 
 * 2. Current Measurement:
 *    Option A: Shunt resistor + Op-amp for amplification
 *       - Place a small resistor (e.g., 0.1Ω) in series with device
 *       - Measure voltage drop across it
 *       - Use op-amp to amplify if needed
 *    Option B: INA219 current sensor module (recommended)
 *    Option C: ACS712 hall-effect current sensor
 *    
 * 3. SHT45 Wiring:
 *    - VCC -> 5V or 3.3V
 *    - GND -> GND
 *    - SDA -> A4 (I2C SDA)
 *    - SCL -> A5 (I2C SCL)
 * 
 * 4. Library Installation:
 *    Install "SensirionI2CSht4x" library from Arduino Library Manager
 *    
 * 5. Data Collection:
 *    Connect Arduino to PC via USB and monitor Serial output at 115200 baud
 *    OR use SD card module to log data independently
 * 
 * TESTING AND CALIBRATION:
 * 1. Verify PWM output with oscilloscope
 * 2. Calibrate current sensing with known current source
 * 3. Verify SHT45 readings are reasonable
 * 4. Adjust CURRENT_SENSE_SCALE based on your current sensor
 * 
 * TROUBLESHOOTING:
 * - If SHT45 not detected, check I2C wiring and pull-up resistors (4.7kΩ)
 * - If current readings are always zero, check current sensor wiring
 * - If voltage is not stable, add capacitor across output
 * - If devices not responding, check enable pin connections
 */

