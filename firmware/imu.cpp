// #define DEBUG
#include "imu.h"
#include "buzzer.h"
#include "hardware.h"
#include "infos.h"
#include "leds.h"
#include "motion.h"
#include <math.h>
#include <stdlib.h>

#ifdef HAS_TERMINAL
#include <terminal.h>
#endif

#ifndef __EMSCRIPTEN__
#include "main.h"
#include <i2c.h>
#include <wirish/wirish.h>
#else
#include "js_utils.h"
#include <emscripten.h>
#include <emscripten/bind.h>
#endif

#ifndef __EMSCRIPTEN__
static bool initialized = false;

#define I2C_TIMEOUT 2

int32 i2c_master_xfer_reinit(i2c_dev *dev, i2c_msg *msgs, uint16 num,
                             uint32 timeout) {
  int32 r = i2c_master_xfer(dev, msgs, num, timeout);
  if (r != 0) {
    initialized = false;
  }
  return r;
}

static int last_update;

float magn_x, magn_y, magn_z;
float gyro_x, gyro_y, gyro_z;
float acc_x, acc_y, acc_z;

// Here is the gyro calibration state
//   the calibration is launched 1 second after the startup
//   (we wait a bit because one often moves the robot at startup,
//    by turning on the button or the plug)
//   the robot is not supposed to move during the calibration time.
//   we simply compute the mean of the gyros value that becomes the zero.
// gyro calibration time in millisecond

enum gyro_calibration_state {
  gyro_calibration_waiting = 0,
  gyro_calibration_calibrating = 1,
  gyro_calibration_ending = 2,
  gyro_calibration_over = 3
};

#define GYRO_CALIB_END_LEDS_TIME 500
#define GYRO_CALIB_WAIT 1000
#define GYRO_CALIB_TIME 2000

int gc_time0 = -1; // the time 0 for the calibration
enum gyro_calibration_state gyro_calibration_state = gyro_calibration_over;
bool gyro_calib_started = false;
bool gyro_calib_ok = false;
#endif

static float yaw = 0;
static float pitch = 0;
static float roll = 0;
static float gyro_yaw = 0;
static float temperature = 0;

#ifndef __EMSCRIPTEN__
TERMINAL_PARAMETER_BOOL(imudbg, "Debug the IMU", false);

// I2C Addresses
#define MAGN_ADDR 0x1e  // HMC5883L
#define MAGN2_ADDR 0x0d // QMC5883L
#define GYRO_ADDR 0x68  // ITG-3200
#define ACC_ADDR 0x53   // ADXL345

// Config
#define MAGN_X_CENTER ((infos->magn_x_min + infos->magn_x_max) / 2.0)
#define MAGN_X_AMP (infos->magn_x_max - infos->magn_x_min)
#define MAGN_Y_CENTER ((infos->magn_y_min + infos->magn_y_max) / 2.0)
#define MAGN_Y_AMP (infos->magn_y_max - infos->magn_y_min)
#define MAGN_Z_CENTER ((infos->magn_z_min + infos->magn_z_max) / 2.0)
#define MAGN_Z_AMP (infos->magn_z_max - infos->magn_z_min)

#define GYRO_GAIN 0.06957

#define DEG2RAD(x) ((x)*M_PI / 180.0)
#define RAD2DEG(x) ((x)*180.0 / M_PI)

// Signing
#define VALUE_SIGN(value, length)                                              \
  ((value < (1 << (length - 1))) ? (value) : (value - (1 << length)))

struct i2c_msg packet;

// Gyroscope packets
static uint8 gyro_reset[] = {0x3e, 0x80};
static uint8 gyro_scale[] = {0x16, 0x1b};
static uint8 gyro_50hz[] = {0x15, 0x0a};
static uint8 gyro_pll[] = {0x3e, 0x00};
static uint8 gyro_req[] = {0x1b};

// Accelerometer packets
static uint8 acc_measure[] = {0x2d, 0x08};
static uint8 acc_resolution[] = {0x31, 0x08};
static uint8 acc_50hz[] = {0x2c, 0x09};
static uint8 acc_req[] = {0x32};

// Magnetometer packets
static uint8 magn_continuous[] = {0x02, 0x00};

// For HMC
static uint8 magn_50hz[] = {0x00, 0b00011000};
static uint8 magn_sens[] = {0x01, 0b11100000};
static uint8 magn_req[] = {0x03};

// For QMC5883L
static uint8 magn2_config[] = {0x09, 0b00010101};
static uint8 magn2_req[] = {0x00};

// 0 for HMC5883L and 1 for QMC5883L
static int magn_type = 0;
#endif

float normalize(float angle) {
  while (angle > 180)
    angle -= 360;
  while (angle < -180)
    angle += 360;

  return angle;
}

#ifndef __EMSCRIPTEN__
TERMINAL_COMMAND(imu, "Imu infos") {
  if (initialized) {
    terminal_io()->println("Initalized");
    terminal_io()->println("Magnetometer type: ");
    if (magn_type == 0) {
      terminal_io()->println("HMC5883L");
    } else {
      terminal_io()->println("QMC5883L");
    }
  } else {
    terminal_io()->println("Not initalized");
  }
  terminal_io()->print("Yaw: ");
  terminal_io()->println(yaw);
  terminal_io()->print("Gyro yaw: ");
  terminal_io()->println(gyro_yaw);
  terminal_io()->print("Pitch: ");
  terminal_io()->println(pitch);
  terminal_io()->print("Roll: ");
  terminal_io()->println(roll);
  terminal_io()->print("Temperature: ");
  terminal_io()->println(temperature);
}

float weight_average(float a1, float w1, float a2, float w2) {
  float x = w1 * cos(a1) + w2 * cos(a2);
  float y = w1 * sin(a1) + w2 * sin(a2);

  return atan2(y, x);
}

void imu_init() {
  yaw = 0.0;
  last_update = millis();
  if (gc_time0 < 0)
    gc_time0 = last_update;

  // Initializing values
  magn_x = magn_y = magn_z = 0;

  // Initializing I2C bus
  i2c_init(I2C_IMU);
  i2c_master_enable(I2C_IMU, I2C_FAST_MODE);

  // Initializing magnetometer, assuming its HMC5883L
  magn_type = 0;
  packet.addr = MAGN_ADDR;
  packet.flags = 0;
  packet.data = magn_continuous;
  packet.length = 2;
  if (magn_type == 0 &&
      i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    magn_type = 1;

  packet.data = magn_50hz;
  if (magn_type == 0 &&
      i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    magn_type = 1;

  packet.data = magn_sens;
  if (magn_type == 0 &&
      i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    magn_type = 1;

  // Magnetometer initialization failed, trying QMC5883L
  if (magn_type == 1) {
    i2c_init(I2C_IMU);
    i2c_master_enable(I2C_IMU, I2C_FAST_MODE);

    packet.addr = MAGN2_ADDR;
    packet.flags = 0;
    packet.data = magn2_config;
    packet.length = 2;
    if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
      goto init_error;
  }

  // Initializing accelerometer
  packet.addr = ACC_ADDR;
  packet.flags = 0;
  packet.data = acc_measure;
  packet.length = 2;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;

  packet.data = acc_resolution;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;

  packet.data = acc_50hz;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;

  // Initializing gyroscope
  packet.addr = GYRO_ADDR;
  packet.flags = 0;
  packet.data = gyro_reset;
  packet.length = 2;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;

  packet.data = gyro_scale;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;
  packet.data = gyro_50hz;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;
  packet.data = gyro_pll;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    goto init_error;

  initialized = true;
  return;

init_error:
  initialized = false;
}

static bool calibrating = false;
static bool first = false;
static float calibrating_t = -1;

void magn_update() {
  if (!initialized)
    return;

  packet.flags = 0;
  if (magn_type == 0) {
    packet.data = magn_req;
    packet.addr = MAGN_ADDR;
  } else {
    packet.data = magn2_req;
    packet.addr = MAGN2_ADDR;
  }
  packet.length = 1;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  char buffer[6];
  packet.flags = I2C_MSG_READ;
  packet.data = (uint8 *)buffer;
  packet.length = 6;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  int magn_x_r, magn_y_r, magn_z_r;

  if (magn_type == 0) {
    magn_x_r = ((buffer[0] & 0xff) << 8) | (buffer[1] & 0xff);
    magn_y_r = ((buffer[4] & 0xff) << 8) | (buffer[5] & 0xff);
    magn_z_r = ((buffer[2] & 0xff) << 8) | (buffer[3] & 0xff);
  } else {
    magn_x_r = ((buffer[1] & 0xff) << 8) | (buffer[0] & 0xff);
    magn_y_r = ((buffer[3] & 0xff) << 8) | (buffer[2] & 0xff);
    magn_z_r = ((buffer[5] & 0xff) << 8) | (buffer[4] & 0xff);
  }
  magn_x_r = VALUE_SIGN(magn_x_r, 16);
  magn_y_r = VALUE_SIGN(magn_y_r, 16);
  magn_z_r = VALUE_SIGN(magn_z_r, 16);

  struct robot_infos *infos = infos_get();
  if (calibrating) {
    if (first) {
      first = false;
      infos->magn_x_min = infos->magn_x_max = magn_x_r;
      infos->magn_y_min = infos->magn_y_max = magn_y_r;
      infos->magn_z_min = infos->magn_z_max = magn_z_r;
    } else {
      if (magn_x_r > infos->magn_x_max)
        infos->magn_x_max = magn_x_r;
      if (magn_x_r < infos->magn_x_min)
        infos->magn_x_min = magn_x_r;
      if (magn_y_r > infos->magn_y_max)
        infos->magn_y_max = magn_y_r;
      if (magn_y_r < infos->magn_y_min)
        infos->magn_y_min = magn_y_r;
      if (magn_z_r > infos->magn_z_max)
        infos->magn_z_max = magn_z_r;
      if (magn_z_r < infos->magn_z_min)
        infos->magn_z_min = magn_z_r;
    }
  } else {
    magn_x = (magn_x_r - MAGN_X_CENTER) / (float)MAGN_X_AMP;
    magn_y = (magn_y_r - MAGN_Y_CENTER) / (float)MAGN_Y_AMP;
    magn_z = (magn_z_r - MAGN_Z_CENTER) / (float)MAGN_Z_AMP;
  }

  if (!calibrating) {
    float new_yaw;
    new_yaw = atan2(magn_x, magn_y) + M_PI;
    if (new_yaw > M_PI)
      new_yaw -= 2 * M_PI;
    float cur_yaw = DEG2RAD(yaw);
    yaw = RAD2DEG(weight_average(new_yaw, 0.05, cur_yaw, 0.95));
  }
}

static void gyro_start_calibration() {
  gc_time0 = millis();
  gyro_calibration_state = gyro_calibration_waiting;
}

void gyro_update() {
  if (!initialized)
    return;

  packet.addr = GYRO_ADDR;
  packet.flags = 0;
  packet.data = gyro_req;
  packet.length = 1;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  char buffer[8];
  packet.flags = I2C_MSG_READ;
  packet.data = (uint8 *)buffer;
  packet.length = 8;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  int temp_r = ((buffer[0] & 0xff) << 8) | (buffer[1] & 0xff);
  temperature = ((VALUE_SIGN(temp_r, 16) + 13200) / 280.0) + 30;
  int gyro_x_r = ((buffer[2] & 0xff) << 8) | (buffer[3] & 0xff);
  gyro_x = GYRO_GAIN * VALUE_SIGN(gyro_x_r, 16);
  int gyro_y_r = ((buffer[4] & 0xff) << 8) | (buffer[5] & 0xff);
  gyro_y = GYRO_GAIN * VALUE_SIGN(gyro_y_r, 16);
  int gyro_z_r = ((buffer[6] & 0xff) << 8) | (buffer[7] & 0xff);
  gyro_z = GYRO_GAIN * VALUE_SIGN(gyro_z_r, 16);

  // Gyrometer calibration
  int dt = millis() - gc_time0;

  struct robot_infos *infos = infos_get();
  if (gyro_calibration_state == gyro_calibration_waiting) {
    if (dt > GYRO_CALIB_WAIT) {
      gc_time0 = millis();

      infos->gyro_x0 = gyro_x;
      infos->gyro_y0 = gyro_y;
      infos->gyro_z0 = gyro_z;
      gc_time0 = millis();
      gyro_calibration_state = gyro_calibration_calibrating;
    }
  } else if (gyro_calibration_state == gyro_calibration_calibrating) {
    infos->gyro_x0 = 0.05 * gyro_x + 0.95 * infos->gyro_x0;
    infos->gyro_y0 = 0.05 * gyro_y + 0.95 * infos->gyro_y0;
    infos->gyro_z0 = 0.05 * gyro_z + 0.95 * infos->gyro_z0;

    if (dt > GYRO_CALIB_TIME) {
      gyro_calibration_state = gyro_calibration_ending;
      buzzer_play(MELODY_OK);
      infos_save();
      imu_calib_stop();
      led_all_color_set(0, 255, 0);
      gc_time0 = millis();
    }
  } else if (gyro_calibration_state == gyro_calibration_ending) {
    if (dt > GYRO_CALIB_END_LEDS_TIME) {
      gyro_calibration_state = gyro_calibration_over;
      led_set_mode(LEDS_BREATH);
    }
  }

  gyro_x -= infos->gyro_x0;
  gyro_y -= infos->gyro_y0;
  gyro_z -= infos->gyro_z0;

  yaw += gyro_z * 0.02;
  yaw = normalize(yaw);

  gyro_yaw += gyro_z * 0.02;
  gyro_yaw = normalize(gyro_yaw);
}
#endif

float imu_yaw_speed() { return gyro_z; }

#ifndef __EMSCRIPTEN__
void acc_update() {
  if (!initialized)
    return;

  packet.addr = ACC_ADDR;
  packet.flags = 0;
  packet.data = acc_req;
  packet.length = 1;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  char buffer[6];
  packet.flags = I2C_MSG_READ;
  packet.data = (uint8 *)buffer;
  packet.length = 6;
  if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0)
    return;

  int acc_x_r = ((buffer[1] & 0xff) << 8) | (buffer[0] & 0xff);
  acc_x = VALUE_SIGN(acc_x_r, 16);
  int acc_y_r = ((buffer[3] & 0xff) << 8) | (buffer[2] & 0xff);
  acc_y = VALUE_SIGN(acc_y_r, 16);
  int acc_z_r = ((buffer[5] & 0xff) << 8) | (buffer[4] & 0xff);
  acc_z = VALUE_SIGN(acc_z_r, 16);

  float robot_front_offset = 30 * M_PI / 180.0;
  float cos_front, sin_front;
  cos_front = cos(robot_front_offset);
  sin_front = sin(robot_front_offset);
  float acc_x_front = acc_x * cos_front - acc_y * sin_front;
  float acc_y_front = acc_x * sin_front + acc_y * cos_front;

  float new_roll = -atan2(acc_x_front, acc_z);
  float new_pitch =
      atan2(acc_y_front, sqrt(acc_x_front * acc_x_front + acc_z * acc_z));

  pitch = RAD2DEG(weight_average(new_pitch, 0.05, DEG2RAD(pitch), 0.95));
  roll = RAD2DEG(weight_average(new_roll, 0.05, DEG2RAD(roll), 0.95));
}

#define IRLOCATOR_ADDR 0x0e
;
static volatile bool irlocator_read = false;
static volatile int irlocator_1200hz[2] = {0, 0};
static volatile int irlocator_600hz[2] = {0, 0};

void irlocator_update() {
  if (irlocator_read) {
    static uint8 zero_req[] = {0x00};

    packet.flags = 0;
    packet.data = zero_req;
    packet.length = 1;
    packet.addr = IRLOCATOR_ADDR;

    if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0) {
      return;
    }

    char buffer[8];
    packet.flags = I2C_MSG_READ;
    packet.data = (uint8 *)buffer;
    packet.length = 8;

    if (i2c_master_xfer_reinit(I2C_IMU, &packet, 1, I2C_TIMEOUT) != 0) {
      return;
    }

    irlocator_1200hz[0] = buffer[0x04] * 5;
    if (irlocator_1200hz[0] > 180)
      irlocator_1200hz[0] -= 360;
    irlocator_1200hz[1] = buffer[0x05];
    irlocator_600hz[0] = buffer[0x06] * 5;
    irlocator_600hz[1] = buffer[0x07];
    if (irlocator_600hz[0] > 180)
      irlocator_600hz[0] -= 360;
  }
}

float irlocator_heading(bool is1200hz) {
  irlocator_read = true;

  return is1200hz ? irlocator_1200hz[0] : irlocator_600hz[0];
}

float irlocator_strength(bool is1200hz) {
  irlocator_read = true;

  return is1200hz ? irlocator_1200hz[1] / 2.55 : irlocator_600hz[1] / 2.55;
}

/* basic check for lost system, if the system is lost it re-launch the system.
 */
float last_acc_x, last_acc_y;
int last_change_tick_nb = 0;
bool imu_ok = true;

void imu_check() {
  if (acc_x != last_acc_x || acc_y != last_acc_y) {
    last_change_tick_nb = 0;
    last_acc_x = acc_x;
    last_acc_y = acc_y;
    imu_ok = true;
    return;
  }
  last_change_tick_nb++;
  if (last_change_tick_nb > 20) {
    imu_ok = false;
    initialized = false;
    delay(1);
    i2c_bus_reset(I2C_IMU);
    delay(1);
    i2c_disable(I2C_IMU);
    delay(1);
    imu_init();
    // terminal_io()->println("caution imu error");
  }
}

void imu_tick() {
  int elapsed = millis() - last_update;

  // Every 20ms
  if (elapsed > 20) {
    last_update += 20;

    if (initialized) {
      gyro_update();
      magn_update();
      acc_update();
      irlocator_update();
    } else {
      imu_init();
    }

    if (calibrating) {
      if (calibrating_t >= 0) {
        calibrating_t += 0.02;
        if (calibrating_t > 7) {
          motion_set_joy_order(0, 0, 0);
          imu_calib_stop();
          gyro_start_calibration();
        }
      }
    }

    imu_check();

    if (imudbg) {
      terminal_io()->print(magn_x);
      terminal_io()->print(" ");
      terminal_io()->print(magn_y);
      terminal_io()->print(" ");
      terminal_io()->print(magn_z);
      terminal_io()->print(" ");

      terminal_io()->print(gyro_x);
      terminal_io()->print(" ");
      terminal_io()->print(gyro_y);
      terminal_io()->print(" ");
      terminal_io()->print(gyro_z);
      terminal_io()->print(" ");

      terminal_io()->print(acc_x);
      terminal_io()->print(" ");
      terminal_io()->print(acc_y);
      terminal_io()->print(" ");
      terminal_io()->print(acc_z);
      terminal_io()->print(" ");

      terminal_io()->print(gyro_yaw);
      terminal_io()->print(" ");

      terminal_io()->print(yaw);
      terminal_io()->print(" ");

      terminal_io()->println();
    }
  }
}

void imu_calib_start() {
  calibrating = true;
  first = true;
}

void imu_calib_stop() { calibrating = false; }

void imu_calib_rotate() {
  imu_calib_start();
  motion_set_joy_order(0, 0, 150);
  calibrating_t = 0.1;
  led_all_color_set(255, 102, 0);
  led_set_blink_duration(400);
  led_set_mode(LEDS_BLINK);
}
#endif

float imu_gyro_yaw() { return gyro_yaw; }

void imu_gyro_yaw_reset() { gyro_yaw = 0; }

void set_yaw(float _yaw) {
  yaw = normalize(_yaw);
  gyro_yaw = normalize(_yaw);
}

float imu_yaw() { return yaw; }

float imu_pitch() { return pitch; }

float imu_roll() { return roll; }

float imu_temperature() { return temperature; }

#ifndef __EMSCRIPTEN__
TERMINAL_COMMAND(irloc, "IR locator data") {
  terminal_io()->print("1200hz heading: ");
  terminal_io()->println(irlocator_heading(true));
  terminal_io()->print("1200hz strength: ");
  terminal_io()->println(irlocator_strength(true));
  terminal_io()->print("600hz heading: ");
  terminal_io()->println(irlocator_heading(false));
  terminal_io()->print("600hz strength: ");
  terminal_io()->println(irlocator_strength(false));
}
#endif

#ifdef HAS_TERMINAL
TERMINAL_COMMAND(calibrot, "Calibrating rotation") { imu_calib_rotate(); }
#endif

void imu_normalize_angle(float *deg) {
  for (int k = 0; k < 10 && *deg < -180; k++)
    *deg += 360;
  for (int k = 0; k < 10 && *deg > 180; k++)
    *deg -= 360;
}

float get_acc_norm() {
  return sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z);
}

#ifdef DEBUG
TERMINAL_COMMAND(imu_acc_norm,
                 "Compute the norm of the vector (acc_x, acc_y, acc_z)") {
  while (!SerialUSB.available()) {
    imu_tick();
    terminal_io()->println(get_acc_norm());
  }
}
#endif

#ifdef __EMSCRIPTEN__
EMSCRIPTEN_BINDINGS(imu) { emscripten::function("set_yaw", &set_yaw); }
#endif
