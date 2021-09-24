//#define DEBUG
#include "voltage.h"
#include <terminal.h>
#include "mux.h"
#include "hardware.h"

// Total voltage [V]
static float voltage;

// Voltage per sectors [V]
static float voltage1, voltage2;

// Is the robot turned on?
static bool is_on;

// Do we monitor the voltage
bool voltage_update = true;

// Is there a voltage error ?
bool voltage_is_error;

bool voltage_error()
{
    return voltage_is_error;
}

/**
 * Converts a sample from the multiplexer to a value in volts, using
 * the R1 and R2 resistor values
 */
float voltage_sample_to_volts(int sample, int r1, int r2)
{
    float volts = 3.3*sample/4096.0;
    volts /= r2/(float)(r1+r2);

    return volts;
}

void voltage_init()
{
    voltage = voltage1 = voltage2 = 0;
    voltage_is_error = false;
}

void voltage_tick()
{
    static int badVoltageSince;
    static int goodVoltageSince;

    // Converting the samples
    float _voltage1 = voltage_sample_to_volts(multiplexers.voltage2, VOLTAGE2_R1, VOLTAGE2_R2);
    float _voltage = voltage_sample_to_volts(multiplexers.voltage1, VOLTAGE1_R1, VOLTAGE1_R2);
    float _voltage2 = _voltage - voltage1;
    is_on = (_voltage1 > 1);

    // Updating the voltages (smoothed)
    if (voltage_update){
      voltage = voltage*0.95 + _voltage*0.05;
      voltage1 = voltage1*0.95 + _voltage1*0.05;
      voltage2 = voltage2*0.95 + _voltage2*0.05;
    }

    // Measuring voltage1 to almost 0 means that the robot is off
    // (we are then powered by USB and should not trigger the error)
    bool badVoltage = (is_on && (voltage1 < VOLTAGE_LIMIT || voltage2 < VOLTAGE_LIMIT));
    bool error = false;

    if (badVoltage) {
        int elapsed = (millis()-badVoltageSince);
        error = (elapsed > 3000);
    } else {
        badVoltageSince = millis();
        error = false;
    }

    bool goodVoltage = (is_on && voltage1 >= (VOLTAGE_LIMIT + 0.2) && voltage2 >= (VOLTAGE_LIMIT + 0.2));
    bool noError = true;

    if (goodVoltage) {
        int elapsed = (millis()-goodVoltageSince);
        noError = (elapsed > 3000);
    } else {
        goodVoltageSince = millis();
        noError = false;
    }


    if (voltage_is_error) {
        if (noError) {
            voltage_is_error = false;
        }
    } else {
        if (error) {
            voltage_is_error = true;
        }
    }
}

float voltage_current()
{
    return voltage;
}

bool voltage_is_robot_on()
{
    return is_on;
}

float voltage_bat1()
{
    return voltage1;
}

float voltage_bat2()
{
    return voltage2;
}

TERMINAL_COMMAND(voltage, "Get the voltage")
{
    terminal_io()->print("voltage=");
    terminal_io()->println((int)(10*voltage_current()));
}

TERMINAL_COMMAND(bat, "Battery status")
{
    if (is_on) {
        terminal_io()->print("Voltage: ");
        terminal_io()->println(voltage);

        terminal_io()->print("Sector 1: ");
        terminal_io()->print(voltage1);
        if (voltage1 < VOLTAGE_LIMIT) {
            terminal_io()->print(" !LOW!");
        }
        terminal_io()->println();
        terminal_io()->print("Sector 2: ");
        terminal_io()->print(voltage2);
        if (voltage2 < VOLTAGE_LIMIT) {
            terminal_io()->print(" !LOW!");
        }
        terminal_io()->println();


        terminal_io()->println("Robot switch is turned on");
    } else {
        terminal_io()->println("Robot switch is turned off");
    }
}

#ifdef DEBUG
void voltage_set(float voltage, int battery)
{
  switch (battery) {
  case 0:
    voltage1 = voltage2 = voltage;
    break;
  case 1:
    voltage1 = voltage;
    break;
  case 2:
    voltage2 = voltage;
    break;
  }
  voltage = voltage1 + voltage2;
}

TERMINAL_COMMAND(voltage_set, "Change battery voltage values")
{
    if (argc == 0) {
      terminal_io()->println("Usage : voltage_set value battery (battery = 1 or 2).");
        terminal_io()->println("Or");
        terminal_io()->println("Usage : voltage_set value (for both batteries).");
    } else if(argc == 1)
    {
      voltage_update = false;
      voltage_set(atof(argv[0]), 0);
    } else if (argc == 2) {
      voltage_update = false;
      voltage_set(atof(argv[0]), atoi(argv[1]));
    }
}

TERMINAL_COMMAND(voltage_monitor, "Start monitoring voltage")
{
    voltage_update = true;
}

#endif
