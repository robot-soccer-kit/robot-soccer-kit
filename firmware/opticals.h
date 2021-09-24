#ifndef _OPTICALS_H
#define _OPTICALS_H

extern int opticals[];

/**
 * Initializes the opticals system
 */
void opticals_init();

/**
 * Ticks the opticals system
 */
void opticals_tick();

/**
 * Called by the multiplexer cycle each time a whole cycle of reading all the
 * sensors is over
 */
void opticals_cycle();

/**
 * Gets the value of the ith optical
 *
 * @param  i Index of the optical
 */
int optical_get(int i);

/**
 * Getting the value of an optical, post correction (0 to 1024)
 */
int optical_get_corrected(int i);

float opticals_get_position();
float opticals_get_quantity();
int get_opticals_individual_quantity(int k);

/**
 * Calibrate the opticals
 */
void opticals_calibrate(bool black);

/**
 * Show opticals raw values on the terminal output.
 */
void show_opticals_raw_values();

#endif
