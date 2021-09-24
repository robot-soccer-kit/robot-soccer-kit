#ifndef _METABOT_LEDS_H
#define _METABOT_LEDS_H

#include <stdint.h>

#define LED_R   (1<<2)
#define LED_G   (1<<1)
#define LED_B   (1<<0)

// The leds are breathing
#define LEDS_BREATH     0
#define LEDS_OFF        1
#define LEDS_BAD        2
#define LEDS_CUSTOM     3
#define LEDS_BLINK      4

struct led {
  uint8_t r, g, b;
};

struct leds {
  struct led u1;
  struct led d1;
  struct led u2;
  struct led d2;
  struct led u3;
  struct led d3;
};

// XXX: Comment this mess
void leds_init();
void led_set_mode(int mode);
void led_set(int index, int value, bool custom=false);
void led_color_set(int index, int r, int g, int b);
void led_all_color_set(int r, int g, int b);
void led_set_all(int value, bool custom=false);
int led_get(int index);
void led_set_blink_duration(int duration);
void led_stream_state();
char leds_are_custom();
char leds_are_blinking();
char leds_are_bad();
void leds_decustom();
void leds_tick();

#endif
