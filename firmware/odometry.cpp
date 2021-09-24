#ifdef HAS_TERMINAL
#include <terminal.h>
#else
#include "no_terminal.h"
#endif

#include "imu.h"
#include "motion.h"
#ifndef __EMSCRIPTEN__
#include "wirish.h"
#else
#include <emscripten.h>
#include <emscripten/bind.h>
#include "js_utils.h"
#endif

#include "dc.h"
#include "hardware.h"
#include "odometry.h"
#include <math.h>

// Encoder last positions
int encoders[3];

// Convenient structures
struct position {
    float x; //[m]
    float y; //[m]
    float theta; //[rad]
};

struct vector {
    float x; //[m]
    float y; //[m]
};

// Robots position in a frame called `world`
// initialized at the beginning of the program.
struct position robot = { 0, 0, 0 };
struct position goal = { 0, 0, 0 };

// Goto order
bool goto_enable = false;

void reset_odometry()
{
    goto_enable = false;
    imu_gyro_yaw_reset();

    robot.x = 0;
    robot.y = 0;
    robot.theta = 0;

    goal.x = 0;
    goal.y = 0;
    goal.theta = 0;
}

static void goal_frame_to_world_frame(const struct vector& src, struct vector* dst)
{
    dst->x = cos(goal.theta) * src.x - sin(goal.theta) * src.y;
    dst->y = sin(goal.theta) * src.x + cos(goal.theta) * src.y;
}

static void self_frame_to_world_frame(const struct vector& src, struct vector* dst)
{
    dst->x = cos(robot.theta) * src.x - sin(robot.theta) * src.y;
    dst->y = sin(robot.theta) * src.x + cos(robot.theta) * src.y;
}

static void world_frame_to_self_frame(const struct vector& src, struct vector* dst)
{
    dst->x = cos(robot.theta) * src.x + sin(robot.theta) * src.y;
    dst->y = -sin(robot.theta) * src.x + cos(robot.theta) * src.y;
}

static void update_position(const struct vector& displacement_self, float theta)
{
    struct vector displacement_world = { 0, 0 };
    self_frame_to_world_frame(displacement_self, &displacement_world);

    robot.x += displacement_world.x;
    robot.y += displacement_world.y;
    robot.theta = imu_gyro_yaw() * M_PI / 180.0;
}

TERMINAL_PARAMETER_FLOAT(goMaxSpeed, "Goto max speed", 50);
TERMINAL_PARAMETER_FLOAT(goMaxTurn, "Goto turn max speed", 50);

#ifdef __EMSCRIPTEN__
TERMINAL_PARAMETER_FLOAT(goKp, "Goto Kp", 10);
TERMINAL_PARAMETER_FLOAT(goTurnKp, "Goto turn Kp", 100);
#else
TERMINAL_PARAMETER_FLOAT(goKp, "Goto Kp", 1.5);
TERMINAL_PARAMETER_FLOAT(goTurnKp, "Goto turn Kp", 75);
#endif

int last_tick = 0;

TERMINAL_PARAMETER_INT(odomP, "", 10); // Update period

static void _limit(float* x, float max)
{
    if (*x > max)
        *x = max;
    if (*x < -max)
        *x = -max;
}

void odometry_tick()
{
#ifdef __EMSCRIPTEN__
    if (true) {
#else
    if ((millis() - last_tick) > (unsigned int)odomP) {
        last_tick = millis();
#endif

        // Update robot position
#ifdef __EMSCRIPTEN__
        // XXX: TODO
#else
        int encoder_0 = encoder_position(0);
        int encoder_1 = encoder_position(1);
        int encoder_2 = encoder_position(2);

        float wheel_delta_0 = delta_enc_to_delta_rad(encoder_0 - encoders[0]);
        float wheel_delta_1 = delta_enc_to_delta_rad(encoder_1 - encoders[1]);
        float wheel_delta_2 = delta_enc_to_delta_rad(encoder_2 - encoders[2]);

        encoders[0] = encoder_0;
        encoders[1] = encoder_1;
        encoders[2] = encoder_2;

        float vx, vy, vtheta;
        dc_fk(wheel_delta_0, wheel_delta_1, wheel_delta_2, &vx, &vy, &vtheta);

        struct vector displacement = { vx, vy };
        update_position(displacement, vtheta);
#endif

        if (goto_enable) {
            struct vector pos;
            struct vector target = { goal.x - robot.x, goal.y - robot.y };
            world_frame_to_self_frame(target, &pos);
            float x_err = (pos.x);
            float y_err = (pos.y);
            float t_err = (goal.theta - robot.theta);

            while (t_err < -M_PI)
                t_err += 2 * M_PI;
            while (t_err > M_PI)
                t_err -= 2 * M_PI;

            x_err *= goKp;
            y_err *= goKp;
            float err_norm = sqrt(x_err*x_err + y_err*y_err);
            if (err_norm > goMaxSpeed) {
                x_err = x_err * goMaxSpeed/err_norm;
                y_err = y_err * goMaxSpeed/err_norm;
            }

            float dx = x_err * goKp;
            float dy = y_err * goKp;
            float dt = t_err * goTurnKp;
            _limit(&dx, goMaxSpeed);
            _limit(&dy, goMaxSpeed);
            _limit(&dt, goMaxTurn);

            motion_set_joy_order(dx, dy, dt);
        }
    }
}

float get_odometry_x()
{
    return robot.x;
}

float get_odometry_y()
{
    return robot.y;
}

float get_odometry_yaw()
{
    return robot.theta;
}

void odometry_control(float dx, float dy, float turn,
    float speed, float turnSpeed)
{
    struct vector worldDisplacement;
    struct vector displacement = { dx, dy };
    goal_frame_to_world_frame(displacement, &worldDisplacement);
    goal.x += worldDisplacement.x;
    goal.y += worldDisplacement.y;
    goal.theta += turn*M_PI/180.0;
    while (goal.theta < -M_PI) {
        goal.theta += 2*M_PI;
    }
    while (goal.theta > M_PI) {
        goal.theta -= 2*M_PI;
    }
    goMaxSpeed = speed;
    goMaxTurn = turnSpeed;
    goto_enable = true;

    // terminal_io()->println("Odometry new goal:");
    // terminal_io()->println(goal.x);
    // terminal_io()->println(goal.y);
    // terminal_io()->println(goal.theta*1000);
}

void odometry_goto(float x, float y, float theta, float speed, float turnSpeed)
{
    goal.x = x;
    goal.y = y;
    goal.theta = theta*M_PI/180.0;
    while (goal.theta < -M_PI) {
        goal.theta += 2*M_PI;
    }
    while (goal.theta > M_PI) {
        goal.theta -= 2*M_PI;
    }
    goMaxSpeed = speed;
    goMaxTurn = turnSpeed;
    goto_enable = true;
}

void odometry_set_goal_to_position()
{
    goal.x = robot.x;
    goal.y = robot.y;
    goal.theta = robot.theta;
}

void odometry_stop()
{
    motion_set_joy_order(0, 0, 0);
    goto_enable = false;
}

bool odometry_reached()
{
    struct vector err = { goal.x - robot.x, goal.y - robot.y };
    float x_err = (err.x);
    float y_err = (err.y);
    float t_err = (goal.theta - robot.theta);

    while (t_err < -M_PI)
        t_err += 2 * M_PI;
    while (t_err > M_PI)
        t_err -= 2 * M_PI;

#ifdef __EMSCRIPTEN__
    return (fabs(x_err) < 1 && fabs(y_err) < 1 && fabs(t_err) < 0.01);
#else
    return (fabs(x_err) < 5 && fabs(y_err) < 5 && fabs(t_err) < 0.12);
#endif
}

#ifdef HAS_TERMINAL
TERMINAL_COMMAND(odom, "Shows the values x y and theta computed with odometry.")
{
    //  while (!SerialUSB.available()) {
    terminal_io()->print("x: ");
    terminal_io()->print(get_odometry_x());
    terminal_io()->print(", y: ");
    terminal_io()->print(get_odometry_y());
    terminal_io()->print(", theta: ");
    terminal_io()->print(get_odometry_yaw());

    if (odometry_reached()) {
        terminal_io()->print(", reached goal");
    }

    terminal_io()->println();
    //  }
}

TERMINAL_COMMAND(odomres, "Resets the odometry.")
{
    reset_odometry();
}

TERMINAL_COMMAND(go, "GoTo servoing")
{
    if (argc == 3) {
        goal.x = terminal_atof(argv[0]);
        goal.y = terminal_atof(argv[1]);
        goal.theta = terminal_atof(argv[2]);
        goto_enable = true;
    } else {
        // If no argument, disable the goto servoing
        motion_set_joy_order(0, 0, 0);
        goto_enable = false;
    }
}
#endif

void odometry_set_pos(float x, float y, float theta)
{
    robot.x = x;
    robot.y = y;
    robot.theta = theta;
}

#ifdef __EMSCRIPTEN__
EMSCRIPTEN_BINDINGS(odometry)
{
    emscripten::function("reset_odometry", &reset_odometry);
    emscripten::function("odometry_tick", &odometry_tick);
    emscripten::function("odometry_set_pos", &odometry_set_pos);
}
#endif
