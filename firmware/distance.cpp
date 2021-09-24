// #define DEBUG
#include <stdlib.h>
#include "hardware.h"
#include "distance.h"
#include <function.h>

#ifdef HAS_TERMINAL
#include <terminal.h>
#else
#include "no_terminal.h"
#endif

#ifndef __EMSCRIPTEN__
#include <wirish/wirish.h>
#include "mux.h"
#else
#include <emscripten.h>
#include <emscripten/bind.h>
#include "js_utils.h"
#endif

static float distance;

#ifndef __EMSCRIPTEN__
static int last;
static bool distance_enabled = false;

// Used for filtering voltage from GP2
#define WINDOW_SIZE 5
static float accepted[WINDOW_SIZE] = {0};
static int accepted_nb = 1; // We suppose that we receive a first value equal to 0.
static float rejected[WINDOW_SIZE] = {0};
static int rejected_nb = 0;
static float current_average = 0;
static float raw_data = 0;
static float filtered_data = 0;

#ifdef DEBUG
TERMINAL_PARAMETER_BOOL(distdbg, "Debug the distance", false);
#endif

// This is used to extrapolate the values from the datasheet to convert the
// voltage measured to a distance in cm
Function volt_to_cm;

/**
 * It computes the average of the array.
 */
static float average( float* array, int size){
  float res = 0;
  for(int i = 0; i < size; i++){
    res += array[i];
  }
  return res/size;
}

/**
 * Filtering outliers.
 * Sometimes, the sampling of the ADC adds an error à 0.2 volt.
 * A value is considered to be an outlayer if the difference
 * with the current average is more than 0.1. If we have a given amount
 * of consecutive outlayers we consider that they are not outlayers.
 */
static float get_filtered_data(float raw_data){
  // The number of saved data should be less than WINDOW_SIZE
  if(accepted_nb + rejected_nb >= WINDOW_SIZE){
    accepted_nb--;
    for(int i = 0; i < accepted_nb; i++){
      accepted[i] = accepted[i+1];
    }
  }

  // If the number of consecutive outlayers is equal to WINDOW_SIZE,
  // they were not outlayers.
  if(rejected_nb == WINDOW_SIZE-1){ // or equivalently accepted_nb == 0.
    for(int i = 0; i < rejected_nb; i++){
      accepted[i] = rejected[i];
    }
    accepted_nb = rejected_nb;
    rejected_nb = 0;

    current_average = average(accepted, accepted_nb);
  }

  if(abs(raw_data - current_average) > 0.1){// raw_data is an outlayer
    rejected[rejected_nb] = raw_data;
    rejected_nb++;
  }
  else{// raw_data is not an outlayer
    accepted[accepted_nb] = raw_data;
    accepted_nb++;
    rejected_nb = 0;
  }

  // Compute average
  current_average = average(accepted, accepted_nb);
  return current_average;
}

void distance_init()
{
    // Transistor pins
    digitalWrite(PIN_DISTANCE_EN, LOW);
    pinMode(PIN_DISTANCE_EN, OUTPUT);

    // From the datasheet
    // http://www.sharp-world.com/products/device/lineup/data/pdf/datasheet/gp2y0a41sk_e.pdf
    volt_to_cm.addPoint(0.0, 40);
    volt_to_cm.addPoint(0.4, 32.5);
    volt_to_cm.addPoint(0.6, 22);
    volt_to_cm.addPoint(1, 13);
    volt_to_cm.addPoint(1.4, 9);
    volt_to_cm.addPoint(1.76, 7);
    volt_to_cm.addPoint(2.35, 5);
    volt_to_cm.addPoint(3.0, 3.5);
    volt_to_cm.addPoint(3.3, 2.0);

    distance_enable(true);

    last = millis();
}

void distance_enable(bool enable)
{
    distance_enabled = enable;
    digitalWrite(PIN_DISTANCE_EN, enable ? HIGH : LOW);
}


void distance_tick()
{
    if (distance_enabled) {
        if ((millis()-last) > 1)  {
            raw_data = multiplexers.distance*3.3/4095;
            filtered_data = get_filtered_data(raw_data);
            distance = DISTANCE_SENSOR_OFFSET + volt_to_cm.get(filtered_data);
            last = millis();

#ifdef DEBUG
            if(distdbg){
              terminal_io()->print(raw_data*1000);
              terminal_io()->print(" ");
              terminal_io()->print(filtered_data*1000);
              terminal_io()->print(" ");
              terminal_io()->println(distance);
            }
#endif
        }
    } else {
        distance = 100;
    }
}

#endif

#ifdef HAS_TERMINAL
void show_distance(){
  for (int k=0; k<WINDOW_SIZE; k++) {
    delay(1);
    distance_tick();
  }

  terminal_io()->println(distance);
}

TERMINAL_COMMAND(dist, "Monitor distances")
{
    distance_enable(true);
    while (!SerialUSB.available()) {
      show_distance();
    }
}
#endif

float get_distance()
{
    return distance;
}

#ifdef __EMSCRIPTEN__
void set_distance(float _distance)
{
    distance = _distance;
}
EMSCRIPTEN_BINDINGS(distance) {
    emscripten::function("set_distance", &set_distance);
}
#endif
