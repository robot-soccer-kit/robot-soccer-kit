#ifndef __DC_H
#define __DC_H

#include <stdint.h>

/**
 * This flag is raised at 100 hz
 */
extern bool dcFlag;

void dc_init();

/**
 * Send raw PWM commands for motor
 *
 * @param m1 motor 1 command [pwm]
 * @param m2 motor 2 command [pwm]
 * @param m3 motor 3 command [pwm]
 */
void dc_command(int m1, int m2, int m3);

/**
 * Set the speed of the wheels
 *
 * @param w1 speed of wheel 1 [rad/s]
 * @param w2 speed of wheel 2 [rad/s]
 * @param w3 speed of wheel 3 [rad/s]
 */
void dc_set_speed_target(float w1, float w2, float w3);

/**
 * Apply the inverse kinematics for wheels orders
 *
 * @param dx Desired frontal speed [mm/s]
 * @param dy Desired lateral speed [mm/s]
 * @param dt Desired rotation speed [deg/s]
 */
void dc_ik(float dx, float dy, float dt);

/**
 * Forward kinematics
 */
void dc_fk(float w1, float w2, float w3, float *dx, float *dy, float *dt);

/**
 * Tick to update the servoing when necessary
 */
void dc_tick();

/**
 * Wheel speed [rad/s]
 *
 * @param  wheel_id the id of the wheel (0 to 2)
 * @return          the wheel speed [rad/s]
 */
float wheel_speed(uint8_t wheel_id);
int encoder_position(uint8_t wheel_id);
float get_wheel_speed_target(uint8_t wheel_id);
float delta_enc_to_delta_rad(int delta);

/**
 * Resets the encoder values and fails to 0.
 */
void reset_encoder();

volatile int* get_encoder_value();

volatile int* get_encoder_fails();
#endif
