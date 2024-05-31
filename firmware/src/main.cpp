#include "alert.h"
#include "com.h"
#include "buzzer.h"
#include "kicker.h"
#include "leds.h"
#include "motors.h"
#include "voltage.h"
#include <WiFi.h>
#include <WiFiUdp.h>

void setup() {

  leds_init();
  kicker_init();
  motors_init();
  buzzer_init();
  voltage_init();
  com_init();
  //buzzer_play(MELODY_BOOT);
}

void loop() {
  buzzer_tick();
  kicker_tick();
  voltage_tick();
  alert_tick();
  com_tick();
  
}
