#include <rhock/native.h>

// Leds
RHOCK_NATIVE_DECLARE(robot_led, 30);
RHOCK_NATIVE_DECLARE(robot_leds, 31);
RHOCK_NATIVE_DECLARE(robot_led_set, 32);

// Moves
RHOCK_NATIVE_DECLARE(robot_control, 40);
RHOCK_NATIVE_DECLARE(robot_control_dir, 41);

// Speed
RHOCK_NATIVE_DECLARE(robot_stop, 50);
RHOCK_NATIVE_DECLARE(robot_x_speed, 51);
RHOCK_NATIVE_DECLARE(robot_y_speed, 52);
RHOCK_NATIVE_DECLARE(robot_turn_speed, 53);

// Distances sensor
RHOCK_NATIVE_DECLARE(robot_dist, 54);

// Distances
RHOCK_NATIVE_DECLARE(robot_turn, 60);
RHOCK_NATIVE_DECLARE(robot_move_x, 61);
RHOCK_NATIVE_DECLARE(robot_move_y, 62);
RHOCK_NATIVE_DECLARE(robot_move_toward, 63);
RHOCK_NATIVE_DECLARE(robot_move_toward_and_turn, 64);
RHOCK_NATIVE_DECLARE(robot_odometry_goto, 42);
RHOCK_NATIVE_DECLARE(robot_odometry_reset, 43);
RHOCK_NATIVE_DECLARE(robot_wheels_speed, 44);
RHOCK_NATIVE_DECLARE(robot_odometry_x, 45);
RHOCK_NATIVE_DECLARE(robot_odometry_y, 46);
RHOCK_NATIVE_DECLARE(robot_odometry_yaw, 47);

// Buzzer
RHOCK_NATIVE_DECLARE(robot_beep, 55);
RHOCK_NATIVE_DECLARE(robot_buzzer_freq, 48);

// IMU
RHOCK_NATIVE_DECLARE(robot_yaw, 33);
RHOCK_NATIVE_DECLARE(robot_pitch, 34);
RHOCK_NATIVE_DECLARE(robot_roll, 35);
RHOCK_NATIVE_DECLARE(robot_gyro_yaw, 36);
RHOCK_NATIVE_DECLARE(robot_temperature, 37);

RHOCK_NATIVE_DECLARE(robot_irlocator, 38);

// // Opticals sensors
// RHOCK_NATIVE_DECLARE(robot_opticals_pos, 56);
// RHOCK_NATIVE_DECLARE(robot_opticals_quantity, 57);
// RHOCK_NATIVE_DECLARE(robot_get_control, 58);
// RHOCK_NATIVE_DECLARE(robot_get_opticals_individual_quantity, 59);
