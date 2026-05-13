/*
 * Exclusive LED control — pins D5, D7, D9, D11 (active HIGH).
 *
 * Serial: 115200 8N1, newline-terminated ASCII commands.
 *   0–3  Turn on only LED index 0..3 (maps to pins 5,7,9,11).
 *   4    or "off" (any case) — all LEDs off.
 * Replies: OK\n on success, ERR\n on unknown input.
 */

const uint8_t LED_PINS[] = {5, 7, 9, 11};
const uint8_t NUM_LEDS = sizeof(LED_PINS) / sizeof(LED_PINS[0]);

static char lineBuf[16];
static uint8_t lineLen = 0;

static void allLow(void) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    digitalWrite(LED_PINS[i], LOW);
  }
}

static void setExclusive(uint8_t index) {
  allLow();
  if (index < NUM_LEDS) {
    digitalWrite(LED_PINS[index], HIGH);
  }
}

static bool equalsIgnoreCase(const char *a, const char *ref) {
  for (; *ref != '\0'; a++, ref++) {
    char ca = *a;
    char cr = *ref;
    if (ca >= 'A' && ca <= 'Z') {
      ca = (char)(ca - 'A' + 'a');
    }
    if (cr >= 'A' && cr <= 'Z') {
      cr = (char)(cr - 'A' + 'a');
    }
    if (ca != cr) {
      return false;
    }
  }
  return *a == '\0';
}

static void handleLine(const char *s) {
  if (s[0] == '\0') {
    Serial.println("ERR");
    return;
  }

  if (s[0] >= '0' && s[0] <= '3' && s[1] == '\0') {
    setExclusive((uint8_t)(s[0] - '0'));
    Serial.println("OK");
    return;
  }

  if (s[0] == '4' && s[1] == '\0') {
    allLow();
    Serial.println("OK");
    return;
  }

  if (equalsIgnoreCase(s, "off")) {
    allLow();
    Serial.println("OK");
    return;
  }

  Serial.println("ERR");
}

void setup(void) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    digitalWrite(LED_PINS[i], LOW);
  }
  Serial.begin(115200);
  lineLen = 0;
}

void loop(void) {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        handleLine(lineBuf);
        lineLen = 0;
      }
      continue;
    }
    if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;
      Serial.println("ERR");
    }
  }
}
