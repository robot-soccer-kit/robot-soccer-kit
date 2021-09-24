#ifndef _INFOS_H
#define _INFOS_H

#include <stdint.h>
#include "hardware.h"

/**
 * Calibration infos that are stored in flash
 */
struct robot_infos
{
    uint32_t key1, key2;

    // IMU calibration
    float gyro_x0, gyro_y0, gyro_z0;
    float magn_x_min, magn_x_max;
    float magn_y_min, magn_y_max;
    float magn_z_min, magn_z_max;

    // Opticals calibration
    int opticals_white[OPTICAL_NB];
    int opticals_black[OPTICAL_NB];
};

void infos_init();

struct robot_infos *infos_get();
void infos_save();

#endif
