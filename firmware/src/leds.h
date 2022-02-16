#pragma once

#include <FastLED.h>
#include <stdint.h>

void leds_default();
void leds_set_alert(bool alert);
void leds_init();
void leds_set(uint8_t r, uint8_t g, uint8_t b);
void leds_refresh();
CRGB *leds_get();