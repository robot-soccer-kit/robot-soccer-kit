#pragma once

// When the robot starts
#define MELODY_BOOT       0
// When the battery is low
#define MELODY_ALERT      1
#define MELODY_ALERT_FAST 2
// When there is a warning
#define MELODY_WARNING    3
// Just some beeps
#define MELODY_OK         4
// A custom melody used by beep
#define MELODY_CUSTOM     5

void buzzer_init();
void buzzer_play(unsigned int melody, bool repeat=false);
void buzzer_tick();