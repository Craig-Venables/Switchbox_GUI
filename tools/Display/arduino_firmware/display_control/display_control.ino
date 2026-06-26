/**************************************************************************
  display_control.ino — ST7789 TFT controller with PC (serial) + button input

  Hardware (Arduino Uno / Nano default pins, same as the existing sketch):
    TFT_CS  = D10
    TFT_DC  = D9
    TFT_RST = D8
    SPI MOSI/SCK on hardware SPI pins (D11/D13 on Uno)
    Buttons: D2 = Up, D3 = Down, D4 = ChangeColour  (active HIGH, INPUT)

  Optional (needed for brightness / true off):
    TFT_BL  = D6   -> wire to the BLK / LITE / LED pin on the ST7789
                     breakout. If left unwired the display is just always
                     on at full brightness; all other commands still work.
                     D6 is a PWM-capable pin on the Uno/Nano.

  Serial protocol (ASCII, line-terminated with '\n', 115200 baud):
    C<n>          Set palette colour. n = 1..9
                  1=RED 2=GREEN 3=BLUE 4=WHITE 5=BLACK
                  6=YELLOW 7=CYAN 8=MAGENTA 9=ORANGE
    RGB r g b     Set custom 24-bit colour (each 0..255). Selects the
                  custom slot (colorIndex == 0).
    F1 / F0       Flash on / off (non-blocking, uses millis()).
    D<ms>         Flash period, clamped 20..60000.
                    - No sequence: full on+off cycle (so each half is D/2).
                    - With sequence (see SEQ): time spent on each colour
                      before advancing to the next entry.
    SEQ <c1>[,<c2>...]
                  Set the cycle sequence to palette indices (1..9). Up
                  to 9 entries, separated by spaces or commas.
                  With SEQ set + F1, the display cycles through these
                  colours (instead of colour↔black). Send "SEQ" alone
                  (or "SEQ -") to clear.
    B<n>          Backlight brightness 0..255 via PWM on TFT_BL.
                  0 = fully off (no light).
    O1 / O0       Backlight on (restore last non-zero brightness) /
                  off (B0). Display content is preserved.
    ?             Reply with current state:
                    "STATE C=<n> RGB=<hex> F=<0|1> D=<ms> B=<bright>
                     SEQ=<csv>"
                  (single line, "SEQ=-" if no sequence is set).
    H             Print help.

  Every command is acknowledged on its own line with either:
    OK
    ERR <reason>

  The flash / cycle loop is non-blocking so serial remains responsive
  while the screen is animating, and the physical buttons keep working
  alongside Python control.
 **************************************************************************/

#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <SPI.h>

// ---------- Pins (match existing wiring) ----------
const int buttonUp = 2;
const int buttonDown = 3;
const int buttonChangeColour = 4;

#define TFT_CS  10
#define TFT_RST  8
#define TFT_DC   9
#define TFT_BL   6   // PWM-capable on Uno/Nano

Adafruit_ST7789 TFTscreen = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);

// ---------- Palette ----------
// Index 0 is reserved for "custom" RGB565 stored in customColor565.
// Indices 1..9 are fixed palette entries.
static const uint8_t PALETTE_SIZE = 9;  // valid indices 1..9
uint16_t paletteColor(uint8_t idx);

// ---------- State ----------
uint8_t  colorIndex     = 1;      // 0 = custom, 1..9 palette; start at RED
uint16_t customColor565 = 0xF800; // only used when colorIndex == 0
bool     flashing       = false;
uint32_t flashPeriodMs  = 1000;   // see header for meaning
uint32_t lastFlashMs    = 0;
bool     flashPhaseOn   = true;   // colour↔black mode only
bool     needsRepaint   = true;

// Backlight / brightness
uint8_t  brightness     = 255;
uint8_t  savedBrightness = 255;   // last non-zero, restored by O1

// Colour sequence (cycle list)
static const uint8_t SEQ_MAX = 9;
uint8_t  sequence[SEQ_MAX];
uint8_t  sequenceLen = 0;
uint8_t  sequenceIdx = 0;

// Serial line buffer
static const uint8_t LINE_BUF_SIZE = 80;
char    lineBuf[LINE_BUF_SIZE];
uint8_t lineLen = 0;

// Button debounce
static const uint16_t BTN_DEBOUNCE_MS = 200;
uint32_t lastButtonMs = 0;

// ---------- Helpers ----------
uint16_t rgbTo565(uint8_t r, uint8_t g, uint8_t b) {
  return ((uint16_t)(r & 0xF8) << 8) | ((uint16_t)(g & 0xFC) << 3) | (b >> 3);
}

uint16_t paletteColor(uint8_t idx) {
  switch (idx) {
    case 1: return ST77XX_RED;
    case 2: return ST77XX_GREEN;
    case 3: return ST77XX_BLUE;
    case 4: return ST77XX_WHITE;
    case 5: return ST77XX_BLACK;
    case 6: return ST77XX_YELLOW;
    case 7: return ST77XX_CYAN;
    case 8: return ST77XX_MAGENTA;
    case 9: return rgbTo565(255, 140, 0);   // orange
    default: return customColor565;          // 0 = custom slot
  }
}

uint16_t activeColor() {
  return (colorIndex == 0) ? customColor565 : paletteColor(colorIndex);
}

void paintColor(uint16_t c) {
  TFTscreen.fillScreen(c);
}

void paintActive() {
  paintColor(activeColor());
}

void paintBlack() {
  paintColor(ST77XX_BLACK);
}

void applyBrightness() {
  analogWrite(TFT_BL, brightness);
}

void printHelp() {
  Serial.println(F("CMDS: C<n>=colour 1..9  RGB r g b=custom 24-bit  "
                   "F0/F1=flash off/on  D<ms>=flash period  "
                   "SEQ c1,c2,...=cycle list  B<0-255>=brightness  "
                   "O0/O1=backlight off/on  ?=state  H=help"));
}

void printState() {
  Serial.print(F("STATE C="));
  Serial.print(colorIndex);
  Serial.print(F(" RGB=0x"));
  if (customColor565 < 0x1000) Serial.print('0');
  if (customColor565 < 0x0100) Serial.print('0');
  if (customColor565 < 0x0010) Serial.print('0');
  Serial.print(customColor565, HEX);
  Serial.print(F(" F="));
  Serial.print(flashing ? 1 : 0);
  Serial.print(F(" D="));
  Serial.print(flashPeriodMs);
  Serial.print(F(" B="));
  Serial.print(brightness);
  Serial.print(F(" SEQ="));
  if (sequenceLen == 0) {
    Serial.println('-');
  } else {
    for (uint8_t i = 0; i < sequenceLen; i++) {
      if (i) Serial.print(',');
      Serial.print(sequence[i]);
    }
    Serial.println();
  }
}

// ---------- Serial command handling ----------
void handleLine(char *line) {
  // Strip leading whitespace
  while (*line == ' ' || *line == '\t') line++;
  if (*line == '\0') return;  // ignore blank lines silently

  // Normalise first token to upper case for cmd dispatch.
  char cmd = *line;
  if (cmd >= 'a' && cmd <= 'z') cmd = cmd - 'a' + 'A';

  // ----- multi-letter keywords first -----
  // SEQ: cycle list
  if ((line[0] == 'S' || line[0] == 's') &&
      (line[1] == 'E' || line[1] == 'e') &&
      (line[2] == 'Q' || line[2] == 'q') &&
      (line[3] == '\0' || line[3] == ' ' || line[3] == '\t' || line[3] == '-')) {
    const char *p = line + 3;
    while (*p == ' ' || *p == '\t') p++;
    // Empty list or "-" clears the sequence.
    if (*p == '\0' || (*p == '-' && *(p + 1) == '\0')) {
      sequenceLen = 0;
      sequenceIdx = 0;
      needsRepaint = true;
      flashPhaseOn = true;
      Serial.println(F("OK"));
      return;
    }
    uint8_t newSeq[SEQ_MAX];
    uint8_t newLen = 0;
    while (*p && newLen < SEQ_MAX) {
      while (*p == ' ' || *p == ',' || *p == '\t') p++;
      if (*p == '\0') break;
      char *endp;
      long v = strtol(p, &endp, 10);
      if (endp == p) {
        Serial.println(F("ERR seq parse"));
        return;
      }
      if (v < 1 || v > PALETTE_SIZE) {
        Serial.println(F("ERR seq index 1..9"));
        return;
      }
      newSeq[newLen++] = (uint8_t)v;
      p = endp;
    }
    if (newLen == 0) {
      Serial.println(F("ERR seq empty"));
      return;
    }
    // Reject overflow if the user supplied more than SEQ_MAX entries.
    while (*p == ' ' || *p == ',' || *p == '\t') p++;
    if (*p != '\0') {
      Serial.println(F("ERR seq too long (max 9)"));
      return;
    }
    for (uint8_t i = 0; i < newLen; i++) sequence[i] = newSeq[i];
    sequenceLen = newLen;
    sequenceIdx = 0;
    needsRepaint = true;
    flashPhaseOn = true;
    Serial.println(F("OK"));
    return;
  }

  // RGB custom colour
  if ((line[0] == 'R' || line[0] == 'r') &&
      (line[1] == 'G' || line[1] == 'g') &&
      (line[2] == 'B' || line[2] == 'b')) {
    const char *p = line + 3;
    while (*p == ' ' || *p == '\t') p++;
    if (*p == '\0') {
      Serial.println(F("ERR usage: RGB r g b"));
      return;
    }
    char *endp;
    long r = strtol(p, &endp, 10);
    if (endp == p) { Serial.println(F("ERR usage: RGB r g b")); return; }
    p = endp;
    long g = strtol(p, &endp, 10);
    if (endp == p) { Serial.println(F("ERR usage: RGB r g b")); return; }
    p = endp;
    long b = strtol(p, &endp, 10);
    if (endp == p) { Serial.println(F("ERR usage: RGB r g b")); return; }
    if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) {
      Serial.println(F("ERR rgb out of range"));
      return;
    }
    customColor565 = rgbTo565((uint8_t)r, (uint8_t)g, (uint8_t)b);
    colorIndex = 0;
    needsRepaint = true;
    flashPhaseOn = true;
    lastFlashMs = millis();
    Serial.println(F("OK"));
    return;
  }

  // ----- single-letter commands -----
  if (cmd == 'C') {
    int n = atoi(line + 1);
    if (n < 1 || n > PALETTE_SIZE) {
      Serial.print(F("ERR bad colour index: "));
      Serial.println(n);
      return;
    }
    colorIndex = (uint8_t)n;
    needsRepaint = true;
    flashPhaseOn = true;
    lastFlashMs = millis();
    Serial.println(F("OK"));
    return;
  }

  if (cmd == 'F') {
    char v = *(line + 1);
    if (v == '0') {
      flashing = false;
      flashPhaseOn = true;
      needsRepaint = true;
      Serial.println(F("OK"));
    } else if (v == '1') {
      flashing = true;
      flashPhaseOn = true;
      sequenceIdx = 0;
      lastFlashMs = millis();
      needsRepaint = true;
      Serial.println(F("OK"));
    } else {
      Serial.println(F("ERR usage: F0 or F1"));
    }
    return;
  }

  if (cmd == 'D') {
    long ms = atol(line + 1);
    if (ms < 20) ms = 20;
    if (ms > 60000) ms = 60000;
    flashPeriodMs = (uint32_t)ms;
    Serial.println(F("OK"));
    return;
  }

  if (cmd == 'B') {
    int v = atoi(line + 1);
    if (v < 0 || v > 255) {
      Serial.println(F("ERR brightness 0..255"));
      return;
    }
    brightness = (uint8_t)v;
    if (brightness > 0) savedBrightness = brightness;
    applyBrightness();
    Serial.println(F("OK"));
    return;
  }

  if (cmd == 'O') {
    char v = *(line + 1);
    if (v == '0') {
      brightness = 0;
      applyBrightness();
      Serial.println(F("OK"));
    } else if (v == '1') {
      brightness = (savedBrightness > 0) ? savedBrightness : 255;
      savedBrightness = brightness;
      applyBrightness();
      Serial.println(F("OK"));
    } else {
      Serial.println(F("ERR usage: O0 or O1"));
    }
    return;
  }

  if (cmd == '?') {
    printState();
    Serial.println(F("OK"));
    return;
  }

  if (cmd == 'H') {
    printHelp();
    Serial.println(F("OK"));
    return;
  }

  Serial.print(F("ERR unknown cmd: "));
  Serial.println(line);
}

void pollSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuf[lineLen] = '\0';
      handleLine(lineBuf);
      lineLen = 0;
    } else if (lineLen < LINE_BUF_SIZE - 1) {
      lineBuf[lineLen++] = c;
    } else {
      // overflow: reset buffer and report
      lineLen = 0;
      Serial.println(F("ERR line too long"));
    }
  }
}

// ---------- Buttons (preserve original semantics, non-blocking) ----------
void pollButtons() {
  uint32_t now = millis();
  if (now - lastButtonMs < BTN_DEBOUNCE_MS) return;

  bool up    = (digitalRead(buttonUp) == HIGH);
  bool down  = (digitalRead(buttonDown) == HIGH);
  bool chgC  = (digitalRead(buttonChangeColour) == HIGH);

  // Up+Down together: stop flashing and repaint current colour
  if (up && down) {
    flashing = false;
    flashPhaseOn = true;
    needsRepaint = true;
    lastButtonMs = now;
    return;
  }

  if (up) {
    if (flashing) {
      uint32_t doubled = flashPeriodMs * 2UL;
      flashPeriodMs = (doubled > 60000UL) ? 60000UL : doubled;
    } else {
      flashing = true;
      flashPhaseOn = true;
      sequenceIdx = 0;
      lastFlashMs = now;
      needsRepaint = true;
    }
    lastButtonMs = now;
    return;
  }

  if (down) {
    if (flashing) {
      uint32_t halved = flashPeriodMs / 2UL;
      flashPeriodMs = (halved < 20UL) ? 20UL : halved;
    } else {
      flashing = true;
      flashPhaseOn = true;
      sequenceIdx = 0;
      lastFlashMs = now;
      needsRepaint = true;
    }
    lastButtonMs = now;
    return;
  }

  if (chgC) {
    // Walk the palette 1..PALETTE_SIZE, wrapping; leaves custom slot only
    // reachable via the RGB command.
    if (colorIndex == 0 || colorIndex >= PALETTE_SIZE) {
      colorIndex = 1;
    } else {
      colorIndex = colorIndex + 1;
    }
    flashPhaseOn = true;
    needsRepaint = true;
    lastButtonMs = now;
    return;
  }
}

// ---------- Flash / cycle state machine (non-blocking) ----------
void updateFlash() {
  if (!flashing) {
    if (needsRepaint) {
      paintActive();
      needsRepaint = false;
    }
    return;
  }

  uint32_t now = millis();

  // Sequence mode: cycle through SEQ list, period = time-per-colour.
  if (sequenceLen > 0) {
    uint32_t interval = flashPeriodMs;
    if (interval < 20UL) interval = 20UL;

    if (needsRepaint) {
      paintColor(paletteColor(sequence[sequenceIdx]));
      needsRepaint = false;
      lastFlashMs = now;
      return;
    }

    if (now - lastFlashMs >= interval) {
      sequenceIdx = (sequenceIdx + 1) % sequenceLen;
      paintColor(paletteColor(sequence[sequenceIdx]));
      lastFlashMs = now;
    }
    return;
  }

  // Classic flash mode: colour ↔ black, period = full cycle.
  uint32_t half = flashPeriodMs / 2UL;
  if (half < 10UL) half = 10UL;

  if (needsRepaint) {
    if (flashPhaseOn) paintActive(); else paintBlack();
    needsRepaint = false;
    lastFlashMs = now;
    return;
  }

  if (now - lastFlashMs >= half) {
    flashPhaseOn = !flashPhaseOn;
    if (flashPhaseOn) paintActive(); else paintBlack();
    lastFlashMs = now;
  }
}

// ---------- Setup / loop ----------
void setup() {
  Serial.begin(115200);

  pinMode(buttonUp, INPUT);
  pinMode(buttonDown, INPUT);
  pinMode(buttonChangeColour, INPUT);

  // Backlight: drive HIGH (full brightness) immediately so init() is visible
  // on boards where BLK floats low by default.
  pinMode(TFT_BL, OUTPUT);
  applyBrightness();

  TFTscreen.init(135, 240);  // 1.14" 240x135 ST7789
  paintActive();

  Serial.println(F("READY display_control v2"));
  printHelp();
}

void loop() {
  pollSerial();
  pollButtons();
  updateFlash();
}
