// #define DEBUG
#include <stdlib.h>
#include <stdio.h>
#include "dc.h"
#include "function.h"
#include "hardware.h"
#include <math.h>
#include "motion.h"

#ifdef HAS_TERMINAL
#include <terminal.h>
#endif

#include "infos.h"
#include "mux.h"
#include <wirish.h>

// Speed targets, in firmware unit [step/speed_dt ms]
static float speed_target[3] = { 0 };

// one controls the variation of speed target
static float smooth_speed_target[3] = { 0 };

// Dividers
static int divider = 0;
static int servo_divider = 0;

// Flags for dc and servoing
bool dcFlag = false;
bool servoFlag = false;

// Values for encoders
static volatile int encoder_value[3] = { 0 };
static volatile int encoder_phase[3] = { 0 };
static volatile int encoder_fails[3] = { 0 };
static volatile int encoder_dir[3] = { 0 };
static volatile int encoder_speed[3] = { 0 };

// Size of the ring speed estimation ring buffer
#define SPEED_RB (((SPEED_DT) / SERVO_DT) + 1)

// Servo divider overflow
#define SERVO_OVF (24 * SERVO_DT)

// Encoder ticks
static int encoder_rb[3][SPEED_RB] = { 0 };

// Encoders position
static int encoder_pos = 0;

struct dc_motor {
    int a, b;
    float x, y;
};

// Motors and kinematics
// XXX: Move the parameters of this to hardware.h?
#define DEG2RAD (M_PI / 180.0)
#define RAD2DEG (180.0 / M_PI)

// HACK : the product needs to be stored in a float
// Needed to compile with emscripten
// Else, the product is seen as a float
// which creates an error in sin(...)
float wheel1_rad = WHEEL1_ALPHA* DEG2RAD;
float wheel2_rad = WHEEL2_ALPHA* DEG2RAD;
float wheel3_rad = WHEEL3_ALPHA* DEG2RAD;

static struct dc_motor motors[3] = {
    { PIN_M1A, PIN_M1B, (float)-sin(wheel1_rad), (float)cos(wheel1_rad) },
    { PIN_M2A, PIN_M2B, (float)-sin(wheel2_rad), (float)cos(wheel2_rad) },
    { PIN_M3A, PIN_M3B, (float)-sin(wheel3_rad), (float)cos(wheel3_rad) },
};

static void encoder_update(int k, int phase)
{
    if (encoder_phase[k] != phase) {
        // Compute the phase diff, could be -1, 1 or 2
        int diff = phase - encoder_phase[k];

        if (diff == -3)
            diff = 1;
        else if (diff == 3)
            diff = -1;
        else if (diff == -2)
            diff = 2;

        if (diff == 1) {
            encoder_dir[k] = 2;
            encoder_value[k]++;
        } else if (diff == -1) {
            encoder_dir[k] = -2;
            encoder_value[k]--;
        } else if (diff == 2) {
            // We missed a step
            encoder_value[k] += encoder_dir[k];
            encoder_fails[k] += 1;
        }

        // Store the phase
        encoder_phase[k] = phase;
    }
}

//                           0b00 0b01 0b10 0b11
const int phasesToState[] = { 0, 1, 3, 2 };

static void encoders_update()
{
    // Computing numerical phases
    int phases[3] = {
        (multiplexers.p1a & 1) | ((multiplexers.p1b & 1) << 1),
        (multiplexers.p2a & 1) | ((multiplexers.p2b & 1) << 1),
        (multiplexers.p3a & 1) | ((multiplexers.p3b & 1) << 1),
    };

    // Updating state
    for (int k = 0; k < 3; k++) {
        int phase = phases[k];
        encoder_update(k, phasesToState[phase]);
    }
}

void servo_update()
{
    int old_pos = encoder_pos;

    // Updating encoder pos
    encoder_pos++;
    if (encoder_pos >= SPEED_RB) {
        encoder_pos = 0;
    }

    // Updating speed estimations
    for (int k = 0; k < 3; k++) {
        encoder_rb[k][old_pos] = encoder_value[k];
        encoder_speed[k] = encoder_rb[k][old_pos] - encoder_rb[k][encoder_pos];
    }
}

// This interrupt is called at 24Khz
static void _dc_ovf()
{
    // Raising DC flag
    divider++;

    // Dc flag is raised at 100 hz (24khz/240)
    if (divider >= 240) {
        divider = 0;
        dcFlag = true;
    }

    // Updating encoders
    if (mux_tick()) {
        encoders_update();
    }

    // Updating servoing
    servo_divider++;

    if (servo_divider >= SERVO_OVF) {
        servo_divider = 0;
        servo_update();
        servoFlag = true;
    }
}

static void _init_timer(int number)
{
    HardwareTimer timer(number);

    // Configuring timer
    timer.pause();
    timer.setPrescaleFactor(1);
    timer.setOverflow(PWM_MAX_VALUE); // 24Khz

    if (number == 4) {
        timer.setChannel4Mode(TIMER_OUTPUT_COMPARE);
        timer.setCompare(TIMER_CH4, 1);
        timer.attachCompare4Interrupt(_dc_ovf);
    }

    timer.refresh();
    timer.resume();
}

Function compensation;

void dc_init()
{
    for (int k = 0; k < 3; k++) {
        pwmWrite(motors[k].a, 0);
        pwmWrite(motors[k].b, 0);
        pinMode(motors[k].a, PWM);
        pinMode(motors[k].b, PWM);
    }

    // XXX Init timers
    _init_timer(1);
    _init_timer(3);
    _init_timer(4);
}

void dc_command(int m1, int m2, int m3)
{
    pwmWrite(PIN_M1A, m1 > 0 ? m1 : 0);
    pwmWrite(PIN_M1B, m1 < 0 ? -m1 : 0);

    pwmWrite(PIN_M2A, m2 > 0 ? m2 : 0);
    pwmWrite(PIN_M2B, m2 < 0 ? -m2 : 0);

    pwmWrite(PIN_M3A, m3 > 0 ? m3 : 0);
    pwmWrite(PIN_M3B, m3 < 0 ? -m3 : 0);
}

// Converts [rad/s] to firmware unit [step / speed_dt ms]
static int _convert(float w)
{
    return w * (SPEED_DT / 1000.0) * WHEELS_CPR / (2 * M_PI);
}

// Converts firmware unit [step / speed_dt ms] to [rad/s]
static float _inverse_convert(int enc_speed)
{
    return ((float)enc_speed) / (SPEED_DT / 1000.0) / WHEELS_CPR * (2 * M_PI);
}

float delta_enc_to_delta_rad(int delta)
{
    return (delta*2*M_PI)/WHEELS_CPR;
}

float wheel_speed(uint8_t wheel_id)
{
    if (wheel_id >= 3)
        return 0.0;

    return _inverse_convert(encoder_speed[wheel_id]);
}

int encoder_position(uint8_t wheel_id)
{
    if (wheel_id >= 3)
        return 0;

    return encoder_value[wheel_id];
}


void dc_fk(float w1, float w2, float w3, float *dx, float *dy, float *dt)
{
    *dx = MODEL_WHEEL_RADIUS*(w1*(motors[1].y - motors[2].y) - w2*(motors[0].y - motors[2].y) + w3*(motors[0].y - motors[1].y))/(motors[0].x*motors[1].y - motors[0].x*motors[2].y - motors[0].y*motors[1].x + motors[0].y*motors[2].x + motors[1].x*motors[2].y - motors[1].y*motors[2].x);
    *dy = -MODEL_WHEEL_RADIUS*(w1*(motors[1].x - motors[2].x) - w2*(motors[0].x - motors[2].x) + w3*(motors[0].x - motors[1].x))/(motors[0].x*motors[1].y - motors[0].x*motors[2].y - motors[0].y*motors[1].x + motors[0].y*motors[2].x + motors[1].x*motors[2].y - motors[1].y*motors[2].x);
    *dt = MODEL_WHEEL_RADIUS*(w1*(motors[1].x*motors[2].y - motors[1].y*motors[2].x) - w2*(motors[0].x*motors[2].y - motors[0].y*motors[2].x) + w3*(motors[0].x*motors[1].y - motors[0].y*motors[1].x))/(MODEL_ROBOT_RADIUS*(motors[0].x*motors[1].y - motors[0].x*motors[2].y - motors[0].y*motors[1].x + motors[0].y*motors[2].x + motors[1].x*motors[2].y - motors[1].y*motors[2].x));
}

float get_wheel_speed_target(uint8_t wheel_id)
{
    if (wheel_id < 0 && wheel_id >= 3)
        return 0.0;
    return _inverse_convert(speed_target[wheel_id]);
}

TERMINAL_COMMAND(dcr, "DC test")
{
    if (argc == 3) {
        dc_command(atoi(argv[0]), atoi(argv[1]), atoi(argv[2]));
    }
}

void dc_ik(float dx, float dy, float dt)
{
    // Converting dt from [deg/s] to [rad/s]
    dt *= DEG2RAD;

    float w1 = (motors[0].x * dx + motors[0].y * dy
                   + MODEL_ROBOT_RADIUS * dt)
        / (MODEL_WHEEL_RADIUS);
    float w2 = (motors[1].x * dx + motors[1].y * dy
                   + MODEL_ROBOT_RADIUS * dt)
        / (MODEL_WHEEL_RADIUS);
    float w3 = (motors[2].x * dx + motors[2].y * dy
                   + MODEL_ROBOT_RADIUS * dt)
        / (MODEL_WHEEL_RADIUS);

    dc_set_speed_target(w1, w2, w3);
}

TERMINAL_COMMAND(fk, "Test fk")
{
    float dx, dy, dt;

    if (argc >= 3) {
        dc_fk(terminal_atof(argv[0]), terminal_atof(argv[1]), terminal_atof(argv[2]), &dx, &dy, &dt);
    } else {
        dc_fk(wheel_speed(0), wheel_speed(1), wheel_speed(2), &dx, &dy, &dt);
    }

    terminal_io()->println(dx);
    terminal_io()->println(dy);
    terminal_io()->println(dt);
}

TERMINAL_COMMAND(enc, "Read encoders")
{
    for (int k = 0; k < 3; k++) {
        terminal_io()->print(encoder_value[k]);
        terminal_io()->print(" ");
    }
    terminal_io()->println();
}

TERMINAL_COMMAND(er, "Encoders reset")
{
  reset_encoder();
}

void reset_encoder(){
  for (int k = 0; k < 3; k++) {
    encoder_value[k] = 0;
    encoder_fails[k] = 0;
  }
}

TERMINAL_COMMAND(es, "Encoders speed")
{
    while (!SerialUSB.available()) {
        for (int k = 0; k < 3; k++) {
            terminal_io()->print(encoder_speed[k]);
            terminal_io()->print(" ");
        }
        terminal_io()->println();
        dc_tick();
        delay(5);
    }
}

// Values for servoing
TERMINAL_PARAMETER_FLOAT(kp, "PID P", 15);
TERMINAL_PARAMETER_FLOAT(ki, "PID I", 0.5);
TERMINAL_PARAMETER_FLOAT(kd, "PID D", 0);
TERMINAL_PARAMETER_FLOAT(st_var_max, "max variation of speed_tgt", 10);
TERMINAL_PARAMETER_FLOAT(serv_A, "pwm linear model A (%/tic)", 0.11);
TERMINAL_PARAMETER_FLOAT(serv_B, "pwm linear model B (%)", 42);
TERMINAL_PARAMETER_FLOAT(serv_max_corr, "max pid (%)", 25);
TERMINAL_PARAMETER_FLOAT(serv_freq, "the servoing period (Hz)", -1);

// Period
static int serv_period = -1;
static int serv_last_tick = -1;

// Output values of servoing (PWMs)
static int m[3];

// Accumulators
static float acc[3] = { 0 };

// Last error (for D)
int lastErr[3] = { 0 };

static void _limit(int* i)
{
    if (*i < -PWM_MAX_VALUE)
        *i = -PWM_MAX_VALUE;
    if (*i > PWM_MAX_VALUE)
        *i = PWM_MAX_VALUE;
}

static void _flimit(float* i)
{
    if (*i < -PWM_MAX_VALUE)
        *i = -PWM_MAX_VALUE;
    if (*i > PWM_MAX_VALUE)
        *i = PWM_MAX_VALUE;
}

// Order for wheels [rad/s]
void dc_set_speed_target(float w1, float w2, float w3)
{
    speed_target[0] = _convert(w1);
    if (speed_target[0] == 0)
        acc[0] = 0;
    speed_target[1] = _convert(w2);
    if (speed_target[1] == 0)
        acc[1] = 0;
    speed_target[2] = _convert(w3);
    if (speed_target[2] == 0)
        acc[2] = 0;
}

TERMINAL_PARAMETER_BOOL(enable_serv, "", true);

void dc_tick()
{
    if (!enable_serv) {
        return;
    }

    if (servoFlag) {
        servoFlag = 0;

        for (int k = 0; k < 3; k++) {
            if (smooth_speed_target[k] + st_var_max < speed_target[k])
                smooth_speed_target[k] += st_var_max;
            else if (smooth_speed_target[k] - st_var_max > speed_target[k])
                smooth_speed_target[k] -= st_var_max;
            else
                smooth_speed_target[k] = speed_target[k];
        }

        // Measuring the exact servoing frequency
        int current_t = millis();
        if (serv_last_tick > 0) {
            serv_period = current_t - serv_last_tick;
            serv_freq = 1.0 / (((float)serv_period) / 1000.0);
        }
        serv_last_tick = current_t;

        // Updating the PWMs servoing
        for (int k = 0; k < 3; k++) {
            int err = (smooth_speed_target[k] - encoder_speed[k]);

            int st_sign = 0;
            if (smooth_speed_target[k] > 0)
                st_sign = 1;
            if (smooth_speed_target[k] < 0)
                st_sign = -1;

            // A priori value
            float a_priori_pwm = PWM_MAX_VALUE * (serv_A * smooth_speed_target[k] + st_sign * serv_B) / 100.0;

            // Applying PID values
            float corr = kp * err + acc[k] + kd * (err - lastErr[k]);

            // limitation of the correction
            if (corr < -serv_max_corr * PWM_MAX_VALUE)
                corr = -serv_max_corr * PWM_MAX_VALUE;
            if (corr > serv_max_corr * PWM_MAX_VALUE)
                corr = serv_max_corr * PWM_MAX_VALUE;

            m[k] = (int)(a_priori_pwm + corr);
            acc[k] += ki * err;

            // We disallow a PWM in the opposite direction as target speed
            if (smooth_speed_target[k] == 0 || (smooth_speed_target[k] > 0 && m[k] < 0)
                || (smooth_speed_target[k] < 0 && m[k] > 0)) {
                m[k] = 0;
            }

            // Limiting the maximum values for accumulation and pwm
            _limit(&m[k]);
            _flimit(&acc[k]);

            lastErr[k] = err;
        }

        dc_command(m[0], m[1], m[2]);
    }
}

// XXX: Remove?
// TERMINAL_COMMAND(st, "Speed target")
// {
//     if (argc == 3) {
//         speed_target[0] = atoi(argv[0]);
//         speed_target[1] = atoi(argv[1]);
//         speed_target[2] = atoi(argv[2]);
//     }
// }
//
TERMINAL_COMMAND(speeds, "Test speeds")
{
    if (argc == 3) {
        speed_target[0] = atoi(argv[0]);
        speed_target[1] = atoi(argv[1]);
        speed_target[2] = atoi(argv[2]);
        while (!SerialUSB.available()) {
            dc_tick();
            for (int k = 0; k < 3; k++) {
                terminal_io()->print(wheel_speed(k)*RAD2DEG);
                terminal_io()->print(" ");
            }
            terminal_io()->println();
        }
        speed_target[0] = 0;
        speed_target[1] = 0;
        speed_target[2] = 0;
    }
}

void dc_command_nth(int n, int pwm)
{
    if (n == 0)
        dc_command(pwm, 0, 0);
    if (n == 1)
        dc_command(0, pwm, 0);
    if (n == 2)
        dc_command(0, 0, pwm);
}

// TERMINAL_COMMAND(speedBench, "Maximum speed benchmark")
// {
//     int min = -1;
//     for (int k = 0; k < 3; k++) {
//         terminal_io()->print("Estimating for motor ");
//         terminal_io()->println(k);
//         for (int d = 0; d < 2; d++) {
//             int pwm = (d == 0) ? PWM_MAX_VALUE : -PWM_MAX_VALUE;
//             terminal_io()->print("Sending ");
//             terminal_io()->print(pwm);
//             dc_command_nth(k, pwm);
//             delay(1000);
//             terminal_io()->print(", speed= ");
//             int speed = abs(encoder_speed[k]);
//             terminal_io()->println(speed);
//             if (speed < min || min == -1) {
//                 min = speed;
//             }
//         }
//     }

//     // Maximum reachable rotation [turn/s] on each wheel
//     float maxRotationSpeed = (min * 1000 / SPEED_DT) / (float)WHEELS_CPR;

//     // Maximum ground speed [mm/s] on one wheel
//     // This is a minimum limit of speed for the robot in translation
//     float maxSpeed = maxRotationSpeed * M_PI * 2 * MODEL_WHEEL_RADIUS;

//     terminal_io()->println();
//     terminal_io()->print("Maximum speed: ");
//     terminal_io()->print(maxSpeed);
//     terminal_io()->println(" mm/s");
// }

TERMINAL_COMMAND(fails, "Fails in the quadrature decoders")
{
    for (int k = 0; k < 3; k++) {
        terminal_io()->print("Fails #");
        terminal_io()->print(k);
        terminal_io()->print(": ");
        terminal_io()->println(encoder_fails[k]);
    }
}

// TERMINAL_COMMAND(dc, "Debug the dc system")
// {
//     for (int k = 0; k < 3; k++) {
//         terminal_io()->print("Motor #");
//         terminal_io()->print(k);
//         terminal_io()->print(": speed=");
//         terminal_io()->print(encoder_speed[k]);
//         terminal_io()->print(", targetSpeed=");
//         terminal_io()->print(speed_target[k]);
//         terminal_io()->print(" -> acc=");
//         terminal_io()->print(((float)100.0 * acc[k]) / PWM_MAX_VALUE);
//         terminal_io()->print("% pwm=");
//         terminal_io()->print(((float)100.0 * m[k]) / PWM_MAX_VALUE);
//         terminal_io()->print("%");
//         terminal_io()->println();
//     }
// }

volatile int* get_encoder_value(){
  return encoder_value;
}
volatile int* get_encoder_fails(){
  return encoder_fails;
}

#ifdef DEBUG
TERMINAL_COMMAND(eb, "Encoders benchmark")
{
    int avg = 0;
    for (int k = 0; k < 10000; k++) {
        int start = micros();
        encoders_update();
        int elapsed = micros() - start;
        avg += elapsed;
    }
    terminal_io()->println(avg / 10000);
}
#endif
