#ifndef _VOLTAGE_H
#define _VOLTAGE_H

/**
 * Is the current voltage an error?
 */
bool voltage_error();

/**
 * Initialize the voltage system
 */
void voltage_init();

/**
 * Ticks the voltage system
 */
void voltage_tick();

/**
 * Battery current voltage [V]
 *
 * @return the current voltage in volt
 */
bool voltage_is_robot_on();
float voltage_current();
float voltage_bat1();
float voltage_bat2();

/**
 * Set voltage value during debug.
 * battery = 0 means both batteries.
 */
void voltage_set(float voltage, int battery);
#endif
