import time
import numpy as np
import cv2
import os
import base64
import sys
import threading
import logging
from . import detection, config, lens_calibration, constants, camera_controls

resolutions = [
    (320, 240),
    (352, 288),
    (640, 360),
    (640, 480),
    (800, 600),
    (800, 448),
    (864, 480),
    (848, 480),
    (960, 544),
    (960, 720),
    (1024, 576),
    (1024, 768),
    (1280, 720),
    (1600, 896),
    (1920, 1080),
]

is_windows = os.name == "nt"
is_linux = sys.platform.startswith("linux")


def open_camera(index: int) -> cv2.VideoCapture:
    """
    Opens a camera. On Linux, the V4L2 backend is used: the index is the one of /dev/videoN.
    Otherwise, when V4L2 can't open an index (e.g. the metadata device of a camera), OpenCV tries
    other backends that number the cameras differently, and the same camera appears several times.

    :param int index: the camera index
    :return cv2.VideoCapture: the capture
    """
    if is_linux:
        return cv2.VideoCapture(index, cv2.CAP_V4L2)
    return cv2.VideoCapture(index)


def camera_name(index: int) -> str:
    """
    Name of a camera, if it can be known (Linux only)

    :param int index: the camera index
    :return str: the camera name, or an empty string
    """
    try:
        with open(f"/sys/class/video4linux/video{index}/name") as file:
            return " ".join(file.read().split())
    except OSError:
        return ""


# Focal of the recommended camera, for a 1080p image [px] (measured with rsk.calibrate_camera)
DEFAULT_FOCAL = 935

# Previous default focal, that was not matching the recommended camera
OLD_DEFAULT_FOCAL = 885

logger: logging.Logger = logging.getLogger("video")

# If the camera gives no image for this duration, a warning is shown [s]
NO_IMAGE_TIMEOUT = 2.0

# Automatic exposure, when the field is calibrated: the brightest parts of the field (white lines,
# white of the markers, the green of the carpet) should be bright but not saturated. 98th
# percentile targeted of the highest color channel of the pixels of the field (a channel can be
# saturated before the luminance is high) [0-255]
AUTO_EXPOSURE_TARGET = 225
AUTO_EXPOSURE_PERCENTILE = 98
# When the field is not calibrated: the mean luminance of the image is the middle gray (18 %
# reflectance in sRGB), as the automatic exposure of cameras (lamps in the image don't matter)
AUTO_EXPOSURE_MEAN_TARGET = 118
# Exposures tried. On Linux (V4L2), the exposure is in 100 µs units: up to the duration of a frame
# at 30 fps. Elsewhere (Windows), OpenCV uses log2 of the exposure in seconds: from 1/2048 s to
# 1/32 s
AUTO_EXPOSURE_MAX_V4L2 = 333
# The lights flicker at twice the frequency of the power line: an exposure that is not a multiple
# of this period makes horizontal bands on the image (the lines of the image are not exposed at
# the same time). With V4L2, the exposure is rounded to a multiple of this period [100 µs]
V4L2_EXPOSURE_UNITS_PER_SECOND = 10000
AUTO_EXPOSURE_RANGE_LOG2 = (-11, -5)
# The preview of a camera (before starting the vision) is stopped when it is not retrieved for this
# duration (e.g. the page is closed), to release the camera [s]
PREVIEW_TIMEOUT = 5.0

# Number of new images to wait for after a change of the camera settings
AUTO_SETTLE_FRAMES = 5


class Video:
    """
    Handles video capture from the camera
    """

    def __init__(self):
        # Limitting the output period
        self.min_period = 1 / 60
        # Image retrieve and processing duration
        self.period = None
        # Current capture
        self.capture = None
        # The last retrieved image
        self.image = None
        # Debug output
        self.debug = False
        # Ask main thread to stop capture
        self.should_stop_capture = False
        # Time of the last image received from the camera (None if no capture is running)
        self.last_image_time = None
        self.no_image_warned = False

        self.detection = detection.Detection()

        # Last processed image (without annotations) and number of images processed, used by the
        # automatic settings
        self.last_frame = None
        self.frame_count = 0
        # Geometry of the last processed image (see thread())
        self.image_geometry = None
        # Ranges and defaults of the controls of the current camera (see camera_controls.py)
        self.controls = {}
        # Preview of a camera, before starting the vision: (index, resolution), None if no preview.
        # The images are captured, but not processed
        self.preview = None
        self.preview_retrieved = 0.0
        self.preview_lock = threading.Lock()
        # Automatic camera settings
        self.auto_state = "idle"
        self.auto_message = ""

        self.settings = {
            "brightness": 0,
            "contrast": 0,
            "saturation": 100,
            "gain": 0,
            "crop_x": 100,
            "crop_y": 100,
            "rescale": 100,
            "exposure": -7 if is_windows else 100,
            "focal": DEFAULT_FOCAL,
            # Frequency of the power line, for the flickering of the lights (0: lights that don't
            # flicker) [Hz]
            "power_line": 50,
        }
        self.favourite_index = None
        self.resolution = len(resolutions) - 1

        # Lens calibration applied (see lens_calibration.py), None if the lens is not calibrated
        self.lens_calibration = None
        # Raw size of the captured images, and the key of the lens intrinsics currently used
        self.raw_size = None
        self.lens_intrinsics_key = None

        # Lens calibration in progress
        self.lens_capture_interval = 0.7  # Minimum time between two captured views [s]
        self.lens_lock = threading.Lock()
        self.lens_collector = None
        self.lens_state = "idle"
        self.lens_result = None
        self.lens_error = None

        if "camera" in config.config:
            if "favourite_index" in config.config["camera"]:
                self.favourite_index = config.config["camera"]["favourite_index"]
            if "resolution" in config.config["camera"]:
                self.resolution = config.config["camera"]["resolution"]
            if "lens_calibration" in config.config["camera"]:
                self.lens_calibration = config.config["camera"]["lens_calibration"]
            for entry in config.config["camera"]["settings"]:
                self.settings[entry] = config.config["camera"]["settings"][entry]

            # The previous default focal was saved in the configuration of all users
            if self.settings["focal"] == OLD_DEFAULT_FOCAL:
                logger.info(
                    f"Updating the focal setting from the previous default "
                    f"({OLD_DEFAULT_FOCAL}) to {DEFAULT_FOCAL}"
                )
                self.settings["focal"] = DEFAULT_FOCAL

        # Starting the video processing thread
        self.running = True
        self.video_thread = threading.Thread(
            target=lambda: self.thread(), daemon=True, name="VideoThread"
        )
        self.video_thread.start()

    def cameras(self) -> list:
        """
        Build a list of available cameras

        :return list: a list containing possible indexes, favourite one (None if no favourite)
                      and the camera names (by index, empty if unknown)
        """
        if self.preview is not None:
            # The camera of the preview is listed too
            self.release_capture()
        if self.capture is None:
            indexes = []
            for index in range(10):
                if is_windows:
                    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                else:
                    cap = open_camera(index)
                if cap.isOpened() and cap.read()[0]:
                    if self.favourite_index is None:
                        self.favourite_index = index
                    indexes.append(index)
                cap.release()

            names = {index: camera_name(index) for index in indexes}
            return [indexes, self.favourite_index, names]
        else:
            return [[], None, {}]

    def resolutions(self) -> list:
        """
        Returns all possible resolutions

        :return list: a list of possible resolutions
        """
        res = ["%d x %d" % res for res in resolutions]

        return [self.resolution, res]

    def save_config(self):
        """
        Save the configuration
        """
        config.config["camera"] = {
            "favourite_index": self.favourite_index,
            "resolution": self.resolution,
            "settings": self.settings,
            "lens_calibration": self.lens_calibration,
        }
        config.save()

    def release_capture(self, timeout: float = 3.0) -> None:
        """
        Stops the capture and waits for the camera to be released by the video thread
        """
        if self.capture is None:
            return
        self.should_stop_capture = True
        start = time.time()
        while self.capture is not None and time.time() - start < timeout:
            time.sleep(0.01)
        if self.capture is not None:
            # The video thread is stuck (e.g. the camera gives no image)
            logger.warning("The camera was not released by the video thread")
            capture, self.capture = self.capture, None
            capture.release()
            self.should_stop_capture = False
            self.preview = None
            self.image = None
            self.last_frame = None

    def start_preview(self, index: int, resolution: int) -> None:
        """
        Starts the preview of a camera (before starting the vision): its images are captured with
        the camera settings, but not processed

        :param int index: the camera index
        :param int resolution: the resolution index
        """
        with self.preview_lock:
            if self.capture is not None and self.preview is None:
                raise RuntimeError("The vision is running")
            self.preview_retrieved = time.time()
            if self.preview == (index, resolution):
                return
            self.release_capture()
            # Set before the camera is opened (it takes time): it is not the vision
            self.preview = (index, resolution)
            self.open_capture(index, resolution)

    def get_preview(self) -> dict:
        """
        Status of the preview (the images are retrieved with preview_stream())

        :return dict: whether the preview is running, whether the camera gives images, the size
            of its images and the frame rate
        """
        self.preview_retrieved = time.time()
        image = self.image
        if self.preview is None or image is None:
            return {"running": self.preview is not None, "has_image": False}
        height, width = image.shape[:2]
        return {
            "running": True,
            "has_image": True,
            "size": [width, height],
            "fps": round(1 / self.period, 1) if self.period else 0,
        }

    def preview_stream(self):
        """
        The images of the preview, as they come from the camera (full size, all the images), to
        be sent as a MJPEG stream. Ends when the preview stops or changes.

        :return: a generator of JPEG images (bytes)
        """
        preview = self.preview
        last_count = None
        last_image = time.time()
        while preview is not None and self.preview == preview and self.running:
            self.preview_retrieved = time.time()
            image = self.image
            if image is None or self.frame_count == last_count:
                if time.time() - last_image > PREVIEW_TIMEOUT:
                    return
                time.sleep(0.005)
                continue
            last_count = self.frame_count
            last_image = time.time()
            yield cv2.imencode(".jpg", image)[1].tobytes()

    def stop_preview(self) -> None:
        """
        Stops the preview of a camera
        """
        if self.preview is not None:
            self.stop_capture()

    def open_capture(self, index: int, resolution: int) -> None:
        """
        Opens a camera with a resolution, and applies the camera settings
        """
        # A stop requested before (e.g. while no capture was running) should not stop this one
        self.should_stop_capture = False
        self.period = None
        self.last_image_time = None
        self.no_image_warned = False
        self.capture = open_camera(index)
        self.controls = camera_controls.query_controls(index)
        w, h = resolutions[resolution]
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

        self.capture.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G")
        )
        self.capture.set(cv2.CAP_PROP_FPS, 30)

        self.favourite_index = index
        self.resolution = resolution
        self.apply_camera_settings()

    def start_capture(self, index: int, resolution: int) -> bool:
        """
        Starts video capture

        :param int index: the camera index to use
        :param int resolution: the resolution index to use
        :return bool: whether the capture started
        """
        if self.preview is not None:
            self.release_capture()
        self.open_capture(index, resolution)
        self.save_config()

        time.sleep(0.1)
        return self.image is not None

    def stop_capture(self) -> None:
        """
        Stop video capture
        """
        # The capture is released by the video thread. If no capture is running, nothing should be
        # done (otherwise the next capture would be stopped as soon as started)
        if self.capture is not None:
            self.should_stop_capture = True

    def stop(self) -> None:
        """
        Stop execution of threads
        """
        self.running = False
        self.stop_capture()

    def apply_camera_settings(self) -> None:
        """
        Use camera settings to set OpenCV properties on capture stream
        """
        if self.capture is not None:
            self.capture.set(cv2.CAP_PROP_BRIGHTNESS, self.settings["brightness"])
            self.capture.set(cv2.CAP_PROP_CONTRAST, self.settings["contrast"])
            self.capture.set(cv2.CAP_PROP_SATURATION, self.settings["saturation"])
            self.capture.set(cv2.CAP_PROP_GAIN, self.settings["gain"])
            self.capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.capture.set(cv2.CAP_PROP_FOCUS, 0)
            self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1.0)
            self.capture.set(cv2.CAP_PROP_EXPOSURE, self.settings["exposure"])
            if self.favourite_index is not None:
                camera_controls.set_power_line_frequency(
                    self.favourite_index, self.settings.get("power_line", 50)
                )

            if self.resolution is not None:
                w, h = resolutions[self.resolution]
                self.detection.field.focal = (
                    self.settings["focal"]
                    * (h / 1080)
                    * (self.settings["rescale"] / 100.0)
                )

    def flicker_period(self):
        """
        Flickering period of the lights, in the exposure units, when the exposure of the camera
        can be a multiple of it (V4L2)

        :return: the period [100 µs], or None
        """
        frequency = self.settings.get("power_line", 50)
        if "exposure" not in self.controls or not frequency:
            return None
        return V4L2_EXPOSURE_UNITS_PER_SECOND / (2 * frequency)

    def flicker_free_exposure(self, exposure: int) -> int:
        """
        The nearest exposure that is a multiple of the flickering period of the lights (to avoid
        bands on the image), at least one period

        :param int exposure: the exposure
        :return int: the exposure
        """
        period = self.flicker_period()
        if period is None:
            return exposure
        maximum = self.controls["exposure"]["max"]
        count = min(max(1, round(exposure / period)), max(1, int(maximum / period)))
        return round(count * period)

    def set_camera_settings(self, settings: dict):
        """
        Set camera settings, save and apply them

        :param dict settings: settings
        """
        self.settings = settings
        if "exposure" in self.settings:
            self.settings["exposure"] = self.flicker_free_exposure(
                self.settings["exposure"]
            )
        self.save_config()
        self.apply_camera_settings()

    def thread(self):
        """
        Main video capture thread
        """
        if self.favourite_index is not None and self.resolution is not None:
            self.start_capture(self.favourite_index, self.resolution)

        while self.running:
            if self.capture is not None:
                try:
                    t0 = time.time()
                    grabbed, image_captured = self.capture.read()
                    image_debug = None

                    if image_captured is not None:
                        self.last_image_time = time.time()
                    elif self.last_image_time is None:
                        self.last_image_time = time.time()
                    elif time.time() - self.last_image_time > NO_IMAGE_TIMEOUT:
                        if not self.no_image_warned:
                            logger.warning(
                                "No image received from the camera, is it used by another "
                                "program?"
                            )
                            self.no_image_warned = True
                        # Avoids spinning when the camera doesn't give images
                        time.sleep(0.05)

                    if self.preview is not None:
                        # Preview: the image is not processed. Stopped when not retrieved anymore
                        if image_captured is not None:
                            self.frame_count += 1
                        if time.time() - self.preview_retrieved > PREVIEW_TIMEOUT:
                            self.should_stop_capture = True
                    elif image_captured is not None and self.lens_collector is not None:
                        # Lens calibration in progress: the raw image is used
                        image_debug = self.process_lens_calibration_frame(
                            image_captured
                        )
                    elif image_captured is not None:
                        height, width, channels = image_captured.shape
                        self.update_lens_intrinsics((width, height))

                        # The settings are read once: they can be changed meanwhile
                        crop_x = self.settings.get("crop_x", 100)
                        crop_y = self.settings.get("crop_y", 100)
                        rescale = self.settings.get("rescale", 100)

                        # When the image geometry changes (resolution, crop, rescale), the field
                        # is calibrated again, with an image having the new geometry
                        geometry = (width, height, crop_x, crop_y, rescale)
                        if geometry != self.image_geometry:
                            if self.image_geometry is not None:
                                self.detection.calibrate_camera()
                            self.image_geometry = geometry

                        frame_size = np.array([width, height])
                        if crop_x < 100 or crop_y < 100:
                            frame_size[0] = round(frame_size[0] * crop_x / 100.0)
                            frame_size[1] = round(frame_size[1] * crop_y / 100.0)
                            x_offset = round((width - frame_size[0]) / 2.0)
                            y_offset = round((height - frame_size[1]) / 2.0)
                            image_captured = image_captured[
                                y_offset : y_offset + frame_size[1],
                                x_offset : x_offset + frame_size[0],
                            ]

                        if 0 < rescale < 100:
                            new_size = frame_size * rescale / 100.0
                            image_captured = cv2.resize(
                                image_captured,
                                (int(new_size[0]), int(new_size[1])),
                                cv2.INTER_LINEAR,
                            )

                        self.last_frame = image_captured
                        self.frame_count += 1

                        # Process the image
                        if self.debug:
                            image_debug = image_captured.copy()
                        self.detection.detect_markers(image_captured, image_debug)
                        self.detection.detect_ball(image_captured, image_debug)
                        self.detection.draw_annotations(image_debug)
                        self.detection.state.publish()

                    # Computing time
                    current_period = time.time() - t0
                    if current_period < self.min_period:
                        time.sleep(self.min_period - current_period)
                    current_period = time.time() - t0

                    if self.period is None:
                        self.period = current_period
                    else:
                        self.period = self.period * 0.9 + current_period * 0.1

                    self.image = (
                        image_debug if image_debug is not None else image_captured
                    )

                    if self.should_stop_capture:
                        self.should_stop_capture = False
                        self.capture.release()
                        del self.capture
                        self.capture = None
                        self.preview = None
                        self.image = None
                        self.last_frame = None
                except Exception:
                    # An error should never stop the video
                    logger.exception("Error in video processing")
                    time.sleep(0.1)
            else:
                time.sleep(0.1)

    def camera_controls(self) -> dict:
        """
        Ranges and defaults of the controls of the current camera, when they are known

        :return dict: setting name => {"min", "max", "step", "default"}
        """
        return self.controls

    def field_outline(self, margin: float, z: float = 0.0) -> np.ndarray:
        """
        Outline of the field with a margin around it, on the processed image (the field should be
        calibrated). Points are taken along the sides, since they are curved by the lens
        distortion.

        :param float margin: margin around the field [m]
        :param float z: height [m]
        :return np.ndarray: the points (N x 2) [px]
        """
        x = constants.field_length / 2 + margin
        y = constants.field_width / 2 + margin
        corners = [(-x, -y), (x, -y), (x, y), (-x, y)]
        points = []
        for (x1, y1), (x2, y2) in zip(corners, corners[1:] + corners[:1]):
            for t in np.linspace(0, 1, 12, endpoint=False):
                points.append(
                    self.detection.field.position_to_pixel(
                        [x1 + t * (x2 - x1), y1 + t * (y2 - y1), z]
                    )
                )
        return np.array(points, dtype=np.float64)

    def auto_crop(self) -> dict:
        """
        Crops the image to the field, with the border around it that should be visible (robots
        leaving the field should be seen, to bring them back). The crop is centered on the image.

        :return dict: the crop settings set
        """
        if self.capture is None or self.raw_size is None:
            raise RuntimeError("The vision is not running")
        if not self.detection.field.calibrated():
            raise RuntimeError(
                "The field is not calibrated: the four field markers should be visible"
            )

        # The border on the ground, and the top of the robots in it
        outline = np.vstack(
            [
                self.field_outline(constants.border_size),
                self.field_outline(constants.border_size, constants.robot_height),
            ]
        )

        # From the processed image to the raw image of the camera
        width, height = self.raw_size
        crop_x = self.settings.get("crop_x", 100)
        crop_y = self.settings.get("crop_y", 100)
        rescale = self.settings.get("rescale", 100)
        cropped = np.array(
            [round(width * crop_x / 100.0), round(height * crop_y / 100.0)]
            if crop_x < 100 or crop_y < 100
            else [width, height]
        )
        offset = np.round((np.array([width, height]) - cropped) / 2.0)
        if 0 < rescale < 100:
            outline = outline * 100.0 / rescale
        outline = outline + offset

        # Smallest centered crop containing the outline
        center = np.array([width, height]) / 2.0
        half = np.max(np.abs(outline - center), axis=0)
        new_crop = np.ceil(200.0 * half / np.array([width, height])) + 1
        new_crop = np.clip(new_crop, 10, 100).astype(int)

        settings = dict(self.settings)
        settings["crop_x"], settings["crop_y"] = int(new_crop[0]), int(new_crop[1])
        # The field is calibrated again by the video thread, on the cropped image
        self.set_camera_settings(settings)

        return {
            "crop_x": settings["crop_x"],
            "crop_y": settings["crop_y"],
            # The field and its border are not entirely in the image of the camera
            "too_small": bool(np.any(half > center)),
        }

    def wait_frames(self, count: int, timeout: float = 3.0) -> bool:
        """
        Waits for new images from the camera

        :param int count: number of new images
        :param float timeout: maximum duration [s]
        :return bool: whether the images were received
        """
        target = self.frame_count + count
        start = time.time()
        while self.frame_count < target:
            if time.time() - start > timeout or self.capture is None:
                return False
            time.sleep(0.01)
        return True

    def measure_brightness(self, on_field: bool) -> float:
        """
        Brightness of the image, compared to the target of the automatic exposure

        :param bool on_field: whether the field is used (it should be calibrated), see
            AUTO_EXPOSURE_TARGET, else the whole image, see AUTO_EXPOSURE_MEAN_TARGET
        :return float: the brightness divided by its target (1: the target is reached)
        """
        if on_field:
            highest = np.max(self.last_frame, axis=2)
            mask = np.zeros(highest.shape, np.uint8)
            outline = self.field_outline(0.0).astype(np.int32)
            cv2.fillPoly(mask, [outline], 255)
            values = highest[mask > 0] if np.count_nonzero(mask) >= 1000 else highest
            return (
                float(np.percentile(values, AUTO_EXPOSURE_PERCENTILE))
                / AUTO_EXPOSURE_TARGET
            )

        gray = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray)) / AUTO_EXPOSURE_MEAN_TARGET

    def set_exposure_and_measure(self, exposure: int, on_field: bool) -> float:
        self.settings["exposure"] = int(exposure)
        if self.capture is not None:
            self.capture.set(cv2.CAP_PROP_EXPOSURE, int(exposure))
        if not self.wait_frames(AUTO_SETTLE_FRAMES):
            raise RuntimeError("No image from the camera")
        return self.measure_brightness(on_field)

    def auto_exposure(self) -> tuple:
        """
        Searches the exposure that makes the brightest parts of the field bright, but not
        saturated, or the image of a medium brightness if the field is not calibrated (the
        brightness grows with the exposure)

        :return tuple: the exposure, whether there is enough light to reach the target, and
            whether the field was used
        """
        on_field = self.detection.field.calibrated()
        if "exposure" in self.controls:
            low = max(1, self.controls["exposure"]["min"])
            high = min(self.controls["exposure"]["max"], AUTO_EXPOSURE_MAX_V4L2)
            # Flickering period of the lights [100 µs] (None if they don't flicker)
            period = self.flicker_period()
        elif is_windows:
            # The exposure can't be a multiple of the flickering period (powers of 2)
            low, high = AUTO_EXPOSURE_RANGE_LOG2
            period = None
        else:
            return None, True, on_field

        def flicker_free(exposure):
            # A multiple of the flickering period of the lights, to avoid bands on the image. When
            # there is a lot of light, one period is used, even if the image is a bit brighter
            if period is None:
                return exposure
            return round(max(1, int(exposure / period)) * period)

        enough_light = True
        if self.set_exposure_and_measure(high, on_field) < 1:
            exposure, enough_light = high, False
        elif self.set_exposure_and_measure(low, on_field) >= 1:
            exposure = low
        else:
            # Brightness at low < target <= brightness at high
            logarithmic = "exposure" in self.controls
            while high - low > (max(1, low * 0.05) if logarithmic else 1):
                middle = (
                    round((low * high) ** 0.5) if logarithmic else (low + high) // 2
                )
                middle = min(max(middle, low + 1), high - 1)
                if self.set_exposure_and_measure(middle, on_field) < 1:
                    low = middle
                else:
                    high = middle
            exposure = low

        exposure = flicker_free(exposure)
        self.set_exposure_and_measure(exposure, on_field)
        return exposure, enough_light, on_field

    def auto_camera_settings(self) -> None:
        """
        Starts the automatic camera settings: the image settings (brightness, contrast, saturation,
        gain) are set to the defaults of the camera (when they are known), then the exposure is
        searched. Runs in the background, see auto_camera_settings_status()
        """
        if self.capture is None or self.preview is not None or self.last_frame is None:
            raise RuntimeError("The vision is not running")
        if self.auto_state == "running":
            return
        if self.lens_collector is not None:
            raise RuntimeError("A lens calibration is in progress")

        self.auto_state = "running"
        self.auto_message = "Adjusting the camera settings..."

        def run():
            try:
                messages = []
                defaults = {
                    name: self.controls[name]["default"]
                    for name in ("brightness", "contrast", "saturation", "gain")
                    if name in self.controls
                }
                if defaults:
                    self.settings.update(defaults)
                    self.apply_camera_settings()
                    self.wait_frames(AUTO_SETTLE_FRAMES)
                    messages.append(
                        ", ".join(defaults) + " set to the defaults of the camera"
                    )

                exposure, enough_light, on_field = self.auto_exposure()
                if exposure is not None:
                    if "exposure" in self.controls:
                        duration = f"{exposure / 10:.1f} ms"
                    else:
                        duration = f"1/{round(2 ** (-exposure))} s"
                    messages.append(f"exposure {exposure} ({duration})")
                    if not on_field:
                        messages.append(
                            "the field was not calibrated: once its four markers are "
                            "visible, Auto again adjusts the exposure to the field"
                        )
                    if not enough_light:
                        messages.append(
                            "the image is still dark: more light is needed (a longer "
                            "exposure would blur the moving robots)"
                        )
                elif not defaults:
                    messages.append(
                        "the settings of this camera can't be adjusted automatically"
                    )

                self.save_config()
                self.auto_message = messages[0][0].upper() + "; ".join(messages)[1:]
                self.auto_state = "done"
            except Exception as error:
                logger.exception("Error in the automatic camera settings")
                self.auto_message = str(error)
                self.auto_state = "error"

        threading.Thread(target=run, daemon=True).start()

    def auto_camera_settings_status(self) -> dict:
        """
        Status of the automatic camera settings

        :return dict: the state (idle, running, done or error) and a message
        """
        return {"state": self.auto_state, "message": self.auto_message}

    def update_lens_intrinsics(self, raw_size: tuple) -> None:
        """
        Gives the lens intrinsics to the field calibration, adapted to the processed image (crop,
        rescale). The field is re-calibrated when they change.

        :param tuple raw_size: size of the image captured by the camera (width, height)
        """
        self.raw_size = raw_size
        key = None
        if self.lens_calibration is not None:
            key = (
                self.lens_calibration.get("date"),
                tuple(self.lens_calibration["image_size"]),
                tuple(raw_size),
                self.settings.get("crop_x", 100),
                self.settings.get("crop_y", 100),
                self.settings.get("rescale", 100),
            )

        if key != self.lens_intrinsics_key:
            self.lens_intrinsics_key = key
            intrinsics = None
            if self.lens_calibration is not None:
                intrinsics = lens_calibration.intrinsics_for_image(
                    self.lens_calibration,
                    raw_size,
                    self.settings.get("crop_x", 100),
                    self.settings.get("crop_y", 100),
                    self.settings.get("rescale", 100),
                )
                if intrinsics is None:
                    logger.warning(
                        "The lens calibration was done with a resolution of %dx%d, it can't be "
                        "used with the current resolution (%dx%d)"
                        % (*self.lens_calibration["image_size"], *raw_size)
                    )
            self.detection.field.lens_intrinsics = intrinsics
            self.detection.calibrate_camera()

    def process_lens_calibration_frame(self, frame):
        """
        Processes a frame during the lens calibration

        :return: the image to display (detected board, coverage)
        """
        with self.lens_lock:
            collector = self.lens_collector
            if collector is None:
                return frame
            collector.process(frame)
            display = frame.copy()
            collector.draw(display)
        return display

    def start_lens_calibration(self) -> None:
        """
        Starts collecting views of the calibration board
        """
        if not lens_calibration.is_supported():
            raise RuntimeError(
                f"OpenCV {cv2.__version__} is too old for the lens calibration (4.7 or newer is "
                "needed)"
            )
        with self.lens_lock:
            self.lens_collector = lens_calibration.ViewCollector(
                self.lens_capture_interval
            )
            self.lens_state = "collecting"
            self.lens_result = None
            self.lens_error = None

    def cancel_lens_calibration(self) -> None:
        """
        Cancels the lens calibration in progress (the applied calibration is kept)
        """
        with self.lens_lock:
            self.lens_collector = None
            self.lens_state = "idle"
            self.lens_result = None
            self.lens_error = None

    def compute_lens_calibration(self) -> None:
        """
        Stops collecting views and computes the calibration (in the background, see
        lens_calibration_status)
        """
        with self.lens_lock:
            collector = self.lens_collector
            if collector is None or self.lens_state != "collecting":
                raise RuntimeError("No lens calibration in progress")
            if not collector.ready():
                raise RuntimeError(
                    "The calibration can't be computed yet: "
                    + collector.not_ready_reason()
                )
            self.lens_collector = None
            self.lens_state = "computing"

        def compute():
            try:
                result = collector.calibrate()
                with self.lens_lock:
                    self.lens_result, self.lens_state = result, "done"
            except Exception as e:
                logger.exception("Lens calibration failed")
                with self.lens_lock:
                    self.lens_error, self.lens_state = str(e), "error"

        threading.Thread(target=compute, daemon=True, name="LensCalibration").start()

    def apply_lens_calibration(self) -> None:
        """
        Uses the computed calibration for the vision (saved in the configuration). The focal
        setting is also set to the measured focal: it is the one of this camera, which is used if
        the calibration is removed or can't be used (other resolution).
        """
        with self.lens_lock:
            if self.lens_state != "done":
                raise RuntimeError("No lens calibration to apply")
            self.lens_calibration = self.lens_result
            self.lens_state, self.lens_result = "idle", None
        self.settings["focal"] = round(self.lens_calibration["rsk_focal_setting"])
        self.save_config()
        self.apply_camera_settings()

    def remove_lens_calibration(self) -> None:
        """
        Stops using the lens calibration (the focal setting is used again)
        """
        self.lens_calibration = None
        self.save_config()

    def lens_calibration_status(self) -> dict:
        """
        Status of the lens calibration

        :return dict: status
        """
        with self.lens_lock:
            collector = self.lens_collector
            status = {
                "supported": lens_calibration.is_supported(),
                "state": self.lens_state,
                "min_views": lens_calibration.MIN_VIEWS,
                "views": len(collector.views) if collector is not None else 0,
                "coverage": collector.coverage() if collector is not None else None,
                "coverage_good": lens_calibration.COVERAGE_GOOD,
                "ready": collector is not None and collector.ready(),
                "missing_views": collector.missing_views()
                if collector is not None
                else lens_calibration.MIN_VIEWS,
                "missing_cells": collector.missing_cells()
                if collector is not None
                else 0,
                "last_capture_age": time.time() - collector.last_capture
                if collector is not None and collector.views
                else None,
                "board_visible": collector is not None
                and collector.last_detection is not None,
                "result": self.lens_result,
                "error": self.lens_error,
            }

        status["current"] = self.lens_calibration
        status["current_used"] = (
            self.lens_calibration is not None
            and self.detection.field.lens_intrinsics is not None
        )
        status["raw_size"] = list(self.raw_size) if self.raw_size is not None else None
        return status

    def get_image(self) -> str:
        """
        Get the current image

        :return str: the image contents (base64 encoded)
        """
        if self.image is not None:
            data = cv2.imencode(".jpg", self.image)
            return base64.b64encode(data[1]).decode("utf-8")
        else:
            return ""

    def get_video(self, with_image: bool) -> dict:
        """
        Get the video status

        :param bool with_image: whether to include the image
        :return dict: a dictionnary containing current status of video service
        """
        data = {
            "running": self.capture is not None and self.preview is None,
            # The camera is opened but doesn't give images (e.g. used by another program)
            "no_image": self.capture is not None
            and self.preview is None
            and self.last_image_time is not None
            and time.time() - self.last_image_time > NO_IMAGE_TIMEOUT,
            "fps": round(1 / self.period, 1) if self.period is not None else 0,
            "detection": self.detection.get_detection(),
        }

        if with_image:
            data["image"] = self.get_image()

        return data
