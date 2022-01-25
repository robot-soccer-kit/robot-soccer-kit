#include <stdlib.h>
#include "bt.h"
#include "buzzer.h"
#include "charge.h"
#include "dc.h"
#include "hardware.h"
#include "infos.h"
#include "leds.h"
#include "motion.h"
#include "mux.h"
#include "kicker.h"
#include "voltage.h"
#include <commands.h>
#include <dxl.h>
#include <function.h>
#include <main.h>
#include <math.h>
#include <rc.h>
#include <rhock.h>
#include <terminal.h>
#include <wirish/wirish.h>
#ifdef HAS_RHOCK
#include "rhock-stream.h"
#include <rhock/event.h>
#include <rhock/stream.h>
#endif

bool isUSB = false;

TERMINAL_COMMAND(rc, "Go to RC mode")
{
    RC.begin(RC_BAUDRATE);
    terminal_init(&RC);
    isUSB = false;
}

TERMINAL_COMMAND(version, "Getting firmware version")
{
    terminal_io()->print("version=");
    terminal_io()->println(METABOT_VERSION);
}

// Maximum translation and rotation
TERMINAL_PARAMETER_FLOAT(maxSpeed, "max speed [mm/s]", 250);

/**
* Initializing
*/
void setup()
{
    init();

    // This disables Serial2 from APB1
    RCC_BASE->APB1ENR &= ~RCC_APB1ENR_USART2EN;

    // Initializing optical sensors
    kicker_init();

    // Initializing terminal on the RC port
    bt_init();
    terminal_init(&RC);

    // Configuring board LED as output
    pinMode(PIN_BOARD_LED, OUTPUT);
    digitalWrite(PIN_BOARD_LED, LOW);

    // Enabling dc motors
    dc_init();

    // Enabling leds
    leds_init();
    led_set_mode(LEDS_BREATH);

    // Enabling the multiplexers
    mux_init();

    // Enabling charge
    charge_init();

    // Voltage monitor
    voltage_init();

    // Infos
    infos_init();

    // Motion reset
    motion_em();

    buzzer_play(MELODY_BOOT);
}

float _limit(float a, float min, float max)
{
    if (a < min)
        return min;
    if (a > max)
        return max;
    return a;
}

/**
* Computing the servo values, called by dc flag at 100hz
*/
void tick()
{
    // Ticking voltage
    voltage_tick();

    // Updating leds
    leds_tick();

    // Checking voltage erro
    if (voltage_error()) {
        motion_em();
        dc_set_speed_target(0, 0, 0);
        led_set_mode(LEDS_BAD);
        buzzer_play(MELODY_ALERT, true);
#ifdef HAS_RHOCK
        // Killing all programs
        rhock_program_killall();
#endif
        return;
    } else {
      if (leds_are_bad()) {
          led_set_mode(LEDS_BREATH);
      }
      if (buzzer_is_melody_alert()) {
          buzzer_stop();
      }

    }

    // Orders from motion
    struct motion_order order = motion_get_order();

    // Desired translation speed [mm/s]
    float desiredSpeed = sqrt(order.dx * order.dx + order.dy * order.dy);

    // Desired translation speed caused by wheel rotation [mm/s]
    float desiredRotationSpeed = (order.turn * M_PI / 180.0) * MODEL_ROBOT_RADIUS;

    // If the desired max speed is reached, re-normalizing speeds to avoid
    // reaching max wheel speed limit
    float desiredMaxSpeed = desiredSpeed + desiredRotationSpeed;
    if (desiredMaxSpeed > maxSpeed) {
        float ratio = maxSpeed / desiredMaxSpeed;

        order.dx *= ratio;
        order.dy *= ratio;
        order.turn *= ratio;
    }

    // Sending orders to ik
    dc_ik(order.dx, order.dy, order.turn);

    kicker_tick();
}

TERMINAL_PARAMETER_INT(loopd, "loop duration", 0);

static int t = 0;

void loop()
{
    // Buzzer update
    buzzer_tick();

    // DC
    dc_tick();

    // Updating the terminal
    terminal_tick();

// Ticking Rhock
#ifdef HAS_RHOCK
    rhock_tick();
#endif

    // If there is data in USB, switching the terminal to USB
    if (SerialUSB.available() && !isUSB) {
        isUSB = true;
        terminal_init(&SerialUSB);
    }

    // Ticking the charging system
    charge_tick();

    // Calling user motion tick
    if (dcFlag) {
        dcFlag = false;
        t = micros();
        tick();
        int tmp = micros() - t;
        if (tmp > loopd)
            loopd = tmp;
    }
}

void emergency_stop()
{
#ifdef HAS_RHOCK
    // Killing all programs
    rhock_program_killall();
#endif

    // Stopping orders
    motion_em();

    // Led breath
    led_set_mode(LEDS_BREATH);

    // Stopping buzzer
    buzzer_stop();
}

TERMINAL_COMMAND(em, "Emergency stop")
{
    emergency_stop();
}
