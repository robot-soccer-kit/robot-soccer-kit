#include "bin_stream.h"
#include "com.h"
#include "buzzer.h"
#include "kicker.h"
#include "leds.h"
#include "motors.h"
#include "shell.h"
#include "voltage.h"
#include "config.h"
#include <BluetoothSerial.h>

#define BIN_STREAM_ROBOT 80

#define COMMAND_CONTROL 2
#define COMMAND_BEEP 3
#define COMMAND_SET_LEDS 7
#define COMMAND_LEDS_DEFAULT 8
#define COMMAND_EMERGENCY 11
#define COMMAND_KICK 12

bool do_forward = false;
bool is_bin = false;
bool is_bt = false;
BluetoothSerial bt;

const char bin_exit[] = "!bin\r";
const int bin_exit_len = 5;
int bin_exit_pos = 0;

char bin_on_packet(uint8_t type) {
  if (type == BIN_STREAM_ROBOT) {
    if (bin_stream_available() >= 1) {
      uint8_t command = bin_stream_read();

      if (command == COMMAND_CONTROL) { // Motion control
        float dx = ((int16_t)bin_stream_read_short()) / 1000.;
        float dy = ((int16_t)bin_stream_read_short()) / 1000.;
        float dt = ((int16_t)bin_stream_read_short()) * M_PI / 180;

        motors_set_ik(dx, dy, dt);
        return 1;
      } else if (command == COMMAND_BEEP) { // Beep
        short freq = bin_stream_read_short();
        short duration = bin_stream_read_short();
        buzzer_beep(freq, duration);
        return 1;
      } else if (command == COMMAND_SET_LEDS) { // Set boards leds
        if (bin_stream_available() == 3) {
          uint8_t red = bin_stream_read();
          uint8_t green = bin_stream_read();
          uint8_t blue = bin_stream_read();

          leds_set(red, green, blue);
        }

        return 1;
      } else if (command == COMMAND_LEDS_DEFAULT) { // Default LEDs
        leds_default();

        return 1;
      } else if (command == COMMAND_EMERGENCY) { // Emergency stop
        motors_disable();
        return 1;
      } else if (command == COMMAND_KICK) { // Kick
        if (bin_stream_available() == 1) {
          kicker_kick(bin_stream_read() / 100.);
        }
        return 1;
      }
    }
  }
  return 0;
}

void bin_on_monitor() {
  bin_stream_begin(BIN_STREAM_USER);

  // Robot version and timestamp
  bin_stream_append(2);
  bin_stream_append_int((uint32_t)millis());
  // Battery voltage, 10th of volts
  bin_stream_append(voltage_value() * 10);
  bin_stream_end();
}

void bin_stream_send(uint8_t c) {
  shell_stream()->write(c);
}

void com_init() {
  bt.enableSSP();
  bt.setPin("1234");
  bt.begin(ROBOT_NAME);
  shell_init();
}

static unsigned long last_byte_timestamp = 0;

void com_bin_tick() {
  while (shell_stream()->available()) {
    uint8_t c = shell_stream()->read();
    last_byte_timestamp = millis();
    // Checking for binary mode exit sequence
    if (bin_exit[bin_exit_pos] == c) {
      bin_exit_pos++;
      if (bin_exit_pos >= bin_exit_len) {
        is_bin = false;
      }
    } else {
      bin_exit_pos = 0;
    }

    // Ticking binary
    bin_stream_recv(c);

  }
  // Stopping motors if we had no news for 3s
  if (last_byte_timestamp != 0 && (millis() - last_byte_timestamp) > 3000) {
    last_byte_timestamp = 0;
    motors_set_ik(0., 0., 0.);
  }

  bin_stream_tick();
}

void com_tick() {
  // In shell mode, testing for the need of switching the stream and tick the
  // shell
  if (!is_bt && bt.available()) {
    is_bt = true;
    shell_set_stream(&bt);
  }
  if (is_bt && Serial.available()) {
    is_bt = false;
    shell_set_stream(&Serial);
  }

  if (do_forward) {
    while (bt.available())
      Serial.write(bt.read());
    while (Serial.available())
      bt.write(Serial.read());
  } else if (is_bin) {
    com_bin_tick();
  } else {
    shell_tick();
  }
}

SHELL_COMMAND(forward, "Starts forwarding BT and USB (for debugging)") {
  do_forward = true;
}

SHELL_COMMAND(bin, "Switch to binary mode") { is_bin = true; }

SHELL_COMMAND(rhock, "Switch to binary mode (legacy)") { is_bin = true; }
