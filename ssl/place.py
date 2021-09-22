import numpy as np
import client
import scipy.linalg as sl
import time
import argparse
import field

def frame(x, y, orientation):
    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x],
                     [sin,  cos, y],
                     [  0,   0,  1]])

def robot_frame(robot):
    pos = robot.position
    return frame(pos[0], pos[1], robot.orientation)

def goto(robot, target):
    if robot.has_position() and robot.age() < 1:
        if callable(target):
            target_frame = target()
        else:
            target_frame = target
        error = np.linalg.inv(robot_frame(robot)) @ target_frame
        twist = sl.logm(error)
        dx, dy, dt = twist[0, 2], twist[1, 2], twist[1, 0]
        robot.control(2500*dx, 2500*dy, 2.5*np.rad2deg(dt))

        return np.linalg.norm([dx, dy, dt]) < 0.05
    else:
        robot.control(0, 0, 0)
        return False

def goto_wait(robot, target):
    while not goto(robot, target):
        time.sleep(0.05)

configurations = {
    'dots': [
        ['red', 1, frame(field.length/4, -field.width/4, np.pi)],
        ['red', 2, frame(field.length/4, field.width/4, np.pi)],
        ['blue', 1, frame(-field.length/4, field.width/4, 0)],
        ['blue', 2, frame(-field.length/4, -field.width/4, 0)],
    ],

    'game': [
        ['red', 1, frame(field.length/4, 0, np.pi)],
        ['red', 2, frame(field.length/2, 0, np.pi)],
        ['blue', 1, frame(-field.length/4, 0, 0)],
        ['blue', 2, frame(-field.length/2, 0, 0)],
    ],

    'side': [
        ['red', 1, frame(field.length/2 - 0.2, field.width/2, -np.pi/2)],
        ['red', 2, frame(field.length/2 - 0.4, field.width/2, -np.pi/2)],
        ['blue', 1, frame(field.length/2 - 0.6, field.width/2, -np.pi/2)],
        ['blue', 2, frame(field.length/2 - 0.8, field.width/2, -np.pi/2)],
    ]
}

def goto_configuration(target):
    targets = configurations[target]

    arrived = False
    while not arrived:
        arrived = True
        for color, index, target in targets:
            robot = controllers[color].robots[index]
            arrived = goto(robot, target) and arrived

        time.sleep(0.05)

def stop_all():
    for color in controllers:
        for index in 1, 2:
            try:
                controllers[color].robots[index].control(0, 0, 0)
            except Exception:
                pass
        controllers[color].stop()

controllers = client.all_controllers()

if __name__ == '__main__':


    parser = argparse.ArgumentParser()
    parser.add_argument('--target', '-t', type=str, default='side')
    args = parser.parse_args()

    if args.target not in configurations:
        print('Unknown target: '+args.target)
        exit()
    else:
        print('Placing to: '+args.target)

    try:
        goto_configuration(args.target)
        
        for color in controllers:
            stop_all()
            controllers[color].stop()
    except KeyboardInterrupt:
        print('Interrupt, stopping robots')
        stop_all()

