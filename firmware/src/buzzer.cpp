#include "buzzer.h"
#include "config.h"
#include "pwm_channels.h"
#include "shell.h"
#include "voltage.h"
#include <Arduino.h>

static int buzzer_pwm_channel;

struct buzzer_note {
  unsigned int freq;
  unsigned int duration;
};

static struct buzzer_note melody_boot[] = {{523, 120}, {622, 120}, {698, 120},
                                           {740, 120}, {784, 120}, {0, 0}};

static struct buzzer_note melody_alert[] = {
    {0, 800}, {600, 200}, {0, 800}, {600, 200}, {0, 0}};

static struct buzzer_note melody_alert_fast[] = {
    {2000, 100}, {200, 100}, {2000, 100}, {200, 100}, {0, 0}};

static struct buzzer_note melody_warning[] = {
    {800, 200}, {400, 200}, {200, 0}, {200, 400}, {0, 0}};

static struct buzzer_note melody_ok[] = {
    {698, 300 / 2}, {659, 160 / 2}, {0, 0}};

static struct buzzer_note melody_custom[] = {{0, 0}, {0, 0}};

// Status
static struct buzzer_note *melody;
static struct buzzer_note *melody_repeat;
static unsigned long melody_st;
static bool initialized = false;
static unsigned int melody_num;

void buzzer_init() {
  buzzer_pwm_channel = pwm_channel_allocate();
  ledcSetup(buzzer_pwm_channel, 500, 10);
  ledcAttachPin(BUZZER, buzzer_pwm_channel);
}

void buzzer_play_note(int note) { ledcWriteTone(buzzer_pwm_channel, note); }

static void buzzer_enter(struct buzzer_note *note) {
  buzzer_play_note(note->freq);
  melody = note;
  melody_st = millis();

  if (note->freq == 0 && note->duration == 0) {
    if (melody_repeat != NULL) {
      buzzer_enter(melody_repeat);
    } else {
      melody = NULL;
    }
  }
}

void buzzer_play(unsigned int melody_num_, bool repeat) {
  // Avoiding entering a melody that is not over yet
  if (melody_num_ == melody_num && melody != NULL &&
      melody_num != MELODY_CUSTOM) {
    return;
  }

  // Avoid playing another melody when there is a battery alert
  if (voltage_is_error() && melody_num_ != MELODY_ALERT &&
      melody_num_ != MELODY_ALERT_FAST) {
    return;
  }

  if (!initialized) {
    buzzer_init();
    initialized = true;
  }

  struct buzzer_note *to_play = NULL;
  melody_num = melody_num_;

  if (melody_num == MELODY_BOOT) {
    to_play = &melody_boot[0];
  } else if (melody_num == MELODY_ALERT) {
    to_play = &melody_alert[0];
  } else if (melody_num == MELODY_ALERT_FAST) {
    to_play = &melody_alert_fast[0];
  } else if (melody_num == MELODY_WARNING) {
    to_play = &melody_warning[0];
  } else if (melody_num == MELODY_OK) {
    to_play = &melody_ok[0];
  } else if (melody_num == MELODY_CUSTOM) {
    to_play = &melody_custom[0];
  } else {
    melody = NULL;
  }

  if (to_play) {
    melody_repeat = repeat ? to_play : NULL;
    buzzer_enter(to_play);
  }
}

void buzzer_tick() {
  if (melody != NULL) {
    if (melody->duration >= 0 && millis() - melody_st > melody->duration) {
      buzzer_enter(melody + 1);
    }
  }
}

void buzzer_stop() {
  buzzer_play_note(0);
  melody = NULL;
  melody_repeat = NULL;
}

bool buzzer_is_playing() { return melody != NULL; }

void buzzer_beep(unsigned int freq, unsigned int duration) {
  if (melody_num != MELODY_CUSTOM || melody_custom[0].duration != -1 ||
      melody_custom[0].freq != freq) {
    melody_custom[0].freq = freq;
    melody_custom[0].duration = duration;
    buzzer_play(MELODY_CUSTOM);
  }
}

SHELL_COMMAND(play, "Play a melody") {
  if (argc) {
    buzzer_play(atoi(argv[0]));
  } else {
    shell_stream()->println("Usage: play [melody #]");
  }
}

SHELL_COMMAND(beep, "Beep") {
  if (argc) {
    buzzer_beep(atoi(argv[0]), 500);
  } else {
    shell_stream()->println("Usage: beep [frequency]");
  }
}
