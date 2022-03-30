import numpy as np
import cv2
import threading
from . import field_dimensions
from .field import Field
import time

class Referee:
    def __init__(self, detection):
        self.ball = None
        self.field = Field()
        self.detection_info = None
        detection.on_update = self.detection_update

        # Starting the Referee thread
        self.running = True
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()
    
    def startReferee(self):
        print("Starting Referee")
        self.stop_capture = True

    def stopReferee(self):
        print("Stoping Referee")
        self.stop_capture = True
        self.running = False

    def detection_update(self, info):
        self.detection_info = info
        self.update(True)

    def update(self, new_detection = True):
        # if new_detection:
        #     print(self.detection_info)
        pass

    def thread(self):
        while self.running:
            self.update(False)
            if self.detection_info is not None:
                goals_coord = self.detection_info['goals_lines']
                ball_coord = self.detection_info['ball']
                if ball_coord is not None:
                    [ball_x, ball_y] = ball_coord
                    [ball_x_old, ball_y_old] = ball_coord
                if goals_coord['green_goals'] is not None:
                    [green_goals_high_x, green_goals_high_x],[green_goals_low_x, green_goals_low_y] = goals_coord['green_goals']
                    [blue_goals_high_x, blue_goals_high_y],[blue_goals_low_x, blue_goals_low_y]  = goals_coord['blue_goals']

            time.sleep(0.1)

    