#ifndef ___RHOCK_STREAM_H
#define ___RHOCK_STREAM_H

extern bool api_control;
extern short api_dx;
extern short api_dy;
extern short api_turn;
void api_disable();

#define RHOCK_CONTROLS 16
extern short rhock_controls[RHOCK_CONTROLS];

#endif
