import time

import cv2
import numpy as np
import pytest
import synthetic

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


class FieldCamera(FakeCamera):
    """
    A camera filming the synthetic field, whose image gets brighter with the exposure (saturated
    beyond 255). Records the settings set.
    """

    def __init__(self, image, full_exposure=100.0):
        super().__init__()
        self.image = image.astype(np.float32)
        self.full_exposure = full_exposure
        self.properties = {}

    def read(self):
        exposure = self.properties.get(cv2.CAP_PROP_EXPOSURE, self.full_exposure)
        image = self.image * exposure / self.full_exposure
        return True, np.clip(image, 0, 255).astype(np.uint8)

    def set(self, prop, value):
        self.properties[prop] = value
        return True


CONTROLS = {
    "brightness": {"min": 0, "max": 255, "step": 1, "default": 128},
    "contrast": {"min": 0, "max": 100, "step": 1, "default": 32},
    "saturation": {"min": 0, "max": 100, "step": 1, "default": 64},
    "exposure": {"min": 2, "max": 1250, "step": 1, "default": 156},
}


def start_field_camera(make_video, monkeypatch, camera, controls=CONTROLS):
    monkeypatch.setattr(video, "open_camera", lambda index: camera)
    monkeypatch.setattr(video.camera_controls, "query_controls", lambda index: controls)
    v = make_video()
    v.detection.state = QuietState()
    v.start_capture(0, len(video.resolutions) - 1)
    return v


def wait_until(condition, timeout=10.0):
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            return False
        time.sleep(0.05)
    return True


def test_auto_camera_settings(make_video, monkeypatch):
    # The green of the field (BGR 40, 120, 40) reaches 225 (the target) for an exposure of 187
    camera = FieldCamera(synthetic.render({}))
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.detection.field.calibrated())

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    status = v.auto_camera_settings_status()
    assert status["state"] == "done", status["message"]
    assert "not calibrated" not in status["message"]
    # The image settings are the defaults of the camera
    assert v.settings["brightness"] == 128
    assert v.settings["contrast"] == 32
    assert v.settings["saturation"] == 64
    assert camera.properties[cv2.CAP_PROP_CONTRAST] == 32
    # The brightest parts of the field are bright, not saturated (exposure of 187), with a
    # multiple of the flickering period of the lights at 50 Hz (10 ms): 100
    assert v.settings["exposure"] == 100
    assert "exposure" in status["message"]
    # Saved
    assert (
        video.config.config["camera"]["settings"]["exposure"] == v.settings["exposure"]
    )


def test_auto_camera_settings_in_the_dark(make_video, monkeypatch):
    # Even with the longest exposure, the image stays dark
    camera = FieldCamera(synthetic.render({}), full_exposure=5000)
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.last_frame is not None)

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    status = v.auto_camera_settings_status()
    assert status["state"] == "done"
    # The longest exposure that is a multiple of the flickering period of the lights
    assert v.settings["exposure"] == 300
    assert "more light" in status["message"]


def test_auto_camera_settings_without_the_field(make_video, monkeypatch):
    # No field: the mean brightness of the image is the middle gray (118), lamps don't matter.
    # A gray of 59 with 4.8 % of saturated lamps: the target is reached for an exposure of ~188
    image = np.full((1080, 1920, 3), 59, np.uint8)
    image[:100, :1000] = 255
    camera = FieldCamera(image)
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.last_frame is not None)

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    status = v.auto_camera_settings_status()
    assert status["state"] == "done", status["message"]
    assert v.settings["exposure"] == 100
    assert "not calibrated" in status["message"]


def test_auto_exposure_with_60_hz_lights(make_video, monkeypatch):
    camera = FieldCamera(synthetic.render({}))
    v = start_field_camera(make_video, monkeypatch, camera)
    v.settings["power_line"] = 60
    assert wait_until(lambda: v.detection.field.calibrated())

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    # Target reached for an exposure of 187: two flickering periods at 60 Hz (8.33 ms)
    assert v.settings["exposure"] == 167


def test_auto_exposure_with_a_lot_of_light(make_video, monkeypatch):
    # The target is reached with a very short exposure: one flickering period is used
    camera = FieldCamera(synthetic.render({}), full_exposure=10)
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.detection.field.calibrated())

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    assert v.settings["exposure"] == 100


def test_auto_camera_settings_needs_images(make_video):
    with pytest.raises(RuntimeError):
        make_video().auto_camera_settings()


def test_auto_crop(make_video, monkeypatch):
    camera = FieldCamera(synthetic.render({}, cam=synthetic.camera(height=2.6)))
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.detection.field.calibrated())

    crop = v.auto_crop()

    assert crop["crop_x"] < 100 and crop["crop_y"] < 100
    assert not crop["too_small"]
    assert v.settings["crop_x"] == crop["crop_x"]
    # The field is calibrated again on the cropped image, the border around it is visible
    assert wait_until(lambda: v.last_frame.shape[1] < 1920)
    assert wait_until(lambda: v.detection.field.calibrated())
    assert v.detection.field.see_whole_field
    height, width = v.last_frame.shape[:2]
    for z in (0.0, video.constants.robot_height):
        outline = v.field_outline(video.constants.border_size, z)
        assert np.all(outline >= -1) and np.all(outline <= [width + 1, height + 1])
    # The crop is tight: the border touches a side of the image
    outline = v.field_outline(video.constants.border_size, video.constants.robot_height)
    margins = [
        outline[:, 0].min(),
        outline[:, 1].min(),
        width - outline[:, 0].max(),
        height - outline[:, 1].max(),
    ]
    assert min(margins) < 0.03 * width

    # Again: the crop doesn't change
    assert v.auto_crop()["crop_x"] == crop["crop_x"]


def test_auto_crop_needs_the_field(make_video, monkeypatch):
    camera = FieldCamera(np.full((1080, 1920, 3), 120, np.uint8))
    v = start_field_camera(make_video, monkeypatch, camera)
    assert wait_until(lambda: v.last_frame is not None)

    with pytest.raises(RuntimeError, match="not calibrated"):
        v.auto_crop()


@pytest.mark.parametrize(
    "power_line, exposure, expected",
    [
        (50, 140, 100),
        (50, 160, 200),
        (50, 20, 100),
        (60, 140, 167),
        (60, 6000, 5000),
        (0, 140, 140),
    ],
)
def test_exposure_follows_the_lights(make_video, power_line, exposure, expected):
    v = make_video()
    v.controls = {"exposure": {"min": 1, "max": 5000, "step": 1, "default": 157}}
    v.set_camera_settings(dict(v.settings, power_line=power_line, exposure=exposure))
    assert v.settings["exposure"] == expected


def test_exposure_is_free_when_its_range_is_unknown(make_video):
    # E.g. on Windows: the exposure is a power of 2, it can't follow the lights
    v = make_video()
    v.set_camera_settings(dict(v.settings, power_line=50, exposure=-6))
    assert v.settings["exposure"] == -6
