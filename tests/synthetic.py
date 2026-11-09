"""
Renders synthetic camera images of the field (ArUco markers of the field corners and robots, orange
ball), to test the detection pipeline without a camera.

The camera can be placed anywhere above the field (not centered, not perpendicular to the field),
and can have a lens with radial/tangential distortion and an off-center principal point.
"""

import functools
import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from rsk import constants
from rsk.field import Field

WIDTH, HEIGHT = 1920, 1080
# Default focal for a 1080p image (see video.py)
FOCAL = 935.0
DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
ROBOT_IDS = {"green1": 4, "green2": 5, "blue1": 6, "blue2": 7}

# A wide angle lens with a strong barrel distortion and an off-center principal point, used to
# test the lens calibration
DISTORTED_LENS = dict(
    focal=935.0,
    principal_offset=(40, -25),
    distortion=(-0.12, 0.03, 0.0005, -0.0003, 0.0),
)

# Images with distortion are rendered without distortion on a larger canvas, then distorted
CANVAS_SCALE = 2.0


@dataclass
class Camera:
    """
    A camera above the field

    :param height: height of the camera [m]
    :param offset: (x, y) position of the camera above the field [m]
    :param roll, pitch: rotation of the camera with respect to looking straight down [deg]
    :param yaw: rotation of the camera around the vertical axis [deg]
    :param focal: real focal of the camera [px]
    :param principal_offset: offset of the principal point with respect to the image center [px]
    :param distortion: OpenCV distortion coefficients (k1, k2, p1, p2, k3)
    """

    height: float = 2.2
    offset: tuple = (0.0, 0.0)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    focal: float = FOCAL
    principal_offset: tuple = (0.0, 0.0)
    distortion: tuple = field(default_factory=lambda: (0.0, 0.0, 0.0, 0.0, 0.0))

    def extrinsic(self):
        """
        :return: (rvec, tvec) of the field in the camera frame
        """
        looking_down = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
        tilt = cv2.Rodrigues(
            np.array([math.radians(self.pitch), math.radians(self.roll), 0])
        )[0]
        yaw = cv2.Rodrigues(np.array([0, 0, math.radians(self.yaw)]))[0]
        rotation = tilt @ looking_down @ yaw
        translation = -rotation @ np.array(
            [self.offset[0], self.offset[1], self.height]
        )
        return cv2.Rodrigues(rotation)[0], translation

    def intrinsic(self, canvas=False):
        width, height = (WIDTH, HEIGHT)
        if canvas:
            width, height = width * CANVAS_SCALE, height * CANVAS_SCALE
        return np.array(
            [
                [self.focal, 0, width / 2 + self.principal_offset[0]],
                [0, self.focal, height / 2 + self.principal_offset[1]],
                [0, 0, 1],
            ],
            dtype=np.float64,
        )

    def has_distortion(self) -> bool:
        return any(self.distortion)

    def project(self, points, canvas=False):
        """
        Projects field points (3D) on the image (or on the undistorted canvas)
        """
        distortion = None if canvas else np.array(self.distortion, dtype=np.float64)
        pixels, _ = cv2.projectPoints(
            np.array(points, dtype=np.float64).reshape(-1, 3),
            *self.extrinsic(),
            self.intrinsic(canvas),
            distortion,
        )
        return pixels.reshape(-1, 2)


def camera(height=2.2, tilt_deg=0.0, yaw_deg=0.0, offset=(0.0, 0.0)) -> Camera:
    return Camera(height=height, pitch=tilt_deg, yaw=yaw_deg, offset=offset)


def draw_texture(image, texture, corners, cam: Camera, canvas: bool):
    """
    Draws a planar texture

    :param texture: the texture (grayscale or BGR image)
    :param corners: positions (3D, field frame) of the top left, top right, bottom right and bottom
                    left corners of the texture
    """
    if texture.ndim == 2:
        texture = cv2.cvtColor(texture, cv2.COLOR_GRAY2BGR)
    height, width = texture.shape[:2]
    source = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32
    )
    transform = cv2.getPerspectiveTransform(
        source, cam.project(corners, canvas).astype(np.float32)
    )
    shape = (image.shape[1], image.shape[0])
    warped = cv2.warpPerspective(texture, transform, shape, flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(
        np.full((height, width), 255, np.uint8), transform, shape
    )
    image[mask > 0] = warped[mask > 0]


def draw_marker(image, marker_id, corners, cam: Camera, canvas: bool, border=0.25):
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
    draw_texture(image, marker, outer, cam, canvas)


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


@functools.lru_cache(maxsize=8)
def distortion_maps(focal, principal_offset, distortion):
    """
    For each pixel of the distorted image, position of the corresponding pixel on the undistorted
    canvas
    """
    cam = Camera(focal=focal, principal_offset=principal_offset, distortion=distortion)
    xs, ys = np.meshgrid(
        np.arange(WIDTH, dtype=np.float32), np.arange(HEIGHT, dtype=np.float32)
    )
    pixels = np.stack([xs.ravel(), ys.ravel()], axis=1).reshape(-1, 1, 2)
    undistorted = cv2.undistortPoints(
        pixels,
        cam.intrinsic(),
        np.array(distortion, dtype=np.float64),
        P=cam.intrinsic(canvas=True),
        criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-6),
    ).reshape(HEIGHT, WIDTH, 2)
    return undistorted[..., 0].astype(np.float32), undistorted[..., 1].astype(
        np.float32
    )


def render(robots: dict, ball=None, cam: Camera = None) -> np.ndarray:
    """
    Renders an image of the field

    :param dict robots: robot name => (x, y, orientation)
    :param ball: ball position (x, y) or None
    :param Camera cam: the camera
    :return np.ndarray: the (BGR) image
    """
    cam = Camera() if cam is None else cam
    canvas = cam.has_distortion()
    image = new_image(cam, (40, 120, 40))

    field = Field()
    for marker_id, name in enumerate(["c1", "c2", "c3", "c4"]):
        corners = field.corner_field_positions[name]
        draw_marker(image, marker_id, [[x, y, 0.0] for x, y in corners], cam, canvas)

    for name, pose in robots.items():
        draw_marker(image, ROBOT_IDS[name], robot_marker_corners(*pose), cam, canvas)

    if ball is not None:
        circle = [
            [
                ball[0] + constants.ball_radius * math.cos(alpha),
                ball[1] + constants.ball_radius * math.sin(alpha),
                constants.ball_height,
            ]
            for alpha in np.linspace(0, 2 * math.pi, 40)
        ]
        cv2.fillPoly(
            image, [cam.project(circle, canvas).astype(np.int32)], (0, 110, 255)
        )

    return apply_distortion(image, cam, (40, 120, 40))


def new_image(cam: Camera, color) -> np.ndarray:
    """
    A new image (the larger undistorted canvas if the camera has a distortion)
    """
    scale = CANVAS_SCALE if cam.has_distortion() else 1
    return np.full((int(HEIGHT * scale), int(WIDTH * scale), 3), color, np.uint8)


def apply_distortion(image, cam: Camera, background) -> np.ndarray:
    """
    Distorts an image rendered on the undistorted canvas (no-op without distortion)
    """
    if not cam.has_distortion():
        return image
    map_x, map_y = distortion_maps(
        cam.focal, tuple(cam.principal_offset), tuple(cam.distortion)
    )
    return cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR, borderValue=background)


def corners_visible(cam: Camera, margin=0.3) -> bool:
    """
    Is the whole field (with the given margin around) visible by the camera?
    """
    points = [
        [
            sx * (constants.field_length / 2 + margin),
            sy * (constants.field_width / 2 + margin),
            0,
        ]
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    pixels = cam.project(points)
    return bool(np.all((pixels >= 0) & (pixels < [WIDTH, HEIGHT])))


def random_camera(rng, distortion=(0.0, 0.0, 0.0, 0.0, 0.0), principal_offset=(0, 0)):
    """
    A random camera pose: not centered, not perpendicular to the field, but seeing the whole field
    """
    while True:
        cam = Camera(
            height=rng.uniform(1.9, 2.6),
            offset=(rng.uniform(-0.25, 0.25), rng.uniform(-0.3, 0.3)),
            roll=rng.uniform(-8, 8),
            pitch=rng.uniform(-8, 8),
            yaw=rng.choice([0, 90, 180, 270]) + rng.uniform(-6, 6),
            principal_offset=principal_offset,
            distortion=distortion,
        )
        if corners_visible(cam):
            return cam


def degrade(image, rng, blur=1.0, noise=4.0, jpeg_quality=80):
    """
    Makes the image more realistic: blur, noise and JPEG compression (the camera is used in MJPG)
    """
    image = cv2.GaussianBlur(image, (0, 0), blur)

    # Gaussian noise (computed with OpenCV in 16 bits integers, much faster than numpy floats)
    cv2.setRNGSeed(int(rng.integers(2**31)))
    noise_image = np.empty(image.shape, np.int16)
    cv2.randn(noise_image, 0, noise)
    image = cv2.add(image.astype(np.int16), noise_image)
    image = np.clip(image, 0, 255).astype(np.uint8)

    _, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
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


def board_view(
    cam: Camera, board, rng, square_pixels=60, margin_squares=0.5, position=None
):
    """
    Renders a view of a calibration board (ChArUco) held in front of the camera, at a random
    position in the image (including the corners), distance and tilt

    :param position: position of the board center in the image, as a fraction of its size (x, y),
                     random if None

    :return: the (BGR) image
    """
    margin = int(margin_squares * square_pixels)
    squares_x, squares_y = board.getChessboardSize()
    texture = board.generateImage(
        (
            squares_x * square_pixels + 2 * margin,
            squares_y * square_pixels + 2 * margin,
        ),
        marginSize=margin,
    )
    meters_per_pixel = board.getSquareLength() / square_pixels
    height, width = texture.shape[:2]
    # Texture corners in the board frame (x right, y down, z behind the board)
    local = (
        np.array(
            [
                [-margin, -margin, 0],
                [width - margin, -margin, 0],
                [width - margin, height - margin, 0],
                [-margin, height - margin, 0],
            ],
            dtype=np.float64,
        )
        * meters_per_pixel
    )
    local -= [
        (squares_x / 2) * board.getSquareLength(),
        (squares_y / 2) * board.getSquareLength(),
        0,
    ]

    # Board orientation: facing the camera (up), rotated and tilted randomly
    facing_up = np.diag([1.0, -1.0, -1.0])
    yaw = cv2.Rodrigues(np.array([0, 0, rng.uniform(-math.pi, math.pi)]))[0]
    axis = rng.uniform(-1, 1, 2)
    axis = np.array([*(axis / np.linalg.norm(axis)), 0]) * math.radians(
        rng.uniform(0, 45)
    )
    rotation = cv2.Rodrigues(axis)[0] @ yaw @ facing_up

    # Board center: on the ray of a random pixel, at a random distance from the camera
    if position is None:
        position = (rng.uniform(0.05, 0.95), rng.uniform(0.05, 0.95))
    pixel = [position[0] * WIDTH, position[1] * HEIGHT]
    ray = np.linalg.inv(cam.intrinsic()) @ [*pixel, 1.0]
    rvec, tvec = cam.extrinsic()
    camera_rotation = cv2.Rodrigues(rvec)[0]
    center = camera_rotation.T @ (
        ray / np.linalg.norm(ray) * rng.uniform(0.6, 1.4) - tvec
    )

    corners = [center + rotation @ point for point in local]
    image = new_image(cam, (128, 128, 128))
    draw_texture(image, texture, corners, cam, cam.has_distortion())
    return apply_distortion(image, cam, (128, 128, 128))


def calibration_board_views(cam: Camera, rng, noisy=False, max_images=300):
    """
    Views of the calibration board, accepted like in a live calibration (board still and in a new
    position), until the calibration is ready (enough views covering the whole image). Like a
    user would do, the board is moved in turn in each zone of the image that is not covered enough
    yet (including the corners), with random distances and tilts.

    :return: list of images
    """
    from rsk import lens_calibration

    columns, rows = lens_calibration.COVERAGE_CELLS
    # Centers of the coverage cells, the board is pushed towards the image borders
    positions = [
        (
            np.interp(column, [0, columns - 1], [0.06, 0.94]),
            np.interp(row, [0, rows - 1], [0.08, 0.92]),
        )
        for row in range(rows)
        for column in range(columns)
    ]

    collector = lens_calibration.ViewCollector(min_interval=0.0)
    images = []
    for k in range(max_images):
        # Like a user, the board is moved to the zones that are not covered enough yet
        coverage = collector.coverage()
        missing = [
            position
            for index, position in enumerate(positions)
            if coverage[index // columns][index % columns]
            < lens_calibration.COVERAGE_GOOD
        ]
        x, y = (missing or positions)[k % len(missing or positions)]
        position = (x + rng.uniform(-0.04, 0.04), y + rng.uniform(-0.04, 0.04))
        image = board_view(cam, collector.board, rng, position=position)
        if noisy:
            image = degrade(image, rng)
        # Twice the same image: the board is still
        collector.process(image)
        if collector.process(image):
            images.append(image)
        if collector.ready():
            return images

    raise RuntimeError(
        "The synthetic views don't allow to calibrate: " + collector.not_ready_reason()
    )
