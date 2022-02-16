#include "motors.h"
#include "config.h"
#include "pwm_channels.h"
#include "shell.h"
#include <Arduino.h>
#include <ESP32Encoder.h>
#include <math.h>

struct Motor {
  // Pins for PWM control
  int pin_pwm1;
  int pin_pwm2;
  // Pins for encoders
  int pin_enc1;
  int pin_enc2;
  // Wheel driving vector
  float drive_x;
  float drive_y;

  // PWM Channels used for pwm control
  int pwm_chan1;
  int pwm_chan2;
  // Encoder
  ESP32Encoder encoder;
  int64_t encoder_window[SPEED_WINDOW];
  uint32_t encoder_window_index;
  // Current target and measured speed
  float speed_target;
  float speed;
  // Current error
  float error;
  // Error accumulator (for integrator)
  float error_accumulator;
  // Is the servoing enabled ?
  bool enabled;
};

SHELL_PARAMETER_FLOAT(kp, "Kp", 1500);
SHELL_PARAMETER_FLOAT(ki, "Ki", 750);

#define DEG2RAD(x) (x * M_PI / 180.0)

struct Motor motors[] = {
    {MOTOR1_PWM1, MOTOR1_PWM2, MOTOR1_ENC1, MOTOR1_ENC2,
     (float)cos(DEG2RAD(WHEEL1_ALPHA)), (float)sin(DEG2RAD(WHEEL1_ALPHA))},
    {MOTOR2_PWM1, MOTOR2_PWM2, MOTOR2_ENC1, MOTOR2_ENC2,
     (float)cos(DEG2RAD(WHEEL2_ALPHA)), (float)sin(DEG2RAD(WHEEL2_ALPHA))},
    {MOTOR3_PWM1, MOTOR3_PWM2, MOTOR3_ENC1, MOTOR3_ENC2,
     (float)cos(DEG2RAD(WHEEL3_ALPHA)), (float)sin(DEG2RAD(WHEEL3_ALPHA))},
};

SHELL_PARAMETER_INT(n, "Counting", 0);

void _bound_pwm(float *value) {
  if (*value < -1024) {
    *value = -1024;
  }
  if (*value > 1024) {
    *value = 1024;
  }
}

void motors_servo(void *args) {
  for (int k = 0; k < 3; k++) {
    int64_t count = motors[k].encoder.getCount();
    motors[k].encoder_window_index += 1;
    if (motors[k].encoder_window_index >= SPEED_WINDOW) {
      motors[k].encoder_window_index = 0;
    }

    int64_t delta =
        count - motors[k].encoder_window[motors[k].encoder_window_index];
    motors[k].encoder_window[motors[k].encoder_window_index] = count;

    motors[k].speed =
        (delta * 2 * M_PI * 1000.0) / ((float)(SPEED_WINDOW * WHEELS_CPR));
    float error = motors[k].speed_target - motors[k].speed;
    motors[k].error = error;

    if (motors[k].enabled) {
      motors[k].error_accumulator += ki * error / 1000.0;
      _bound_pwm(&motors[k].error_accumulator);

      float pwm = -kp * error - motors[k].error_accumulator;
      _bound_pwm(&pwm);

      motors_set_pwm(k, pwm);
    } else {
      motors[k].error_accumulator = 0;
    }
  }
  n += 1;
}

void motors_init() {
  int pwm_channel;
  for (int k = 0; k < 3; k++) {
    pwm_channel = pwm_channel_allocate();
    ledcSetup(pwm_channel, 22000, 10);
    ledcAttachPin(motors[k].pin_pwm1, pwm_channel);
    motors[k].pwm_chan1 = pwm_channel;

    pwm_channel = pwm_channel_allocate();
    ledcSetup(pwm_channel, 22000, 10);
    motors[k].pwm_chan2 = pwm_channel;
    ledcAttachPin(motors[k].pin_pwm2, pwm_channel);

    motors[k].encoder.attachFullQuad(motors[k].pin_enc1, motors[k].pin_enc2);
    for (int i = 0; i < SPEED_WINDOW; i++) {
      motors[k].encoder_window[i] = 0;
    }
    motors[k].encoder_window_index = 0;
    motors[k].speed = 0;
    motors[k].error = 0;
    motors[k].speed_target = 0;
    motors[k].error_accumulator = 0;
    motors[k].enabled = false;
  }

  // Configuring a 1000 Hz timer
  esp_timer_create_args_t periodic_timer_args;
  periodic_timer_args.callback = &motors_servo;
  periodic_timer_args.name = "servo";

  esp_timer_handle_t periodic_timer;
  ESP_ERROR_CHECK(esp_timer_create(&periodic_timer_args, &periodic_timer));
  ESP_ERROR_CHECK(esp_timer_start_periodic(periodic_timer, 1000));
}

void motors_set_pwm(int index, int16_t pwm) {
  if (index >= 0 && index < 3) {
    if (pwm < -1024)
      pwm = -1024;
    if (pwm > 1024)
      pwm = 1024;

    if (pwm > 0) {
      ledcWrite(motors[index].pwm_chan1, pwm);
      ledcWrite(motors[index].pwm_chan2, 0);
    } else {
      ledcWrite(motors[index].pwm_chan1, 0);
      ledcWrite(motors[index].pwm_chan2, -pwm);
    }
  }
}

void motors_set_pwms(int16_t motor1, int16_t motor2, int16_t motor3) {
  motors_set_pwm(0, motor1);
  motors_set_pwm(1, motor2);
  motors_set_pwm(2, motor3);
}

void motors_set_speed(int index, int speed) {
  motors[index].speed_target = speed;
  motors[index].enabled = true;
}

void motors_set_speed(float w1, float w2, float w3) {
  motors_set_speed(0, w1);
  motors_set_speed(1, w2);
  motors_set_speed(2, w3);
}

void motors_set_ik(float dx, float dy, float dt) {
  float w1 = (motors[0].drive_x * dx + motors[0].drive_y * dy +
              MODEL_ROBOT_RADIUS * dt) /
             (MODEL_WHEEL_RADIUS);
  float w2 = (motors[1].drive_x * dx + motors[1].drive_y * dy +
              MODEL_ROBOT_RADIUS * dt) /
             (MODEL_WHEEL_RADIUS);
  float w3 = (motors[2].drive_x * dx + motors[2].drive_y * dy +
              MODEL_ROBOT_RADIUS * dt) /
             (MODEL_WHEEL_RADIUS);

  motors_set_speed(w1, w2, w3);
}

SHELL_COMMAND(motors, "Motors status") {
  for (int k = 0; k < 3; k++) {
    shell_stream()->print("Motor #");
    shell_stream()->print((int)k);
    shell_stream()->println(": ");

    shell_stream()->print("- Encoder (pulses): ");
    shell_stream()->println((int)motors[k].encoder.getCount());
    shell_stream()->print("- Speed (rad/s): ");
    shell_stream()->println(motors[k].speed);
    shell_stream()->print("- Error: ");
    shell_stream()->println(motors[k].error);
    shell_stream()->print("- Error accumulator: ");
    shell_stream()->println(motors[k].error_accumulator);
  }
}

SHELL_COMMAND(pwms, "Test motor (set pwms)") {
  if (argc > 2) {
    motors_set_pwms(atoi(argv[0]), atoi(argv[1]), atoi(argv[2]));
  } else {
    shell_stream()->println("Usage: pwms [pwm1] [pwm2] [pwm3]");
  }
}

SHELL_COMMAND(servo, "Servo targets") {
  if (argc > 2) {
    motors_set_speed(atof(argv[0]), atof(argv[1]), atof(argv[2]));
  } else {
    shell_stream()->println("Usage: servo [speed1] [speed2] [speed3]");
  }
}

SHELL_COMMAND(ik, "Servo chassis speed") {
  if (argc > 2) {
    motors_set_ik(atof(argv[0]), atof(argv[1]), atof(argv[2]));
  } else {
    shell_stream()->println("Usage: ik [dx] [dy] [dt]");
  }
}

void motors_disable() {
  for (int k = 0; k < 3; k++) {
    motors[k].enabled = false;
  }
  motors_set_pwms(0, 0, 0);
}

SHELL_COMMAND(em, "Stop") { motors_disable(); }