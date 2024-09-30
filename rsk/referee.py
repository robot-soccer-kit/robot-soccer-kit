import math
import copy
import numpy as np
import threading
import logging
from . import constants, utils, config, control, tasks, state
from .field import Field
import time


class Referee:
    """
    Handles the referee
    """

    def __init__(self, state: state.State):
        self.logger: logging.Logger = logging.getLogger("referee")

        self.control: control.Control = control.Control()

        # Info from detection
        self._state_info = None
        self.state: state.State = state

        # Last actions
        self.referee_history = []

        # Timestamp when the timer started
        self.chrono_is_running: bool = False
        self.start_timer = 0.0

        # Set when a goal validation is pending
        self.goal_validated = None

        # Position where we wait for the ball to be
        self.wait_ball_position = None

        # Timers to penalize robots staying in te
        self.timed_circle_timers = {robot: 0 for robot in utils.all_robots()}

        # Game state structure
        self.game_state = {
            "game_is_running": False,
            "game_paused": True,
            "halftime_is_running": False,
            "timer": 0,
            "game_state_msg": "",
            "teams": {
                team: {
                    "name": "",
                    "score": 0,
                    "x_positive": team == utils.robot_teams()[0],
                }
                for team in utils.robot_teams()
            },
        }

        # Robots Penalties
        self.penalties = {}
        self.penalty_spot = [
            {
                "robot": None,
                "last_use": 0,
                "pos": (x, side * (constants.field_width / 2 + constants.robot_radius), side * np.pi / 2),
            }
            for x in np.linspace(-constants.field_length / 2, constants.field_length / 2, constants.penalty_spots // 2 + 2)[
                1:-1
            ]
            for side in (-1, 1)
        ]
        self.reset_penalties()

        # Starting the Referee thread
        self.lock = threading.Lock()
        self.referee_thread = threading.Thread(target=lambda: self.thread())
        self.referee_thread.start()

    def set_state_info(self, info: dict) -> None:
        """
        Sets internal detection info

        :param dict info: detection infos
        """
        self.lock.acquire()
        self._state_info = info
        self.lock.release()

    def get_game_state(self, full: bool = True) -> dict:
        game_state = copy.deepcopy(self.game_state)

        # Updating robot statuses
        control_status = self.control.status()
        for team, number in utils.all_robots():
            robot_state = {
                "penalized": False,
                "penalized_remaining": None,
                "penalized_reason": None,
                "preempted": False,
                "preemption_reasons": [],
            }

            robot_id = utils.robot_list2str(team, number)
            robot_state["penalized"] = self.penalties[robot_id]["remaining"] is not None
            if robot_state["penalized"]:
                robot_state["penalized_remaining"] = math.ceil(self.penalties[robot_id]["remaining"])
            else:
                robot_state["penalized_remaining"] = None
            robot_state["penalized_reason"] = self.penalties[robot_id]["reason"]

            preempted_reasons = control_status[team]["preemption_reasons"][number]
            robot_state["preempted"] = len(preempted_reasons) > 0
            robot_state["preemption_reasons"] = preempted_reasons

            if "robots" not in game_state["teams"][team]:
                game_state["teams"][team]["robots"] = {}
            game_state["teams"][team]["robots"][number] = robot_state

        if full:
            game_state["referee_history_sliced"] = self.referee_history[-constants.referee_history_size :]
        else:
            del game_state["game_state_msg"]

        # Updating timer
        game_state["timer"] = math.ceil(game_state["timer"])

        return game_state

    def wait_for_ball_placement(self, target_position=(0.0, 0.0)):
        """
        Waits for the ball to be placed somewhere, pauses the game until then

        :param tuple target_position: the target position for the ball, defaults to (0.0, 0.0)
        """
        self.wait_ball_position = target_position
        self.game_state["game_paused"] = True
        self.game_state["game_state_msg"] = "Place the ball on the dot"
        # The wait is managed in the referee thread

    def start_game(self):
        """
        Starts the game
        """
        self.logger.info("Game started")
        self.game_state["timer"] = constants.game_duration
        self.game_state["game_is_running"] = True
        self.referee_history = []
        self.reset_score()
        self.pause_game("game-start")
        self.start_timer = 0
        self.chrono_is_running = False
        self.wait_for_ball_placement()

    def pause_game(self, reason: str = "manually-paused"):
        """
        Pause the game

        :param str reason: the reason for this pause, defaults to "manually-paused"
        """
        self.logger.info(f"Game paused, reason: {reason}")

        self.game_state["game_paused"] = True
        task = tasks.StopAllTask(reason)
        self.control.add_task(task)
        self.game_state["game_state_msg"] = "Game has been manually paused"

    def resume_game(self):
        """
        Resume the game
        """
        self.logger.info("Game resumed")

        self.game_state["game_paused"] = False
        self.game_state["game_state_msg"] = "Game is running..."
        self.wait_ball_position = None

        if self.control.has_task("game-start"):
            self.chrono_is_running = True

        self.control.remove_task("manually-paused")
        self.control.remove_task("sideline-crossed")
        self.control.remove_task("goal")
        self.control.remove_task("force-place")
        self.control.remove_task("game-start")
        self.control.remove_task("half-time")

        # Ensuring all robots are stopped
        self.control.add_task(tasks.StopAllTask("stop-all", forever=False))

    def stop_game(self):
        """
        Stop the game (end)
        """
        self.logger.info("Game stopped")
        self.game_state["game_paused"] = True
        self.game_state["game_is_running"] = False
        self.chrono_is_running = False
        self.wait_ball_position = None
        self.start_timer = 0.0

        self.reset_penalties()
        self.control.remove_task("manually-paused")
        self.control.remove_task("sideline-crossed")
        self.control.remove_task("goal")
        self.control.remove_task("game-start")
        self.control.remove_task("force-place")
        self.control.remove_task("half-time")

        self.game_state["game_state_msg"] = "Game is ready to start"

    def start_half_time(self):
        """
        Start an half time break
        """
        self.game_state["timer"] = constants.halftime_duration
        self.chrono_is_running = True
        self.game_state["game_is_running"] = False
        self.game_state["halftime_is_running"] = True
        self.game_state["game_paused"] = True
        self.game_state["game_state_msg"] = "Half Time"

        task = tasks.StopAllTask("half-time")
        self.control.add_task(task)
        self.reset_penalties()

        self.control.remove_task("sideline-crossed")
        self.control.remove_task("goal")

    def start_second_half_time(self):
        """
        Resume after an half time break
        """
        self.pause_game("game-start")
        self.chrono_is_running = False
        self.game_state["timer"] = constants.game_duration
        self.game_state["halftime_is_running"] = False
        self.game_state["game_is_running"] = True
        self.game_state["game_state_msg"] = "Game is running..."
        self.wait_for_ball_placement()

    def force_place(self, configuration: str, **kwargs):
        """
        Force the robots to be placed somewhere

        :param str configuration: the name of the target configuration
        """
        task = tasks.GoToConfigurationTask("force-place", configuration, priority=50, **kwargs)
        self.control.add_task(task)

    def place_game(self, configuration: str, **kwargs):
        """
        Place the robot for the current game setup

        :param str configuration: the target configuration
        """
        if configuration == "standard":
            if self.game_state["teams"][utils.robot_teams()[1]]["x_positive"]:
                configuration = "game_blue_positive"
            else:
                configuration = "game_green_positive"
            self.reset_penalties()

        elif configuration == "swap_covers":
            if self.game_state["teams"][utils.robot_teams()[1]]["x_positive"]:
                configuration = "swap_covers_blue_positive"
            else:
                configuration = "swap_covers_green_positive"

        self.force_place(configuration, **kwargs)

    def increment_score(self, team: str, increment: int):
        """
        Increments a team score

        :param str team: team name
        :param int increment: how much should be incremented
        """
        self.game_state["teams"][team]["score"] += increment

    def reset_score(self):
        """
        Reset team scores
        """
        for team in utils.robot_teams():
            self.game_state["teams"][team]["score"] = 0

    def add_referee_history(self, team: str, action: str) -> list:
        """
        Adds an entry to the referee history

        :param str team: the team
        :param str action: action
        :return list: the referee history entry created
        """
        timestamp = math.ceil(self.game_state["timer"])
        i = len(self.referee_history)
        new_history_line = [i, timestamp, team, action]
        self.referee_history.append(new_history_line)

        return self.referee_history

    def reset_penalties(self):
        """
        Resets all robot penalties
        """
        for robot_id in utils.all_robots_id():
            self.cancel_penalty(robot_id)

    def add_penalty(self, duration: float, robot: str, reason: str = "manually_penalized"):
        """
        Adds some penalty to a r obot

        :param float duration: the penalty duration
        :param str robot: the target robot
        :param str reason: penalty reason, defaults to "manually_penalized"
        """
        self.penalties[robot]["reason"] = reason
        markers = self.state_info["markers"]

        if self.penalties[robot]["remaining"] is None:
            self.penalties[robot]["remaining"] = float(duration)
            team, number = utils.robot_str2list(robot)
            task_name = "penalty-" + robot
            self.logger.info(f"Adding penalty for robot {robot}, reason: {reason}")

            if robot in markers:
                x, y = markers[robot]["position"]

                # Find the nearest free penalty spot
                distances = []
                for penalty_spot in self.penalty_spot:
                    distance = math.dist((x, y), penalty_spot["pos"][:2])
                    for marker in markers:
                        if (
                            marker != robot
                            and math.dist(markers[marker]["position"], penalty_spot["pos"][:2]) < constants.robot_radius * 1.3
                        ):
                            distance = math.inf

                    if (
                        penalty_spot["robot"] is not None
                        or time.time() - penalty_spot["last_use"] < constants.penalty_spot_lock_time
                    ):
                        distance = math.inf
                    distances.append(distance)

                free_penaltly_spot_index = distances.index(min(distances))

                target = self.penalty_spot[free_penaltly_spot_index]["pos"]
                self.penalty_spot[free_penaltly_spot_index]["robot"] = robot

                self.logger.info(f"----  Penalty Spot : {free_penaltly_spot_index}")

                task = tasks.GoToTask(task_name, team, number, target, forever=True)
            else:
                task = tasks.StopTask(task_name, team, number)

            self.control.add_task(task)
        else:
            self.penalties[robot]["remaining"] += float(duration)

    def cancel_penalty(self, robot: str):
        """
        Cancels a robot's penalty

        :param str robot: the robot
        """
        self.penalties[robot] = {"remaining": None, "reason": None, "grace": constants.grace_time}

        penalty_spot = [spot for spot in self.penalty_spot if spot["robot"] == robot]
        if penalty_spot != []:
            penalty_spot[0]["last_use"] = time.time()
            penalty_spot[0]["robot"] = None

        # Replacing the control task with a one-time stop to ensure the robot is not moving
        team, number = utils.robot_str2list(robot)
        task = tasks.StopTask("penalty-" + robot, team, number, forever=False)
        self.control.add_task(task)

    def tick_penalties(self, elapsed: float):
        """
        Update robot penalties and grace time

        :param float elapsed: time elapsed since last tick
        """
        for robot in self.penalties:
            if self.penalties[robot]["remaining"] is not None:
                self.penalties[robot]["remaining"] -= elapsed
                if self.penalties[robot]["remaining"] < 0:
                    self.cancel_penalty(robot)
            if self.penalties[robot]["grace"] is not None:
                self.penalties[robot]["grace"] -= elapsed
                if self.penalties[robot]["grace"] < 0:
                    self.penalties[robot]["grace"] = None

    def can_be_penalized(self, robot: str) -> bool:
        """
        Can a given robot be penalized?
        It can be penalized if:
        * It is not already penalized
        * Its grace time is not expired
        * It has no other tasks to do (it is not preempted)

        :param str robot: robot
        :return bool: True if the robot can be penalized
        """
        tasks = self.control.robot_tasks(*utils.robot_str2list(robot))

        return len(tasks) == 0 and (self.penalties[robot]["remaining"] is None) and (self.penalties[robot]["grace"] is None)

    def set_team_name(self, team: str, name: str):
        self.game_state["teams"][team]["name"] = name

    def swap_team_sides(self):
        """
        Swap team sides (x positive referring to the team defending goals on the
        positive x axis of field)
        """
        for team in self.game_state["teams"]:
            self.game_state["teams"][team]["x_positive"] = not self.game_state["teams"][team]["x_positive"]

    def validate_goal(self, yes_no: bool):
        """
        Handles goal validation by user

        :param bool yes_no: whether the goal is validated or canceller
        """
        if yes_no:
            if self.game_state["teams"]["blue"]["x_positive"]:
                self.force_place("game_blue_positive", end_buzz=True)
            else:
                self.force_place("game_green_positive", end_buzz=True)

            self.wait_for_ball_placement()
            self.goal_validated = True
        else:
            self.increment_score(self.referee_history[-1][2], -1)
            self.goal_validated = False
            self.resume_game()

    def check_line_crosses(self, ball_coord: np.ndarray, ball_coord_old: np.ndarray):
        """
        Checks for line crosses (sideline crosses and goals)

        :param np.ndarray ball_coord: ball position (now)
        :param np.ndarray ball_coord_old: ball position on previous frame
        """
        [x_pos_goals_low, x_pos_goals_high] = constants.goal_posts(x_positive=True)
        [x_neg_goals_high, x_neg_goals_low] = constants.goal_posts(x_positive=False)
        [field_UpRight_in, _, field_DownLeft_in, _] = constants.field_corners(margin=constants.field_in_margin)
        [field_UpRight_out, field_DownRight_out, field_DownLeft_out, field_UpLeft_out] = constants.field_corners(
            margin=constants.field_out_margin
        )

        # Goals and ball trajectory intersection (Goal detection)
        intersect_x_neg_goal, _ = utils.intersect(ball_coord_old, ball_coord, x_neg_goals_low, x_neg_goals_high)
        intersect_x_pos_goal, _ = utils.intersect(ball_coord_old, ball_coord, x_pos_goals_low, x_pos_goals_high)
        intersect_goal = intersect_x_neg_goal or intersect_x_pos_goal

        if intersect_goal and not self.ball_out_field:
            goal_team = self.positive_team if intersect_x_neg_goal else self.negative_team
            self.logger.info(f"Goal for team {goal_team}")

            self.ball_out_field = True
            self.increment_score(goal_team, 1)
            self.add_referee_history(goal_team, "Goal")
            self.reset_penalties()
            self.pause_game("goal")
            self.game_state["game_state_msg"] = "Waiting for Goal Validation"

        # Sideline (field+margin) and ball trajectory intersection (Sideline fool detection)
        intersect_field_Upline_out = utils.intersect(ball_coord_old, ball_coord, field_UpLeft_out, field_UpRight_out)
        intersect_field_DownLine_out = utils.intersect(ball_coord_old, ball_coord, field_DownLeft_out, field_DownRight_out)
        intersect_field_LeftLine_out = utils.intersect(ball_coord_old, ball_coord, field_UpLeft_out, field_DownLeft_out)
        intersect_field_RightLine_out = utils.intersect(ball_coord_old, ball_coord, field_UpRight_out, field_DownRight_out)

        intersect_field_out = bool(
            intersect_field_Upline_out[0]
            or intersect_field_RightLine_out[0]
            or intersect_field_DownLine_out[0]
            or intersect_field_LeftLine_out[0]
        )

        if intersect_field_out and not intersect_goal and not self.ball_out_field:
            for intersection in (
                intersect_field_Upline_out,
                intersect_field_DownLine_out,
                intersect_field_LeftLine_out,
                intersect_field_RightLine_out,
            ):
                has_intersection, point = intersection
                if has_intersection:
                    target = (
                        (1 if point[0] > 0 else -1) * constants.dots_x,
                        (1 if point[1] > 0 else -1) * constants.dots_y,
                    )
                    self.wait_for_ball_placement(target)
            self.ball_out_field = True
            self.add_referee_history("neutral", "Sideline crossed")
            self.pause_game("sideline-crossed")

        # Verification that the ball has been inside a smaller field (field-10cm margin) at least once before a new goal or a sideline foul is detected
        if self.ball_out_field and utils.in_rectangle(ball_coord, field_DownLeft_in, field_UpRight_in):
            self.ball_out_field = False

    def penalize_fools(self, elapsed: float):
        """
        Penalize robots that are not respecting some rules

        :param float elapsed: elapsed time (s) since last tick
        """
        # Checking the robot respect timed circle and defense area rules
        defender = {}
        for marker in self.state_info["markers"]:
            team, number = utils.robot_str2list(marker)
            robot_position = np.array(self.state_info["markers"][marker]["position"])

            if team in utils.robot_teams():
                robot = (team, number)

                # Penalizing robots that are staying close to the ball
                if self.state_info["ball"] is not None and self.can_be_penalized(marker):
                    ball_position = np.array(self.state_info["ball"])
                    distance = np.linalg.norm(ball_position - robot_position)

                    if distance < constants.timed_circle_radius:
                        if self.timed_circle_timers[(team, number)] is None:
                            self.timed_circle_timers[robot] = 0
                        else:
                            self.timed_circle_timers[robot] += elapsed

                            if self.timed_circle_timers[robot] > constants.timed_circle_time:
                                self.add_penalty(constants.default_penalty, marker, "ball_abuse")
                    else:
                        self.timed_circle_timers[(team, number)] = None
                else:
                    self.timed_circle_timers[(team, number)] = None

                # Penalizing extra robots that are entering the defense area
                if self.can_be_penalized(marker):
                    my_defense_area = constants.defense_area(self.positive_team == team)
                    opponent_defense_area = constants.defense_area(self.positive_team != team)

                    # This is penalizing robots for abusive attack (suspended)
                    if utils.in_rectangle(robot_position, *opponent_defense_area):
                        self.add_penalty(constants.default_penalty, marker, "abusive_attack")

                    if utils.in_rectangle(robot_position, *my_defense_area):
                        if team in defender:
                            other_robot, other_robot_position = defender[team]
                            robot_to_penalize = marker

                            if abs(other_robot_position[0]) < abs(robot_position[0]):
                                robot_to_penalize = other_robot

                            self.add_penalty(constants.default_penalty, robot_to_penalize, "abusive_defense")
                        else:
                            defender[team] = [marker, robot_position]

    def thread(self):
        """
        Referee thread
        """
        self.ball_out_field = False
        wait_ball_timestamp = None

        ball_coord_old = np.array([0, 0])

        self.game_state["game_state_msg"] = "Game is ready to start"
        last_tick = time.time()

        while True:
            self.state_info = copy.deepcopy(self.state.get_state())
            self.state.set_referee(self.get_game_state())
            self.control.allow_extra_features = not self.game_state["game_is_running"]

            elapsed = time.time() - last_tick
            if self.chrono_is_running:
                self.game_state["timer"] -= elapsed

            last_tick = time.time()

            # Updating positive and negative teams
            all_teams = utils.robot_teams()

            if self.game_state["teams"][all_teams[0]]["x_positive"]:
                self.positive_team, self.negative_team = all_teams
            else:
                self.negative_team, self.positive_team = all_teams

            if not self.game_state["game_paused"]:
                if self.state_info is not None:
                    if self.state_info["ball"] is not None:
                        ball_coord = np.array(self.state_info["ball"])
                        if (ball_coord != ball_coord_old).any():
                            self.check_line_crosses(ball_coord, ball_coord_old)
                            ball_coord_old = ball_coord

                    self.penalize_fools(elapsed)

                self.tick_penalties(elapsed)
            else:
                # Waiting for the ball to be at a specific position to resume the game
                if (
                    (self.wait_ball_position is not None)
                    and (self.state_info is not None)
                    and (self.state_info["ball"] is not None)
                ):
                    distance = np.linalg.norm(np.array(self.wait_ball_position) - np.array(self.state_info["ball"]))

                    if distance < constants.place_ball_margin:
                        if wait_ball_timestamp is None:
                            wait_ball_timestamp = time.time()
                        elif time.time() - wait_ball_timestamp >= 1:
                            self.game_state["game_state_msg"] = "Game is running..."
                            self.goal_validated = None
                            self.resume_game()
                    else:
                        wait_ball_timestamp = None

            time.sleep(0.1)
