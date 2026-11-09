"""
Camera lens calibration (focal, principal point and distortion) with a ChArUco board (a chessboard
with ArUco markers in its white squares).

The board can be partially visible, which allows to bring it in the corners of the image, where the
distortion of wide angle lenses is the largest.

This module is used by the Game Controller (Camera tab) and by the command line tool
(python -m rsk.calibrate_camera).
"""

import math
import time
import datetime

import cv2
import numpy as np

# Board: 9x6 squares, 5x5 ArUco markers (different from the 4x4 markers of the field and robots)
BOARD_SQUARES = (9, 6)
SQUARE_LENGTH = 0.030  # [m] (only used to scale the board pose, not the intrinsics)
MARKER_LENGTH = 0.022  # [m]
DICTIONARY = cv2.aruco.DICT_5X5_100

# Minimum number of chessboard corners detected for a view to be used
MIN_CORNERS = 12
# Minimum number of views to calibrate
MIN_VIEWS = 30

# Coverage grid of the image (columns, rows)
COVERAGE_CELLS = (6, 4)
# Number of board corners in a cell for it to be considered covered: all the cells should be
# covered (green) to calibrate
COVERAGE_GOOD = 30

# How long the capture of a view is shown on the image [s]
CAPTURE_FEEDBACK_DURATION = 0.8


def is_supported() -> bool:
    """
    ChArUco boards detection needs OpenCV >= 4.7
    """
    return hasattr(cv2, "aruco") and hasattr(cv2.aruco, "CharucoDetector")


def make_board():
    dictionary = cv2.aruco.getPredefinedDictionary(DICTIONARY)
    return cv2.aruco.CharucoBoard(
        BOARD_SQUARES, SQUARE_LENGTH, MARKER_LENGTH, dictionary
    )


def board_image(square_pixels: int = 300, margin_pixels: int = 150) -> np.ndarray:
    """
    Image of the board, to be printed (its size doesn't matter)
    """
    size = (
        BOARD_SQUARES[0] * square_pixels + 2 * margin_pixels,
        BOARD_SQUARES[1] * square_pixels + 2 * margin_pixels,
    )
    return make_board().generateImage(size, marginSize=margin_pixels)


def detect_board(image, detector, board):
    """
    Detects the board in an image

    :return: (object_points, image_points) or None if the board is not (enough) visible
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    charuco_corners, charuco_ids, _, _ = detector.detectBoard(gray)

    if charuco_corners is None or len(charuco_corners) < MIN_CORNERS:
        return None

    object_points, image_points = board.matchImagePoints(charuco_corners, charuco_ids)
    if object_points is None or len(object_points) < MIN_CORNERS:
        return None

    return object_points.reshape(-1, 3), image_points.reshape(-1, 2)


def calibrate(views: list, image_size: tuple) -> dict:
    """
    Calibrates the camera

    :param list views: list of (object_points, image_points)
    :param tuple image_size: (width, height)
    :return dict: calibration result
    """
    if len(views) < MIN_VIEWS:
        raise ValueError(f"At least {MIN_VIEWS} views are needed, got {len(views)}")

    object_points = [np.asarray(o, dtype=np.float32) for o, _ in views]
    image_points = [np.asarray(i, dtype=np.float32) for _, i in views]

    rms, intrinsic, distortion, _, _ = cv2.calibrateCamera(
        object_points, image_points, image_size, None, None
    )
    distortion = distortion.ravel()

    width, height = image_size
    focal = (intrinsic[0, 0] + intrinsic[1, 1]) / 2

    # How much the distortion moves the points in the corners of the image
    corners = np.array(
        [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]],
        dtype=np.float64,
    ).reshape(-1, 1, 2)
    undistorted = cv2.undistortPoints(
        corners, intrinsic, distortion, P=intrinsic
    ).reshape(-1, 2)
    corner_displacement = float(
        np.max(np.linalg.norm(undistorted - corners.reshape(-1, 2), axis=1))
    )

    return {
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "image_size": [int(width), int(height)],
        "views": len(views),
        "rms_reprojection_error_px": float(rms),
        "focal_px": [float(intrinsic[0, 0]), float(intrinsic[1, 1])],
        "principal_point_px": [float(intrinsic[0, 2]), float(intrinsic[1, 2])],
        "principal_point_offset_px": [
            float(intrinsic[0, 2] - width / 2),
            float(intrinsic[1, 2] - height / 2),
        ],
        # OpenCV model: k1, k2, p1, p2, k3
        "distortion": [float(d) for d in distortion[:5]],
        "distortion_at_image_corners_px": corner_displacement,
        # Value of the "focal" setting of the Game Controller (defined for a 1080p image)
        "rsk_focal_setting": float(focal * 1080 / height),
        "diagonal_fov_deg": float(
            2 * math.degrees(math.atan(math.hypot(width / 2, height / 2) / focal))
        ),
    }


def intrinsics_for_image(
    calibration: dict, raw_size: tuple, crop_x=100, crop_y=100, rescale=100
):
    """
    Intrinsic parameters for the image processed by the detection, which is cropped (centered) and
    rescaled (see video.py)

    :param dict calibration: calibration result (see calibrate())
    :param tuple raw_size: size of the image captured by the camera (width, height)
    :return: (intrinsic matrix, distortion) or None if the calibration was done with another
             image size
    """
    if tuple(calibration["image_size"]) != tuple(raw_size):
        return None

    width, height = raw_size
    intrinsic = np.array(
        [
            [calibration["focal_px"][0], 0, calibration["principal_point_px"][0]],
            [0, calibration["focal_px"][1], calibration["principal_point_px"][1]],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )

    # Cropping (centered)
    cropped = np.array([width, height])
    if crop_x < 100 or crop_y < 100:
        cropped[0] = round(width * crop_x / 100.0)
        cropped[1] = round(height * crop_y / 100.0)
        intrinsic[0, 2] -= round((width - cropped[0]) / 2.0)
        intrinsic[1, 2] -= round((height - cropped[1]) / 2.0)

    # Rescaling (pixel centers are scaled)
    if 0 < rescale < 100:
        new_size = (cropped * rescale / 100.0).astype(int)
        for axis in (0, 1):
            scale = new_size[axis] / cropped[axis]
            intrinsic[axis, axis] *= scale
            intrinsic[axis, 2] = (intrinsic[axis, 2] + 0.5) * scale - 0.5

    return intrinsic, np.array(calibration["distortion"], dtype=np.float64)


def view_key(image_points, image_size):
    """
    A descriptor of a view (position, size and shape of the board in the image), used to only keep
    views that are different enough
    """
    width, height = image_size
    center = image_points.mean(axis=0) / [width, height]
    hull = cv2.convexHull(image_points.astype(np.float32))
    area = math.sqrt(cv2.contourArea(hull)) / width
    # Elongation of the board in the image gives an idea of its tilt
    _, (w, h), angle = cv2.minAreaRect(image_points.astype(np.float32))
    elongation = min(w, h) / max(w, h, 1e-6)
    return np.array([center[0], center[1], area, elongation, math.radians(angle) / 4])


class ViewCollector:
    """
    Collects views of the board from a video stream: a view is captured automatically when the
    board is still (no motion blur) and in a new position
    """

    def __init__(self, min_interval: float = 0.7):
        self.board = make_board()
        self.detector = cv2.aruco.CharucoDetector(self.board)
        self.min_interval = min_interval

        self.views: list = []
        self.keys: list = []
        self.points: list = []
        self.image_size = None
        self.previous_points = None
        self.last_capture = 0.0
        self.last_detection = None

    def process(self, frame, force: bool = False) -> bool:
        """
        Processes a frame

        :param frame: the camera image
        :param bool force: capture the view if the board is visible, even if it is not still or
                           not in a new position
        :return bool: True if a view was captured
        """
        size = (frame.shape[1], frame.shape[0])
        if self.image_size is not None and size != self.image_size:
            # The resolution changed, previous views can't be used anymore
            self.reset()
        self.image_size = size

        detection = detect_board(frame, self.detector, self.board)
        self.last_detection = detection
        if detection is None:
            self.previous_points = None
            return False

        _, image_points = detection
        still = (
            self.previous_points is not None
            and self.previous_points.shape == image_points.shape
            and np.max(np.abs(self.previous_points - image_points)) < 1.5
        )
        self.previous_points = image_points

        key = view_key(image_points, size)
        new_view = (
            not self.keys or min(np.linalg.norm(k - key) for k in self.keys) > 0.08
        )

        if force or (
            still and new_view and time.time() - self.last_capture > self.min_interval
        ):
            self.views.append(detection)
            self.keys.append(key)
            self.points.extend(image_points.tolist())
            self.last_capture = time.time()
            return True

        return False

    def reset(self):
        self.views, self.keys, self.points = [], [], []
        self.previous_points = None

    def missing_views(self) -> int:
        """
        Number of views still needed
        """
        return max(0, MIN_VIEWS - len(self.views))

    def missing_cells(self) -> int:
        """
        Number of cells of the image that are not covered enough yet
        """
        return sum(count < COVERAGE_GOOD for row in self.coverage() for count in row)

    def ready(self) -> bool:
        """
        Are there enough views, covering the whole image, to calibrate?
        """
        return self.missing_views() == 0 and self.missing_cells() == 0

    def not_ready_reason(self) -> str:
        """
        What is still missing to calibrate (empty if ready)
        """
        reasons = []
        if self.missing_views():
            reasons.append(f"{self.missing_views()} more views are needed")
        if self.missing_cells():
            reasons.append(
                f"{self.missing_cells()} zones of the image are not covered enough (not green)"
            )
        return ", ".join(reasons)

    def coverage(self) -> list:
        """
        Number of board corners captured in each cell of the image (rows of the coverage grid)
        """
        columns, rows = COVERAGE_CELLS
        counts = np.zeros((rows, columns), dtype=int)
        if self.image_size is not None:
            width, height = self.image_size
            for x, y in self.points:
                row = min(max(int(y * rows / height), 0), rows - 1)
                column = min(max(int(x * columns / width), 0), columns - 1)
                counts[row, column] += 1
        return counts.tolist()

    def draw(self, image):
        """
        Draws the coverage, the captured corners and the detected board on the image, and shows
        when a view was just captured
        """
        height, width = image.shape[:2]
        columns, rows = COVERAGE_CELLS
        overlay = image.copy()
        for row, counts in enumerate(self.coverage()):
            for column, count in enumerate(counts):
                color = (
                    (0, 0, 255)
                    if count == 0
                    else (0, 200, 255)
                    if count < COVERAGE_GOOD
                    else (0, 200, 0)
                )
                cv2.rectangle(
                    overlay,
                    (column * width // columns, row * height // rows),
                    ((column + 1) * width // columns, (row + 1) * height // rows),
                    color,
                    -1,
                )
        cv2.addWeighted(overlay, 0.25, image, 0.75, 0, image)

        for x, y in self.points:
            cv2.circle(image, (int(x), int(y)), 2, (255, 255, 0), -1)

        if self.last_detection is not None:
            for x, y in self.last_detection[1]:
                cv2.circle(image, (int(x), int(y)), 4, (0, 255, 0), -1)

        # The capture of a view is shown for a while: green frame and message
        if self.views and time.time() - self.last_capture < CAPTURE_FEEDBACK_DURATION:
            thickness = max(10, width // 60)
            cv2.rectangle(
                image, (0, 0), (width - 1, height - 1), (0, 220, 0), 2 * thickness
            )
            text = f"Captured! ({len(self.views)})"
            scale = width / 600
            (text_width, text_height), _ = cv2.getTextSize(
                text, cv2.FONT_HERSHEY_SIMPLEX, scale, int(3 * scale)
            )
            origin = ((width - text_width) // 2, (height + text_height) // 2)
            for color, weight in (((0, 0, 0), 8), ((0, 255, 0), 3)):
                cv2.putText(
                    image,
                    text,
                    origin,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    scale,
                    color,
                    int(weight * scale),
                )

    def calibrate(self) -> dict:
        return calibrate(self.views, self.image_size)
