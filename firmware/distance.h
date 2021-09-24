#ifndef __DISTANCE_H
#define __DISTANCE_H

#include "hardware.h"

/**
 * Initializes the distance measurement system
 */
void distance_init();

/**
 * Enable or disable the distance sensors
 *
 * @param enable enable/disable
 */
void distance_enable(bool enable);

/**
 * Tick the distance measurement system
 */
void distance_tick();

/**
 * Getting the distance. With GP2Y0A41SK, this should be in the range
 * of 4-30 [cm].
 * 
 * DISTANCE_SENSOR_OFFSET is added to get the distance to the center of the robot.
 *
 */
float get_distance();

/**
 * Computes and print the current distance.
 */
void show_distance();
#endif
