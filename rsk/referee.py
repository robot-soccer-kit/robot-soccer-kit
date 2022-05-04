import math
import numpy as np
import threading
import logging
from . import constants, utils, config, control, tasks
from .field import Field
import time

class Referee:
    """
    Handles the referee
    """    

    def __init__(self, detection, control: control.Control):
        self.logger: logging.Logger = logging.getLogger("referee")

        self.control:control.Control = control
        self.detection = detection

        self.detection_info = None
        detection.on_update = self.detection_update

        self.referee_history = []
        
        self.halftime_is_running:bool = False
        self.chrono_is_running:bool = False
        self.start_timer = 0.

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

        # Robots Penalties
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
        self.logger.info("Game started")
        self.start_timer = time.time()
        self.game_state["game_paused"] = False
        self.chrono_is_running = True
        self.game_state["game_is_running"] = True
        self.referee_history = []
        self.game_state["referee_history_sliced"] = []
        self.resetScore()
        self.game_state["game_state_msg"] = "Game is running..."

    def pauseGame(self, reason:str ='manually-paused'):
        self.logger.info(f"Game paused, reason: {reason}")

        self.game_state["game_paused"] = True

        task = tasks.StopAllTask(reason)
        self.control.add_task(task)
        self.game_state["game_state_msg"] = "Game has been manually paused"

    def resumeGame(self):
        self.logger.info("Game resumed")
        self.game_state["game_paused"] = False
        self.game_state["game_state_msg"] = "Game is running..."
        self.wait_ball_position = None

        self.control.remove_task('manually-paused')
        self.control.remove_task('sideline-crossed')
        self.control.remove_task('goal')
        self.control.remove_task('half-time')

    def stopGame(self):
        self.logger.info("Game stopped")
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
        self.game_state["game_state_msg"] = "Half Time"
        task = tasks.StopAllTask('half-time')
        self.control.add_task(task)
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

    def resetPenalties(self):
        for robot_id in utils.all_robots_id():
            self.cancelPenalty(robot_id)

    def addPenalty(self, duration: float, robot: str, reason: str = 'manually_penalized'):
        self.penalties[robot]['reason'] = reason

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
            'reason': None,
            'grace': constants.grace_time,
            'max': constants.default_penalty
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
                int(self.penalties[robot]['max']),
                self.penalties[robot]['reason']
            ]
            for robot in self.penalties
        }

    def setTimer(self):
        if self.game_state["game_is_running"]:
            duration = constants.game_duration
        elif self.game_state["halftime_is_running"]:
            duration = constants.halftime_duration

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

    def check_line_crosses(self, ball_coord:np.ndarray, ball_coord_old:np.ndarray):
        """
        Checks for line crosses (sideline crosses and goals)

        :param np.ndarray ball_coord: ball position (now)
        :param np.ndarray ball_coord_old: ball position on previous frame
        """        
        [x_pos_goals_low,x_pos_goals_high] = constants.goal_posts(x_positive=True)
        [x_neg_goals_high,x_neg_goals_low]  = constants.goal_posts(x_positive=False)
        [field_UpRight_in, _, field_DownLeft_in, _] = constants.field_corners(margin=constants.field_in_margin)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = constants.field_corners(margin=constants.field_out_margin)
    
        # Goals and ball trajectory intersection (Goal detection)
        intersect_x_neg_goal, _ = utils.intersect(ball_coord_old,ball_coord,x_neg_goals_low,x_neg_goals_high)
        intersect_x_pos_goal, _ = utils.intersect(ball_coord_old,ball_coord,x_pos_goals_low,x_pos_goals_high)
        intersect_goal = intersect_x_neg_goal or intersect_x_pos_goal

        if intersect_goal and not self.ball_out_field:
            goal_team = self.positive_team if intersect_x_neg_goal else self.negative_team
            self.logger.info(f"Goal for team {goal_team}")

            self.ball_out_field = True
            self.updateScore(goal_team, 1)
            self.addRefereeHistory(goal_team, "Goal")
            self.resetPenalties()
            self.pauseGame("goal")
            self.game_state["game_state_msg"] = "Waiting for Goal Validation"
        
        # Sideline (field+2cm margin) and ball trajectory intersection (Sideline fool detection)
        intersect_field_Upline_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out,field_UpRight_out)
        intersect_field_DownLine_out = utils.intersect(ball_coord_old,ball_coord,field_DownLeft_out, field_DownRight_out)
        intersect_field_LeftLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpLeft_out, field_DownLeft_out)
        intersect_field_RightLine_out = utils.intersect(ball_coord_old,ball_coord,field_UpRight_out, field_DownRight_out)

        intersect_field_out = bool(intersect_field_Upline_out[0] or intersect_field_RightLine_out[0] or intersect_field_DownLine_out[0] or intersect_field_LeftLine_out[0])

        if intersect_field_out and not intersect_goal and not self.ball_out_field:
            for intersection in (intersect_field_Upline_out, intersect_field_DownLine_out, intersect_field_LeftLine_out, intersect_field_RightLine_out):
                has_intersection, point = intersection
                if has_intersection:
                    self.game_state["game_state_msg"] = "Place the ball on the dot"
                    self.wait_ball_position = (
                        (1 if point[0] > 0 else -1) * constants.dots_x,
                        (1 if point[1] > 0 else -1) * constants.dots_y
                    )
                pass
            self.ball_out_field = True
            self.addRefereeHistory("neutral", "Sideline crossed")
            self.pauseGame("sideline-crossed")

        # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
        if self.ball_out_field and utils.in_rectangle(ball_coord, field_DownLeft_in, field_UpRight_in):
            self.ball_out_field = False

    def penalize_fools(self, elapsed:float):
        """
        Penalize robots that are not respecting some rules

        :param float elapsed: elapsed time (s) since last tick
        """        
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

                    if distance < constants.timed_circle_radius:
                        if self.timed_circle_timers[(team, number)] is None:
                            self.timed_circle_timers[robot] = 0
                        else:
                            self.timed_circle_timers[robot] += elapsed

                            if self.timed_circle_timers[robot] > constants.timed_circle_time:
                                self.addPenalty(constants.default_penalty, marker, 'ball_abuse')
                    else:
                        self.timed_circle_timers[(team, number)] = None
                else:
                    self.timed_circle_timers[(team, number)] = None
    
                # Penalizing extra robots that are entering the defense area
                if self.canBePenalized(marker):
                    my_defense_area = constants.defense_area(self.positive_team == team)
                    opponent_defense_area = constants.defense_area(self.positive_team != team)

                    if utils.in_rectangle(robot_position, *opponent_defense_area):
                        self.addPenalty(constants.default_penalty, marker, 'abusive_attack')

                    if utils.in_rectangle(robot_position, *my_defense_area):
                        if team in defender:
                            other_robot, other_robot_position = defender[team]
                            robot_to_penalize = marker

                            if abs(other_robot_position[0]) < abs(robot_position[0]):
                                robot_to_penalize = other_robot
                            
                            self.addPenalty(constants.default_penalty, robot_to_penalize, 'abusive_defense')
                        else:
                            defender[team] = [marker, robot_position]

    def thread(self):
        self.ball_out_field = False
        wait_ball_timestamp = None

        ball_coord_old = np.array([0, 0])

        self.game_state["game_state_msg"] = "Game is ready to start"
        last_tick = time.time()

        while True:
            elapsed = time.time() - last_tick
            last_tick = time.time()

            # Updating positive and negative teams
            all_teams = utils.robot_teams()
            self.positive_team = self.game_state["x_positive_goal"]
            self.negative_team = all_teams[0] if all_teams[0] != self.game_state["x_positive_goal"] else all_teams[1]

            if not self.game_state["game_paused"]:
                if self.detection_info is not None:
                    if self.detection_info['ball'] is not None:
                        ball_coord = np.array(self.detection_info['ball'])
                        if (ball_coord != ball_coord_old).any():
                            self.check_line_crosses(ball_coord, ball_coord_old)
                            ball_coord_old = ball_coord

                    self.penalize_fools(elapsed)
                
                self.tickPenalty(elapsed)
            else:                              
                # Waiting for the ball to be at a specific position to resume the game
                if (self.wait_ball_position is not None) and (self.detection_info is not None) and (self.detection_info['ball'] is not None):
                    distance = np.linalg.norm(np.array(self.wait_ball_position) - np.array(self.detection_info['ball']))

                    if distance < constants.place_ball_margin:
                        if wait_ball_timestamp is None:
                            wait_ball_timestamp = time.time()
                        elif time.time() - wait_ball_timestamp >= 1:
                            self.game_state["game_state_msg"] = "Game is running..."
                            self.goal_validated = None
                            self.resumeGame()
                    else:
                        wait_ball_timestamp = None

            # XXX: Maybe detection should not be responsible for drawing this    
            self.detection.wait_ball_position = self.wait_ball_position            

            time.sleep(0.1)