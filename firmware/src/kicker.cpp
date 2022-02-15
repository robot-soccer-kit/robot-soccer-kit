#pragma once

#include <Arduino.h>
#include "pinout.h"
#include "shell.h"

void kicker_init()
{
  pinMode(KICK_PIN, OUTPUT);
}

void kicker_kick()
{
  digitalWrite(KICK_PIN, HIGH);
  vTaskDelay(15);
  digitalWrite(KICK_PIN, LOW);
}

SHELL_COMMAND(kick, "Kick")
{
  kicker_kick();
}