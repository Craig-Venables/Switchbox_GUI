/*
 * FC-2901V MFC interface firmware for Arduino UNO / Nano
 *
 * Hardware required:
 *   - MCP4725 DAC breakout (Adafruit or equivalent) on I2C (A4=SDA, A5=SCL)
 *     --> MCP4725 VOUT  -> MFC 15-pin D pin 5  (0-5 V setpoint)
 *   - Analog input AI0 -> MFC 15-pin D pin 9   (0-5 V flow output)  [A0]
 *   - Digital output   -> MFC 15-pin D pin 14  (TTL valve-OFF)       [D2]
 *   - Arduino 5V / GND -> MFC pin 8 (Common/GND)
 *   - External ±15 V supply for the MFC (the Arduino cannot power it)
 *
 * Serial protocol: 115200 8N1, \r\n terminated
 *   S:<sccm>\r\n    Set setpoint (0 – 200 sccm)   → OK\r\n
 *   R\r\n           Read flow                      → F:<sccm>\r\n
 *   O:<0|1>\r\n     Valve-OFF: 0=close, 1=normal   → OK\r\n
 *   ?\r\n           Identity                       → FC2901V_CTRL\r\n
 *
 * Libraries: Adafruit_MCP4725  (install via Arduino Library Manager)
 */

#include <Wire.h>
#include <Adafruit_MCP4725.h>

Adafruit_MCP4725 dac;

const uint8_t VALVE_OFF_PIN    = 2;    // D2 → MFC pin 14 (TTL low = valve closed)
const uint8_t FLOW_AI_PIN      = A0;   // A0 ← MFC pin 9  (0-5 V flow output)
const float   FULL_SCALE_SCCM  = 200.0f;
const float   ADC_MAX          = 1023.0f;
const float   DAC_MAX          = 4095.0f;

String inputBuffer = "";

void setup() {
  Serial.begin(115200);
  Wire.begin();
  dac.begin(0x60);            // default MCP4725 I2C address

  pinMode(VALVE_OFF_PIN, OUTPUT);
  digitalWrite(VALVE_OFF_PIN, HIGH);  // TTL high = normal control on startup

  dac.setVoltage(0, false);   // setpoint = 0 V on startup
  inputBuffer.reserve(64);
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
    } else if (c != '\r') {
      inputBuffer += c;
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();

  if (cmd.equals("?")) {
    Serial.println("FC2901V_CTRL");

  } else if (cmd.equals("R")) {
    // Read flow: average 8 samples for stability
    long sum = 0;
    for (int i = 0; i < 8; i++) {
      sum += analogRead(FLOW_AI_PIN);
      delayMicroseconds(500);
    }
    float adcVal = (float)(sum / 8);
    float sccm   = (adcVal / ADC_MAX) * FULL_SCALE_SCCM;
    Serial.print("F:");
    Serial.println(sccm, 3);

  } else if (cmd.startsWith("S:")) {
    float sccm = cmd.substring(2).toFloat();
    sccm = constrain(sccm, 0.0f, FULL_SCALE_SCCM);
    uint16_t dacVal = (uint16_t)((sccm / FULL_SCALE_SCCM) * DAC_MAX);
    dac.setVoltage(dacVal, false);
    Serial.println("OK");

  } else if (cmd.startsWith("O:")) {
    int val = cmd.substring(2).toInt();
    // TTL high = normal control; TTL low = valve closed
    digitalWrite(VALVE_OFF_PIN, val != 0 ? HIGH : LOW);
    Serial.println("OK");

  } else {
    Serial.println("ERR:unknown");
  }
}
