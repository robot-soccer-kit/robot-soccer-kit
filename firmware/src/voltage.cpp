#include "voltage.h"
#include "config.h"
#include "shell.h"
#include <Arduino.h>

static unsigned long last_measurement = 0;
SHELL_PARAMETER_FLOAT(voltage, "Voltage", 0.0);
static bool voltage_error = false;
#define DIVIDER_RATIO (VOLTAGE_R2 / ((float)(VOLTAGE_R1 + VOLTAGE_R2)))

// Voltage sampling frequency
#define SAMPLE_FREQUENCY 100

// Smoothing of voltage variation (V/s)
static float max_variation = 0.25;

#define MAX_VARIATION_STEP (max_variation / (float)SAMPLE_FREQUENCY)

static void voltage_sample(bool first = false) {
  last_measurement = millis();

  // Since ESP32 uncalibrated ADC seems to be inaccurate, we use 3.5 instead of 3.3V here.
  // Note that the goal is to only provide a warning; the batteries are physically protected by the BMS
  float sampled_voltage = (analogRead(VOLTAGE) * 3.5 / 4095) / DIVIDER_RATIO;

  if (first) {
    voltage = sampled_voltage;
  } else {
    voltage = max(voltage - MAX_VARIATION_STEP,
                  min(voltage + MAX_VARIATION_STEP, sampled_voltage));
  }
}

// Initializes voltage measurement
void voltage_init() {
  pinMode(VOLTAGE, ANALOG);
  voltage_error = false;

  voltage_sample(true);
}

// Update the voltage measurement
void voltage_tick() {
  if (millis() - last_measurement > 1000 / SAMPLE_FREQUENCY) {
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

float voltage_value() { return voltage; }

SHELL_COMMAND(volt, "Shows input voltage") {
  shell_stream()->print("Voltage: ");
  shell_stream()->print(voltage);
  shell_stream()->println("V");
}