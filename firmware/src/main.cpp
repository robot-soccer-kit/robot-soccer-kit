#include <WiFi.h>
#include "shell.h"
#include "kicker.h"
#include "motors.h"
#include "buzzer.h"
#include "leds.h"

void setup()
{
  leds_init();
  kicker_init();
  shell_init();
  motors_init();
  buzzer_init();
}

void loop()
{
  shell_tick();
}

