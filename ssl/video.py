import time
import numpy as np
import cv2
import base64
import threading
import detection
import field
import config


class Video:
    def __init__(self):
        # Limitting the output period
        self.min_period = 1/30
        # Image retrieve and processing duration
        self.period = None
        # Current capture
        self.capture = None
        # The last retrieved image
        self.image = None
        # Debug output
        self.debug = False
        # Ask main thread to stop capture
        self.stop_capture = False

        self.detection = detection.Detection()

        # Starting the video processing thread
        self.running = True
        self.video_thread = threading.Thread(target=lambda: self.thread())
        self.video_thread.start()

        self.settings = {
            'brightness': 100,
            'contrast': 100,
            'saturation': 100
        }
        self.favourite_index = None

        if 'camera' in config.config:
            self.favourite_index = config.config['camera']['favourite_index']
            self.settings = config.config['camera']['settings']
            self.startCapture(self.favourite_index)
            self.applyCameraSettings()

    def cameras(self):
        indexes = []
        for index in range(10):
            cap = cv2.VideoCapture(index)
            if cap.read()[0]:
                if self.favourite_index is None:
                    self.favourite_index = index
                indexes.append(index)
                cap.release()

        return [indexes, self.favourite_index]

    def saveConfig(self):
        config.config['camera'] = {
            'favourite_index': self.favourite_index,
            'settings': self.settings
        }
        config.save()

    def startCapture(self, index):
        self.capture = cv2.VideoCapture(index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

        self.favourite_index = index
        self.saveConfig()

        time.sleep(0.1)
        return self.image is not None

    def stopCapture(self):
        self.stop_capture = True

    def stop(self):
        self.running = False
        self.stopCapture()

    def applyCameraSettings(self):
        if self.capture is not None:
            self.capture.set(cv2.CAP_PROP_BRIGHTNESS, self.settings['brightness'])
            self.capture.set(cv2.CAP_PROP_CONTRAST, self.settings['contrast'])
            self.capture.set(cv2.CAP_PROP_SATURATION, self.settings['saturation'])

    def setCameraSettings(self, settings):
        self.settings = settings
        self.saveConfig()

        self.applyCameraSettings()

    def thread(self):
        while self.running:
            if self.capture is not None:
                t0 = time.time()
                grabbed, image_captured = self.capture.read()

                if image_captured is not None:
                    # Process the image
                    self.detection.detectAruco(image_captured, self.debug)
                    self.detection.detectBall(image_captured, self.debug)
                    self.detection.publish()

                # Computing time
                current_period = time.time() - t0
                if current_period < self.min_period:
                    time.sleep(self.min_period - current_period)
                current_period = time.time() - t0

                if self.period is None:
                    self.period = current_period
                else:
                    self.period = self.period*0.95 + current_period*0.05

                self.image = image_captured

                if self.stop_capture:
                    self.stop_capture = False
                    self.capture.release()
                    del self.capture
                    self.capture = None
                    self.image = None
            else:
                time.sleep(0.1)

    def getImage(self):
        if self.image is not None:
            data = cv2.imencode('.jpg', self.image)
            return base64.b64encode(data[1]).decode('utf-8')
        else:
            return ''

    def getVideo(self, with_image):
        data = {
            'running': self.capture is not None,
            'fps': round(1/self.period, 2) if self.period is not None else 0,
            'detection': self.detection.getDetection(),
        }

        if with_image:
            data['image'] = self.getImage()

        return data
