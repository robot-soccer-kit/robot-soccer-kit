#include "motors.h"
#include "pinout.h"
#include "shell.h"
#include <Arduino.h>
#include <ESP32Encoder.h>
#include <math.h>

#define SPEED_WINDOW 10

struct Motor {
  // Pins for PWM control
  int pin_pwm1;
  int pin_pwm2;
  // Pins for encoders
  int pin_enc1;
  int pin_enc2;
  // PWM Channels used for pwm control
  int pwm_chan1;
  int pwm_chan2;
  // Encoder
  ESP32Encoder encoder;
  int64_t encoder_last[SPEED_WINDOW];
  uint32_t encoder_last_index;
  float speed;
  float error;
  float error_accumulator;
  float speed_target;
  bool enabled;
};

SHELL_PARAMETER_FLOAT(kp, "Kp", 1000);
SHELL_PARAMETER_FLOAT(ki, "Ki", 10);

struct Motor motors[] = {
    {MOTOR1_PWM1, MOTOR1_PWM2, MOTOR1_ENC1, MOTOR1_ENC2},
    {MOTOR2_PWM1, MOTOR2_PWM2, MOTOR2_ENC1, MOTOR2_ENC2},
    {MOTOR3_PWM1, MOTOR3_PWM2, MOTOR3_ENC1, MOTOR3_ENC2},
};

SHELL_PARAMETER_INT(n, "Counting", 0);
SHELL_PARAMETER_BOOL(l, "Log", false);

void motors_servo(void *args) {
  for (int k = 0; k < 3; k++) {
    int64_t count = motors[k].encoder.getCount();
    motors[k].encoder_last_index += 1;
    if (motors[k].encoder_last_index >= SPEED_WINDOW) {
      motors[k].encoder_last_index = 0;
    }

    int64_t delta =
        count - motors[k].encoder_last[motors[k].encoder_last_index];
    motors[k].encoder_last[motors[k].encoder_last_index] = count;

    motors[k].speed =
        (delta * 2 * M_PI * 1000.0) / ((float)(SPEED_WINDOW * WHEELS_CPR));
    float error = motors[k].speed_target - motors[k].speed;
    motors[k].error = error;

    if (motors[k].enabled) {
      motors[k].error_accumulator += error / 1000.0;
      if (motors[k].error_accumulator < -16)
        motors[k].error_accumulator = -16;
      if (motors[k].error_accumulator > 16)
        motors[k].error_accumulator = 16;

      motors_set_pwm(k, -kp * error - motors[k].error_accumulator * ki);
    } else {
      motors[k].error_accumulator = 0;
    }
  }
  n += 1;
}

void motors_init() {
  int pwm_channel = 0;
  for (int k = 0; k < 3; k++) {
    ledcSetup(pwm_channel, 22000, 10);
    ledcAttachPin(motors[k].pin_pwm1, pwm_channel);
    motors[k].pwm_chan1 = pwm_channel;
    pwm_channel++;

    ledcSetup(pwm_channel, 22000, 10);
    motors[k].pwm_chan2 = pwm_channel;
    ledcAttachPin(motors[k].pin_pwm2, pwm_channel);
    pwm_channel++;

    motors[k].encoder.attachFullQuad(motors[k].pin_enc1, motors[k].pin_enc2);
    for (int i = 0; i < SPEED_WINDOW; i++) {
      motors[k].encoder_last[i] = 0;
    }
    motors[k].encoder_last_index = 0;
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
    motors[0].speed_target = atof(argv[0]);
    motors[0].enabled = true;
    motors[1].speed_target = atof(argv[1]);
    motors[1].enabled = true;
    motors[2].speed_target = atof(argv[2]);
    motors[2].enabled = true;
  } else {
    shell_stream()->println("Usage: servo [speed1] [speed2] [speed3]");
  }
}

SHELL_COMMAND(em, "Stop") {
  for (int k = 0; k < 3; k++) {
    motors[k].enabled = false;
  }
  motors_set_pwms(0, 0, 0);
}