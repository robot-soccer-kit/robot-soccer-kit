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

def intersect(A,B,C,D):

    u = (B-A)
    v = (D-C)

    uv=np.vstack((u, -v)).T

    if(np.linalg.det(uv)==0):
        return None
    else: 
        lambdas = np.linalg.inv(uv)@(C-A)

        V = np.all(0<=lambdas) and np.all(lambdas<=1)

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
    return range(1, robot_max_number()+1)

def robot_teams() -> list:
    """
    List of possible robot team (colors)

    :return list: possible robot colors
    """    
    return ['green', 'blue']

def all_robots() -> list:
    """
    List of all possible robots (eg: ['blue', 1])

    :return list: robots
    """    
    return [
        (color, id)
        for color in robot_teams()
        for id in robot_numbers()
    ]

def robot_id(color:str, number:int) -> str:
    """
    Transforms a robot tuple (eg: ['blue', 1]) to a robot string (eg: 'blue1')

    :param str color: robot color (eg: "blue")
    :param int number: robot number (eg: 1)
    :return str: robot id (eg: blue1)
    """    
    return '%s%d' % (color, number)

def all_robots_id() -> list:
    """
    Returns all possible robot id (eg "blue1")

    :return list: robot ids
    """    
    return [robot_id(*robot) for robot in all_robots()]