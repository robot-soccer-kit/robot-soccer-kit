#pragma once

#include "kicker.h"
#include "config.h"
#include "shell.h"
#include <Arduino.h>

static int kick_end = 0;
static bool kicking = false;

void kicker_init() { pinMode(KICK_PIN, OUTPUT); }

void kicker_tick() {
  if (kicking && micros() > kick_end) {
    kicking = false;
    digitalWrite(KICK_PIN, LOW);
  }
}

void kicker_kick(float power) {
  if (!kicking) {
    if (power < 0)
      power = 0;
    if (power > 1)
      power = 1;
    kicking = true;
    kick_end = micros() + KICK_MAX_DURATION * power;
    digitalWrite(KICK_PIN, HIGH);
  }
}

SHELL_COMMAND(kick, "Kick") { kicker_kick(); }