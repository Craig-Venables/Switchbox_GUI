/**************************************************************************
  This is a library for several Adafruit displays based on ST77* drivers.

  Works with the Adafruit 1.8" TFT Breakout w/SD card
    ----> http://www.adafruit.com/products/358
  The 1.8" TFT shield
    ----> https://www.adafruit.com/product/802
  The 1.44" TFT breakout
    ----> https://www.adafruit.com/product/2088
  The 1.14" TFT breakout
  ----> https://www.adafruit.com/product/4383
  The 1.3" TFT breakout
  ----> https://www.adafruit.com/product/4313
  The 1.54" TFT breakout
    ----> https://www.adafruit.com/product/3787
  The 1.69" TFT breakout
    ----> https://www.adafruit.com/product/5206
  The 2.0" TFT breakout
    ----> https://www.adafruit.com/product/4311
  as well as Adafruit raw 1.8" TFT display
    ----> http://www.adafruit.com/products/618

  Check out the links above for our tutorials and wiring diagrams.
  These displays use SPI to communicate, 4 or 5 pins are required to
  interface (RST is optional).

  Adafruit invests time and resources providing this open source code,
  please support Adafruit and open-source hardware by purchasing
  products from Adafruit!

  Written by Limor Fried/Ladyada for Adafruit Industries.
  MIT license, all text above must be included in any redistribution
 **************************************************************************/

#include <Adafruit_GFX.h>    // Core graphics library
#include <Adafruit_ST7735.h> // Hardware-specific library for ST7735
#include <Adafruit_ST7789.h> // Hardware-specific library for ST7789
#include <SPI.h>
const int buttonUp=2;
const int buttonDown=3;
const int buttonChangeColour=4;
int FlashingDelay; /// in milliseconds
int Flashing; // is Flashing on or off
int ScreenColour;   // screenColour red=1, green=2, blue=3, white=4



#if defined(ARDUINO_FEATHER_ESP32) // Feather Huzzah32
  #define TFT_CS         14
  #define TFT_RST        15
  #define TFT_DC         32

#elif defined(ESP8266)
  #define TFT_CS         4
  #define TFT_RST        16                                            
  #define TFT_DC         5

#else
  // For the breakout board, you can use any 2 or 3 pins.
  // These pins will also work for the 1.8" TFT shield.
  #define TFT_CS        10
  #define TFT_RST        8 // Or set to -1 and connect to Arduino RESET pin
  #define TFT_DC         9
#endif

// OPTION 1 (recommended) is to use the HARDWARE SPI pins, which are unique
// to each board and not reassignable. For Arduino Uno: MOSI = pin 11 and
// SCLK = pin 13. This is the fastest mode of operation and is required if
// using the breakout board's microSD card.

// For 1.44" and 1.8" TFT with ST7735 use:
//Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

// For 1.14", 1.3", 1.54", 1.69", and 2.0" TFT with ST7789:
Adafruit_ST7789 TFTscreen = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_RST);


// OPTION 2 lets you interface the display using ANY TWO or THREE PINS,
// tradeoff being that performance is not as fast as hardware SPI above.
//#define TFT_MOSI 11  // Data out
//#define TFT_SCLK 13  // Clock out

// For ST7735-based displays, we will use this call
//Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST);

// OR for the ST7789-based displays, we will use this call
//Adafruit_ST7789 tft = Adafruit_ST7789(TFT_CS, TFT_DC, TFT_MOSI, TFT_SCLK, TFT_RST);


float p = 3.1415926;

void setup(void) {
  Serial.begin(9600);
  Serial.print(F("Hello! ST77xx TFT Test"));
  pinMode(buttonUp, INPUT);
  pinMode(buttonDown, INPUT);
  pinMode(buttonChangeColour, INPUT);
  FlashingDelay=1000; /// 1000 milliseconds
  Flashing=0; // is Flashing on or off
  ScreenColour=1;   // starting screenColour red=1, green=2, blue=3, white=4

  // Use this initializer if using a 1.8" TFT screen:
  //tft.initR(INITR_BLACKTAB);      // Init ST7735S chip, black tab

  // OR use this initializer if using a 1.8" TFT screen with offset such as WaveShare:
  // tft.initR(INITR_GREENTAB);      // Init ST7735S chip, green tab

  // OR use this initializer (uncomment) if using a 1.44" TFT:
  //tft.initR(INITR_144GREENTAB); // Init ST7735R chip, green tab

  // OR use this initializer (uncomment) if using a 0.96" 160x80 TFT:
  //tft.initR(INITR_MINI160x80);  // Init ST7735S mini display
  // OR use this initializer (uncomment) if using a 0.96" 160x80 TFT with 
  // plug-in FPC (if you see the display is inverted!)
  //tft.initR(INITR_MINI160x80_PLUGIN);  // Init ST7735S mini display

  // OR use this initializer (uncomment) if using a 1.3" or 1.54" 240x240 TFT:
  //tft.init(240, 240);           // Init ST7789 240x240

  // OR use this initializer (uncomment) if using a 1.69" 280x240 TFT:
  //tft.init(240, 280);           // Init ST7789 280x240

  // OR use this initializer (uncomment) if using a 2.0" 320x240 TFT:
  //tft.init(240, 320);           // Init ST7789 320x240

  // OR use this initializer (uncomment) if using a 1.14" 240x135 TFT:
  TFTscreen.init(135, 240);           // Init ST7789 240x135
  
  // OR use this initializer (uncomment) if using a 1.47" 172x320 TFT:
  //tft.init(172, 320);           // Init ST7789 172x320

  // SPI speed defaults to SPI_DEFAULT_FREQ defined in the library, you can override it here
  // Note that speed allowable depends on chip and quality of wiring, if you go too fast, you
  // may end up with a black screen some times, or all the time.
  //tft.setSPISpeed(40000000);

  Serial.println(F("Initialized"));
  TFTscreen.fillScreen(ST77XX_RED); //set intial screen colour
}

void loop() {



if (digitalRead(buttonUp)==HIGH) {
                                        if (Flashing==1) {FlashingDelay=FlashingDelay*2;}
                                        else {Flashing=1;}
                                    }
if (digitalRead(buttonDown)==HIGH) {
                                        if (Flashing==1) {FlashingDelay=FlashingDelay/2;}
                                        else {Flashing=1;}
                                    }
if ((digitalRead(buttonUp)==HIGH) && (digitalRead(buttonDown)==HIGH)) {
                                    Flashing=0;
                                    if (ScreenColour==1) TFTscreen.fillScreen(ST77XX_RED);
                                    if (ScreenColour==2) TFTscreen.fillScreen(ST77XX_GREEN);
                                    if (ScreenColour==3) TFTscreen.fillScreen(ST77XX_BLUE);
                                    if (ScreenColour==4) TFTscreen.fillScreen(ST77XX_WHITE);
                                    if (ScreenColour==5) TFTscreen.fillScreen(ST77XX_BLACK);
                                    }
if (digitalRead(buttonChangeColour)==HIGH) 
      {
        if (ScreenColour<5) {ScreenColour=ScreenColour+1;} else {ScreenColour=1;} 
        if (ScreenColour==1) TFTscreen.fillScreen(ST77XX_RED);
        if (ScreenColour==2) TFTscreen.fillScreen(ST77XX_GREEN);
        if (ScreenColour==3) TFTscreen.fillScreen(ST77XX_BLUE);
        if (ScreenColour==4) TFTscreen.fillScreen(ST77XX_WHITE);
        if (ScreenColour==5) TFTscreen.fillScreen(ST77XX_BLACK);
        delay(200);
      }

if (Flashing==1) 
 {
  TFTscreen.fillScreen(ST77XX_BLACK);
  delay(FlashingDelay/2);
  if (ScreenColour==1) {TFTscreen.fillScreen(ST77XX_RED);}
  if (ScreenColour==2) {TFTscreen.fillScreen(ST77XX_GREEN);}
  if (ScreenColour==3) {TFTscreen.fillScreen(ST77XX_BLUE);}
  if (ScreenColour==4) {TFTscreen.fillScreen(ST77XX_WHITE);}
   delay(FlashingDelay/2);
 }
  // draw the background based on the mapped values
  //TFTscreen.background(redVal, greenVal, blueVal);
  //TFTscreen.background(0, 255, 255); //red
  
  //TFTscreen.fillScreen(ST77XX_RED);
  // delay(2000);
  //TFTscreen.fillScreen(ST77XX_RED);
  // delay(2000);
  //TFTscreen.fillScreen(ST77XX_GREEN);; //green
  //delay(2000);
  // TFTscreen.fillScreen(ST77XX_BLUE);;  //blue
  //delay(2000);

 // testdrawrects(ST77XX_RED);
 //  delay(1000);
 // testfillrects(ST77XX_RED, ST77XX_BLACK);
 // delay(1000);
  // wait for a moment
  //delay(330);
}

void testdrawrects(uint16_t color) {
  TFTscreen.fillScreen(ST77XX_BLACK);
  for (int16_t x=0; x < TFTscreen.width(); x+=6) {
    TFTscreen.drawRect(TFTscreen.width()/2 -x/2, TFTscreen.height()/2 -x/2 , x, x, color);
  }
}

void testfillrects(uint16_t color1, uint16_t color2) {
 TFTscreen.fillScreen(ST77XX_BLACK);
  for (int16_t x=TFTscreen.width()-1; x > 6; x-=6) {
    TFTscreen.fillRect(TFTscreen.width()/2 -x/2, TFTscreen.height()/2 -x/2 , x, x, color1);
    TFTscreen.drawRect(TFTscreen.width()/2 -x/2, TFTscreen.height()/2 -x/2 , x, x, color2);
  }
}