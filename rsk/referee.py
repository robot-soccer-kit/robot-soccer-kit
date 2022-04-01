import numpy as np
import cv2
import threading
from . import field_dimensions, utils
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
        [green_goals_high,green_goals_low] = field_dimensions.goalsCoord("green")
        [blue_goals_high,blue_goals_low]  = field_dimensions.goalsCoord("blue")
        ball_coord_old = np.array([0,0])
        while self.running:
            self.update(False)
            if self.detection_info is not None:
                if self.detection_info['ball'] is not None:
                    ball_coord = np.array(self.detection_info['ball'])
                    if (ball_coord_old is not ball_coord):
                        print(ball_coord)
                        intersect_blue_goal = utils.intersect(ball_coord_old,ball_coord,blue_goals_low,blue_goals_high)
                        intersect_green_goal = utils.intersect(ball_coord_old,ball_coord,green_goals_low,green_goals_high)
                        if intersect_blue_goal is not None: 
                            print("Green GOAL")
                        if intersect_green_goal is not None: 
                            print("Blue GOAL")
                        ball_coord_old = ball_coord


            time.sleep(0.1)