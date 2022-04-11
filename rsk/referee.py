import numpy as np
import threading
from . import field_dimensions, utils, config
from .field import Field
import time

class Referee:
    def __init__(self, detection):
        self.ball = None
        self.field = Field()
        self.detection_info = None
        detection.on_update = self.detection_update
        
        self.green_score = 0
        self.blue_score = 0

        self.referee_history = []
        
        self.game_is_running = False
        self.start_timer = 0.

        self.running = False
        self.sideline_intersect = (False, np.array([0,0]))

        # Starting the Referee thread
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()


    
    def startReferee(self):
        print("Starting Referee")
        self.running = True
        self.stop_capture = True

    def stopReferee(self):
        print("Stoping Referee")
        self.stop_capture = True
        self.running = False

    def startGame(self):
        print("|Game Started")
        self.start_timer = time.time()
        self.game_is_running = True

    def pauseGame(self):
        print("||Game Paused")

    def resumeGame(self):
        print("||Game Resumed")

    def stopGame(self):
        print("|Game Stopped")
        self.game_is_running = False
        self.start_timer = 0.

    def updateScore(self, team, increment):
        if team == "green" : 
            self.green_score = self.green_score + increment
        elif team == "blue" : 
            self.blue_score = self.blue_score + increment
        pass

    def resetScore(self):
        self.green_score = 0
        self.blue_score = 0

    def getScore(self, team):
        if team == "green" : 
            return self.green_score
        elif team == "blue" : 
            return self.blue_score

    def detection_update(self, info):
        self.detection_info = info
        self.update(True)

    def update(self, new_detection = True):
        # if new_detection:
        #     print(self.detection_info)
        pass

    def getIntersection(self):
        return self.sideline_intersect
    
    def getTimer(self):
        if self.game_is_running :
            time_now = time.time() - self.start_timer
            minutes = int(time_now / 60)
            seconds = int(time_now % 60)
        else : 
            minutes = 0
            seconds = 0
        return [minutes, seconds]

    def thread(self):
        # Initialisation coordinates goals
        [green_goals_low,green_goals_high] = field_dimensions.goalsCoord("green")
        [blue_goals_high,blue_goals_low]  = field_dimensions.goalsCoord("blue")

        # Initialisation coordinates field for sidelines (+2cm)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = field_dimensions.fieldCoordMargin(0.02)
        # Initialisation coordinates field for reseting sidelines and goals memory (-10cm)
        [field_UpRight_in, field_DownRight_in, field_DownLeft_in, field_UpLeft_in] = field_dimensions.fieldCoordMargin(-0.08)
        memory = 0

        ball_coord_old = np.array([0,0])

        while True:
            if self.running:
                self.update(False)
                if self.detection_info is not None:
                    if self.detection_info['ball'] is not None:
                        ball_coord = np.array(self.detection_info['ball'])
                        if (ball_coord_old[0] != ball_coord[0] and ball_coord_old[1] != ball_coord[1]):
                            # Goals and ball trajectory intersection (Goal detection)
                            intersect_blue_goal = utils.intersect(ball_coord_old,ball_coord,blue_goals_low,blue_goals_high)
                            intersect_green_goal = utils.intersect(ball_coord_old,ball_coord,green_goals_low,green_goals_high)
                            if intersect_blue_goal[0] and memory == 0: 
                                self.updateScore("green", 1)
                                memory = 1
                            if intersect_green_goal[0] and memory == 0: 
                                self.updateScore("blue", 1)
                                memory = 1
                            
                            # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
                            if memory == 1:
                                intersect_field_in = bool(
                                    (field_UpLeft_in[0]<=ball_coord[0]<=field_DownRight_in[0]) 
                                    and 
                                    (field_DownRight_in[1]<=ball_coord[1]<=field_UpLeft_in[1]))

                                if intersect_field_in:
                                    memory = 0
                                    print("reset")
                            
                            # Sideline (field+2cm margin) and ball trajectory intersection (Sideline fool detection)
                            intersect_field_Upline_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out,field_UpRight_out)
                            intersect_field_DownLine_out = utils.intersect(ball_coord_old,ball_coord,field_DownLeft_out, field_DownRight_out)
                            intersect_field_LeftLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out, field_DownLeft_out)
                            intersect_field_RightLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpRight_out, field_DownRight_out)

                            intersect_field_out = bool(intersect_field_Upline_out[0] or intersect_field_RightLine_out[0] or intersect_field_DownLine_out[0] or intersect_field_LeftLine_out[0])
                            
                            if intersect_field_out and not (intersect_blue_goal[0] or intersect_green_goal[0]) and memory == 0:
                                for i in (intersect_field_Upline_out, intersect_field_DownLine_out, intersect_field_LeftLine_out, intersect_field_RightLine_out):
                                    if i[0]:
                                        self.sideline_intersect = (True, i[1])
                                    pass
                                memory = 1
                                print("line crossed")

                            ball_coord_old = ball_coord
                time.sleep(0.1)
            
            else:
                time.sleep(0.5)