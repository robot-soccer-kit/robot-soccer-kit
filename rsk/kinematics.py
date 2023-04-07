import numpy as np
from . import constants

"""
This file provide IK/FK kinematics for the robot. Note that there is an equivalent code embedded in
the robots themselfs, allowing them to compute their own kinematics. This is only intended in the case
we need to do some simulations.
"""

# Maxium wheel RPM [rotation/min]
max_wheel_rpm: float = 150

# Wheel drive direction orientations [deg]
wheel_alphas: list = [-90, 30, 150]

# Wheel drive vectors
drive_vectors = np.array([[np.cos(np.deg2rad(alpha)), np.sin(np.deg2rad(alpha))] for alpha in wheel_alphas])

# Inverse Kinematics matrix
IK: np.ndarray = (1 / constants.wheel_radius) * np.hstack(
    (drive_vectors, np.array([[constants.wheel_center_spacing] * len(wheel_alphas)]).T)
)

# Forward Kinematics matrix
FK: np.ndarray = np.linalg.pinv(IK)

# Maximum wheel speed [rad/s]
max_wheel_speed: float = max_wheel_rpm * 2 * np.pi / 60


def forward_kinematics(w: np.ndarray) -> np.ndarray:
    """
    Computes the forward kinematics (given wheel velocities [rad/s], compute the chassis velocity
    (xd [m/s], yd [m/s], thetad [rad/s]))

    Args:
        w (np.ndarray): wheel velocities (list of [rad/s])

    Returns:
        np.ndarray: chassis frame speed (xd [m/s], yd [m/s], thetad [rad/s])
    """
    return FK @ w


def inverse_kinematics(s: np.ndarray) -> np.ndarray:
    """
    Computes the inverse kinematics (given the target chassis velocity  (xd [m/s], yd [m/s], thetad [rad/s]),
    compute the wheel velocities [rad/s])

    Args:
        s (np.ndarray): (xd [m/s], yd [m/s], thetad [rad/s])

    Returns:
        np.ndarray: wheel velocities (list of [rad/s])
    """

    return IK @ s


def clip_target_order(s: np.ndarray) -> np.ndarray:
    """
    Clips the target order to a feasible one according to the maximum wheel velocities

    Args:
        s (np.ndarray): a chassis velocity (xd [m/s], yd [m/s], thetad [rad/s])

    Returns:
        np.ndarray: the clipped chassis velocity (xd [m/s], yd [m/s], thetad [rad/s])
    """

    # Compute the wheel velocities that would be needed to reach the target chassis velocity
    w = inverse_kinematics(s)

    # Computes the highest max_wheel_speed/wheel_speed ratio that would require to resize w to make it
    # feasible, while preserving the vector direction
    ratio = max(1, max(abs(w) / max_wheel_speed))

    # Since the IK/FK are linear, we can apply the same ratio to the chassis velocity
    return np.array(s) / ratio
