"""
Renders synthetic camera images of the field (ArUco markers of the field corners and robots, orange
ball), to test the detection pipeline without a camera.
"""

import math

import cv2
import numpy as np

from rsk import constants
from rsk.field import Field

WIDTH, HEIGHT = 1920, 1080
# Default focal for a 1080p image (see video.py)
FOCAL = 885.0
INTRINSIC = np.array(
    [[FOCAL, 0, WIDTH / 2], [0, FOCAL, HEIGHT / 2], [0, 0, 1]], dtype=np.float64
)
DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ROBOT_IDS = {"green1": 4, "green2": 5, "blue1": 6, "blue2": 7}


def camera(height=2.2, tilt_deg=0.0, yaw_deg=0.0, offset=(0.0, 0.0)):
    """
    A camera above the field, looking down

    :return: (rvec, tvec) of the field in the camera frame
    """
    looking_down = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
    tilt = cv2.Rodrigues(np.array([math.radians(tilt_deg), 0, 0]))[0]
    yaw = cv2.Rodrigues(np.array([0, 0, math.radians(yaw_deg)]))[0]
    rotation = tilt @ looking_down @ yaw
    translation = -rotation @ np.array([offset[0], offset[1], height])
    return cv2.Rodrigues(rotation)[0], translation


def project(points, cam):
    pixels, _ = cv2.projectPoints(
        np.array(points, dtype=np.float64).reshape(-1, 3), *cam, INTRINSIC, None
    )
    return pixels.reshape(-1, 2)


def draw_marker(image, marker_id, corners, cam, border=0.25):
    """
    Draws a marker (with its white border)

    :param corners: field positions (3D) of the top left, top right, bottom right and bottom left
                    corners of the black area of the marker
    """
    side = 200
    marker = cv2.aruco.generateImageMarker(DICTIONARY, marker_id, side)
    pad = int(side * border)
    marker = cv2.copyMakeBorder(
        marker, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255
    )

    corners = np.array(corners, dtype=np.float64)
    center = corners.mean(axis=0)
    outer = center + (corners - center) * (side + 2 * pad) / side

    size = marker.shape[0]
    source = np.array([[0, 0], [size, 0], [size, size], [0, size]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(
        source, project(outer, cam).astype(np.float32)
    )
    warped = cv2.warpPerspective(
        cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR), transform, (WIDTH, HEIGHT)
    )
    mask = cv2.warpPerspective(
        np.full(marker.shape, 255, np.uint8), transform, (WIDTH, HEIGHT)
    )
    image[mask > 0] = warped[mask > 0]


def robot_marker_corners(x, y, orientation):
    """
    Corners of a robot marker, its front (top edge) pointing towards the orientation
    """
    front = np.array([math.cos(orientation), math.sin(orientation)])
    left = np.array([-front[1], front[0]])
    half = constants.robot_tag_size / 2
    center = np.array([x, y])
    corners = [
        center + half * front + half * left,
        center + half * front - half * left,
        center - half * front - half * left,
        center - half * front + half * left,
    ]
    return [[cx, cy, constants.robot_height] for cx, cy in corners]


def render(robots: dict, ball=None, cam=None) -> np.ndarray:
    """
    Renders an image of the field

    :param dict robots: robot name => (x, y, orientation)
    :param ball: ball position (x, y) or None
    :param cam: camera (see camera())
    :return np.ndarray: the (BGR) image
    """
    cam = camera() if cam is None else cam
    image = np.full((HEIGHT, WIDTH, 3), (40, 120, 40), np.uint8)

    field = Field()
    for marker_id, name in enumerate(["c1", "c2", "c3", "c4"]):
        corners = field.corner_field_positions[name]
        draw_marker(image, marker_id, [[x, y, 0.0] for x, y in corners], cam)

    for name, pose in robots.items():
        draw_marker(image, ROBOT_IDS[name], robot_marker_corners(*pose), cam)

    if ball is not None:
        circle = [
            [
                ball[0] + constants.ball_radius * math.cos(alpha),
                ball[1] + constants.ball_radius * math.sin(alpha),
                constants.ball_height,
            ]
            for alpha in np.linspace(0, 2 * math.pi, 40)
        ]
        cv2.fillPoly(image, [project(circle, cam).astype(np.int32)], (0, 110, 255))

    return image


def degrade(image, rng, blur=1.0, noise=4.0, jpeg_quality=80):
    """
    Makes the image more realistic: blur, noise and JPEG compression (the camera is used in MJPG)
    """
    image = cv2.GaussianBlur(image, (0, 0), blur)
    image = np.clip(
        image.astype(np.float32) + rng.normal(0, noise, image.shape), 0, 255
    )
    _, encoded = cv2.imencode(
        ".jpg", image.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
    )
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def random_robots(rng, margin=0.1):
    """
    Random robot poses on the field, robots don't overlap
    """
    while True:
        robots = {
            name: (
                rng.uniform(
                    -constants.field_length / 2 + margin,
                    constants.field_length / 2 - margin,
                ),
                rng.uniform(
                    -constants.field_width / 2 + margin,
                    constants.field_width / 2 - margin,
                ),
                rng.uniform(-math.pi, math.pi),
            )
            for name in ROBOT_IDS
        }
        poses = list(robots.values())
        if all(
            math.dist(a[:2], b[:2]) > 2 * constants.robot_radius
            for k, a in enumerate(poses)
            for b in poses[k + 1 :]
        ):
            return robots
