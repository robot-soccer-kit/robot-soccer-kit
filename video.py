import time
import numpy as np
import cv2
import base64
import threading
import detection
import field


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
        self.video_thread = threading.Thread(target=lambda: self.thread())
        self.video_thread.start()

    def cameras(self):
        indexes = []
        for index in range(10):
            cap = cv2.VideoCapture(index)
            if cap.read()[0]:
                indexes.append(index)
                cap.release()

        return indexes

    def startCapture(self, index):
        self.capture = cv2.VideoCapture(index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

        time.sleep(0.1)
        return self.image is not None

    def stopCapture(self):
        self.stop_capture = True

    def setCameraSettings(self, brightness, contrast, saturation):
        if self.capture is not None:
            self.capture.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
            self.capture.set(cv2.CAP_PROP_CONTRAST, contrast)
            self.capture.set(cv2.CAP_PROP_SATURATION, saturation)

    def thread(self):
        while True:
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

                if image_captured is None:
                    self.capture = None

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
