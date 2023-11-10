import numpy as np

"""
This file contains all relevant constants. It can be dimension of items or values from
the rules.
"""

# Field dimension
field_length: float = 1.84  # [m] (x axis)
field_width: float = 1.23  # [m] (y axis)

# Carpet dimension
carpet_length: float = 2.45  # [m] (x axis)
carpet_width: float = 1.84  # [m] (y axis)

# Goals size
goal_width: float = 0.6  # [m]
goal_virtual_height: float = 0.1  # [m]

# Side of the (green) border we should be able to see around the field
border_size: float = 0.3  # [m]

# Dots coordinates (x, y)
dots_x: float = 0.45  # [m]
dots_y: float = 0.305  # [m]

# Defense area
defense_area_width = 0.9  # [m]
defense_area_length = 0.3  # [m]

# Timed circle radius and maximum time before being penalized
timed_circle_radius: float = 0.25  # [m]
timed_circle_time: float = 3 # [s]

# Margin for ball re-placement (on the center or on dots)
place_ball_margin: float = 0.05  # [m]

# Margins for being in and out the field
field_in_margin: float = -0.08  # [m]
field_out_margin: float = 0.02  # [m]

# Tag sizes
corner_tag_size: float = 0.16  # [m]
corner_tag_border: float = 0.025  # [m]
robot_tag_size: float = 0.08  # [m]

# Heights
robot_height: float = 0.076  # [m]
ball_radius: float = 0.021  # [m]

# We detect the center of the orange blog to see the ball, and not the top of the ball
# that is why we use the radius here instead of the diameter
ball_height: float = ball_radius  # [m]

# Durations
game_duration: float = 300.0  # [s]
halftime_duration: float = 120.0  # [s]
default_penalty: float = 5.0  # [s]
grace_time: float = 3.0  # [s]

# Number of penalty spots
penalty_spots: int = 8
penalty_spot_lock_time: int = 1
# Parameters
referee_history_size: int = 3

# For simulation
robot_mass: float = 0.710  # [kg]
max_linear_acceleration: float = 3  # [m.s^-2]
max_angular_accceleration: float = 50  # [rad.s^-2]
ball_mass: float = 0.008  # [kg]
ball_deceleration: float = 0.3  # [m.s^-2]
kicker_x_tolerance: float = 0.03  # [m]
kicker_y_tolerance: float = 0.065  # [m]

# Wheel radius [m]
wheel_radius: float = 0.035

# Distance between its center and wheels [m]
wheel_center_spacing: float = 0.0595

# Robot radius [m]
robot_radius: float = 0.088


def goal_posts(x_positive: bool = True) -> np.ndarray:
    """
    Returns the coordinates of the goal posts
    :param x_positive: True if the goal is on the positive x axis, False otherwise
    :return: The coordinates of the goal posts
    """
    sign = 1 if x_positive else -1

    return np.array([[sign * field_length / 2, -goal_width / 2.0], [sign * field_length / 2, goal_width / 2]])


def field_corners(margin: float = 0) -> np.ndarray:
    """
    Returns the coordinates of the field corners with margins (For goals and sideline)
    :param margin: Margin to add to the field
    :return: The coordinates of the field corners
    """
    return [
        np.array([sign1 * ((field_length / 2.0) + margin), sign2 * ((field_width / 2.0) + margin)])
        for sign1, sign2 in [[1, 1], [1, -1], [-1, -1], [-1, 1]]
    ]


def defense_area(x_positive: bool = True) -> np.ndarray:
    """
    Returns the coordinates of the defense area
    :param x_positive: True if the goal is on the positive x axis, False otherwise
    :return: The coordinates of the defense area
    """
    if x_positive:
        return [
            [field_length / 2 - defense_area_length, -defense_area_width / 2],
            [field_length / 2 + defense_area_length, defense_area_width / 2],
        ]
    else:
        return [
            [-field_length / 2 - defense_area_length, -defense_area_width / 2],
            [-field_length / 2 + defense_area_length, defense_area_width / 2],
        ]
