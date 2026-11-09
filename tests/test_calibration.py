import json

import cv2
import numpy as np
import pytest
import synthetic

from rsk import calibrate_camera

# A camera with a wide angle lens (barrel distortion) and an off-center principal point
CAMERA = synthetic.Camera(
    focal=885.0,
    principal_offset=(18, -12),
    distortion=(-0.12, 0.03, 0.0005, -0.0003, 0.0),
)


@pytest.fixture(scope="module")
def board_images():
    """
    Synthetic images of the calibration board seen by CAMERA
    """
    board = calibrate_camera.make_board()
    detector = cv2.aruco.CharucoDetector(board)
    rng = np.random.default_rng(0)

    images = []
    while len(images) < 18:
        image = synthetic.degrade(synthetic.board_view(CAMERA, board, rng), rng)
        if calibrate_camera.detect_board(image, detector, board) is not None:
            images.append(image)
    return images


def distortion_field(intrinsic, distortion):
    """
    Displacement (in pixels) caused by the lens distortion, on a grid covering the image
    """
    xs, ys = np.meshgrid(
        np.linspace(0, synthetic.WIDTH - 1, 20),
        np.linspace(0, synthetic.HEIGHT - 1, 12),
    )
    pixels = np.stack([xs.ravel(), ys.ravel()], axis=1).reshape(-1, 1, 2)
    undistorted = cv2.undistortPoints(
        pixels, intrinsic, np.array(distortion, dtype=np.float64), P=intrinsic
    )
    return (undistorted - pixels).reshape(-1, 2)


def test_generated_board_is_detected(tmp_path):
    filename = str(tmp_path / "board.png")
    calibrate_camera.generate_board(filename)

    image = cv2.imread(filename)
    board = calibrate_camera.make_board()
    object_points, _ = calibrate_camera.detect_board(
        image, cv2.aruco.CharucoDetector(board), board
    )

    squares_x, squares_y = calibrate_camera.BOARD_SQUARES
    assert len(object_points) == (squares_x - 1) * (squares_y - 1)


def test_calibration_recovers_the_camera(board_images):
    board = calibrate_camera.make_board()
    detector = cv2.aruco.CharucoDetector(board)
    views = [
        calibrate_camera.detect_board(image, detector, board) for image in board_images
    ]

    result = calibrate_camera.calibrate(views, (synthetic.WIDTH, synthetic.HEIGHT))

    assert result["rms_reprojection_error_px"] < 0.5
    assert result["focal_px"] == pytest.approx([CAMERA.focal] * 2, rel=0.01)
    assert result["principal_point_offset_px"] == pytest.approx(
        CAMERA.principal_offset, abs=4
    )
    assert result["rsk_focal_setting"] == pytest.approx(CAMERA.focal, rel=0.01)

    # The estimated distortion moves the pixels like the real one (within 2 pixels, in the image
    # corners where the board is rarely seen), while it
    # moves them by more than 100 pixels in the image corners
    intrinsic = np.array(
        [
            [result["focal_px"][0], 0, result["principal_point_px"][0]],
            [0, result["focal_px"][1], result["principal_point_px"][1]],
            [0, 0, 1],
        ]
    )
    estimated = distortion_field(intrinsic, result["distortion"])
    truth = distortion_field(CAMERA.intrinsic(), CAMERA.distortion)
    assert np.max(np.linalg.norm(truth, axis=1)) > 100
    assert np.max(np.linalg.norm(estimated - truth, axis=1)) < 2.0
