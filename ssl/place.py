import numpy as np
from client import Client, ClientError
import time
import argparse
import field

def frame(x, y=0, orientation=0):
    if type(x) is tuple:
        x, y, orientation = x

    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x],
                     [sin,  cos, y],
                     [  0,   0,  1]])

def frame_inv(frame):
    frame_inv = np.eye(3)
    R = frame[:2, :2]
    frame_inv[:2, :2] = R.T
    frame_inv[:2, 2] = -R.T @ frame[:2, 2]
    return frame_inv

def robot_frame(robot):
    pos = robot.position
    return frame(pos[0], pos[1], robot.orientation)

def angle_wrap(alpha):
    return (alpha + np.pi) % (2 * np.pi) - np.pi

def goto(robot, target):
    if robot.has_position():
        if callable(target):
            target = target()

        x, y, orientation = target
        Ti = frame_inv(robot_frame(robot))
        target_in_robot = Ti @ np.array([x, y, 1])

        error_x = target_in_robot[0]
        error_y = target_in_robot[1]
        error_orientation = angle_wrap(orientation - robot.orientation)

        robot.control(2500*error_x, 2500*error_y, 2.5*np.rad2deg(error_orientation))

        return np.linalg.norm([error_x, error_y, error_orientation]) < 0.05
    else:
        robot.control(0, 0, 0)
        return False

def goto_wait(robot, target):
    while not goto(robot, target):
        time.sleep(0.05)

configurations = {
    'dots': [
        ['red', 1, (field.length/4, -field.width/4, np.pi)],
        ['red', 2, (field.length/4, field.width/4, np.pi)],
        ['blue', 1, (-field.length/4, field.width/4, 0)],
        ['blue', 2, (-field.length/4, -field.width/4, 0)],
    ],

    'game': [
        ['red', 1, (field.length/4, 0, np.pi)],
        ['red', 2, (field.length/2, 0, np.pi)],
        ['blue', 1, (-field.length/4, 0, 0)],
        ['blue', 2, (-field.length/2, 0, 0)],
    ],

    'side': [
        ['red', 1, (0.2, field.width/2, -np.pi/2)],
        ['red', 2, (0.6, field.width/2, -np.pi/2)],
        ['blue', 1, (-0.2, field.width/2, -np.pi/2)],
        ['blue', 2, (-0.6, field.width/2, -np.pi/2)],
    ]
}

def goto_configuration(client, target):
    targets = configurations[target]

    arrived = False
    while not arrived:
        arrived = True
        for color, index, target in targets:
            robot = client.teams[color][index]
            try:
                arrived = goto(robot, target) and arrived
            except ClientError:
                pass

        time.sleep(0.05)


if __name__ == '__main__':
    client = Client()

    parser = argparse.ArgumentParser()
    parser.add_argument('--target', '-t', type=str, default='side')
    args = parser.parse_args()

    if args.target not in configurations:
        print('Unknown target: '+args.target)
        exit()
    else:
        print('Placing to: '+args.target)

    try:
        goto_configuration(client, args.target)
    except KeyboardInterrupt:
        print('Interrupt, stopping robots')
    finally:
        client.stop()

