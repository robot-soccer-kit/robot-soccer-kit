#ifndef _MUX_H
#define _MUX_H

#include <stdint.h>
#include <wirish/wirish.h>

struct muxs
{
    // Motor quadrature phases bits
    int p1a, p1b;
    int p2a, p2b;
    int p3a, p3b;
    // Optical sensors
    int opticals[7];
    // Buttons
    int buttons[4];
    // Distance sensors
    int distance;
    // Voltage
    int voltage1;
    int voltage2;
    // Reserved
    int in1;
    int in2;
    // Dummy
    int dummy;
};

/**
 * Values are polled by call in mux_tick() and available in the
 * multiplexers global variable
 */
extern volatile struct muxs multiplexers;

/**
 * Initializes the multiplexer
 */
void mux_init();

/**
 * Sample the multiplexer pins
 */
bool mux_tick();

#endif
