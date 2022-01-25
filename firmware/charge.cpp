#include <stdlib.h>
#include <wirish/wirish.h>
#include <terminal.h>
#include "buzzer.h"
#include "charge.h"
#include "hardware.h"

static bool charge_force_fast = false;
static bool charge_is_fast = false;

void charge_init()
{
    digitalWrite(PIN_MORE_CHARGE, LOW);
    pinMode(PIN_MORE_CHARGE, INPUT);
    charge_fast(false);
}

void charge_fast(bool enable)
{
    if (enable && !charge_is_fast) {
        buzzer_play(MELODY_OK);
    }

    if (enable) {
        pinMode(PIN_MORE_CHARGE, OUTPUT);
    } else {
        pinMode(PIN_MORE_CHARGE, INPUT);
    }
    charge_is_fast = enable;
}

static int lastConnected = 0;

void charge_tick()
{
    if (SerialUSB.isConnected()) {
        lastConnected = millis();
    }

    // We allow the charger to draw more current if the board was not connected
    if (charge_force_fast || ((millis() - lastConnected) > 5000)) {
        charge_fast(true);
    } else {
        charge_fast(false);
    }
}


TERMINAL_COMMAND(charge, "Charge status")
{
    if (charge_is_fast) {
        terminal_io()->println("Charging fast");
    } else {
        terminal_io()->println("Charging normally");
    }
}

TERMINAL_COMMAND(fastCharge, "Force fast charge")
{
    if (argc == 0) {
        terminal_io()->println("Usage: fastCharge [0|1]");
    } else {
        int force = atoi(argv[0]);
        charge_force_fast = force;

        if (force) {
            terminal_io()->println("Enabling force fast charge");
        } else {
            terminal_io()->println("Disabling force fast charge");
        }
    }
}

