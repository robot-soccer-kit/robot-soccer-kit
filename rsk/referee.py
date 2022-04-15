import numpy as np
import threading
from . import field_dimensions, utils, config
from .field import Field
import time
from playsound import playsound

class Referee:
    def __init__(self, detection):
        self.ball = None
        self.field = Field()
        self.detection_info = None
        detection.on_update = self.detection_update
        
        self.green_score = 0
        self.blue_score = 0
        self.xpos_is_green = True

        self.referee_history = []
        self.game_state = ""
        
        self.game_is_running = False
        self.halftime_is_running = False
        self.chrono_is_running = False
        self.start_timer = 0.
        self.game_duration = 301.
        self.halftime_duration = 121.

        self.running = False
        self.sideline_intersect = (False, np.array([0,0]))

        # Starting the Referee thread
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()

    # def startReferee(self):
    #     print("Starting Referee")
    #     self.running = True
    #     self.referee_history = []
    #     self.resetScore()

    # def stopReferee(self):
    #     print("Stopping Referee")
    #     self.stopGame()
    #     self.running = False

    def startGame(self):
        print("|Game Started")
        playsound('rsk/static/sounds/a.wav',False)
        self.start_timer = time.time()
        self.running = True
        self.chrono_is_running = True
        self.game_is_running = True
        self.referee_history = []
        self.resetScore()


    def pauseGame(self):
        print("||Game Paused")
        self.running = False

    def resumeGame(self):
        print("||Game Resumed")
        self.running = True 

    def placeGame(self):
        pass

    def stopGame(self):
        print("|Game Stopped")
        playsound('rsk/static/sounds/b.wav',False)
        self.running = False
        self.game_is_running = False
        self.chrono_is_running = False
        self.start_timer = 0.

    def startHalfTime(self):
        playsound('rsk/static/sounds/c.wav',False)
        self.start_timer = time.time()
        self.game_is_running = False
        self.halftime_is_running = True
        self.running = False
    
    def startSecondHalfTime(self):
        playsound('rsk/static/sounds/d.wav',False)
        self.start_timer = time.time()
        self.halftime_is_running = False
        self.running = True
        self.game_is_running = True

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

    def addRefereeHistory(self, team: str, action: str) -> list:
        [minutes, seconds,sign] = self.getTimer()
        i = len(self.referee_history)
        if sign == "neg" and minutes == 0:
            minutes ="-" + str(minutes)
        new_history_line= [i, minutes, seconds, team, action]
        self.referee_history.append(new_history_line)
        return self.referee_history

    def getRefereeHistory(self, slice)-> list:
        last_rows = []
        if len(self.referee_history)<slice:
            return self.referee_history
        else:
            for i in range(len(self.referee_history)-slice, len(self.referee_history)):
                last_rows.append(self.referee_history[i])
        return last_rows

    def setGameState(self, msg_state):
        self.game_state = msg_state

    def getGameState(self):
        return self.game_state
    
    def getIntersection(self):
        return self.sideline_intersect

    def detection_update(self, info):
        self.detection_info = info
        self.update(True)

    def update(self, new_detection = True):
        # if new_detection:
        #     print(self.detection_info)
        pass

    def setGameDuration(self, duration):
        self.game_duration = duration

    def getTimer(self):
        sign="pos"
        if self.game_is_running:
            duration = self.game_duration
        elif self.halftime_is_running:
            duration = self.halftime_duration

        if self.chrono_is_running :
            time_now =  (self.start_timer + duration) - time.time()
            if time_now > 0:
                minutes = int(time_now / 60)
                seconds = int(time_now % 60)
                sign = "pos"
            else:
                time_now =  time.time() - (self.start_timer + duration) + 1
                minutes = -int(time_now / 60)
                seconds = int(time_now % 60)  
                sign = "neg"
        else : 
            minutes = 0
            seconds = 0
        return [minutes, seconds, sign]

    def setTeamSides(self):
        if self.xpos_is_green == False:
            self.xpos_is_green = True
        elif self.xpos_is_green == True:
            self.xpos_is_green = False

    def thread(self):
        # Initialisation coordinates goals
        [x_pos_goals_low,x_pos_goals_high] = field_dimensions.goalsCoord("x_positive")
        [x_neg_goals_high,x_neg_goals_low]  = field_dimensions.goalsCoord("x_negative")

        # Initialisation coordinates field for sidelines (+2cm)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = field_dimensions.fieldCoordMargin(0.02)
        # Initialisation coordinates field for reseting sidelines and goals memory (-10cm)
        [field_UpRight_in, field_DownRight_in, field_DownLeft_in, field_UpLeft_in] = field_dimensions.fieldCoordMargin(-0.08)
        memory = 0

        ball_coord_old = np.array([0,0])

        self.setGameState("Game is ready to start")

        while True:
            if self.running:
                self.update(False)
                if self.detection_info is not None:
                    if self.detection_info['ball'] is not None:
                        ball_coord = np.array(self.detection_info['ball'])
                        if (ball_coord_old[0] != ball_coord[0] and ball_coord_old[1] != ball_coord[1]):
                            # Goals and ball trajectory intersection (Goal detection)
                            intersect_x_neg_goal = utils.intersect(ball_coord_old,ball_coord,x_neg_goals_low,x_neg_goals_high)
                            intersect_x_pos_goal = utils.intersect(ball_coord_old,ball_coord,x_pos_goals_low,x_pos_goals_high)

                            if self.xpos_is_green:
                                if intersect_x_neg_goal[0] and memory == 0: 
                                    self.updateScore("green", 1)
                                    self.addRefereeHistory("green", "goal")
                                    playsound('rsk/static/sounds/e.wav',False)
                                    memory = 1
                                if intersect_x_pos_goal[0] and memory == 0: 
                                    self.updateScore("blue", 1)
                                    self.addRefereeHistory("blue", "goal")
                                    playsound('rsk/static/sounds/f.wav',False)
                                    memory = 1

                            else:
                                if intersect_x_neg_goal[0] and memory == 0: 
                                    self.updateScore("blue", 1)
                                    self.addRefereeHistory("blue", "goal")
                                    playsound('rsk/static/sounds/f.wav',False)
                                    memory = 1
                                if intersect_x_pos_goal[0] and memory == 0: 
                                    self.updateScore("gren", 1)
                                    self.addRefereeHistory("green", "goal")
                                    playsound('rsk/static/sounds/e.wav',False)
                                    memory = 1
                            
                            # Sideline (field+2cm margin) and ball trajectory intersection (Sideline fool detection)
                            intersect_field_Upline_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out,field_UpRight_out)
                            intersect_field_DownLine_out = utils.intersect(ball_coord_old,ball_coord,field_DownLeft_out, field_DownRight_out)
                            intersect_field_LeftLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out, field_DownLeft_out)
                            intersect_field_RightLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpRight_out, field_DownRight_out)

                            intersect_field_out = bool(intersect_field_Upline_out[0] or intersect_field_RightLine_out[0] or intersect_field_DownLine_out[0] or intersect_field_LeftLine_out[0])

                            if intersect_field_out and not (intersect_x_neg_goal[0] or intersect_x_pos_goal[0]) and memory == 0:
                                for i in (intersect_field_Upline_out, intersect_field_DownLine_out, intersect_field_LeftLine_out, intersect_field_RightLine_out):
                                    if i[0]:
                                        self.sideline_intersect = (True, i[1])
                                    pass
                                memory = 1
                                self.addRefereeHistory("neutral", "Sideline crossed")
                                playsound('rsk/static/sounds/g.wav',False)

                            # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
                            if memory == 1:
                                intersect_field_in = bool(
                                    (field_UpLeft_in[0]<=ball_coord[0]<=field_DownRight_in[0]) 
                                    and 
                                    (field_DownRight_in[1]<=ball_coord[1]<=field_UpLeft_in[1]))

                                if intersect_field_in:
                                    memory = 0

                            ball_coord_old = ball_coord
                time.sleep(0.1)
            
            else:
                time.sleep(0.5)