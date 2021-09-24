#ifndef _HARDWARE_H
#define _HARDWARE_H

/**
* Holo hardware configuration
*/

// optical buttons enable
#define OPTICAL_BUTTON_ENABLE 0
#define OPTICAL_NB 7

// Wheel radius [mm]
#define MODEL_WHEEL_RADIUS    35

// Distance from robot center to wheel [mm]
#define MODEL_ROBOT_RADIUS    51.4

// Wheels gear reduction ratio
#define REDUCTION_RATIO        210

// Cycles per revolution [cycles/turn]
#define WHEELS_CPR   (7*4*REDUCTION_RATIO)

// PWM max value
#define PWM_MAX_VALUE 3000

// Front offset alpha [deg]
// Changing this will change the "front" of the robot used in the kinematics
#define FRONT_OFFSET_ALPHA  0

// Wheels orientations [deg]
#define WHEEL1_ALPHA    (FRONT_OFFSET_ALPHA + 60)
#define WHEEL2_ALPHA    (FRONT_OFFSET_ALPHA + 180)
#define WHEEL3_ALPHA    (FRONT_OFFSET_ALPHA - 60)

// Delta time of the servoing (ms)
#define SERVO_DT        10

// Delta time of the speed estimation (ms), should be a multiple of above
#define SPEED_DT        50

// Motors pins mapping
#define PIN_M1A 15  // 4 CH2
#define PIN_M1B 16  // 4 CH1
#define PIN_M2A 5   // 3 CH1
#define PIN_M2B 27  // 1 CH1
#define PIN_M3A 3   // 3 CH3
#define PIN_M3B 4   // 3 CH2

// (lower) voltage per sector to trigger the robot alarm [V]
#define VOLTAGE_LIMIT   3.5

// Voltage1 resistors [ohm]
#define VOLTAGE1_R1      20
#define VOLTAGE1_R2      10

// Voltage2 resistors [ohm]
#define VOLTAGE2_R1      10
#define VOLTAGE2_R2      10

// The board (blue) led pin
#define PIN_BOARD_LED       22

// The leds (rgb daisy chained) pin
#define LEDS_SPI            2

// Enable or disable more charge pin
#define PIN_MORE_CHARGE     29

// Buzzer pin
#define PIN_BUZZER          11

// Transistor to enable or disable features
// #define PIN_DISTANCE_EN     28
#define PIN_OPTICAL_EN1     14
#define PIN_OPTICAL_EN2     13
#define DISTANCE_SENSOR_OFFSET  4.0
#define PIN_DISTANCE_EN     17

// IMU I2C port
#define I2C_IMU             I2C2

// Bluetooth configuration pin
#define PIN_BTCONF          19
#define RC_BAUDRATE         115200

// Buttons value threshold
#define BTN_THRESHOLD       50

#endif
