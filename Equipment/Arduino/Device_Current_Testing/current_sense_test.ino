/*
 * Current Sensing Test Sketch
 * 
 * This sketch tests analog current measurement without the SHT45.
 * Use this to calibrate your current sensing circuit.
 */

// ==================== CONFIGURATION ====================
#define NUM_TEST_PINS 6
const int ANALOG_PINS[NUM_TEST_PINS] = {A0, A1, A2, A3, A4, A5};
const int ENABLE_PINS[NUM_TEST_PINS] = {3, 5, 6, 9, 10, 11};

// Calibration: Adjust this based on your circuit
float VOLTS_TO_AMPS = 0.001;  // Conversion factor: 1V = how many Amps?

// PWM value for 0.2V output (on 5V Arduino)
int TARGET_PWM = (0.2 / 5.0) * 255;  // Should be about 10

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("============================================");
  Serial.println("Current Sensing Test");
  Serial.println("============================================");
  Serial.print("PWM value for 0.2V: ");
  Serial.println(TARGET_PWM);
  Serial.println();
  
  // Initialize pins
  for (int i = 0; i < NUM_TEST_PINS; i++) {
    pinMode(ANALOG_PINS[i], INPUT);
    pinMode(ENABLE_PINS[i], OUTPUT);
    digitalWrite(ENABLE_PINS[i], LOW);
  }
  
  Serial.println("Ready. Cycle through all devices...");
  Serial.println();
  Serial.println("Device  Raw ADC  Voltage(V)  Current(A)");
  Serial.println("---------------------------------------");
  delay(1000);
}

void loop() {
  // Cycle through each device
  for (int device = 0; device < NUM_TEST_PINS; device++) {
    // Enable device with PWM
    analogWrite(ENABLE_PINS[device], TARGET_PWM);
    
    // Wait for stabilization
    delay(50);
    
    // Read current measurement
    int rawADC = analogRead(ANALOG_PINS[device]);
    float voltage = (rawADC * 5.0) / 1023.0;
    float current = voltage * VOLTS_TO_AMPS;
    
    // Print measurement
    Serial.print(device);
    Serial.print("       ");
    Serial.print(rawADC);
    Serial.print("       ");
    Serial.print(voltage, 3);
    Serial.print("      ");
    Serial.println(current, 6);
    
    // Disable device
    analogWrite(ENABLE_PINS[device], 0);
    digitalWrite(ENABLE_PINS[device], LOW);
    
    delay(100);
  }
  
  Serial.println();
  delay(2000);
}

/*
 * CALIBRATION INSTRUCTIONS:
 * 
 * 1. Without any device connected, note the "zero current" reading
 * 2. Connect a known current source (or known resistor/voltage combo)
 * 3. Measure actual current with multimeter
 * 4. Calculate conversion factor:
 *    VOLTS_TO_AMPS = Actual_Current / Measured_Voltage
 * 
 * Example:
 * - Reading: 0.5V
 * - Actual current: 0.001A (1mA)
 * - VOLTS_TO_AMPS = 0.001 / 0.5 = 0.002
 * 
 * CIRCUIT EXAMPLE (Shunt Resistor):
 * - 0.1Ω shunt resistor
 * - Arduino measures voltage across shunt
 * - Current = Voltage / 0.1
 * - VOLTS_TO_AMPS = 1 / 0.1 = 10
 * 
 * IMPORTANT NOTES:
 * - Add capacitor (10µF) across output for stable voltage
 * - Use proper low-pass filter if using PWM
 * - Ensure proper grounding
 * - Verify analog reference is 5V
 */

