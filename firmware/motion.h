#ifndef _HOLO_SIMULATOR_MOTION_H
#define _HOLO_SIMULATOR_MOTION_H

#include <stdint.h>

struct rhock_context;

struct motion_order
{
    bool enable;
    void *data;
    uint32_t timestamp;
    float dx;
    float dy;
    float turn;
};

void motion_set_api_order(float dx, float dy, float turn);
void motion_set_joy_order(float dx, float dy, float turn);
void motion_set_prog_order(void * prog, float dx, float dy, float turn);
void motion_set_prog_enable(void *prog, bool enable);

struct motion_order motion_get_order();

void motion_em();

#endif
