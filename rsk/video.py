import time
import numpy as np
import cv2
import os
import base64
import threading
from . import detection, config

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
            "focal": 885,
        }
        self.favourite_index = None
        self.resolution = len(resolutions) - 1

        if "camera" in config.config:
            if "favourite_index" in config.config["camera"]:
                self.favourite_index = config.config["camera"]["favourite_index"]
            if "resolution" in config.config["camera"]:
                self.resolution = config.config["camera"]["resolution"]
            for entry in config.config["camera"]["settings"]:
                self.settings[entry] = config.config["camera"]["settings"][entry]

        # Starting the video processing thread
        self.running = True
        self.video_thread = threading.Thread(target=lambda: self.thread())
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

        self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G"))

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
                self.detection.field.focal = self.settings["focal"] * (h / 1080) * (self.settings["rescale"] / 100.0)

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

                    if image_captured is not None:
                        height, width, channels = image_captured.shape
                        frame_size = np.array([width, height])
                        if "crop_x" in self.settings and "crop_y" in self.settings:
                            if self.settings["crop_x"] < 100 or self.settings["crop_y"] < 100:
                                frame_size[0] = round(frame_size[0] * self.settings["crop_x"] / 100.0)
                                frame_size[1] = round(frame_size[1] * self.settings["crop_y"] / 100.0)
                                x_offset = round((width - frame_size[0]) / 2.0)
                                y_offset = round((height - frame_size[1]) / 2.0)
                                image_captured = image_captured[
                                    y_offset : y_offset + frame_size[1], x_offset : x_offset + frame_size[0]
                                ]

                        if "rescale" in self.settings and self.settings["rescale"] < 100 and self.settings["rescale"] > 0:
                            new_size = frame_size * self.settings["rescale"] / 100.0
                            image_captured = cv2.resize(image_captured, (int(new_size[0]), int(new_size[1])), cv2.INTER_LINEAR)

                        # Process the image
                        if self.debug:
                            image_debug = image_captured.copy()
                        self.detection.detect_markers(image_captured, image_debug)
                        self.detection.detect_ball(image_captured, image_debug)
                        self.detection.draw_annotations(image_debug)

                    # Computing time
                    current_period = time.time() - t0
                    if current_period < self.min_period:
                        time.sleep(self.min_period - current_period)
                    current_period = time.time() - t0

                    if self.period is None:
                        self.period = current_period
                    else:
                        self.period = self.period * 0.9 + current_period * 0.1

                    self.image = image_debug if image_debug is not None else image_captured

                    if self.should_stop_capture:
                        self.should_stop_capture = False
                        self.capture.release()
                        del self.capture
                        self.capture = None
                        self.image = None
                except cv2.error as e:
                    print("OpenCV error")
                    print(e)
            else:
                time.sleep(0.1)

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
