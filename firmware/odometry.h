#ifndef __ODOMETRY_H
#define __ODOMETRY_H

void reset_odometry();
void odometry_tick();

float  get_odometry_x();
float  get_odometry_y();
float  get_odometry_yaw();

void odometry_control(float dx, float dy, float turn, float speed, float turnSpeed);
void odometry_goto(float x, float y, float theta, float speed, float turnSpeed);
bool odometry_reached();
void odometry_stop();
void odometry_set_goal_to_position();
void odometry_set_pos(float x, float y, float theta);

#endif
