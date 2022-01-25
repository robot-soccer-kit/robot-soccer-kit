#ifdef HAS_TERMINAL
#include <terminal.h>
#else
#include "no_terminal.h"
#endif

#include "motion.h"

#define PGM_ORDERS  3
#define ORDERS      (PGM_ORDERS+2)

static struct motion_order orders[ORDERS];

// User (joystick) order
TERMINAL_PARAMETER_FLOAT(dx, "dx [mm/s]", 0);
TERMINAL_PARAMETER_FLOAT(dy, "dy [mm/s]", 0);
TERMINAL_PARAMETER_FLOAT(turn, "turn [deg/s]", 0);

#ifdef HAS_TERMINAL
TERMINAL_COMMAND(joy, "Joystick control")
{
    if (argc < 3) {
        dx = dy = turn = 0;
    } else {
        dx = terminal_atof(argv[0]);
        dy = terminal_atof(argv[1]);
        turn = terminal_atof(argv[2]);
    }
}
#endif

void motion_set_api_order(float dx, float dy, float turn)
{
    orders[0].enable = true;
    orders[0].dx = dx;
    orders[0].dy = dy;
    orders[0].turn = turn;
}

void motion_set_joy_order(float dx_, float dy_, float turn_)
{
    orders[1].enable = true;
    dx = dx_;
    dy = dy_;
    turn = turn_;
    orders[1].dx = dx;
    orders[1].dy = dy;
    orders[1].turn = turn;
}

void motion_set_prog_order(void *prog, float dx, float dy, float turn)
{
    int id = 0;
    int older_id = 2;
    uint32_t older = 0;

    for (int k=2; k<ORDERS; k++) {
        if (orders[k].data == prog) {
            id = k;
            break;
        }
        if (orders[k].timestamp <= older) {
            older = orders[k].timestamp;
            older_id = k;
        }
    }

    if (id == 0) {
        id = older_id;
        orders[id].data = prog;
    }

    orders[id].enable = true;
    orders[id].timestamp = millis();
    orders[id].dx = dx;
    orders[id].dy = dy;
    orders[id].turn = turn;
}

void motion_set_prog_enable(void *prog, bool enable)
{
    for (int k=2; k<ORDERS; k++) {
        if (orders[k].data == prog) {
            orders[k].enable = enable;
            break;
        }
    }
}

struct motion_order motion_get_order()
{
    struct motion_order result;
    result.dx = 0;
    result.dy = 0;
    result.turn = 0;
    motion_set_joy_order(dx, dy, turn);

    for (int k=0; k<ORDERS; k++) {
        if (orders[k].enable) {
            result.dx += orders[k].dx;
            result.dy += orders[k].dy;
            result.turn += orders[k].turn;
        }
    }

    return result;
}

void motion_em()
{
    dx = dy = turn = 0;

    for (int k=0; k<ORDERS; k++) {
        orders[k].enable = false;
        orders[k].dx = 0;
        orders[k].dy = 0;
        orders[k].turn = 0;
    }
}

float get_dx()
{
    return motion_get_order().dx;
}

float get_dy()
{
  return motion_get_order().dy;
}

float get_turn()
{
  return motion_get_order().turn;
}

