/*
 * Simple Voltage Divider Approach
 * 
 * If you want the SIMPLEST solution without PWM filtering or DAC:
 * Use a voltage divider circuit to step down 5V to 0.2V
 * 
 * Circuit:
 *   Arduino Pin 9 (5V) -> [R1: 24kΩ] -> Output -> [R2: 1kΩ] -> GND
 *                                              -> Device
 * 
 * Formula: Vout = Vin × R2/(R1+R2)
 * 0.2V = 5V × 1k/(24k+1k)
 * 0.2V = 5V × 1/25 = 0.2V ✓
 * 
 * This gives you a simple on/off control at exactly 0.2V
 */

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("============================================");
  Serial.println("Voltage Divider Approach");
  Serial.println("============================================");
  Serial.println();
  Serial.println("Circuit: Arduino Pin -> [24kΩ] -> Output -> [1kΩ] -> GND");
  Serial.println("Result: When pin HIGH (5V), output = 0.2V");
  Serial.println("       When pin LOW (0V), output = 0.0V");
  Serial.println();
  
  // Set up the output pin
  pinMode(9, OUTPUT);
  
  Serial.println("Starting test sequence:");
  Serial.println("1. Output OFF (0V)");
  Serial.println("2. Output ON (0.2V)");
  Serial.println();
  
  // Cycle on/off
  for (int cycle = 0; cycle < 5; cycle++) {
    // Turn OFF
    digitalWrite(9, LOW);
    Serial.println("OFF -> 0.0V");
    delay(2000);
    
    // Turn ON
    digitalWrite(9, HIGH);
    Serial.println("ON -> 0.2V");
    Serial.println("Measure voltage: should be 0.2V");
    delay(2000);
  }
  
  // Leave it off
  digitalWrite(9, LOW);
  Serial.println();
  Serial.println("Test complete. Pin now OFF.");
  Serial.println();
  Serial.println("============================================");
  Serial.println("BENEFITS:");
  Serial.println("- Very simple circuit");
  Serial.println("- Exact 0.2V (no calibration needed)");
  Serial.println("- No PWM filtering required");
  Serial.println("- On/off control is easy");
  Serial.println();
  Serial.println("DOWNSIDES:");
  Serial.println("- Voltage is fixed (can't adjust)");
  Serial.println("- Current through R1/R2 (wastes some power)");
  Serial.println("============================================");
}

void loop() {
  // Nothing here
}

/*
 * VOLTAGE DIVIDER RATIO CALCULATOR:
 * 
 * For different target voltages:
 * 
 * 0.2V from 5V: R1 = 24kΩ, R2 = 1kΩ
 * 0.5V from 5V: R1 = 9kΩ, R2 = 1kΩ  
 * 1.0V from 5V: R1 = 4kΩ, R2 = 1kΩ
 * 2.5V from 5V: R1 = 1kΩ, R2 = 1kΩ
 * 
 * General formula:
 * R1/R2 = (Vin/Vout) - 1
 * 
 * Example for 0.2V from 5V:
 * R1/R2 = (5/0.2) - 1 = 25 - 1 = 24
 * So R1 = 24k, R2 = 1k
 * 
 * STABILITY NOTE:
 * For better voltage stability with devices connected,
 * add a capacitor across the output:
 * Output -> [10µF capacitor] -> GND
 * This smooths out any fluctuations.
 */

