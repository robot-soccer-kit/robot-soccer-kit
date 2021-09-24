#ifndef _IMU_H
#define _IMU_H

extern float magn_x, magn_y, magn_z;
extern float gyro_x, gyro_y, gyro_z;
extern float acc_x, acc_y, acc_z;

/**
 * Returns the IMU yaw pitch and roll
 */
float imu_yaw();
float imu_gyro_yaw();
float imu_pitch();
float imu_roll();
float imu_temperature();

/**
 *  IR Locator if any
 */
float irlocator_heading(bool is1200hz);
float irlocator_strength(bool is1200hz);

/**
 * Allow to set the IMU values.
 * It is used by the simulator.
 */
void set_imu_yaw(float _yaw);

/**
 *  Returns the yaw speed given by the gyrometer
 */
float imu_yaw_speed();

/**
 * Initializes and tick the gyrometer
 */
void imu_init();
void imu_tick();

/**
 * Controls the calibration (gyrometer + magnetometer)
 */
void imu_calib_start();
void imu_calib_rotate();
void imu_calib_stop();

void imu_normalize_angle(float *deg);

float get_acc_norm();

void imu_gyro_yaw_reset();
#endif
