#include "rhock-stream.h"
#include "buzzer.h"
#include "dc.h"
#include "hardware.h"
#include "leds.h"
#include "voltage.h"
#include "opticals.h"
#include "buzzer.h"
#include "distance.h"
#include "imu.h"
#include "main.h"
#include "math.h"
#include "motion.h"
#include "odometry.h"
#include "kicker.h"
#include <rhock/event.h>
#include <rhock/stream.h>
#include <stdio.h>

#define RHOCK_STREAM_METABOT 50
#define RHOCK_STREAM_HOLOBOT 80

short rhock_controls[16] = { 0 };

bool monitor_opticals_raw = false;
bool monitor_encoders_values = false;

#ifndef __EMSCRIPTEN__
#include <wirish/wirish.h>
#else
#include <emscripten.h>
#include <emscripten/bind.h>
#include "js_utils.h"
#endif
#define LED_PIN 22

char rhock_on_packet(uint8_t type)
{

    if (type == RHOCK_STREAM_METABOT) {
        if (rhock_stream_available() >= 1) {
            uint8_t command = rhock_stream_read();
            switch (command) {
            case 0: // Starting the robot
                // XXX: Does not make any sense in holo
                // motors_enable();
                return 1;
                break;
            case 1: // Stop
                // XXX: Does not make any sense in holo
                // motors_disable();
                return 1;
                break;
            case 2: // Rotate calibration
#ifndef __EMSCRIPTEN__
                imu_calib_rotate();
#endif
                return 1;
                break;
            case 3: // Set control
                if (rhock_stream_available() == 3) {
                    uint8_t control = rhock_stream_read();
                    if (control < RHOCK_CONTROLS) {
                        uint16_t value = rhock_stream_read_short();
                        rhock_controls[control] = (short)value;
                    }
                }
                return 1;
                break;
            }
        }
    }

    if (type == RHOCK_STREAM_HOLOBOT) {
        if (rhock_stream_available() >= 1) {
            uint8_t command = rhock_stream_read();
            switch (command) {
            case 0: { // Controlling board led
#ifndef __EMSCRIPTEN__
                uint8_t state = rhock_stream_read();
                digitalWrite(LED_PIN, state ? HIGH : LOW);
#endif
                return 1;
                break;
            }
            case 2: { // Motion control
#ifndef __EMSCRIPTEN__
                motion_set_api_order(
                    (int16_t)rhock_stream_read_short(), 
                    (int16_t)rhock_stream_read_short(),
                    (int16_t)rhock_stream_read_short()
                );
#endif

                return 1;
                break;
            }
            case 3: { // Beep
                short freq = rhock_stream_read_short();
                short duration = rhock_stream_read_short();
                buzzer_beep(freq, duration);
                return 1;
                break;
            }
            case 4: { // Play
                short melody_id = rhock_stream_read_short();
                buzzer_play(melody_id);
                return 1;
                break;
            }
            case 5: { // Calibrate opticals
#ifndef __EMSCRIPTEN__
                if (rhock_stream_available() == 1) {
                    uint8_t black = rhock_stream_read();
                    // opticals_calibrate(black);
                }
#endif
                return 1;
                break;
            }
            case 6: { // Rotate calibration
#ifndef __EMSCRIPTEN__
                imu_calib_rotate();
#endif
                return 1;
                break;
            }
            case 7: { // Set boards leds
                if (rhock_stream_available() == 3) {
                    uint8_t red = rhock_stream_read();
                    uint8_t green = rhock_stream_read();
                    uint8_t blue = rhock_stream_read();

                    led_all_color_set(red, green, blue);
                }

                return 1;
                break;
            }
            case 8: { // Enable breathing
                led_set_mode(LEDS_BREATH);

                return 1;
                break;
            }
            case 9: { // Monitor opticals raw
                if (rhock_stream_available() == 1) {
                    monitor_opticals_raw = rhock_stream_read();
                }

                return 1;
                break;
            }
            case 10: { // Monitor encoders
                if (rhock_stream_available() == 1) {
                    monitor_encoders_values = rhock_stream_read();
                }

                return 1;
                break;
            }
            case 11: { // Emergency stop
            #ifdef __EMSCRIPTEN__
                motion_em();
                rhock_program_killall();
            #else
                emergency_stop();
            #endif
                return 1;
                break;
            }
            case 12: { // Kick
            if (rhock_stream_available() == 1) {
              kicker_kick(rhock_stream_read());
            }
            }
            }
        }
    }
    return 0;
}
void rhock_on_monitor()
{
    rhock_stream_begin(RHOCK_STREAM_USER);

    // Robot version and timestamp
    rhock_stream_append(METABOT_VERSION);
    rhock_stream_append_int((uint32_t)millis());

    // Distances sensor (converted from [cm] (float) to [mm] (int))
    rhock_stream_append_short((uint16_t)((int16_t)(10 * get_distance())));

    // Opticals sensors, calibrated or raw (depending on config)
    for (int i = 0; i < OPTICAL_NB; i++) {
        if (monitor_opticals_raw) {
            rhock_stream_append((uint8_t)(0 >> 4));
        } else {
            rhock_stream_append((uint8_t)(0 >> 2));
        }
    }

    // Whell speeds in [deg/s] or encoders values
    for (int i = 0; i < 3; i++) {
        if (monitor_encoders_values) {
            rhock_stream_append_short((uint16_t)(encoder_position(i) & 0xffff));
        } else {
            rhock_stream_append_short((uint16_t)((int16_t)(10 * wheel_speed(i) / M_PI * 180.0)));
        }
    }

    // IMU values
#ifndef __EMSCRIPTEN__
    rhock_stream_append_short((uint16_t)((int16_t)(imu_yaw() * 10)));
    rhock_stream_append_short((uint16_t)((int16_t)(imu_gyro_yaw() * 10)));
    rhock_stream_append_short((uint16_t)((int16_t)(imu_pitch() * 10)));
    rhock_stream_append_short((uint16_t)((int16_t)(imu_roll() * 10)));
#else
    rhock_stream_append_short((uint16_t)((int16_t)(imu_yaw() * 10)));
    rhock_stream_append_short(0);
    rhock_stream_append_short(0);
    rhock_stream_append_short(0);
#endif

    // Odometry
    rhock_stream_append_short((int)get_odometry_x()); // X [mm]
    rhock_stream_append_short((int)get_odometry_y()); // Y [mm]
    rhock_stream_append_short((int)(get_odometry_yaw()*3600/(2*M_PI))); // Yaw [mm]

    // Batteries voltage, 0/0 if the robot is off
    // Unit is 40th of volts
#ifndef __EMSCRIPTEN__
    if (voltage_is_robot_on()) {
        rhock_stream_append(voltage_bat1()*40);
        rhock_stream_append(voltage_bat2()*40);
    } else {
        rhock_stream_append(0);
        rhock_stream_append(0);
    }
#else
    rhock_stream_append(0);
    rhock_stream_append(0);
#endif

    rhock_stream_end();
}

void api_disable()
{
    api_control = false;
    api_dx = 0;
    api_dy = 0;
    api_turn = 0;
}
