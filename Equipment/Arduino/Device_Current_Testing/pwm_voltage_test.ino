/*
 * PWM Voltage Output Test
 * 
 * This sketch demonstrates why you need a filter or voltage divider
 * to get 0.2V output from Arduino.
 * 
 * TEST: Measure the output with a multimeter and oscilloscope.
 * Without a filter: You'll see a square wave, not 0.2V DC
 * With a filter: You'll see approximately 0.2V DC
 */

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("============================================");
  Serial.println("PWM Voltage Output Test");
  Serial.println("============================================");
  Serial.println("Measuring with multimeter...");
  Serial.println();
  
  // Calculate PWM value for 0.2V
  // Arduino outputs 5V, so to get 0.2V:
  int pwmValue = (0.2 / 5.0) * 255;  // = 10
  
  Serial.print("PWM value: ");
  Serial.println(pwmValue);
  Serial.print("Expected voltage: ");
  Serial.print((pwmValue * 5.0) / 255.0, 3);
  Serial.println("V");
  Serial.println();
  
  Serial.println("Reading at different PWM values:");
  Serial.println("PWM\tExpected\tActual (unfiltered)");
  Serial.println("----\t--------\t------------------");
  
  // Test different PWM values
  for (int pwm = 0; pwm <= 255; pwm += 10) {
    analogWrite(9, pwm);
    
    float expected = (pwm * 5.0) / 255.0;
    
    Serial.print(pwm);
    Serial.print("\t");
    Serial.print(expected, 3);
    Serial.print("V\t");
    Serial.println("Square wave (not DC)");
    
    delay(2000);  // Wait so you can measure with multimeter
  }
  
  analogWrite(9, 0);
  Serial.println();
  Serial.println("Test complete.");
  Serial.println();
  Serial.println("============================================");
  Serial.println("KEY POINT:");
  Serial.println("============================================");
  Serial.println("PWM alone gives you a SQUARE WAVE, not DC voltage!");
  Serial.println();
  Serial.println("To get steady 0.2V, you need:");
  Serial.println("1. PWM + Low-Pass Filter (RC circuit)");
  Serial.println("2. Voltage Divider circuit");
  Serial.println("3. External DAC module");
  Serial.println();
  Serial.println("See README_CURRENT_TESTING.md for circuit details.");
}

void loop() {
  // Nothing here - test runs once in setup()
}

/*
 * CRITICAL UNDERSTANDING:
 * 
 * Arduino digitalWrite() gives:
 * - LOW = 0V
 * - HIGH = 5V
 * 
 * Arduino analogWrite() (PWM) gives:
 * - Duty cycle from 0% to 100%
 * - Average voltage from 0V to 5V
 * - BUT: It's a square wave switching on/off rapidly
 * - Frequency: ~490 Hz on most pins (~980 Hz on pins 5,6)
 * 
 * For CURRENT MEASUREMENT, you typically need:
 * - Steady DC voltage (not switching)
 * - Many devices won't respond correctly to PWM
 * 
 * SOLUTION OPTIONS:
 * 
 * 1. SIMPLE: Voltage Divider
 *    Arduino Pin (5V) -> [R1: 24kΩ] -> Output -> [R2: 1kΩ to GND]
 *    Gives: 5V × (1k / 25k) = 0.2V
 *    Downside: Fixed voltage, not adjustable
 * 
 * 2. PWM + Low-Pass Filter (RC Filter)
 *    Arduino PWM Pin -> [10kΩ resistor] -> Output -> [10µF cap to GND]
 *    Then: analogWrite(pin, 10) gives ~0.2V DC
 *    Better: Can adjust voltage by changing PWM value
 * 
 * 3. EXTERNAL DAC (Most precise)
 *    Use MCP4725 module with I2C
 *    Very accurate, programmable voltage
 *    Best for precision measurements
 * 
 * For most applications, Option 2 (PWM + Filter) is the sweet spot:
 * - Adjustable
 * - Simple
 * - Good enough accuracy for current sensing
 */

