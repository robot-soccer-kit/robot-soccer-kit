#pragma once
#include <stdint.h>

void motors_init();

// Set target PWMs for motors
void motors_set_pwm(int index, int16_t pwm);
void motors_set_pwms(int16_t motor1, int16_t motor2, int16_t motor3);

// Set target speeds for motors (rad/s)
void motors_set_speed(int index, float speed);
void motors_set_speeds(float w1, float w2, float w3);

// Set target chassis speed (m/s, m/s, rad/s)
void motors_set_ik(float dx, float dy, float dt);

// Get the current encoder value for a given motor
int64_t motors_get_encoder(int index);

void motors_disable();