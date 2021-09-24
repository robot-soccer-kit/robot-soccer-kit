#include <stdio.h>
#include <stdlib.h>
#include "buzzer.h"
#include "hardware.h"
#include "opticals.h"

#ifdef HAS_TERMINAL
#include <terminal.h>
#else
#include "no_terminal.h"
#endif

#ifndef __EMSCRIPTEN__
#include "infos.h"
#include "mux.h"
#else
#include <emscripten.h>
#include <emscripten/bind.h>
#include "js_utils.h"
#endif

static bool should_compute = false;

static int opticals_state = 0;

int opticals[OPTICAL_NB];
int opticals_mapping[] = { 0, 1, 2, 3, 4, 5, 6 };
int opticals_pos[] = { 3, 2, 1, 0, -1, -2, -3 };

float opticals_position = 0, opticals_quantity = 0;

#ifndef __EMSCRIPTEN__
TERMINAL_PARAMETER_INT(optdbg, "dump opticals", 0);
#endif


float opticals_get_position()
{
    return opticals_position;
}

float opticals_get_quantity()
{
    return opticals_quantity;
}

int optical_get(int i)
{
    if (i < 0 || i >= OPTICAL_NB)
        return 0;
    return opticals[opticals_mapping[i]];
}

int optical_get_corrected(int k)
{
    int v = optical_get(k);
#ifndef __EMSCRIPTEN__
    struct robot_infos *infos = infos_get();

    v -= infos->opticals_white[k];
    v *= 1023;
    if (infos->opticals_black[k] != infos->opticals_white[k]) {
        v /= (infos->opticals_black[k] - infos->opticals_white[k]);
    }
#endif
    if (v < 0)
        v = 0;
    if (v > 1023)
        v = 1023;

    return v;
}

int get_opticals_individual_quantity(int k)
{
    return optical_get_corrected(k);
}

void compute_optical_quantity_and_position()
{
    int total_quantity = 0;
    int total_pos = 0;
    for (int k = 0; k < (int)OPTICAL_NB; k++) {
        int v = optical_get_corrected(k);

        v -= 256;
        if (v < 0)
            v = 0;

        total_quantity += v;
        total_pos += opticals_pos[k] * v;
    }
    opticals_quantity = (total_quantity*1000)/5369;
    
    if (total_quantity > 0) {
        opticals_position = opticals_position * 0.95 + 0.05 * total_pos / (float)total_quantity;
    } else {
        opticals_position = opticals_position * 0.95;
    }
}

#ifndef __EMSCRIPTEN__
void opticals_calibrate(bool black)
{
    struct robot_infos *infos = infos_get();
    for (int k = 0; k < OPTICAL_NB; k++) {
      if (black) {
        infos->opticals_black[k] = optical_get(k);
      } else {
        infos->opticals_white[k] = optical_get(k);
      }
    }
    infos_save();
    buzzer_beep(800, 100);
}

void opticals_en(int index)
{
    digitalWrite(PIN_OPTICAL_EN1, index == 1 ? HIGH : LOW);
    digitalWrite(PIN_OPTICAL_EN2, index == 2 ? HIGH : LOW);
}

void opticals_init()
{
    // Enables all the transistor to low state (LEDs disabled)
    digitalWrite(PIN_OPTICAL_EN1, LOW);
    digitalWrite(PIN_OPTICAL_EN2, LOW);
    pinMode(PIN_OPTICAL_EN1, OUTPUT);
    pinMode(PIN_OPTICAL_EN2, OUTPUT);
}

static int last = 0;

// XXX: Opticals should be enabled only by burst, and maybe in sync with mux.cpp?
void opticals_tick()
{
    int elapsed = millis() - last;

    if (should_compute) {
        should_compute = false;
        compute_optical_quantity_and_position();
    }

    if (elapsed >= 10) {
        if (optdbg != 0) {
            for (int k = 0; k < OPTICAL_NB; k++) {
                if (optdbg == 1) {
                    terminal_io()->print(optical_get_corrected(k));
                } else {
                    terminal_io()->print(optical_get(k));
                }
                terminal_io()->print(" ");
            }
            terminal_io()->println(opticals_position);
        }
        last = millis();
        opticals_state = 1;
    }
}

void opticals_cycle()
{
    if (opticals_state == 0) { // Idle
        return;
    } else {
        if (opticals_state == 1) {
            opticals_en(1); // Turn the first on
        } else if (opticals_state == 2) {
            opticals[0] = multiplexers.opticals[0];
            opticals[2] = multiplexers.opticals[2];
            opticals[4] = multiplexers.opticals[4];
            opticals[6] = multiplexers.opticals[6];
            opticals_en(2); // Turn the second on
        } else if (opticals_state == 3) {
            opticals[1] = multiplexers.opticals[1];
            opticals[3] = multiplexers.opticals[3];
            opticals[5] = multiplexers.opticals[5];
            opticals_en(0); // Turn all off
        }

        opticals_state++;

        if (opticals_state > 3) {
            opticals_state = 0;

            should_compute = true;
        }
    }
}

void show_opticals_raw_values(){
  terminal_io()->print(opticals[0]);
  terminal_io()->print(" ");
  terminal_io()->print(opticals[1]);
  terminal_io()->print(" ");
  terminal_io()->print(opticals[2]);
  terminal_io()->print(" ");
  terminal_io()->print(opticals[3]);
  terminal_io()->print(" ");
  terminal_io()->print(opticals[4]);
  terminal_io()->print(" ");
  terminal_io()->print(opticals[5]);
  terminal_io()->print(" ");
  terminal_io()->println(opticals[6]);
}

TERMINAL_COMMAND(oc, "1 : black, 0 : white")
{
  opticals_calibrate(atoi(argv[0]) ? true : false);
}
#endif

#ifdef __EMSCRIPTEN__
void set_optical_sensors(int val0, int val1, int val2, int val3, int val4, int val5, int val6)
{
  opticals[0] = val0;
  opticals[1] = val1;
  opticals[2] = val2;
  opticals[3] = val3;
  opticals[4] = val4;
  opticals[5] = val5;
  opticals[6] = val6;

  compute_optical_quantity_and_position();
}

EMSCRIPTEN_BINDINGS(opticals) {
    emscripten::function("set_optical_sensors", &set_optical_sensors);
}
#endif
