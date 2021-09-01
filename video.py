import time
import cv2
import base64
from imutils.video import VideoStream
import threading

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
        capture.start()
        captures[index] = capture

    time.sleep(0.1)
    return image is not None

def setCameraSettings(brightness, contrast):
    if capture is not None:
        capture.stream.stream.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
        capture.stream.stream.set(cv2.CAP_PROP_CONTRAST, contrast)

def thread():
    global capture, image
    while True:
        if capture is not None:
            image = capture.read()
            if image is None:
                capture = None

def getImage():
    global image
    if image is not None:
        data = cv2.imencode('.jpg', image)
        return base64.b64encode(data[1]).decode('utf-8')
    else:
        return ''

captures = {}
capture = None
image = None
cameras = listCameras()

video_thread = threading.Thread(target=thread)
video_thread.start()