import math
import time

import cv2
import numpy as np
import pytest
import synthetic

from rsk import lens_calibration, video
from rsk.state import State

# A camera with a strong barrel distortion and an off-center principal point
CAMERA_LENS = dict(
    focal=935.0,
    principal_offset=(40, -25),
    distortion=(-0.12, 0.03, 0.0005, -0.0003, 0.0),
)


class QuietState(State):
    def publish(self):
        pass


class FakeCapture:
    """
    A fake camera, returning the given images (each one several times, like a still scene)
    """

    def __init__(self, images, repeat=3):
        self.set_images(images, repeat)

    def set_images(self, images, repeat=3):
        self.frames = [image for image in images for _ in range(repeat)]
        self.index = 0

    def read(self):
        time.sleep(0.005)
        frame = self.frames[self.index % len(self.frames)]
        self.index += 1
        return True, frame

    def set(self, *args):
        return True

    def release(self):
        pass


def wait_for(condition, timeout=30.0):
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            return False
        time.sleep(0.02)
    return True


@pytest.fixture
def camera_video(isolated_config):
    isolated_config.config.pop("camera", None)
    v = video.Video()
    v.detection.state = QuietState()
    v.lens_capture_interval = 0.0
    yield v
    v.stop()
    isolated_config.config.pop("camera", None)


@pytest.fixture(scope="module")
def board_images():
    rng = np.random.default_rng(1)
    camera = synthetic.Camera(**CAMERA_LENS)
    board = lens_calibration.make_board()
    detector = cv2.aruco.CharucoDetector(board)
    images = []
    while len(images) < 18:
        image = synthetic.board_view(camera, board, rng)
        if lens_calibration.detect_board(image, detector, board) is not None:
            images.append(image)
    return images


def field_scenes(count, seed=2):
    """
    Field images seen by cameras with the lens CAMERA_LENS
    """
    rng = np.random.default_rng(seed)
    scenes = []
    for _ in range(count):
        camera = synthetic.random_camera(
            rng,
            distortion=CAMERA_LENS["distortion"],
            principal_offset=CAMERA_LENS["principal_offset"],
        )
        robots = synthetic.random_robots(rng)
        scenes.append((robots, synthetic.render(robots, None, camera)))
    return scenes


def max_position_error(v, scenes):
    """
    Shows each scene to the video, and returns the maximum error on robot positions
    """
    errors = []
    for robots, image in scenes:
        # Each scene has a different camera pose: the field is calibrated again once the new
        # image is processed
        v.capture.set_images([image])
        time.sleep(0.2)
        v.detection.calibrate_camera()
        assert wait_for(
            lambda: (
                v.detection.field.calibrated() and len(v.detection.state.markers) == 4
            )
        )
        time.sleep(0.2)
        markers = v.detection.state.markers
        for name, (x, y, _) in robots.items():
            px, py = markers[name]["position"]
            errors.append(math.hypot(px - x, py - y))
    return max(errors)


def test_lens_calibration_in_the_game_controller(
    camera_video, board_images, isolated_config
):
    v = camera_video
    v.capture = FakeCapture(board_images)
    # Done by start_capture() with a real camera (gives the focal setting to the field)
    v.apply_camera_settings()

    # Collecting views of the board
    v.start_lens_calibration()
    assert wait_for(lambda: v.lens_calibration_status()["views"] >= 16)
    status = v.lens_calibration_status()
    assert status["state"] == "collecting"
    assert sum(map(sum, status["coverage"])) > 0

    # Computing the calibration (in the background)
    v.compute_lens_calibration()
    assert wait_for(lambda: v.lens_calibration_status()["state"] == "done")
    result = v.lens_calibration_status()["result"]
    assert np.mean(result["focal_px"]) == pytest.approx(CAMERA_LENS["focal"], rel=0.02)
    assert result["principal_point_offset_px"] == pytest.approx(
        CAMERA_LENS["principal_offset"], abs=8
    )

    # Applying it: it is saved in the configuration
    v.apply_lens_calibration()
    assert isolated_config.config["camera"]["lens_calibration"] == result
    assert v.lens_calibration_status()["state"] == "idle"

    # The vision uses it
    scenes = field_scenes(3)
    assert max_position_error(v, scenes) < 0.005
    assert v.lens_calibration_status()["current_used"]

    # Also with a cropped and rescaled image
    v.settings.update(crop_x=90, crop_y=95, rescale=60)
    v.apply_camera_settings()
    assert max_position_error(v, scenes) < 0.006

    # Without the calibration, the distortion is not handled
    v.settings.update(crop_x=100, crop_y=100, rescale=100)
    v.apply_camera_settings()
    v.remove_lens_calibration()
    assert isolated_config.config["camera"]["lens_calibration"] is None
    assert max_position_error(v, scenes) > 0.01


def test_lens_calibration_needs_enough_views(camera_video, board_images):
    v = camera_video
    v.capture = FakeCapture(board_images[:3])
    v.start_lens_calibration()
    assert wait_for(lambda: v.lens_calibration_status()["views"] == 3)

    with pytest.raises(RuntimeError, match="views are needed"):
        v.compute_lens_calibration()

    v.cancel_lens_calibration()
    assert v.lens_calibration_status()["state"] == "idle"


def test_lens_calibration_for_another_resolution_is_not_used(camera_video):
    v = camera_video
    v.lens_calibration = {
        "date": "2026-01-01T00:00:00",
        "image_size": [1280, 720],
        "focal_px": [620.0, 620.0],
        "principal_point_px": [640.0, 360.0],
        "distortion": [0.0] * 5,
    }
    robots, image = field_scenes(1)[0]
    v.capture = FakeCapture([image])

    assert wait_for(lambda: v.raw_size == (synthetic.WIDTH, synthetic.HEIGHT))
    assert v.detection.field.lens_intrinsics is None
    assert not v.lens_calibration_status()["current_used"]


def test_intrinsics_for_cropped_and_rescaled_image():
    calibration = {
        "image_size": [1920, 1080],
        "focal_px": [935.0, 936.0],
        "principal_point_px": [1000.0, 520.0],
        "distortion": [0.1, -0.1, 0.0, 0.0, 0.05],
    }
    intrinsic, distortion = lens_calibration.intrinsics_for_image(
        calibration, (1920, 1080), crop_x=50, crop_y=100, rescale=50
    )

    # Cropping 50% horizontally removes 480 px on the left, then the image is scaled by 0.5
    assert intrinsic[0, 0] == pytest.approx(935.0 * 0.5)
    assert intrinsic[1, 1] == pytest.approx(936.0 * 0.5)
    assert intrinsic[0, 2] == pytest.approx((1000.0 - 480 + 0.5) * 0.5 - 0.5)
    assert intrinsic[1, 2] == pytest.approx((520.0 + 0.5) * 0.5 - 0.5)
    assert list(distortion) == calibration["distortion"]

    assert lens_calibration.intrinsics_for_image(calibration, (1280, 720)) is None
