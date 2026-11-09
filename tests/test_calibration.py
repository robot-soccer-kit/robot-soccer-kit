import json

import cv2
import numpy as np
import pytest
import synthetic

from rsk import calibrate_camera, lens_calibration

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
    board = lens_calibration.make_board()
    detector = cv2.aruco.CharucoDetector(board)
    rng = np.random.default_rng(0)

    images = []
    while len(images) < 18:
        image = synthetic.degrade(synthetic.board_view(CAMERA, board, rng), rng)
        if lens_calibration.detect_board(image, detector, board) is not None:
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
    board = lens_calibration.make_board()
    object_points, _ = lens_calibration.detect_board(
        image, cv2.aruco.CharucoDetector(board), board
    )

    squares_x, squares_y = lens_calibration.BOARD_SQUARES
    assert len(object_points) == (squares_x - 1) * (squares_y - 1)


def test_calibration_recovers_the_camera(board_images):
    board = lens_calibration.make_board()
    detector = cv2.aruco.CharucoDetector(board)
    views = [
        lens_calibration.detect_board(image, detector, board) for image in board_images
    ]

    result = lens_calibration.calibrate(views, (synthetic.WIDTH, synthetic.HEIGHT))

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


def test_command_line_with_images(board_images, tmp_path):
    for k, image in enumerate(board_images):
        cv2.imwrite(str(tmp_path / f"view_{k:02d}.png"), image)
    output = tmp_path / "calibration.json"

    code = calibrate_camera.main(
        ["--images", str(tmp_path / "*.png"), "--output", str(output)]
    )

    assert code == 0
    result = json.loads(output.read_text())
    assert result["views"] == len(board_images)
    assert result["distortion"][0] == pytest.approx(CAMERA.distortion[0], abs=0.02)


def test_command_line_not_enough_views(board_images, tmp_path):
    for k, image in enumerate(board_images[:3]):
        cv2.imwrite(str(tmp_path / f"view_{k:02d}.png"), image)

    code = calibrate_camera.main(
        ["--images", str(tmp_path / "*.png"), "--output", str(tmp_path / "out.json")]
    )

    assert code == 1
    assert not (tmp_path / "out.json").exists()


def test_command_line_without_camera(capsys):
    # No camera with this index
    code = calibrate_camera.main(["--camera", "99"])

    assert code == 1
    assert "Can't open camera 99" in capsys.readouterr().out


def test_generate_board_in_the_current_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert calibrate_camera.main(["--generate"]) == 0

    board_file = tmp_path / calibrate_camera.DEFAULT_BOARD_FILE
    assert board_file.exists()
    # The full path is shown, so the user knows where the file is
    assert str(board_file) in capsys.readouterr().out
