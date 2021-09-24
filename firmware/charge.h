#ifndef _CHARGE_H

/**
 * Initializes the charge system
 */
void charge_init();

/**
 * Enable or disable the fast carge. By default, the charging system will
 * consume a maximum of 500mA, which is the limit allowed by USB.
 * Enabling the fast charge will allow it to consume up to 1A.
 *
 * @param enable if true, the fast charge will be enabled
 */
void charge_fast(bool enable);

/**
 * Updates the charge system. This will enable the fast charge automatically
 * if the board is not connected with USB.
 */
void charge_tick();

#endif
