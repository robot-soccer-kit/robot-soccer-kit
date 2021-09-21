import numpy as np
import client
import scipy.linalg as sl
import time
import argparse
import field

parser = argparse.ArgumentParser()
parser.add_argument('--target', '-t', type=str, default='side')
args = parser.parse_args()

def frame(x, y, orientation):
    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x],
                     [sin,  cos, y],
                     [  0,   0,  1]])

def robot_frame(robot):
    pos = robot.position
    return frame(pos[0], pos[1], robot.orientation)

configurations = {
    'dots': [
        ['red', 1, frame(field.length/4, field.width/4, np.pi)],
        ['red', 2, frame(field.length/4, -field.width/4, np.pi)],
        ['blue', 1, frame(-field.length/4, field.width/4, 0)],
        ['blue', 2, frame(-field.length/4, -field.width/4, 0)],
    ],

    'game': [
        ['red', 1, frame(field.length/10, 0, np.pi)],
        ['red', 2, frame(field.length/2, 0, np.pi)],
        ['blue', 1, frame(-field.length/4, 0, 0)],
        ['blue', 2, frame(-field.length/2, 0, 0)],
    ],

    'side': [
        ['red', 1, frame(field.length/2 - 0.4, field.width/2, -np.pi/2)],
        ['red', 2, frame(field.length/2 - 0.2, field.width/2, -np.pi/2)],
        ['blue', 1, frame(field.length/2 - 0.6, field.width/2, -np.pi/2)],
        ['blue', 2, frame(field.length/2 - 0.8, field.width/2, -np.pi/2)],
    ]
}

if args.target not in configurations:
    print('Unknown target: '+args.target)
    exit()
else:
    print('Placing to: '+args.target)

targets = configurations[args.target]

controllers = {
    'red': client.Controller('red'),
    'blue': client.Controller('blue')
}

def stop_all():
    for color, index, target in targets:
        controllers[color].robots[index].control(0, 0, 0)

try:
    while True:
        moved = False
        arrived = True
        for color, index, target in targets:
            robot = controllers[color].robots[index]
            if robot.has_position():
                error = np.linalg.inv(robot_frame(robot)) @ target
                twist = sl.logm(error)
                dx, dy, dt = twist[0, 2], twist[1, 2], twist[1, 0]
                try:
                    robot.control(1000*dx, 1000*dy, np.rad2deg(dt))
                    moved = True
                except Exception:
                    pass
                if np.linalg.norm([dx, dy, dt]) > 0.05:
                    arrived = False

        if moved and arrived:
            break

        time.sleep(0.05)
    
    for color in controllers:
        stop_all()
        controllers[color].stop()
except KeyboardInterrupt:
    print('Interrupt, stopping robots')
    stop_all()

