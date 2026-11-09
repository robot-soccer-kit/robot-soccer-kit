import time

import numpy as np
import pytest

from rsk import video
from rsk.state import State


class QuietState(State):
    def publish(self):
        pass


@pytest.fixture
def make_video(isolated_config):
    created = []

    def make(camera_config=None):
        isolated_config.config.pop("camera", None)
        if camera_config is not None:
            isolated_config.config["camera"] = camera_config
        created.append(video.Video())
        return created[-1]

    yield make
    for v in created:
        v.stop()
    isolated_config.config.pop("camera", None)


def test_default_focal(make_video):
    assert make_video().settings["focal"] == video.DEFAULT_FOCAL == 935


def test_old_default_focal_is_updated(make_video):
    v = make_video({"settings": {"focal": video.OLD_DEFAULT_FOCAL, "gain": 3}})

    assert v.settings["focal"] == video.DEFAULT_FOCAL
    assert v.settings["gain"] == 3


def test_custom_focal_is_kept(make_video):
    assert make_video({"settings": {"focal": 1200}}).settings["focal"] == 1200


class FakeCamera:
    """
    A fake camera: readable or not, records whether it was released
    """

    def __init__(self, readable=True):
        self.readable = readable
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        if self.readable:
            return True, np.zeros((1080, 1920, 3), np.uint8)
        return False, None

    def set(self, *args):
        return True

    def release(self):
        self.released = True


def test_cameras_listing(make_video, monkeypatch):
    # Cameras 1 and 3 can be opened but not read (e.g. metadata devices on Linux)
    cameras = {index: FakeCamera(readable=index in (0, 2)) for index in range(10)}
    monkeypatch.setattr(video, "is_windows", False)
    monkeypatch.setattr(video, "open_camera", lambda index: cameras[index])
    monkeypatch.setattr(video, "camera_name", lambda index: f"Camera model {index}")

    indexes, favourite, names = make_video().cameras()

    assert indexes == [0, 2]
    assert favourite == 0
    assert names == {0: "Camera model 0", 2: "Camera model 2"}
    # All the cameras opened to be tested are released
    assert all(camera.released for camera in cameras.values())


def test_capture_starts_after_a_stop_without_capture(make_video, monkeypatch):
    monkeypatch.setattr(video, "open_camera", lambda index: FakeCamera())
    v = make_video()
    v.detection.state = QuietState()

    # Stopping while no capture is running should not stop the next one
    v.stop_capture()
    v.start_capture(0, len(video.resolutions) - 1)
    time.sleep(0.5)
    assert v.capture is not None
    assert v.get_video(False)["running"]

    v.stop_capture()
    time.sleep(0.5)
    assert v.capture is None


def test_camera_without_images_is_reported(make_video, monkeypatch):
    camera = FakeCamera(readable=False)
    monkeypatch.setattr(video, "open_camera", lambda index: camera)
    monkeypatch.setattr(video, "NO_IMAGE_TIMEOUT", 0.3)
    v = make_video()
    v.detection.state = QuietState()

    v.start_capture(0, len(video.resolutions) - 1)
    time.sleep(0.1)
    assert not v.get_video(False)["no_image"]
    time.sleep(0.5)
    assert v.get_video(False)["no_image"]

    # Images come back
    camera.readable = True
    time.sleep(0.3)
    assert not v.get_video(False)["no_image"]
