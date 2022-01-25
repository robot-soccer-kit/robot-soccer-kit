#include "hardware.h"
#include "leds.h"
#include "terminal.h"
#include <stdlib.h>
#include <wirish.h>

#define KICK_DURATION 5000
#define CHARGE_TIME 500
static int last_kick = 0;

void kicker_init() {
  pinMode(PIN_OPTICAL_EN1, OUTPUT);
  digitalWrite(PIN_OPTICAL_EN1, LOW);
}

void kicker_tick() {
}

void kicker_kick(uint8_t power) {
  if ((millis() - last_kick) > CHARGE_TIME) {
    last_kick = millis();
    digitalWrite(PIN_OPTICAL_EN1, HIGH);
    delay_us((power * KICK_DURATION)/100);
    digitalWrite(PIN_OPTICAL_EN1, LOW);
  }
}

TERMINAL_COMMAND(kick, "Kick") {
  if (argc == 0) {
    kicker_kick(100);
  } else {
    kicker_kick(atoi(argv[0]));
  }
}