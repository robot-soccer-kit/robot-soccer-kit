"""
Tests with the real cameras plugged to the computer (Linux or Windows): listing, resolutions,
preview, automatic settings and vision. They are skipped unless RSK_TEST_CAMERAS=1:

    RSK_TEST_CAMERAS=1 uv run --extra gc --group dev pytest tests/test_cameras_hardware.py -v -s

(on Windows, in PowerShell: $env:RSK_TEST_CAMERAS=1 before the command). No Game Controller
should be running, and no other program should use the cameras.

The configuration file is not modified, but the automatic settings change the settings of the
cameras (brightness, contrast, exposure...) until they are unplugged. What is printed (-s) helps
to check the results: the cameras, their resolutions, the frame rates measured...
"""

import os
import sys
import time

import cv2
import numpy as np
import pytest
from rsk import video
from rsk.state import State

pytestmark = pytest.mark.skipif(
    os.environ.get("RSK_TEST_CAMERAS") != "1",
    reason="Tests with real cameras: set RSK_TEST_CAMERAS=1",
)

is_linux = sys.platform.startswith("linux")

# The images of a camera should come at least at this rate [FPS] (cameras give 30 FPS)
MIN_FPS = 20


class QuietState(State):
    def publish(self):
        pass


def wait_until(condition, timeout=10.0):
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            return False
        time.sleep(0.05)
    return True


@pytest.fixture
def make_video(isolated_config):
    created = []

    def make():
        # No camera is started automatically
        isolated_config.config.pop("camera", None)
        v = video.Video()
        v.detection.state = QuietState()
        created.append(v)
        return v

    yield make
    for v in created:
        v.stop()
    time.sleep(0.5)
    isolated_config.config.pop("camera", None)


@pytest.fixture(scope="module")
def cameras():
    """
    The cameras plugged (listed once: it takes time)
    """
    from rsk import config

    config.config.pop("camera", None)
    v = video.Video()
    try:
        indexes, _, names = v.cameras()
    finally:
        v.stop()
        time.sleep(0.5)
    print(f"\nCameras: {[(index, names.get(index, '')) for index in indexes]}")
    if not indexes:
        pytest.skip("No camera plugged")
    return indexes


def measure_preview(v, seconds=2.0):
    """
    Size of the images of the preview, and their rate [FPS]
    """
    assert wait_until(lambda: v.get_preview()["has_image"]), "No image from the camera"
    time.sleep(1.0)  # The first images can be slower
    start_count, start = v.frame_count, time.time()
    time.sleep(seconds)
    fps = (v.frame_count - start_count) / (time.time() - start)
    return v.get_preview()["size"], fps


def resolutions_to_test(v, index):
    """
    The resolutions of a camera tested: the smallest, 1280 x 720 and the largest
    """
    available = v.resolutions(index)[2]
    if available is None:
        # Unknown (Windows): the usual ones
        numbers = [
            video.resolutions.index(size)
            for size in [(640, 480), (1280, 720), (1920, 1080)]
        ]
    else:
        numbers = [number for number, _ in available]
        middle = video.resolutions.index((1280, 720))
        numbers = sorted({numbers[0], numbers[-1]} | ({middle} & set(numbers)))
    return numbers


def test_resolutions(make_video, cameras):
    v = make_video()
    for index in cameras:
        available = v.resolutions(index)[2]
        print(f"Camera {index}: resolutions {available}")
        if is_linux:
            # Listed by the driver
            assert available, f"No resolution listed for the camera {index}"
            for number, fps in available:
                assert 0 <= number < len(video.resolutions)
                assert fps > 0
        else:
            # Unknown: all the resolutions are proposed
            assert available is None


def test_camera_controls(cameras):
    for index in cameras:
        controls = video.camera_controls.query_controls(index)
        print(f"Camera {index}: controls {controls}")
        if is_linux:
            for name, control in controls.items():
                assert control["min"] <= control["default"] <= control["max"], name
        else:
            assert controls == {}


def test_preview_size_and_rate(make_video, cameras):
    v = make_video()
    for index in cameras:
        for number in resolutions_to_test(v, index):
            v.start_preview(index, number)
            size, fps = measure_preview(v)
            print(
                f"Camera {index}, {video.resolutions[number]}: images {size}, "
                f"{fps:.1f} FPS"
            )
            # The vision is not running
            assert not v.get_video(False)["running"]
            assert tuple(size) == video.resolutions[number], (
                f"The camera {index} gives {size} images for "
                f"{video.resolutions[number]}"
            )
            assert fps >= MIN_FPS, f"The camera {index} gives {fps:.1f} FPS"

            # The stream sends all the images, full size
            stream = v.preview_stream()
            image = cv2.imdecode(
                np.frombuffer(next(stream), np.uint8), cv2.IMREAD_COLOR
            )
            stream.close()
            assert (image.shape[1], image.shape[0]) == video.resolutions[number]

    v.stop_preview()
    assert wait_until(lambda: v.capture is None), "The camera is not released"


def test_switching_cameras_quickly(make_video, cameras):
    # As when choosing cameras and resolutions in the interface
    v = make_video()
    number = video.resolutions.index((1280, 720))
    for _ in range(2):
        for index in cameras:
            v.start_preview(index, number)
            assert not v.get_video(False)["running"]
    assert wait_until(lambda: v.get_preview()["has_image"])
    v.stop_preview()
    assert wait_until(lambda: v.capture is None)


def test_automatic_settings(make_video, cameras):
    for index in cameras:
        v = make_video()
        v.start_capture(index, video.resolutions.index((1280, 720)))
        assert wait_until(lambda v=v: v.last_frame is not None), "No image"

        v.auto_camera_settings()
        assert wait_until(
            lambda v=v: v.auto_camera_settings_status()["state"] != "running", 60
        )
        status = v.auto_camera_settings_status()
        print(f"Camera {index}: {status['message']} -> {v.settings}")
        assert status["state"] == "done", status["message"]

        if "exposure" in v.controls:
            # A multiple of the flickering period of the lights at 50 Hz (10 ms)
            assert v.settings["exposure"] % 100 == 0
            for name in ("brightness", "contrast", "saturation"):
                if name in v.controls:
                    assert v.settings[name] == v.controls[name]["default"]
        elif not is_linux:
            low, high = video.AUTO_EXPOSURE_RANGE_LOG2
            assert low <= v.settings["exposure"] <= high
        v.stop()
        time.sleep(0.5)


def test_vision_after_the_preview(make_video, cameras):
    v = make_video()
    index = cameras[0]
    number = video.resolutions.index((1280, 720))
    v.start_preview(index, number)
    assert wait_until(lambda: v.get_preview()["has_image"])

    v.start_capture(index, number)
    assert wait_until(lambda: v.last_frame is not None), "The vision gives no image"
    assert v.get_video(False)["running"]
    # The images are processed, at the rate of the camera (the first ones can be slower)
    time.sleep(1.0)
    start_count, start = v.frame_count, time.time()
    time.sleep(3.0)
    fps = (v.frame_count - start_count) / (time.time() - start)
    print(f"Camera {index}: vision at {fps:.1f} FPS")
    assert fps >= MIN_FPS, f"The vision processes {fps:.1f} images per second"
