#include "buzzer.h"
#include "voltage.h"
#include "hardware.h"
#ifdef HAS_TERMINAL
#include <terminal.h>
#endif

// Config
HardwareTimer           timer(2);

// Partitions
struct buzzer_note {
    unsigned int freq;
    unsigned int duration;
};

static struct buzzer_note melody_boot[] = {
    {523, 120},
    {622, 120},
    {698, 120},
    {740, 120},
    {784, 120},
    {0, 0}
};

static struct buzzer_note melody_alert[] = {
    {0, 800},
    {600, 200},
    {0, 800},
    {600, 200},
    {0, 0}
};

static struct buzzer_note melody_alert_fast[] = {
    {2000, 100},
    {200, 100},
    {2000, 100},
    {200, 100},
    {0, 0}
};

static struct buzzer_note melody_warning[] = {
    {800, 200},
    {400, 200},
    {200, 0},
    {200, 400},
    {0, 0}
};

static struct buzzer_note melody_ok[] = {
    {698, 300/2},
    {659, 160/2},
    {0, 0}
};

static struct buzzer_note melody_custom[] = {
    {0, 0},
    {0, 0}
};

// Status
static struct buzzer_note *melody;
static struct buzzer_note *melody_repeat;
static int melody_st;
static bool initialized = false;
static unsigned int melody_num;


void buzzer_init()
{
    melody = NULL;
    pwmWrite(PIN_BUZZER, 0);
    pinMode(PIN_BUZZER, PWM);
}

void buzzer_play_note(int note)
{
    timer.pause();
    timer.setPrescaleFactor(72000000 / (note * 100));
    timer.setOverflow(100);

    if (note == 0) {
        pinMode(PIN_BUZZER, OUTPUT);
        digitalWrite(PIN_BUZZER, LOW);
    } else {
        timer.refresh();
        timer.resume();
        pinMode(PIN_BUZZER, PWM);
        pwmWrite(PIN_BUZZER, 50);
    }
}

static void buzzer_enter(struct buzzer_note *note)
{
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

void buzzer_play(unsigned int melody_num_, bool repeat)
{
    // Avoid playing another melody when there is a battery alert
    if (melody_num_ == melody_num && melody != NULL && melody_num != MELODY_CUSTOM){
        return;
    }

    if (voltage_error() && melody_num_ != MELODY_ALERT && melody_num_ != MELODY_ALERT_FAST) {
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

void buzzer_tick()
{
    if (melody != NULL) {
        if (melody->duration >= 0 && millis()-melody_st > melody->duration) {
            buzzer_enter(melody+1);
        }
    }
}

void buzzer_stop()
{
    buzzer_play_note(0);
    melody = NULL;
    melody_repeat = NULL;
}

bool buzzer_is_playing()
{
    return melody != NULL;
}

void buzzer_wait_play()
{
    while (buzzer_is_playing()) {
        buzzer_tick();
    }
}

void buzzer_beep(unsigned int freq, unsigned int duration)
{
    if (melody_num != MELODY_CUSTOM || melody_custom[0].duration != -1 || melody_custom[0].freq != freq) {
        melody_custom[0].freq = freq;
        melody_custom[0].duration = duration;
        buzzer_play(MELODY_CUSTOM);
    }
}

bool buzzer_is_melody_alert()
{
    return melody_num == MELODY_ALERT;
}
#ifdef HAS_TERMINAL
TERMINAL_COMMAND(play, "Play a melody")
{
    int melnum = atoi(argv[0]);
    terminal_io()->print("Playing melody ");
    terminal_io()->print(melnum);
    terminal_io()->println();
    buzzer_play(melnum);
}

TERMINAL_COMMAND(beep, "Plays a beep")
{
    if (argc == 2) {
        buzzer_beep(atoi(argv[0]), atoi(argv[1]));
    } else if (argc == 1) {
        buzzer_beep(atoi(argv[0]), 1000);
    } else {
        terminal_io()->println("Usage: beep freq [duration]");
    }
}
#endif
