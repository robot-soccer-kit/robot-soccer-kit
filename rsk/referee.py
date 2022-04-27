from turtle import listen
import numpy as np
import threading
from . import field_dimensions, utils, config
from .field import Field
import time
# from playsound import playsound

class Referee:
    def __init__(self, detection, robots):
        self.robots = robots
        self.control = self.robots.control
        self.detection = detection

        self.ball = None
        self.field = Field()
        self.detection_info = None
        detection.on_update = self.detection_update

        self.referee_history = []
        
        self.halftime_is_running = False
        self.chrono_is_running = False
        self.start_timer = 0.
        self.game_duration = 301.
        self.halftime_duration = 121.

        self.pause_timer = 0

        self.sideline_intersect = (False, np.array([0,0]))
        self.goal_validated = None

        self.game_state = {
            "team_colors": utils.robot_teams(),
            "team_names": ["",""],
            "game_is_running": False,
            "game_is_not_paused": False,
            "halftime_is_running": False, 
            "x_positive_goal": utils.robot_teams()[0],
            "timer": 0,
            "score": {team: 0 for team in utils.robot_teams()},
            "referee_history_sliced": [],
            "game_state_msg": "",
            "penalties": {},
            "robots_state": {
                robots: {"state":"", "preemption_reasons":()}
                for robots in utils.all_robots_id()
                }
        }

        #Robots Penalties
        self.penalties = {}
        self.resetPenalty()

        # Starting the Referee thread
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()
    
    def getFullGameState(self)-> dict:
        nb_history_send_to_JS = 3

        for color in utils.robot_teams():
            for number in utils.robot_numbers():
                self.game_state["robots_state"][color+str(number)]["preemption_reasons"] = tuple(self.control.teams[color]["preemption_reasons"][number])

        self.game_state["referee_history_sliced"] = self.referee_history[-nb_history_send_to_JS:]
        self.setTimer()
        self.setPenalty()

        return self.game_state

    def startGame(self):
        print("|Game Started")
        # playsound('rsk/static/sounds/a.wav',False)
        self.start_timer = time.time()
        self.game_state["game_is_not_paused"] = True
        self.chrono_is_running = True
        self.game_state["game_is_running"] = True
        self.referee_history = []
        self.game_state["referee_history_sliced"] = []
        self.resetScore()
        self.game_state["game_state_msg"] = "Game is running..."

    def pauseGame(self, reason=None):
        self.pause_timer = time.time()
        print("||Game Paused")
        self.game_state["game_is_not_paused"] = False

        if reason is not None: 
            self.control.preempt_all_robots(reason)
        else:
            self.control.preempt_all_robots("manually paused")
            self.game_state["game_state_msg"] = "Game has been manually paused"

        self.control.stop_all()


    def resumeGame(self):
        print("||Game Resumed")
        self.game_state["game_is_not_paused"] = True 
        self.resumePenalty()
        for color, number in utils.all_robots():
            if self.control.is_preempted(color, number, "manually paused"):
                self.control.unpreempt_robot(color, number, "manually paused")
            if self.control.is_preempted(color, number, "sideline crossed"):
                self.control.unpreempt_robot(color, number, "sideline crossed")
        self.game_state["game_state_msg"] = "Game is running..."


    def stopGame(self):
        print("|Game Stopped")
        # playsound('rsk/static/sounds/b.wav',False)
        self.game_state["game_is_not_paused"] = False
        self.game_state["game_is_running"] = False
        self.chrono_is_running = False
        self.start_timer = 0.
        self.resetPenalty()
        for reason in ["sideline crossed","goal","manually paused"]:
            for color, number in utils.all_robots():
                if self.control.is_preempted(color,number,reason):
                    self.control.unpreempt_robot(color,number,reason)
        self.game_state["game_state_msg"] = "Game is ready to start"


    def startHalfTime(self):
        # playsound('rsk/static/sounds/c.wav',False)
        self.start_timer = time.time()
        self.game_state["game_is_running"] = False
        self.game_state["halftime_is_running"] = True
        self.game_state["game_is_not_paused"] = False
        self.resetPenalty()
    
    def startSecondHalfTime(self):
        # playsound('rsk/static/sounds/d.wav',False)
        self.start_timer = time.time()
        self.game_state["halftime_is_running"] = False
        self.game_state["game_is_not_paused"] = True
        self.game_state["game_is_running"] = True
        self.game_state["game_state_msg"] = "Game is running..."

    def placeGame(self, configuration):
        self.control.preempt_all_robots('force place robots')
        if configuration == "standard":
            if (self.game_state["x_positive_goal"] == utils.robot_teams()[1]):
                self.control.set_target_configuration('game-blue-positive')
            else:
                self.control.set_target_configuration('game-green-positive')

        elif configuration == "swap_covers":
            if (self.game_state["x_positive_goal"] == utils.robot_teams()[1]):
                self.control.set_target_configuration('swap_covers_blue_positive')
            else:
                self.control.set_target_configuration('swap_covers_green_positive')

        else: 
            self.control.set_target_configuration(configuration)

    def updateScore(self, team: str, increment: int):
        if team == utils.robot_teams()[0] : 
            self.game_state["score"][utils.robot_teams()[0]] += increment
        elif team == utils.robot_teams()[1] : 
            self.game_state["score"][utils.robot_teams()[1]] += increment

    def resetScore(self):
        for team in utils.robot_teams():
            self.game_state["score"][team] = 0

    def addRefereeHistory(self, team: str, action: str) -> list:
        timestamp = self.game_state["timer"]
        i = len(self.referee_history)
        new_history_line= [i, timestamp, team, action]
        self.referee_history.append(new_history_line)
        return self.referee_history
    
    def getIntersection(self):
        return self.sideline_intersect

    def detection_update(self, info):
        self.detection_info = info

    def setGameDuration(self, duration:int):
        self.game_duration = duration

    def resetPenalty(self):
        for robot_id in utils.all_robots_id():
            self.cancelPenalty(robot_id)
    
    def resumePenalty(self):
        for robot in self.penalties:
                if self.penalties[robot]['time_end'] is not None:
                    self.penalties[robot]['time_end'] += time.time() - self.pause_timer

    def addPenalty(self, duration: int, robot: str):
        if self.penalties[robot]['time_end'] is None:
            self.penalties[robot]['time_end'] = time.time() + duration + 1
            self.penalties[robot]['max'] = duration
            [color, number] = utils.robot_str2list(robot)
            self.control.preempt_robot(color, number,"penalty")

        else:
            self.penalties[robot]['time_end'] += duration
            self.penalties[robot]['max'] += duration

    def cancelPenalty(self, robot: str):
        self.penalties[robot] = {
            'time_end': None,
            'max': 5
        }
        [color, number] = utils.robot_str2list(robot)
        if self.control.is_preempted(color, number, "penalty"):
            self.control.unpreempt_robot(color, number,"penalty")
    
    def tickPenalty(self):
        for robot in self.penalties:
            if (self.penalties[robot]['time_end'] is not None) and (self.penalties[robot]['time_end'] < time.time() + 1):
                self.penalties[robot]['time_end'] = None
                [color, number] = utils.robot_str2list(robot)
                self.control.unpreempt_robot(color, number,"penalty")

    def setPenalty(self)-> dict:
        if self.game_state["game_is_not_paused"]:
            self.game_state["penalties"] = {
                robot: [
                    int(self.penalties[robot]['time_end'] - time.time())
                    if self.penalties[robot]['time_end'] is not None else None,
                    self.penalties[robot]['max']
                ]
                for robot in self.penalties
            }
        else:
            self.game_state["penalties"] = {
                robot: [
                    int(self.penalties[robot]['time_end'] - self.pause_timer)
                    if self.penalties[robot]['time_end'] is not None else None,
                    self.penalties[robot]['max']
                ]
                for robot in self.penalties  
            }

    def setTimer(self):
        if self.game_state["game_is_running"]:
            duration = self.game_duration
        elif self.game_state["halftime_is_running"]:
            duration = self.halftime_duration

        if self.chrono_is_running :
            self.game_state["timer"] = int((self.start_timer + duration) - time.time())
        else:
            self.game_state["timer"] = 0

    def setTeamNames(self,team: str, name: str):
        if team == utils.robot_teams()[0]:
            self.game_state["team_names"][0] = name
        elif team == utils.robot_teams()[1]:
            self.game_state["team_names"][1] =  name

    def setTeamSides(self):
        if self.game_state["x_positive_goal"] == utils.robot_teams()[0]:
            self.game_state["x_positive_goal"] = utils.robot_teams()[1]
        elif self.game_state["x_positive_goal"] == utils.robot_teams()[1]:
            self.game_state["x_positive_goal"] = utils.robot_teams()[0]

    def validateGoal(self, yes_no: bool):
        if yes_no:
            if (self.game_state["x_positive_goal"] == utils.robot_teams()[1]):
                self.control.set_target_configuration('game-blue-positive')
            else:
                self.control.set_target_configuration('game-green-positive')

            self.goal_validated = True
            self.detection.goal_validated = True
        else:
            self.updateScore(self.game_state["referee_history_sliced"][-1][2],-1)
            self.goal_validated = False
            self.detection.goal_validated = False

    def thread(self):
        # Initialisation coordinates goals
        [x_pos_goals_low,x_pos_goals_high] = field_dimensions.goalsCoord("x_positive")
        [x_neg_goals_high,x_neg_goals_low]  = field_dimensions.goalsCoord("x_negative")

        # Initialisation coordinates field for sidelines (+2cm)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = field_dimensions.fieldCoordMargin(0.02)
        # Initialisation coordinates field for reseting sidelines and goals memory (-10cm)
        [_, field_DownRight_in, _, field_UpLeft_in] = field_dimensions.fieldCoordMargin(-0.08)
        memory = 0
        memory_sideline_timestamp = 0

        ball_coord_old = np.array([0,0])

        self.game_state["game_state_msg"] = "Game is ready to start"

        while True:
            if self.game_state["game_is_not_paused"]:
                if self.detection_info is not None:
                    if self.detection_info['ball'] is not None:
                        ball_coord = np.array(self.detection_info['ball'])
                        if (ball_coord_old[0] != ball_coord[0] and ball_coord_old[1] != ball_coord[1]):
                            # Goals and ball trajectory intersection (Goal detection)
                            intersect_x_neg_goal = utils.intersect(ball_coord_old,ball_coord,x_neg_goals_low,x_neg_goals_high)
                            intersect_x_pos_goal = utils.intersect(ball_coord_old,ball_coord,x_pos_goals_low,x_pos_goals_high)
                            
                            
                            if self.game_state["x_positive_goal"] == utils.robot_teams()[0]:
                                if intersect_x_neg_goal[0]:
                                    GoalTeam = (utils.robot_teams()[0],"f")
                                if intersect_x_pos_goal[0]:
                                    GoalTeam = (utils.robot_teams()[1],"e")
                            elif self.game_state["x_positive_goal"] == utils.robot_teams()[1]:
                                if intersect_x_neg_goal[0]: 
                                    GoalTeam = (utils.robot_teams()[1],"e")
                                if intersect_x_pos_goal[0]: 
                                    GoalTeam = (utils.robot_teams()[0],"f")

                            if (intersect_x_neg_goal[0] or intersect_x_pos_goal[0]) and memory == 0:
                                self.updateScore(GoalTeam[0], 1)
                                self.addRefereeHistory(GoalTeam[0], "Goal")
                                # playsound('rsk/static/sounds/'+GoalTeam[1]+'.wav',False)
                                memory = 1
                                self.pauseGame("goal")
                                self.game_state["game_state_msg"] = "Waiting for Goal Validation"

                            
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
                                # playsound('rsk/static/sounds/g.wav',False)
                                self.pauseGame("sideline crossed")

                            # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
                            if memory == 1:
                                intersect_field_in = bool(
                                    (field_UpLeft_in[0]<=ball_coord[0]<=field_DownRight_in[0]) 
                                    and 
                                    (field_DownRight_in[1]<=ball_coord[1]<=field_UpLeft_in[1]))

                                if intersect_field_in:
                                    memory = 0

                            ball_coord_old = ball_coord
                
                self.tickPenalty()

                time.sleep(0.1)
            else:
                time.sleep(0.5)
                
                if self.game_state["halftime_is_running"]:
                    self.game_state["game_state_msg"] = "Half Time"
                    self.control.preempt_all_robots('half time')
                else:
                    self.control.unpreempt_all_robots('half time')

                [color, number] = utils.all_robots()[0]

                if self.control.is_preempted(color, number,"sideline crossed"):
                    if (self.sideline_intersect[1][0]>=0) and (self.sideline_intersect[1][1]>0):
                        self.game_state["game_state_msg"] = "Place the ball on dot 1"
                        self.detection.sideline_dots = "dot1"
                    elif (self.sideline_intersect[1][0]>0) and (self.sideline_intersect[1][1]<=0):
                        self.game_state["game_state_msg"] = "Place the ball on dot 2"
                        self.detection.sideline_dots = "dot2"
                    elif (self.sideline_intersect[1][0]<=0) and (self.sideline_intersect[1][1]<0):
                        self.game_state["game_state_msg"] = "Place the ball on dot 3"
                        self.detection.sideline_dots = "dot3"
                    elif(self.sideline_intersect[1][0]<0) and (self.sideline_intersect[1][1]>=0):
                        self.game_state["game_state_msg"] = "Place the ball on dot 4"
                        self.detection.sideline_dots = "dot4"

                    if self.detection.sideline_dots is not None:
                        pointA = [field_dimensions.dots_pos[self.detection.sideline_dots][0]-0.05,field_dimensions.dots_pos[self.detection.sideline_dots][1]+0.05]
                        pointB = [field_dimensions.dots_pos[self.detection.sideline_dots][0]+0.05,field_dimensions.dots_pos[self.detection.sideline_dots][1]-0.05]

                        if self.detection_info is not None:
                            if self.detection_info['ball'] is not None:
                                ball_coord = np.array(self.detection_info['ball'])

                                if (pointA[0]<=ball_coord[0]<=pointB[0]) and (pointB[1]<=ball_coord[1]<=pointA[1]):
                                    if memory_sideline_timestamp == 0:
                                        start = time.time()
                                        memory_sideline_timestamp = 1

                                    if time.time() - start >= 2:
                                        self.control.unpreempt_all_robots("sideline crossed")
                                        self.detection.sideline_dots = None
                                        memory_sideline_timestamp = 0
                                        self.game_state["game_state_msg"] = "Game is running..."
                                        self.resumeGame()

                if self.control.is_preempted(color, number,"goal"):
                    if self.goal_validated is not None : 
                        if self.goal_validated:
                            pointA = [-0.05,0.05]
                            pointB = [0.05,-0.05]
                        else: 
                            if self.game_state["referee_history_sliced"][-1][2] == self.game_state["x_positive_goal"]:
                                self.detection.canceled_goal_side = "xpos_goal"
                                pointA = [-0.29-0.05,0.05]
                                pointB = [-0.29+0.05,-0.05]
                            else:
                                self.detection.canceled_goal_side = "xneg_goal"
                                pointA = [0.29-0.05,0.05]
                                pointB = [0.29+0.05,-0.05]

                        if self.detection_info is not None:
                            if self.detection_info['ball'] is not None:
                                ball_coord = np.array(self.detection_info['ball'])
                                print(pointA, ball_coord, pointB)
                                if (pointA[0]<=ball_coord[0]<=pointB[0]) and (pointB[1]<=ball_coord[1]<=pointA[1]):
                                    if memory_sideline_timestamp == 0:
                                        start = time.time()
                                        memory_sideline_timestamp = 1

                                    if time.time() - start >= 2:
                                        self.control.unpreempt_all_robots("goal")
                                        self.detection.sideline_dots = None
                                        memory_sideline_timestamp = 0
                                        self.game_state["game_state_msg"] = "Game is running..."
                                        self.detection.canceled_goal_side = None
                                        self.detection.goal_validated = None
                                        self.goal_validated = None
                                        self.resumeGame()

                                                