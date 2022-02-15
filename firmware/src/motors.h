#pragma once
#include <stdint.h>

void motors_init();
void motors_set_pwm(int index, int16_t pwm);
void motors_set_pwms(int16_t motor1, int16_t motor2, int16_t motor3);
