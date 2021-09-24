#ifndef _BUTTONS_H
#define _BUTTONS_H

void buttons_tick();
bool button_is_pressed(int k);
int get_button_raw_value(int k);
void show_buttons_raw_values();

#endif