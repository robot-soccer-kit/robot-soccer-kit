#pragma once
#include <stdint.h>

void motors_init();

// Set target PWMs for motors
void motors_set_pwm(int index, int16_t pwm);
void motors_set_pwms(int16_t motor1, int16_t motor2, int16_t motor3);

// Set target speeds for motors (rad/s)
void motors_set_speed(int index, int speed);
void motors_set_speed(float s1, float s2, float s3);
void motors_disable();