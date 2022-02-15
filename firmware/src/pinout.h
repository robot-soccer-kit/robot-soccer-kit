#pragma once

#define KICK_PIN 33

// Wheels gear reduction ratio
#define REDUCTION_RATIO        210

// Cycles per revolution [cycles/turn]
#define WHEELS_CPR   (7*4*REDUCTION_RATIO)

#define MOTOR1_PWM1    13
#define MOTOR1_PWM2    14
#define MOTOR1_ENC1    4
#define MOTOR1_ENC2    16

#define MOTOR2_PWM1    17
#define MOTOR2_PWM2    18
#define MOTOR2_ENC1    19
#define MOTOR2_ENC2    21

#define MOTOR3_PWM1    22
#define MOTOR3_PWM2    23
#define MOTOR3_ENC1    25
#define MOTOR3_ENC2    26