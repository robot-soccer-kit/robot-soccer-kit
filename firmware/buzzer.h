#ifndef _BUZZER_H
#define _BUZZER_H

/**
 * Robot melodies
 */

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
/**
 * Initializes the buzzer
 */
void buzzer_init();

/**
 * Plays a melody
 *
 * @param melody The melody id (see MELODY_*)
 * @param repeat Does the melody repeats continuously?
 */
void buzzer_play(unsigned int melody, bool repeat=false);

/**
 * Stops playing any sound
 */
void buzzer_stop();

/**
 * Ticking the buzzer
 */
void buzzer_tick();

/**
 * Is the buzzer playing?
 */
bool buzzer_is_playing();

/**
 * Wait the end of the play
 */
void buzzer_wait_play();

/**
 * Plays a beep
 *
 * @param freq     The frequency (hz)
 * @param duration The duration (ms)
 */
void buzzer_beep(unsigned int freq, unsigned int duration);

/**
 * Is the playing melody MELODY_ALERT.
 */
bool buzzer_is_melody_alert();

#endif
