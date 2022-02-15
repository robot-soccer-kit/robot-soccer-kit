#include <WiFi.h>
#include "shell.h"
#include "kicker.h"
#include "motors.h"

void setup()
{
  kicker_init();
  shell_init();
  motors_init();
}

void loop()
{
  shell_tick();
}

