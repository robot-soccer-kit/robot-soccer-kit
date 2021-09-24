#include <stdlib.h>
#include <wirish.h>
#include "terminal.h"
#include "hardware.h"
#include "leds.h"

#define CHARGE_TIME 1500
#define BLINK_DT 200
static int last_kick = 0;

void kicker_init()
{
  pinMode(PIN_OPTICAL_EN1, OUTPUT);
  digitalWrite(PIN_OPTICAL_EN1, LOW);
}

void kicker_tick()
{
  int time_since_last_tick = (millis() - last_kick);
  if (time_since_last_tick > CHARGE_TIME) {
    time_since_last_tick = CHARGE_TIME;
  }
  uint8_t charge = ((100*time_since_last_tick)/CHARGE_TIME);

  // if (charge < 100) {
  //   int phase = (time_since_last_tick / BLINK_DT) % 2;
  //   if (phase == 0) {
  //     led_all_color_set(255, 0, 0);
  //   } else {
  //     led_all_color_set(0, 0, 0);
  //   }
  // } else {
  //   led_all_color_set(0, 255, 0);
  // }

}

void kicker_kick(uint8_t power)
{
  if ((millis() - last_kick) > CHARGE_TIME) {
    last_kick = millis();
    digitalWrite(PIN_OPTICAL_EN1, HIGH);
    delay(power/2);
    digitalWrite(PIN_OPTICAL_EN1, LOW);
  }
}

TERMINAL_COMMAND(kick, "Kick")
{
  if (argc == 0) {
    kicker_kick(100);
  } else {
    kicker_kick(atoi(argv[0]));
  }
}