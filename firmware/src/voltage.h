#pragma once

// Initializes voltage measurement
void voltage_init();

// Update the voltage measurement
void voltage_tick();

// Checks if the voltage is ok
bool voltage_is_error();
bool voltage_can_move();

float voltage_value();