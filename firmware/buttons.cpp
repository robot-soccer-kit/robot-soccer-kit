#include "buttons.h"
#include "rhock.h"
#include <rhock/chain.h>
#include <rhock/memory.h>
#include <rhock/native.h>
#include <rhock/obj.h>
#include <rhock/program.h>
#include <rhock/store.h>
#include <rhock/vm.h>
#include <stdlib.h>

#ifdef HAS_TERMINAL
#include <terminal.h>
#else
#include "no_terminal.h"
#endif
#ifndef __EMSCRIPTEN__
#include "hardware.h"
#include "main.h"
#include "imu.h"
#include "opticals.h"
#include "mux.h"
#include <wirish/wirish.h>
#endif

static bool buttons_state[4] = { false, false, false, false };

TERMINAL_COMMAND(btn, "Buttons state")
{
    while (!SerialUSB.available()) {
        show_buttons_raw_values();
    }
}

int get_button_raw_value(int k)
{
    if (k < 4) {
        return multiplexers.buttons[k];
    } else {
        return 1000;
    }
}

void show_buttons_raw_values()
{
    for (int k = 0; k < 4; k++) {
        terminal_io()->print(multiplexers.buttons[k]);
        terminal_io()->print(" ");
    }
    terminal_io()->println();
}

bool button_is_pressed(int k)
{
    return get_button_raw_value(k) < BTN_THRESHOLD;
}

void button_press(int k)
{
    // Stopping all programs
    emergency_stop();

    // Run a program
    if (k < 3) {
        if (buttons_state[3]) {
            // Button 3 is pressed, running calibrations
            switch (k) {
                case 0:
                imu_calib_rotate();
                break;
                case 1:
                // opticals_calibrate(0);
                break;
                case 2:
                // opticals_calibrate(1);
                break;
            };
        } else {
            // Button 3 is not pressed, running the nth program
            struct rhock_obj** objs = rhock_get_programs();
            int i = 0;
            while (*objs != NULL) {
                struct rhock_obj* obj = *objs;
                objs++;
                if (i == k) {
                    rhock_memory_addr addr = rhock_vm_get_program(obj->id);
                    if (addr == RHOCK_NULL) {
                        rhock_program_load(obj);
                    } else {
                        rhock_program_run(obj->id);
                    }
                }
                i++;
            }
        }
    }
}

void buttons_tick()
{
    for (int k = 0; k < 4; k++) {
        bool new_state = button_is_pressed(k);
        if (new_state && !buttons_state[k]) {
            button_press(k);
        }
        buttons_state[k] = new_state;
    }
}