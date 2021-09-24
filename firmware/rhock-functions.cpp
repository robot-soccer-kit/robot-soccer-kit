#include <math.h>
#include <stdio.h>
#include <rhock/stream.h>
#include <rhock/event.h>
#include "rhock-functions.h"
#include "rhock-functions_native_declare.h"
#ifndef __EMSCRIPTEN__
#include "main.h"
#include <wirish/wirish.h>
#else
#include <emscripten.h>
#include <emscripten/bind.h>
#include "js_utils.h"
#endif
#include "motion.h"
#include "distance.h"
#include "leds.h"
#include "odometry.h"
#include "buzzer.h"
#include "dc.h"
#include "imu.h"
// #include "opticals.h"
#include "rhock-stream.h"

bool controlSpeed = true;
struct rhock_context *controllingOdometry = NULL;
struct rhock_context *controllingBuzzer = NULL;

void motion_stop(struct rhock_context *context)
{
    motion_set_prog_enable(context, false);
}

void motion_init()
{
    motion_em();
}

void context_odometry_control(struct rhock_context* context,
    float dx, float dy, float turn,
    float speed, float turnSpeed)
{
    if (controlSpeed) {
        odometry_set_goal_to_position();
    }
    controlSpeed = false;
    
    controllingOdometry = context;
    motion_stop(context);
    odometry_control(dx, dy, turn, speed, turnSpeed);
}

void context_odometry_goto(struct rhock_context* context,
    float x, float y, float theta,
    float speed, float turnSpeed)
{
    if (controlSpeed) {
        odometry_set_goal_to_position();
    }
    controlSpeed = false;
    
    controllingOdometry = context;
    motion_stop(context);
    odometry_goto(x, y, theta, speed, turnSpeed);
}

/**
 * Called when all rhock processes are stopped
 */
void rhock_on_all_stopped()
{
    // Decustom the leds
    leds_decustom();

    // Stopping the motion
    motion_em();

    controlSpeed = true;
}

/**
 * called when rhock process starts
 */
void rhock_on_reset()
{
}

/**
 * Handling thread pause, stop and start
 */
void rhock_on_pause(struct rhock_context *context)
{
    motion_set_prog_enable((void*)context, false);
}

void rhock_on_stop(struct rhock_context *context)
{
    motion_set_prog_enable((void*)context, false);

    if (context == controllingBuzzer) {
        buzzer_stop();
        controllingBuzzer = NULL;
    }

    if (context == controllingOdometry) {
        odometry_stop();
        controllingOdometry = NULL;
    }
}

void rhock_on_start(struct rhock_context *context)
{
    motion_set_prog_enable((void*)context, true);
}

RHOCK_NATIVE(robot_led)
{
    int value = RHOCK_POPF();
    int led = RHOCK_POPF();
    led_set(led, value, true);
    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_leds)
{
    int32_t r = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t g = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t b = RHOCK_VALUE_TO_INT(RHOCK_POPI());

    if (r < 0) r = 0;
    if (r > 255) r = 255;
    if (g < 0) g = 0;
    if (g > 255) g = 255;
    if (b < 0) b = 0;
    if (b > 255) b = 255;

    int32_t color = (r<<16)|(g<<8)|b;
    led_set_all(color, true);
    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_led_set)
{
    int32_t idx = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t r = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t g = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t b = RHOCK_VALUE_TO_INT(RHOCK_POPI());

    if (r < 0) r = 0;
    if (r > 255) r = 255;
    if (g < 0) g = 0;
    if (g > 255) g = 255;
    if (b < 0) b = 0;
    if (b > 255) b = 255;

    led_color_set(idx,r,g,b);
    led_color_set(idx+3,r,g,b);
    return RHOCK_NATIVE_CONTINUE;
}

static void motion_control(float x_speed, float y_speed, float turn_speed,
        struct rhock_context *context)
{
    controlSpeed = true;
    motion_set_prog_order((void*)context, x_speed, y_speed, turn_speed);
}

RHOCK_NATIVE(robot_control)
{
    float turn_speed = RHOCK_POPF();
    float y_speed = RHOCK_POPF();
    float x_speed = RHOCK_POPF();
    motion_control(x_speed, y_speed, turn_speed, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_control_dir)
{
    float speed = RHOCK_POPF();
    float dir = RHOCK_POPF();
    float turn_speed = RHOCK_POPF();

    float x_speed = cos(dir*M_PI/180.0)*speed;
    float y_speed = sin(dir*M_PI/180.0)*speed;

    motion_control(x_speed, y_speed, turn_speed, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_stop)
{
    motion_em();

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_x_speed)
{
    float x_speed = RHOCK_POPF();
    motion_control(x_speed, 0, 0, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_y_speed)
{
    float y_speed = RHOCK_POPF();
    motion_control(0, y_speed, 0, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_turn_speed)
{
    float turn_speed = RHOCK_POPF();
    motion_control(0, 0, turn_speed, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(board_led)
{
#ifndef __EMSCRIPTEN__
    digitalWrite(BOARD_LED_PIN, !RHOCK_POPI());
#endif

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_turn)
{
    ON_ENTER() {
        float turnSpeed = RHOCK_POPF();
        float deg = RHOCK_POPF();
        context_odometry_control(context, 0, 0, deg, 50, turnSpeed);
    }
    
    if (odometry_reached()) {
        odometry_stop();
        return RHOCK_NATIVE_CONTINUE;
    } else {
        return RHOCK_NATIVE_WAIT;
    }
}

RHOCK_NATIVE(robot_move_x)
{
    ON_ENTER() {
        float speed = RHOCK_POPF();
        float dist = RHOCK_POPF();
        context_odometry_control(context, dist, 0, 0, speed, 50);
    }
    
    if (odometry_reached()) {
        odometry_stop();
        return RHOCK_NATIVE_CONTINUE;
    } else {
        return RHOCK_NATIVE_WAIT;
    }
}

RHOCK_NATIVE(robot_move_y)
{
    ON_ENTER() {
        float speed = RHOCK_POPF();
        float dist = RHOCK_POPF();
        context_odometry_control(context, 0, dist, 0, speed, 50);
    }
    
    if (odometry_reached()) {
        odometry_stop();
        return RHOCK_NATIVE_CONTINUE;
    } else {
        return RHOCK_NATIVE_WAIT;
    }
}

RHOCK_NATIVE(robot_move_toward)
{
    ON_ENTER() {
        float speed = RHOCK_POPF();
        float dir = -RHOCK_POPF();
        float dist = RHOCK_POPF();
        if (dist < 0 && speed > 0) {
            speed = -speed;
        }
        float dx = cos(dir*M_PI/180.0)*dist;
        float dy = sin(dir*M_PI/180.0)*dist;

        context_odometry_control(context, dx, dy, 0, speed, 50);
    }

    if (odometry_reached()) {
        odometry_stop();
        return RHOCK_NATIVE_CONTINUE;
    } else {
        return RHOCK_NATIVE_WAIT;
    }
}

RHOCK_NATIVE(robot_odometry_goto)
{
    ON_ENTER() {
        float speed = RHOCK_POPF();
        float theta = RHOCK_POPF();
        float y = RHOCK_POPF();
        float x = RHOCK_POPF();
        context_odometry_goto(context, x, y, theta, speed, 90);
    }
    
    if (odometry_reached()) {
        odometry_stop();
        return RHOCK_NATIVE_CONTINUE;
    } else {
        return RHOCK_NATIVE_WAIT;
    }
}

RHOCK_NATIVE(robot_odometry_reset)
{
    reset_odometry();

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_wheels_speed)
{
    float w3 = RHOCK_POPF()*M_PI/180.0;
    float w2 = RHOCK_POPF()*M_PI/180.0;
    float w1 = RHOCK_POPF()*M_PI/180.0;
    float dx, dy, turn;
    dc_fk(w1, w2, w3, &dx, &dy, &turn);

    motion_control(dx, dy, turn*180.0/M_PI, context);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_odometry_x)
{
    RHOCK_PUSHF(get_odometry_x());

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_odometry_y)
{
    RHOCK_PUSHF(get_odometry_y());

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_odometry_yaw)
{
    RHOCK_PUSHF(get_odometry_yaw()*180/M_PI);

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_dist)
{
    RHOCK_PUSHF(get_distance());

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_beep)
{
    ON_ENTER() {
        float duration = RHOCK_POPF();
        float freq = RHOCK_POPF();
        RHOCK_PUSHF(duration);

        buzzer_beep(freq, duration);
        controllingBuzzer = context;

        return RHOCK_NATIVE_WAIT;
    }
    ON_ELAPSED() {
        RHOCK_SMASH(1);
        buzzer_stop();
        return RHOCK_NATIVE_CONTINUE;
    }
}

RHOCK_NATIVE(robot_buzzer_freq)
{
    float freq = RHOCK_POPF();

    buzzer_beep(freq, -1);
    controllingBuzzer = context;

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_yaw)
{
    RHOCK_PUSHF(imu_yaw());

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_pitch)
{
#ifndef __EMSCRIPTEN__
    RHOCK_PUSHF(imu_pitch());
#else
    RHOCK_PUSHF(0.0);
#endif

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_roll)
{
#ifndef __EMSCRIPTEN__
    RHOCK_PUSHF(imu_roll());
#else
    RHOCK_PUSHF(0.0);
#endif

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_gyro_yaw)
{
#ifndef __EMSCRIPTEN__
    RHOCK_PUSHF(imu_gyro_yaw());
#else
    RHOCK_PUSHF(imu_yaw());
#endif

    return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_temperature)
{
#ifndef __EMSCRIPTEN__
    RHOCK_PUSHF(imu_temperature());
#else
    RHOCK_PUSHF(25);
#endif

return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_irlocator)
{
    int32_t heading = RHOCK_VALUE_TO_INT(RHOCK_POPI());
    int32_t is1200hz = RHOCK_VALUE_TO_INT(RHOCK_POPI());

#ifndef __EMSCRIPTEN__
    if (heading) {
        RHOCK_PUSHF(irlocator_heading(is1200hz));
    } else {
        RHOCK_PUSHF(irlocator_strength(is1200hz));
    }
#else
    RHOCK_PUSHF(0);
#endif

return RHOCK_NATIVE_CONTINUE;
}

RHOCK_NATIVE(robot_get_control)
{
    int32_t control = RHOCK_VALUE_TO_INT(RHOCK_POPI());

    if (control < RHOCK_CONTROLS) {
        RHOCK_PUSHF(rhock_controls[control]/100.0);
    } else {
        RHOCK_PUSHF(0);
    }

    return RHOCK_NATIVE_CONTINUE;
}

// RHOCK_NATIVE(robot_opticals_pos)
// {
//     RHOCK_PUSHF(opticals_get_position());
//     return RHOCK_NATIVE_CONTINUE;
// }

// RHOCK_NATIVE(robot_opticals_quantity)
// {
//     RHOCK_PUSHF(opticals_get_quantity()/10.0);
//     return RHOCK_NATIVE_CONTINUE;
// }

// RHOCK_NATIVE(robot_get_opticals_individual_quantity)
// {
//   int32_t optical_id = RHOCK_VALUE_TO_INT(RHOCK_POPI());
//   RHOCK_PUSHF(get_opticals_individual_quantity(6-optical_id)/10.23);
//   return RHOCK_NATIVE_CONTINUE;
// }

#ifdef __EMSCRIPTEN__
EMSCRIPTEN_BINDINGS(rhock_function) {
    emscripten::function("motion_init", &motion_init);
}
#endif

