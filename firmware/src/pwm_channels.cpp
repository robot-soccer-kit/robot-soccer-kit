#include "pwm_channels.h"

static int channel = 0;

int pwm_channel_allocate()
{
  int allocated = channel;
  channel += 1;

  return channel;
}