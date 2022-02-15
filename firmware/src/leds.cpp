#include <Arduino.h>
#include <FastLED.h>
#include "pinout.h"

CRGB leds[6];

void leds_init()
{
  FastLED.addLeds<NEOPIXEL, LEDS>(leds, 6); 

  for (int k=0; k<6; k++) {
    leds[k] = CRGB(0, 255, 0);
  }

  FastLED.show();
}