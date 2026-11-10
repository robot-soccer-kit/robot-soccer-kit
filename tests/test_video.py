import copy
import threading
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
    # The video threads can still save the configuration (e.g. when starting the favourite
    # camera): they are finished before the configuration is cleared for the next test
    for v in created:
        v.video_thread.join(timeout=5)
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


def start_preview(make_video, monkeypatch, cameras=None):
    cameras = {} if cameras is None else cameras
    monkeypatch.setattr(
        video, "open_camera", lambda index: cameras.setdefault(index, FakeCamera())
    )
    monkeypatch.setattr(video.camera_controls, "query_controls", lambda index: {})
    v = make_video()
    v.detection.state = QuietState()
    v.start_preview(0, len(video.resolutions) - 1)
    return v, cameras


def test_preview(make_video, monkeypatch):
    v, cameras = start_preview(make_video, monkeypatch)

    assert wait_until(lambda: v.get_preview()["has_image"])
    preview = v.get_preview()
    assert preview["size"] == [1920, 1080]

    # The images of the camera, full size
    stream = v.preview_stream()
    images = [next(stream) for _ in range(3)]
    decoded = cv2.imdecode(np.frombuffer(images[0], np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (1080, 1920, 3)
    # The preview is not the vision: the images are not processed
    assert not v.get_video(False)["running"]
    assert v.last_frame is None
    # The camera chosen is not saved
    assert "camera" not in video.config.config

    # Another camera
    v.start_preview(2, 0)
    assert cameras[0].released
    assert v.preview == (2, 0)

    # The stream of the previous camera ends
    assert next(stream, None) is None

    v.stop_preview()
    assert wait_until(lambda: v.capture is None)
    assert cameras[2].released
    assert not v.get_preview()["has_image"]


def test_preview_is_not_the_vision_while_the_camera_opens(make_video, monkeypatch):
    class SlowCamera(FakeCamera):
        def __init__(self):
            time.sleep(0.5)
            super().__init__()

    states = []
    monkeypatch.setattr(video, "open_camera", lambda index: SlowCamera())
    monkeypatch.setattr(video.camera_controls, "query_controls", lambda index: {})
    v = make_video()
    v.detection.state = QuietState()

    opening = threading.Thread(target=v.start_preview, args=(0, 0))
    opening.start()
    while opening.is_alive():
        states.append(v.get_video(False)["running"])
        time.sleep(0.02)
    states.append(v.get_video(False)["running"])

    assert not any(states)


def test_preview_is_stopped_when_not_retrieved(make_video, monkeypatch):
    monkeypatch.setattr(video, "PREVIEW_TIMEOUT", 0.3)
    v, cameras = start_preview(make_video, monkeypatch)

    assert wait_until(lambda: v.capture is None, 3)
    assert cameras[0].released
    assert v.preview is None


def test_vision_starts_after_the_preview(make_video, monkeypatch):
    v, cameras = start_preview(make_video, monkeypatch)
    assert wait_until(lambda: v.image is not None)

    v.start_capture(0, len(video.resolutions) - 1)

    assert cameras[0].released
    assert v.preview is None
    assert wait_until(lambda: v.last_frame is not None)
    assert v.get_video(False)["running"]
    # No preview while the vision is running
    with pytest.raises(RuntimeError, match="running"):
        v.start_preview(0, 0)


def test_cameras_are_listed_during_a_preview(make_video, monkeypatch):
    v, _ = start_preview(make_video, monkeypatch)
    monkeypatch.setattr(video, "camera_name", lambda index: "")

    indexes, _, _ = v.cameras()

    # The camera of the preview is released, to be listed
    assert v.preview is None
    assert 0 in indexes


def test_resolutions_of_a_camera(make_video, monkeypatch):
    sizes = {
        (1920, 1080): 30.0,
        (1280, 720): 30.0,
        (2592, 1944): 15.0,
        (640, 480): 30.0,
    }
    monkeypatch.setattr(video.camera_controls, "frame_sizes", lambda index: sizes)
    v = make_video()

    _, labels, available = v.resolutions(0)

    assert labels == [f"{width} x {height}" for width, height in video.resolutions]
    # Only the resolutions of RSK that the camera can give, with their frame rate
    assert [video.resolutions[number] for number, _ in available] == [
        (640, 480),
        (1280, 720),
        (1920, 1080),
    ]
    assert all(fps == 30.0 for _, fps in available)


def test_resolutions_of_an_unknown_camera(make_video, monkeypatch):
    # E.g. on Windows: all the resolutions are proposed
    monkeypatch.setattr(video.camera_controls, "frame_sizes", lambda index: {})
    v = make_video()

    assert v.resolutions(0)[2] is None
    assert v.resolutions()[2] is None


class WindowsFieldCamera(FieldCamera):
    """
    The camera of FieldCamera as seen on Windows: the exposure is the log2 of the exposure time in
    seconds, the image has its full brightness for an exposure of -7 (1/128 s)
    """

    def read(self):
        exposure = self.properties.get(cv2.CAP_PROP_EXPOSURE, -7)
        image = self.image * 2 ** (exposure + 7)
        return True, np.clip(image, 0, 255).astype(np.uint8)


def test_auto_camera_settings_on_windows(make_video, monkeypatch):
    # On Windows, the ranges of the settings are unknown and the exposure is a power of 2
    monkeypatch.setattr(video, "is_windows", True)
    camera = WindowsFieldCamera(synthetic.render({}))
    v = start_field_camera(make_video, monkeypatch, camera, controls={})
    assert wait_until(lambda: v.detection.field.calibrated())
    settings = dict(v.settings)

    v.auto_camera_settings()
    assert wait_until(lambda: v.auto_camera_settings_status()["state"] != "running", 30)

    status = v.auto_camera_settings_status()
    assert status["state"] == "done", status["message"]
    # The green of the field reaches 225 between -7 (120) and -6 (240): the longest exposure
    # under the target, not rounded to the flickering of the lights
    assert v.settings["exposure"] == -7
    assert "1/128 s" in status["message"]
    # The image settings are kept (the defaults of the camera are unknown)
    for name in ("brightness", "contrast", "saturation", "gain"):
        assert v.settings[name] == settings[name]


def test_camera_controls_outside_linux(monkeypatch):
    # On Windows, nothing is known: the interface proposes all the resolutions, numbers for the
    # settings, and no automatic image settings
    monkeypatch.setattr(video.camera_controls, "is_linux", False)
    assert video.camera_controls.query_controls(0) == {}
    assert video.camera_controls.frame_sizes(0) == {}
    assert not video.camera_controls.set_power_line_frequency(0, 50)


def test_camera_controls_of_a_missing_camera():
    assert video.camera_controls.query_controls(99) == {}
    assert video.camera_controls.frame_sizes(99) == {}
    assert not video.camera_controls.set_power_line_frequency(99, 50)


def test_v4l2_structures():
    # Sizes of the structures of the Linux kernel (linux/videodev2.h), part of the ioctl numbers
    import ctypes

    controls = video.camera_controls
    assert ctypes.sizeof(controls.v4l2_queryctrl) == 68
    assert ctypes.sizeof(controls.v4l2_control) == 8
    assert ctypes.sizeof(controls.v4l2_fmtdesc) == 64
    assert ctypes.sizeof(controls.v4l2_frmsizeenum) == 44
    assert ctypes.sizeof(controls.v4l2_frmivalenum) == 52
    assert controls.VIDIOC_QUERYCTRL == 0xC0445624
    assert controls.VIDIOC_S_CTRL == 0xC008561C
    assert controls.MJPG == 0x47504A4D


CAMERA_NAMES = {0: "Integrated Camera", 2: "USB Live camera"}
CAMERA_CONTROLS = {
    0: CONTROLS,
    2: {
        "brightness": {"min": -64, "max": 64, "step": 1, "default": 0},
        "contrast": {"min": 0, "max": 64, "step": 1, "default": 32},
        "saturation": {"min": 0, "max": 128, "step": 1, "default": 85},
        "gain": {"min": 0, "max": 100, "step": 1, "default": 0},
        "exposure": {"min": 1, "max": 5000, "step": 1, "default": 157},
    },
}


@pytest.fixture
def two_cameras(monkeypatch):
    monkeypatch.setattr(video, "open_camera", lambda index: FakeCamera())
    monkeypatch.setattr(video, "camera_name", lambda index: CAMERA_NAMES.get(index, ""))
    monkeypatch.setattr(
        video.camera_controls,
        "query_controls",
        lambda index: CAMERA_CONTROLS.get(index, {}),
    )


def test_settings_of_each_camera(make_video, two_cameras):
    v = make_video()
    v.detection.state = QuietState()
    full_hd = len(video.resolutions) - 1

    # A new camera: the image settings are the defaults of the camera
    v.start_capture(0, full_hd)
    assert (v.settings["brightness"], v.settings["contrast"]) == (128, 32)
    v.set_camera_settings(dict(v.settings, contrast=50, crop_x=80, power_line=60))

    # Another camera: its own settings, but the lights are the same
    v.start_capture(2, full_hd)
    assert (v.settings["brightness"], v.settings["contrast"]) == (0, 32)
    assert v.settings["saturation"] == 85
    assert v.settings["crop_x"] == 100
    assert v.settings["power_line"] == 60
    v.set_camera_settings(dict(v.settings, brightness=-10))

    # Back to the first camera: its settings
    v.start_capture(0, full_hd)
    assert v.settings["contrast"] == 50
    assert v.settings["crop_x"] == 80

    # Saved for each camera
    saved = video.config.config["camera"]["cameras"]
    assert saved["Integrated Camera"]["settings"]["contrast"] == 50
    assert saved["USB Live camera"]["settings"]["brightness"] == -10
    # Loaded again
    v2 = make_video(copy.deepcopy(video.config.config["camera"]))
    assert v2.cameras_settings["USB Live camera"]["settings"]["brightness"] == -10


def test_lens_calibration_of_each_camera(make_video, two_cameras):
    v = make_video()
    v.start_preview(0, 0)
    v.lens_calibration = {"date": "calibration of the camera 0"}

    v.start_preview(2, 0)
    assert v.lens_calibration is None

    v.start_preview(0, 0)
    assert v.lens_calibration == {"date": "calibration of the camera 0"}


def test_settings_of_a_previous_configuration(make_video, two_cameras):
    # Before, the settings were not saved for each camera: they are the ones of the favourite
    v = make_video(
        {
            "favourite_index": 2,
            "resolution": 0,
            "settings": {"brightness": 5, "contrast": 7},
            "lens_calibration": None,
        }
    )
    v.detection.state = QuietState()
    assert v.cameras_settings["USB Live camera"]["settings"]["contrast"] == 7

    # The favourite camera is started automatically
    assert wait_until(lambda: v.capture is not None)
    assert (v.settings["brightness"], v.settings["contrast"]) == (5, 7)


def test_camera_without_name(make_video, two_cameras):
    # E.g. on Windows: the camera is known by its index
    v = make_video()
    v.start_preview(1, 0)
    assert v.camera_key == "Camera 1"
    # Its image settings are the defaults of RSK (the ones of the camera are unknown)
    assert v.settings["contrast"] == video.default_settings()["contrast"]


def test_image_settings_out_of_the_range_of_the_camera(make_video, two_cameras):
    # The settings of another camera were saved for this one (e.g. previous configuration)
    v = make_video(
        {
            "favourite_index": None,
            "settings": {},
            "cameras": {
                "USB Live camera": {
                    "settings": {"brightness": 128, "contrast": 32, "saturation": 64},
                    "lens_calibration": None,
                }
            },
        }
    )
    v.start_preview(2, 0)

    # Brightness from -64 to 64: the default of the camera
    assert v.settings["brightness"] == 0
    # In the ranges: kept
    assert (v.settings["contrast"], v.settings["saturation"]) == (32, 64)


def test_image_is_encoded_once(make_video, monkeypatch):
    v = make_video()
    v.image = np.zeros((1080, 1920, 3), np.uint8)
    encoded = []
    original = cv2.imencode
    monkeypatch.setattr(
        video.cv2, "imencode", lambda *args: encoded.append(1) or original(*args)
    )

    first = v.get_image()
    assert v.get_image() == first
    assert len(encoded) == 1

    # A new image
    v.image = np.full((1080, 1920, 3), 255, np.uint8)
    assert v.get_image() != first
    assert len(encoded) == 2


class RecordingCamera(FakeCamera):
    """
    A camera recording the properties set
    """

    def __init__(self):
        super().__init__()
        self.sets = []

    def set(self, prop, value):
        self.sets.append((prop, value))
        return True


def test_settings_changed_live(make_video, monkeypatch):
    # As while a slider is moved: many changes, only the setting changed is sent to the camera,
    # the configuration is not saved
    camera = RecordingCamera()
    monkeypatch.setattr(video, "open_camera", lambda index: camera)
    monkeypatch.setattr(video.camera_controls, "query_controls", lambda index: CONTROLS)
    v = make_video()
    v.detection.state = QuietState()
    v.start_capture(0, len(video.resolutions) - 1)
    saved = copy.deepcopy(video.config.config["camera"]["settings"])

    for contrast in (10, 20, 30):
        camera.sets.clear()
        v.set_camera_settings(dict(v.settings, contrast=contrast), save=False)
        assert camera.sets == [(cv2.CAP_PROP_CONTRAST, contrast)]
    assert video.config.config["camera"]["settings"] == saved
    assert v.settings["contrast"] == 30

    # Released: saved
    v.set_camera_settings(dict(v.settings), save=True)
    assert video.config.config["camera"]["settings"]["contrast"] == 30


def test_focal_change_calibrates_the_field_again(make_video, monkeypatch):
    monkeypatch.setattr(video, "open_camera", lambda index: FakeCamera())
    monkeypatch.setattr(video.camera_controls, "query_controls", lambda index: {})
    v = make_video()
    v.detection.state = QuietState()
    v.start_preview(0, 0)

    v.detection.field.should_calibrate = False
    v.set_camera_settings(dict(v.settings, brightness=v.settings["brightness"] + 1))
    assert not v.detection.field.should_calibrate

    v.set_camera_settings(dict(v.settings, focal=v.settings["focal"] + 10))
    assert v.detection.field.should_calibrate
