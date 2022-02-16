#include "voltage.h"
#include "config.h"
#include "shell.h"
#include <Arduino.h>

static int last_measurement = 0;
static float voltage = 0.0;
static bool voltage_error = false;
#define DIVIDER_RATIO (VOLTAGE_R2 / ((float)(VOLTAGE_R1 + VOLTAGE_R2)))

static void voltage_sample(bool first = false) {
  last_measurement = millis();
  float sampled_voltage = (analogRead(VOLTAGE) * 3.3 / 4096) / DIVIDER_RATIO;

  if (first) {
    voltage = sampled_voltage;
  } else {
    voltage = 0.95 * voltage + 0.05 * sampled_voltage;
  }
}

// Initializes voltage measurement
void voltage_init() {
  pinMode(VOLTAGE, ANALOG);
  voltage_error = false;
}

// Update the voltage measurement
void voltage_tick() {
  if (millis() - last_measurement > 10) {
    voltage_sample();

    if (voltage_error) {
      if (voltage > VOLTAGE_MIN + 0.25 || voltage < VOLTAGE_USB) {
        voltage_error = false;
      }
    } else {
      if (voltage > VOLTAGE_USB && voltage < VOLTAGE_MIN) {
        voltage_error = true;
      }
    }
  }
}

// Checks if the voltage is ok
bool voltage_is_error() { return voltage_error; }

bool voltage_can_move() { return voltage > VOLTAGE_MIN; }

SHELL_COMMAND(volt, "Shows input voltage") {
  shell_stream()->print("Voltage: ");
  shell_stream()->print(voltage);
  shell_stream()->println("V");
}