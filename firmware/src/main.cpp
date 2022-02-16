#include <WiFi.h>
#include "shell.h"
#include "kicker.h"
#include "motors.h"
#include "buzzer.h"
#include "leds.h"

void setup()
{
  shell_init();
  leds_init();
  kicker_init();
  motors_init();
  buzzer_init();
  buzzer_play(MELODY_BOOT);
}

void loop()
{
  shell_tick();
  buzzer_tick();
  kicker_tick();
}

