import numpy as np
import re


def frame(x, y=0, orientation=0):
    if type(x) is tuple:
        x, y, orientation = x

    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x], [sin, cos, y], [0, 0, 1]])


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


def intersect(A, B, C, D):

    u = B - A
    v = D - C

    uv = np.vstack((u, -v)).T

    if np.linalg.det(uv) == 0:
        return None
    else:
        lambdas = np.linalg.inv(uv) @ (C - A)

        V = np.all(0 <= lambdas) and np.all(lambdas <= 1)

        if V:
            P = A + lambdas[0] * u
            return (True, P)
        else:
            return (False, None)


def robot_max_number() -> int:
    """
    The maximum number of robots

    :return int: Maximum number of robots per team on the field
    """
    return 2


def robot_numbers() -> list:
    """
    List all possible robot numbers (starting at 1)

    :return list: robot numbers
    """
    return range(1, robot_max_number() + 1)


def robot_teams() -> list:
    """
    List of possible robot team (colors)

    :return list: possible robot team (colors)
    """
    return ["green", "blue"]


def robot_leds_color(name: str) -> list:
    """
    Returns the LEDs color for a given name

    :param str name: color name
    :return list: list of [r, g, b] values for this color
    """
    if name == "preempted":
        return [128, 0, 128]
    elif name == "blue":
        return [0, 0, 128]
    elif name == "green":
        return [0, 128, 0]
    else:
        raise NotImplemented(f"Unknown color: {name}")


def all_robots() -> list:
    """
    List of all possible robots (eg: ['blue', 1])

    :return list: robots
    """
    return [(team, number) for team in robot_teams() for number in robot_numbers()]


def robot_list2str(team: str, number: int) -> str:
    """
    Transforms a robot tuple (eg: ['blue', 1]) to a robot string (eg: 'blue1')

    :param str team: robot team (eg: "blue")
    :param int number: robot number (eg: 1)
    :return str: robot id (eg: blue1)
    """
    return "%s%d" % (team, number)


def robot_str2list(robot: str) -> list:
    """
    Transforms a robot string (eg: 'blue1') to a robot list (eg: ['blue', 1])

    :param str robot: string robot name (eg: 'blue1')
    :return list: robot id (eg: ['blue', 1])
    """
    matches = re.match("([^\d]+)([0-9]+)", robot)

    return matches[1], int(matches[2])


def all_robots_id() -> list:
    """
    Returns all possible robot id (eg "blue1")

    :return list: robot ids
    """
    return [robot_list2str(*robot) for robot in all_robots()]


def in_rectangle(point: list, bottom_left: list, top_right: list) -> bool:
    """
    Checks if a point is in a rectangle

    :param list point: the point (x, y)
    :param list bottom_left point
    :param list top_right point
    :return bool: True if the point is in the rectangle
    """
    return (np.array(point) >= np.array(bottom_left)).all() and (np.array(point) <= np.array(top_right)).all()
