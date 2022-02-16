#include <Arduino.h>
#include "leds.h"
#include "config.h"

CRGB leds[6];

void leds_init()
{
  FastLED.addLeds<NEOPIXEL, LEDS>(leds, 6); 

  for (int k=0; k<6; k++) {
    leds[k] = CRGB(128, 64, 0);
  }

  FastLED.show();
}

void leds_set(uint8_t r, uint8_t g, uint8_t b)
{
  for (int k=0; k<6; k++) {
    leds[k] = CRGB(r, g, b);
  }

  FastLED.show();
}

CRGB *leds_get()
{
  return leds;
}

void leds_refresh()
{
  FastLED.show();
}