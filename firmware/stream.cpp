#include "stream.h"
#include "bin_stream.h"
#include "buzzer.h"
#include "dc.h"
#include "hardware.h"
#include "kicker.h"
#include "leds.h"
#include "main.h"
#include "math.h"
#include "motion.h"
#include "terminal.h"
#include "voltage.h"
#include <stdio.h>

#define BIN_STREAM_HOLOBOT 80

short bin_controls[16] = {0};

bool monitor_encoders_values = false;

#include <wirish/wirish.h>
#define LED_PIN 22

char bin_on_packet(uint8_t type) {
  if (type == BIN_STREAM_HOLOBOT) {
    if (bin_stream_available() >= 1) {
      uint8_t command = bin_stream_read();
      switch (command) {
      case 0: { // Controlling board led
        uint8_t state = bin_stream_read();
        digitalWrite(LED_PIN, state ? HIGH : LOW);
        return 1;
        break;
      }
      case 2: { // Motion control
        motion_set_api_order((int16_t)bin_stream_read_short(),
                             (int16_t)bin_stream_read_short(),
                             (int16_t)bin_stream_read_short());
        return 1;
        break;
      }
      case 3: { // Beep
        short freq = bin_stream_read_short();
        short duration = bin_stream_read_short();
        buzzer_beep(freq, duration);
        return 1;
        break;
      }
      case 4: { // Play
        short melody_id = bin_stream_read_short();
        buzzer_play(melody_id);
        return 1;
        break;
      }
      case 7: { // Set boards leds
        if (bin_stream_available() == 3) {
          uint8_t red = bin_stream_read();
          uint8_t green = bin_stream_read();
          uint8_t blue = bin_stream_read();

          led_all_color_set(red, green, blue);
        }

        return 1;
        break;
      }
      case 8: { // Enable breathing
        led_set_mode(LEDS_BREATH);

        return 1;
        break;
      }
      case 10: { // Monitor encoders
        if (bin_stream_available() == 1) {
          monitor_encoders_values = bin_stream_read();
        }

        return 1;
        break;
      }
      case 11: { // Emergency stop
        emergency_stop();
        return 1;
        break;
      }
      case 12: { // Kick
        if (bin_stream_available() == 1) {
          kicker_kick(bin_stream_read());
        }
      }
      }
    }
  }
  return 0;
}
void bin_on_monitor() {
  bin_stream_begin(BIN_STREAM_USER);

  // Robot version and timestamp
  bin_stream_append(METABOT_VERSION);
  bin_stream_append_int((uint32_t)millis());

  // Legacy/dummy: Distances sensor
  bin_stream_append_short((uint16_t)((int16_t)(10 * 0)));

  // Legacy/dummy: IMU
  for (int i = 0; i < OPTICAL_NB; i++) {
    bin_stream_append((uint8_t)(0 >> 2));
  }

  // Whell speeds in [deg/s] or encoders values
  for (int i = 0; i < 3; i++) {
    if (monitor_encoders_values) {
      bin_stream_append_short((uint16_t)(encoder_position(i) & 0xffff));
    } else {
      bin_stream_append_short(
          (uint16_t)((int16_t)(10 * wheel_speed(i) / M_PI * 180.0)));
    }
  }

  // Legacy/dummy: IMU values
  bin_stream_append_short(0);
  bin_stream_append_short(0);
  bin_stream_append_short(0);
  bin_stream_append_short(0);

  // LEgacy/dummy: odometry
  bin_stream_append_short(0);
  bin_stream_append_short(0);
  bin_stream_append_short(0);

  // Batteries voltage, 0/0 if the robot is off
  // Unit is 40th of volts
  if (voltage_is_robot_on()) {
    bin_stream_append(voltage_bat1() * 40);
    bin_stream_append(voltage_bat2() * 40);
  } else {
    bin_stream_append(0);
    bin_stream_append(0);
  }

  bin_stream_end();
}

void api_disable() {
  api_control = false;
  api_dx = 0;
  api_dy = 0;
  api_turn = 0;
}

const char bin_exit[] = "!bin\r";
const int bin_exit_len = 7;
int bin_exit_pos = 0;
bool bin_mode = false;

bool is_bin_mode() { return bin_mode; }

void bin_stream_send(uint8_t c) {
  if (bin_mode) {
    terminal_io()->write(&c, 1);
  }
}

TERMINAL_COMMAND(rhock, "Enter rhock mode (legacy)") {
  bin_mode = true;
  terminal_disable();
}

TERMINAL_COMMAND(bin, "Enter bin mode") {
  bin_mode = true;
  terminal_disable();
}

/**
 * Main loop
 */
void bin_tick() {
  if (bin_mode) {
    while (terminal_io()->io->available()) {
      char c = terminal_io()->io->read();
      if (bin_exit[bin_exit_pos] == c) {
        bin_exit_pos++;
        if (bin_exit_pos >= bin_exit_len) {
          bin_mode = false;
          terminal_enable();
        }
      } else {
        bin_exit_pos = 0;
      }

      bin_stream_recv(c);
    }

    bin_stream_tick();
  }
}