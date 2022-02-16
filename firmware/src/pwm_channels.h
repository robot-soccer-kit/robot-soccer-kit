#pragma once

/**
 * This is just incrementing a number and returning it, it is meant to be used to allocate PWM channels by
 * devices that needs it to avoid conflicts
 */
int pwm_channel_allocate();