import time
import numpy as np
import cv2
import base64
from imutils.video import VideoStream
import threading
import detection
import field

# Limitting the output period
min_period = 1/30
# Image retrieve and processing duration
period = None
# Current capture opened streams
captures = {}
# Current capture
capture = None
# The last retrieved image
image = None

def listCameras():
    indexes = []
    for index in range(10):
        cap = cv2.VideoCapture(index)
        if cap.read()[0]:
            indexes.append(index)
            cap.release()
    return indexes

def startCapture(index):
    global captures, capture, image

    if index in captures:
        capture = captures[index]
    else:
        capture = VideoStream(src=index, framerate=25)
        capture.stream.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        capture.stream.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        capture.start()
        captures[index] = capture

    time.sleep(0.1)
    return image is not None

def stopCapture():
    global capture, image
    capture = None
    image = None

def setCameraSettings(brightness, contrast):
    if capture is not None:
        capture.stream.stream.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
        capture.stream.stream.set(cv2.CAP_PROP_CONTRAST, contrast)

def thread():
    global capture, image, period
    while True:
        if capture is not None:
            t0 = time.time()
            image_captured = capture.read()

            # Process the image
            detection.detectAruco(image_captured)
            detection.detectBall(image_captured)

            # Computing time
            current_period = time.time() - t0
            if current_period < min_period:
                time.sleep(min_period - current_period)
            current_period = time.time() - t0

            if period is None:
                period = current_period
            else:
                period = period*0.99 + current_period*0.01

            if image_captured is None:
                capture = None

            image = image_captured
        else:
            time.sleep(0.1)

def getImage():
    global image
    if image is not None:
        data = cv2.imencode('.jpg', image)
        return base64.b64encode(data[1]).decode('utf-8')
    else:
        return ''

def getVideo():
    global period
    return {
        'image': getImage(), 
        'fps': round(1/period, 2) if period is not None else 0,
        'detection': detection.getDetection()
    }

# Listing available cameras
cameras = listCameras()

# Starting the video processing thread
video_thread = threading.Thread(target=thread)
video_thread.start()
