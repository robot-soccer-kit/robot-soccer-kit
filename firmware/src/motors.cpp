#include "motors.h"
#include "pinout.h"
#include "shell.h"
#include <Arduino.h>
#include <ESP32Encoder.h>

struct Motor {
  int pin_pwm1;
  int pin_pwm2;
  int pin_enc1;
  int pin_enc2;
  int pwm_chan1;
  int pwm_chan2;
  ESP32Encoder encoder;
};

struct Motor motors[] = {
    {MOTOR1_PWM1, MOTOR1_PWM2, MOTOR1_ENC1, MOTOR1_ENC2},
    {MOTOR2_PWM1, MOTOR2_PWM2, MOTOR2_ENC1, MOTOR2_ENC2},
    {MOTOR3_PWM1, MOTOR3_PWM2, MOTOR3_ENC1, MOTOR3_ENC2},
};

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
  }
}

void motors_set_pwm(int index, int16_t pwm) {
  if (index >= 0 && index < 3) {
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
    shell_stream()->print(": ");
    shell_stream()->println((int)motors[k].encoder.getCount());
  }
}

SHELL_COMMAND(pwms, "Test motor (set pwms)") {
  if (argc > 2) {
    motors_set_pwms(atoi(argv[0]), atoi(argv[1]), atoi(argv[2]));
  } else {
    shell_stream()->println("Usage: pwms [pwm1] [pwm2] [pwm3]");
  }
}

SHELL_COMMAND(em, "Stop") { motors_set_pwms(0, 0, 0); }