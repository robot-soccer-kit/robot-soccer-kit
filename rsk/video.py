import time
import numpy as np
import cv2
import os
import base64
import threading
import logging
from . import detection, config, lens_calibration

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

# Focal of the recommended camera, for a 1080p image [px] (measured with rsk.calibrate_camera)
DEFAULT_FOCAL = 935

# Previous default focal, that was not matching the recommended camera
OLD_DEFAULT_FOCAL = 885

logger: logging.Logger = logging.getLogger("video")


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

        self.detection = detection.Detection()

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

        :return list: a list containing possible indexes and favourite one (None if no favourite)
        """
        if self.capture is None:
            indexes = []
            for index in range(10):
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if is_windows else None)
                if cap.read()[0]:
                    if self.favourite_index is None:
                        self.favourite_index = index
                    indexes.append(index)
                    cap.release()

            return [indexes, self.favourite_index]
        else:
            return [[], None]

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

    def start_capture(self, index: int, resolution: int) -> bool:
        """
        Starts video capture

        :param int index: the camera index to use
        :param int resolution: the resolution index to use
        :return bool: whether the capture started
        """

        self.capture = cv2.VideoCapture(index)
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
        self.save_config()

        time.sleep(0.1)
        return self.image is not None

    def stop_capture(self) -> None:
        """
        Stop video capture
        """
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

            if self.resolution is not None:
                w, h = resolutions[self.resolution]
                self.detection.field.focal = (
                    self.settings["focal"]
                    * (h / 1080)
                    * (self.settings["rescale"] / 100.0)
                )

    def set_camera_settings(self, settings: dict):
        """
        Set camera settings, save and apply them

        :param dict settings: settings
        """
        self.settings = settings
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

                    if image_captured is not None and self.lens_collector is not None:
                        # Lens calibration in progress: the raw image is used
                        image_debug = self.process_lens_calibration_frame(
                            image_captured
                        )
                    elif image_captured is not None:
                        height, width, channels = image_captured.shape
                        self.update_lens_intrinsics((width, height))
                        frame_size = np.array([width, height])
                        if "crop_x" in self.settings and "crop_y" in self.settings:
                            if (
                                self.settings["crop_x"] < 100
                                or self.settings["crop_y"] < 100
                            ):
                                frame_size[0] = round(
                                    frame_size[0] * self.settings["crop_x"] / 100.0
                                )
                                frame_size[1] = round(
                                    frame_size[1] * self.settings["crop_y"] / 100.0
                                )
                                x_offset = round((width - frame_size[0]) / 2.0)
                                y_offset = round((height - frame_size[1]) / 2.0)
                                image_captured = image_captured[
                                    y_offset : y_offset + frame_size[1],
                                    x_offset : x_offset + frame_size[0],
                                ]

                        if (
                            "rescale" in self.settings
                            and self.settings["rescale"] < 100
                            and self.settings["rescale"] > 0
                        ):
                            new_size = frame_size * self.settings["rescale"] / 100.0
                            image_captured = cv2.resize(
                                image_captured,
                                (int(new_size[0]), int(new_size[1])),
                                cv2.INTER_LINEAR,
                            )

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
                        self.image = None
                except Exception:
                    # An error should never stop the video
                    logger.exception("Error in video processing")
                    time.sleep(0.1)
            else:
                time.sleep(0.1)

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
            "running": self.capture is not None,
            "fps": round(1 / self.period, 1) if self.period is not None else 0,
            "detection": self.detection.get_detection(),
        }

        if with_image:
            data["image"] = self.get_image()

        return data
