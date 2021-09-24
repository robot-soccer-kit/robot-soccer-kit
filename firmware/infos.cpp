#include <stdlib.h>
#include <wirish/wirish.h>
#include <flash_write.h>
#include "mux.h"
#ifdef HAS_TERMINAL
#include <terminal.h>
#endif
#include "hardware.h"
#include "infos.h"

// Flash address to write/read infos
#define INFOS_FLASH_ADDR    0x0801FC00

#define INFOS_KEY1 0xBE34AAE5
#define INFOS_KEY2 0x228710DE

static struct robot_infos infos;

void infos_init()
{
    flash_read(INFOS_FLASH_ADDR, (void *)&infos, sizeof(infos));

    if (infos.key1 != INFOS_KEY1 || infos.key2 != INFOS_KEY2) {
        infos.key1 = INFOS_KEY1;
        infos.key2 = INFOS_KEY2;

        infos.gyro_x0 = 0;
        infos.gyro_y0 = 0;
        infos.gyro_z0 = 0;

        infos.magn_x_min = -0.5;
        infos.magn_x_max = 0.5;
        infos.magn_y_min = -0.5;
        infos.magn_y_max = 0.5;
        infos.magn_z_min = -0.5;
        infos.magn_z_max = 0.5;

        for (int k=0; k<OPTICAL_NB; k++) {
            infos.opticals_white[k] = 0;
            infos.opticals_black[k] = 0;
        }
    }
}

struct robot_infos *infos_get()
{
    return &infos;
}

void infos_save()
{
    flash_write(INFOS_FLASH_ADDR, (void *)&infos, sizeof(infos));
}
