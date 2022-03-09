#include "buzzer.h"
#include "leds.h"
#include "voltage.h"
#include "motors.h"

static unsigned long last_update = 0;
static int leds_blink = 0;
static bool is_alert = false;
CRGB leds_save[6];

void alert_tick()
{
  if (is_alert) {
    // Ensuring motors are disabled
    motors_disable();

    // Ensuring the buzzer is playing alert melody
    buzzer_play(MELODY_ALERT, true);

    // Getting the LEDs blinking red
    if (millis() - last_update > 250) {
      last_update = millis();
      leds_blink = !leds_blink;
      leds_set(255 * leds_blink, 0, 0);
    }

    if (!voltage_is_error()) {
      is_alert = false;
      
      // Stopping buzzer
      buzzer_stop();

      // Restoring LEDs
      CRGB *leds = leds_get();
      for (int k=0; k<6; k++) {
        leds[k] = leds_save[k];
      }
      leds_refresh();
    }
  } else {
    if (voltage_is_error()) {
      is_alert = true;

      // Saving LEDs
      CRGB *leds = leds_get();
      for (int k=0; k<6; k++) {
        leds_save[k] = leds[k];
      }
    }
  }
}
