import time
import numpy as np
import cv2
import os
import base64
import threading
from . import detection, config

resolutions =[
    (320,240),
    (352,288),
    (640,360),
    (640,480),
    (800,600),
    (800,448),
    (864,480),
    (848,480),
    (960,544),
    (960,720),
    (1024,576),
    (1024,768),
    (1280,720),
    (1600,896),
    (1920,1080),
]

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

        is_windows = os.name == 'nt'

        self.settings = {
            'brightness': 0,
            'contrast': 0,
            'saturation': 100,
            'gamma': 0,
            'gain': 0,
            'crop_x': 100,
            'crop_y': 100,
            'rescale': 100,
            'exposure': -7 if is_windows else 100
        }
        self.favourite_index = None
        self.resolution = len(resolutions)-1

        if 'camera' in config.config:
            if 'favourite_index' in config.config['camera']:
                self.favourite_index = config.config['camera']['favourite_index']
            if 'resolution' in config.config['camera']:
                self.resolution = config.config['camera']['resolution']
            for entry in config.config['camera']['settings']:
                self.settings[entry] = config.config['camera']['settings'][entry]

        # Starting the video processing thread
        self.running = True
        self.video_thread = threading.Thread(target=lambda: self.thread())
        self.video_thread.start()

    def cameras(self):
        if self.capture is None:
            indexes = []
            for index in range(10):
                cap = cv2.VideoCapture(index)
                if cap.read()[0]:
                    if self.favourite_index is None:
                        self.favourite_index = index
                    indexes.append(index)
                    cap.release()

            return [indexes, self.favourite_index]
        else:
            return [[], None]

    def resolutions(self):
        res = ['%d x %d' % res for res in resolutions]

        return [self.resolution, res]

    def saveConfig(self):
        config.config['camera'] = {
            'favourite_index': self.favourite_index,
            'resolution': self.resolution,
            'settings': self.settings
        }
        config.save()

    def startCapture(self, index, resolution):
        self.capture = cv2.VideoCapture(index)
        w, h = resolutions[self.resolution]
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

        self.capture.set(cv2.CAP_PROP_FOURCC,
                         cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

        self.applyCameraSettings()

        self.favourite_index = index
        self.resolution = resolution
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
            self.capture.set(cv2.CAP_PROP_BRIGHTNESS,
                             self.settings['brightness'])
            self.capture.set(cv2.CAP_PROP_CONTRAST, self.settings['contrast'])
            self.capture.set(cv2.CAP_PROP_SATURATION,
                             self.settings['saturation'])
            self.capture.set(cv2.CAP_PROP_GAMMA, self.settings['gamma'])
            self.capture.set(cv2.CAP_PROP_GAIN, self.settings['gain'])
            self.capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self.capture.set(cv2.CAP_PROP_FOCUS, 0)
            self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1.0)
            self.capture.set(cv2.CAP_PROP_EXPOSURE, self.settings['exposure'])

    def setCameraSettings(self, settings):
        self.settings = settings
        self.saveConfig()

        self.applyCameraSettings()

    def thread(self):
        if self.favourite_index is not None and self.resolution is not None:
            self.startCapture(self.favourite_index, self.resolution)

        while self.running:
            if self.capture is not None:
                try:
                    t0 = time.time()
                    grabbed, image_captured = self.capture.read()

                    if image_captured is not None:
                        height, width, channels = image_captured.shape
                        frame_size = np.array([width, height])
                        if 'crop_x' in self.settings and 'crop_y' in self.settings:
                            if self.settings['crop_x'] < 100 or self.settings['crop_y'] < 100:
                                frame_size[0] = round(frame_size[0] * self.settings['crop_x'] / 100.)
                                frame_size[1] = round(frame_size[1] * self.settings['crop_y'] / 100.)
                                x_offset = round((width - frame_size[0])/2.)
                                y_offset = round((height - frame_size[1])/2.)
                                image_captured = image_captured[y_offset:y_offset+frame_size[1], x_offset:x_offset+frame_size[0]]


                        if 'rescale' in self.settings and self.settings['rescale'] < 100 and self.settings['rescale'] > 0:
                            new_size = frame_size * self.settings['rescale']/100.
                            image_captured = cv2.resize(image_captured, (int(
                                new_size[0]), int(new_size[1])), cv2.INTER_LINEAR)
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
                        self.period = self.period*0.9 + current_period*0.1

                    self.image = image_captured

                    if self.stop_capture:
                        self.stop_capture = False
                        self.capture.release()
                        del self.capture
                        self.capture = None
                        self.image = None
                except cv2.error as e:
                    print('OpenCV error')
                    print(e)
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
