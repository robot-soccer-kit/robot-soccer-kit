import math
import numpy as np
import threading
from . import field_dimensions, utils, config, control, tasks
from .field import Field
import time

class Referee:
    def __init__(self, detection, ctrl: control.Control):
        self.control:control.Control = ctrl
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
        self.invicibility_frame = {}

        self.wait_ball_position = None
        self.goal_validated = None
        self.timed_circle_timers = {robot: 0 for robot in utils.all_robots()}

        self.game_state = {
            "team_colors": utils.robot_teams(),
            "team_names": ["",""],
            "game_is_running": False,
            "game_paused": True,
            "halftime_is_running": False, 
            "x_positive_goal": utils.robot_teams()[0],
            "timer": 0,
            "score": {team: 0 for team in utils.robot_teams()},
            "referee_history_sliced": [],
            "game_state_msg": "",
            "penalties": {},
            "control": None
        }

        #Robots Penalties
        self.penalties = {}
        self.resetPenalties()

        # Starting the Referee thread
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()
    
    def getFullGameState(self)-> dict:
        nb_history_send_to_JS = 3

        self.game_state["control"] = self.control.status()
        self.game_state["referee_history_sliced"] = self.referee_history[-nb_history_send_to_JS:]
        self.setTimer()
        self.setPenalty()

        return self.game_state

    def startGame(self):
        print("|Game Started")
        self.start_timer = time.time()
        self.game_state["game_paused"] = False
        self.chrono_is_running = True
        self.game_state["game_is_running"] = True
        self.referee_history = []
        self.game_state["referee_history_sliced"] = []
        self.resetScore()
        self.game_state["game_state_msg"] = "Game is running..."

    def pauseGame(self, reason:str ='manually-paused'):
        self.pause_timer = time.time()
        print("||Game Paused")
        self.game_state["game_paused"] = True

        task = tasks.StopAllTask(reason)
        self.control.add_task(task)
        self.game_state["game_state_msg"] = "Game has been manually paused"

    def resumeGame(self):
        print("||Game Resumed")
        self.game_state["game_paused"] = False
        self.game_state["game_state_msg"] = "Game is running..."
        self.wait_ball_position = None

        self.control.remove_task('manually-paused')
        self.control.remove_task('sideline-crossed')
        self.control.remove_task('goal')
        self.control.remove_task('half-time')

    def stopGame(self):
        print("|Game Stopped")
        self.game_state["game_paused"] = True
        self.game_state["game_is_running"] = False
        self.chrono_is_running = False
        self.start_timer = 0.
        self.resetPenalties()

        self.control.remove_task('manually-paused')
        self.control.remove_task('sideline-crossed')
        self.control.remove_task('goal') 
        self.control.remove_task('force-place')
        self.control.remove_task('half-time')

        self.game_state["game_state_msg"] = "Game is ready to start"


    def startHalfTime(self):
        self.start_timer = time.time()
        self.game_state["game_is_running"] = False
        self.game_state["halftime_is_running"] = True
        self.game_state["game_paused"] = True
        self.resetPenalties()
    
    def startSecondHalfTime(self):
        self.start_timer = time.time()
        self.game_state["halftime_is_running"] = False
        self.game_state["game_is_running"] = True
        self.game_state["game_state_msg"] = "Game is running..."
        self.resumeGame()

    def forcePlace(self, configuration:str):
        task = tasks.GoToConfigurationTask('force-place', configuration, priority=50)
        self.control.add_task(task)


    def placeGame(self, configuration:str):
        if configuration == "standard":
            if (self.game_state["x_positive_goal"] == utils.robot_teams()[1]):
                configuration = 'game_blue_positive'
            else:
                configuration = 'game_green_positive'

        elif configuration == "swap_covers":
            if (self.game_state["x_positive_goal"] == utils.robot_teams()[1]):
                configuration = 'swap_covers_blue_positive'
            else:
                configuration = 'swap_covers_green_positive'
        
        self.forcePlace(configuration)

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

    def detection_update(self, info):
        self.detection_info = info

    def setGameDuration(self, duration:int):
        self.game_duration = duration

    def resetPenalties(self):
        for robot_id in utils.all_robots_id():
            self.cancelPenalty(robot_id)

    def addPenalty(self, duration: float, robot: str):
        if self.penalties[robot]['remaining'] is None:
            self.penalties[robot]['remaining'] = float(duration)
            self.penalties[robot]['max'] = float(duration)
            team, number = utils.robot_str2list(robot)

            task = tasks.StopTask('penalty-' + robot, team, number)
            self.control.add_task(task)
        else:
            self.penalties[robot]['remaining'] += float(duration)
            self.penalties[robot]['max'] += float(duration)

    def cancelPenalty(self, robot: str):
        self.penalties[robot] = {
            'remaining': None,
            'grace': 3.,
            'max': 5.
        }

        self.control.remove_task('penalty-' + robot)
    
    def tickPenalty(self, elapsed:float):
        for robot in self.penalties:
            if self.penalties[robot]['remaining'] is not None:
                self.penalties[robot]['remaining'] -= elapsed
                if self.penalties[robot]['remaining'] < 0:
                    self.cancelPenalty(robot)
            if self.penalties[robot]['grace'] is not None:
                self.penalties[robot]['grace'] -= elapsed
                if self.penalties[robot]['grace'] < 0:
                    self.penalties[robot]['grace'] = None

    def canBePenalized(self, robot):
        return self.penalties[robot]['remaining'] is None and self.penalties[robot]['grace'] is None

    def setPenalty(self)-> dict:
        self.game_state["penalties"] = {
            robot: [
                math.ceil(self.penalties[robot]['remaining']) 
                if self.penalties[robot]['remaining'] is not None else None,
                int(self.penalties[robot]['max'])
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
                self.forcePlace('game_blue_positive')
            else:
                self.forcePlace('game_green_positive')

            self.wait_ball_position = (0., 0.)
            self.goal_validated = True
        else:
            self.updateScore(self.game_state["referee_history_sliced"][-1][2],-1)
            self.goal_validated = False
            self.resumeGame()

    def thread(self):
        # Initialisation coordinates goals
        [x_pos_goals_low,x_pos_goals_high] = field_dimensions.goalsCoord(True)
        [x_neg_goals_high,x_neg_goals_low]  = field_dimensions.goalsCoord(False)

        # Initialisation coordinates field for sidelines (+2cm)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = field_dimensions.fieldCoord(margin=0.02)
        # Initialisation coordinates field for reseting sidelines and goals memory (-10cm)
        [field_UpRight_in, _, field_DownLeft_in, _] = field_dimensions.fieldCoord(margin=-0.08)
        ball_out_field = False
        wait_ball_timestamp = None

        ball_coord_old = np.array([0,0])

        self.game_state["game_state_msg"] = "Game is ready to start"
        last_tick = time.time()

        while True:
            elapsed = time.time() - last_tick
            last_tick = time.time()

            if not self.game_state["game_paused"]:
                all_teams = utils.robot_teams()
                positive_team = self.game_state["x_positive_goal"]
                negative_team = all_teams[0] if all_teams[0] != self.game_state["x_positive_goal"] else all_teams[1]

                if self.detection_info is not None:
                    if self.detection_info['ball'] is not None:
                        ball_coord = np.array(self.detection_info['ball'])

                        if (ball_coord != ball_coord_old).any():
                            # Goals and ball trajectory intersection (Goal detection)
                            intersect_x_neg_goal, _ = utils.intersect(ball_coord_old,ball_coord,x_neg_goals_low,x_neg_goals_high)
                            intersect_x_pos_goal, _ = utils.intersect(ball_coord_old,ball_coord,x_pos_goals_low,x_pos_goals_high)
                            intersect_goal = intersect_x_neg_goal or intersect_x_pos_goal
        
                            if intersect_goal and not ball_out_field:
                                goal_team = positive_team if intersect_x_neg_goal else negative_team

                                self.updateScore(goal_team, 1)
                                self.addRefereeHistory(goal_team, "Goal")
                                ball_out_field = True
                                self.resetPenalties()
                                self.pauseGame("goal")
                                self.game_state["game_state_msg"] = "Waiting for Goal Validation"
                            
                            # Sideline (field+2cm margin) and ball trajectory intersection (Sideline fool detection)
                            intersect_field_Upline_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out,field_UpRight_out)
                            intersect_field_DownLine_out = utils.intersect(ball_coord_old,ball_coord,field_DownLeft_out, field_DownRight_out)
                            intersect_field_LeftLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out, field_DownLeft_out)
                            intersect_field_RightLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpRight_out, field_DownRight_out)

                            intersect_field_out = bool(intersect_field_Upline_out[0] or intersect_field_RightLine_out[0] or intersect_field_DownLine_out[0] or intersect_field_LeftLine_out[0])

                            if intersect_field_out and not intersect_goal and not ball_out_field:
                                for intersection in (intersect_field_Upline_out, intersect_field_DownLine_out, intersect_field_LeftLine_out, intersect_field_RightLine_out):
                                    has_intersection, point = intersection
                                    if has_intersection:
                                        self.game_state["game_state_msg"] = "Place the ball on the dot"
                                        self.wait_ball_position = (
                                            (1 if point[0] > 0 else -1) * field_dimensions.dots_x,
                                            (1 if point[1] > 0 else -1) * field_dimensions.dots_y
                                        )
                                    pass
                                ball_out_field = True
                                self.addRefereeHistory("neutral", "Sideline crossed")
                                self.pauseGame("sideline-crossed")

                            # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
                            if ball_out_field and utils.in_rectangle(ball_coord, field_DownLeft_in, field_UpRight_in):
                                ball_out_field = False

                            ball_coord_old = ball_coord

                    # Checking the robot respect timed circle and defense area rules
                    defender = {}
                    for marker in self.detection_info['markers']:
                            team, number = utils.robot_str2list(marker)
                            robot_position = np.array(self.detection_info['markers'][marker]['position'])

                            if team in utils.robot_teams():
                                robot = (team, number)

                                # Penalizing robots that are staying close to the ball
                                if self.detection_info['ball'] is not None and self.canBePenalized(marker):
                                    ball_position = np.array(self.detection_info['ball'])
                                    distance = np.linalg.norm(ball_position - robot_position)

                                    if distance < field_dimensions.timed_circle_radius:
                                        if self.timed_circle_timers[(team, number)] is None:
                                            self.timed_circle_timers[robot] = 0
                                        else:
                                            self.timed_circle_timers[robot] += elapsed

                                            if self.timed_circle_timers[robot] > 5:
                                                self.addPenalty(5., marker)
                                    else:
                                        self.timed_circle_timers[(team, number)] = None
                                else:
                                    self.timed_circle_timers[(team, number)] = None
                    
                                # Penalizing extra robots that are entering the defense area
                                if self.canBePenalized(marker):
                                    my_defense_area = field_dimensions.defenseArea(positive_team == team)
                                    opponent_defense_area = field_dimensions.defenseArea(positive_team != team)

                                    if utils.in_rectangle(robot_position, *opponent_defense_area):
                                        self.addPenalty(5., marker)

                                    if utils.in_rectangle(robot_position, *my_defense_area):
                                        if team in defender:
                                            other_robot, other_robot_position = defender[team]
                                            robot_to_penalize = marker

                                            if abs(other_robot_position[0]) < abs(robot_position[0]):
                                                robot_to_penalize = other_robot
                                            
                                            self.addPenalty(5., robot_to_penalize)
                                        else:
                                            defender[team] = [marker, robot_position]

                
                self.tickPenalty(elapsed)
            else:                              
                if self.game_state["halftime_is_running"]:
                    self.game_state["game_state_msg"] = "Half Time"
                    task = tasks.StopAllTask('half-time')
                    self.control.add_task(task)

                if (self.wait_ball_position is not None) and (self.detection_info is not None) and (self.detection_info['ball'] is not None):
                    # Computing target rectangle
                    x, y = self.wait_ball_position
                    margin = 0.05 # XXX: This should not be defined here

                    if utils.in_rectangle(self.detection_info['ball'], [x-margin, y-margin], [x+margin, y+margin]):
                        if wait_ball_timestamp is None:
                            wait_ball_timestamp = time.time()
                        elif time.time() - wait_ball_timestamp >= 1:
                            self.game_state["game_state_msg"] = "Game is running..."
                            self.goal_validated = None
                            self.resumeGame()
                    else:
                        wait_ball_timestamp = None
        

            # Maybe detection should not be responsible for drawing this    
            self.detection.wait_ball_position = self.wait_ball_position            

            time.sleep(0.1)