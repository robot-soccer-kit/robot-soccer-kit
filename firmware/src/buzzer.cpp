#include <Arduino.h>
#include "pinout.h"
#include "shell.h"

void buzzer_init()
{
  ledcSetup(10, 500, 10);
  ledcAttachPin(BUZZER, 10);
}

SHELL_COMMAND(beep, "Beep")
{
  if (argc) {
    ledcWriteTone(10, atoi(argv[0]));
    delay(500);
    ledcWriteTone(10, 0);
  }
}

