import numpy as np

def frame(x, y=0, orientation=0):
    if type(x) is tuple:
        x, y, orientation = x

    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x],
                     [sin,  cos, y],
                     [0,   0,  1]])


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