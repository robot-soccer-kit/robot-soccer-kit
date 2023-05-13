from concurrent.futures import thread
import copy
from multiprocessing.dummy.connection import Client
import zmq
import time
import uuid
import threading
import logging
from . import robots, utils, client, constants, tasks
from .robot import RobotError


class Control:
    """
    This class is responsible for publishing the API allowing to control the robots.
    It also runs its own internal client to preempt the robots, for instance to stop them or to
    force them to be placed somewhere on the field.
    """

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger("control")  # type: ignore[annotation-unchecked]

        self.robots: robots.Robots = None

        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:7558")
        self.socket.RCVTIMEO = 1000
        self.master_key = str(uuid.uuid4())

        # Allowing "extra" features (LEDs, buzzer etc.)
        self.allow_extra_features: bool = True

        # Target for client
        self.targets = {robot: None for robot in utils.all_robots()}
        self.targets_buffer: dict = {}
        self.lock: threading.Lock = threading.Lock()

        self.tasks: dict = {}
        self.robots_color: dict = {}

        self.teams = {team: {"allow_control": True, "key": "", "packets": 0} for team in utils.robot_teams()}

    def available_robots(self) -> list:
        """
        Returns a list of the available robots

        :return list: list of (str) available robots
        """
        return self.robots.robots_by_marker.keys()

    def add_task(self, task: tasks.ControlTask):
        """
        Adds a task to the controller, this will preempt the concerned robots

        :param tasks.ControlTask task: the task
        """
        self.lock.acquire()
        self.tasks[task.name] = task
        self.lock.release()

    def has_task(self, task_name: str) -> bool:
        """
        Checks if a task exists

        :param str task_name: the task name
        :return bool: True if the tasks exists
        """
        return task_name in self.tasks

    def remove_task(self, name: str) -> None:
        """
        Removes a task

        :param str name: the task name
        """
        self.lock.acquire()
        if name in self.tasks:
            del self.tasks[name]
        self.lock.release()

    def process_command(self, marker: str, command: list, is_master: bool) -> list:
        response: list = [False, "Unknown error"]

        try:
            if marker in self.robots.robots_by_marker:
                if type(command) == list:
                    robot = self.robots.robots_by_marker[marker]

                    if command[0] == "kick" and len(command) == 2:
                        robot.kick(float(command[1]))
                        response = [True, "ok"]
                    elif command[0] == "control" and len(command) == 4:
                        robot.control(float(command[1]), float(command[2]), float(command[3]))
                        response = [True, "ok"]
                    elif command[0] == "teleport" and len(command) == 4:
                        robot.teleport(float(command[1]), float(command[2]), float(command[3]))
                        response = [True, "ok"]
                    elif command[0] == "leds" and len(command) == 4:
                        if is_master or self.allow_extra_features:
                            robot.leds(int(command[1]), int(command[2]), int(command[3]))
                            response = [True, "ok"]
                        else:
                            response[0] = 2
                            response[1] = "Only master can set the LEDs"

                    elif command[0] == "beep" and len(command) == 3:
                        if is_master or self.allow_extra_features:
                            robot.beep(int(command[1]), int(command[2]))
                            response = [True, "ok"]
                        else:
                            response[0] = 2
                            response[1] = "Only master can set the LEDs"
                    else:
                        response[0] = 2
                        response[1] = "Unknown command"
            elif marker == "ball":
                self.robots.ball.teleport(float(command[1]), float(command[2]), float(command[3]))
                response = [True, "ok"]
            else:
                response[1] = f"Unknown robot: {marker}"
        except RobotError as e:
            response = [False, str(e)]
        except (TypeError, ValueError) as e:
            response = [False, "ArgumentError: "+str(e)]


        return response

    def thread(self):
        """
        Main control loop, process commands received from the API
        """
        while self.running:
            try:
                json = self.socket.recv_json()
                response = [False, "Unknown error"]

                if type(json) == list and len(json) == 4:
                    key, team, number, command = json

                    if team in self.teams:
                        allow_control = True
                        is_master = key == self.master_key

                        if not is_master:
                            tasks = [task.name for task in self.robot_tasks(team, number)]
                            if self.teams[team]["key"] != key:
                                response[1] = f"Bad key for team {team}"
                                allow_control = False
                            elif not self.teams[team]["allow_control"]:
                                response[0] = 2
                                response[1] = f"You are not allowed to control the robots of team {team}"
                                allow_control = False
                            elif len(tasks):
                                reasons = str(tasks)
                                response[0] = 2
                                response[1] = f"Robot {number} of team {team} is preempted: {reasons}"
                                allow_control = False

                        if allow_control:
                            marker = utils.robot_list2str(team, number)
                            response = self.process_command(marker, command, is_master)
                        self.teams[team]["packets"] += 1

                    if team == "ball":
                        is_master = key == self.master_key
                        response = self.process_command("ball", command, is_master)

                self.socket.send_json(response)
            except zmq.error.Again:
                pass

    def start(self):
        """
        Starts the control's threads
        """
        self.running = True

        control_thread = threading.Thread(target=lambda: self.thread())
        control_thread.start()

        client_thread = threading.Thread(target=lambda: self.client_thread())
        client_thread.start()

    def stop(self):
        """
        Stops the threads from running (to do at the end of the program)
        """
        self.running = False

    def robot_tasks(self, team: str, number: int) -> list:
        """
        Gather all current tasks about a given robot

        :param str team: robot's team
        :param int number: robot's number
        :return list: list of tasks concerning this robot
        """
        tasks = []
        for task in self.tasks.values():
            for task_team, task_number in task.robots():
                if (team, number) == (task_team, task_number):
                    tasks.append(task)

        return tasks

    def status(self) -> dict:
        """
        Create the status structure for the control

        :return dict: a dictionary containing control's status
        """
        state = copy.deepcopy(self.teams)

        for team in utils.robot_teams():
            state[team]["preemption_reasons"] = {number: [] for number in utils.robot_numbers()}

        for task in self.tasks.values():
            for team, number in task.robots():
                state[team]["preemption_reasons"][number].append(task.name)

        return state

    def allow_team_control(self, team: str, allow: bool) -> None:
        """
        Sets the team allowance flag

        :param str team: team
        :param bool allow: is the team allowed to control its robots?
        """
        self.teams[team]["allow_control"] = allow

    def emergency(self) -> None:
        """
        Performs an emergency stop
        """
        # Clearing all the tasks, and creating a one-time stop all task. This can prevent
        # races conditions when the client thread is actually ticking tasks and might send
        # orders to the robots anyway.
        self.tasks.clear()
        self.add_task(tasks.StopAllTask("emergency", forever=False))

        # Disallowing teams to control robots
        for team in utils.robot_teams():
            self.allow_team_control(team, False)

        # Sending a stop moving order to all robots
        for port in self.robots.robots:
            self.robots.robots[port].control(0, 0, 0)

    def set_key(self, team: str, key: str):
        """
        Sets a team's key

        :param str team: the team name
        :param str key: the team's key
        """
        self.teams[team]["key"] = key

    def ensure_robots_on_field(self):
        """
        Ensure that the robots don't leave the field. If they go outside a given area, they will
        be sent back inside the field using goto.
        """
        [limit_up_right, _, limit_down_left, _] = constants.field_corners(0.25)

        for team, number in utils.all_robots():
            robot = self.client.robots[team][number]
            if robot.position is not None:
                out_of_field = not utils.in_rectangle(robot.position, limit_down_left, limit_up_right)
                task_name = "out-of-game-%s" % utils.robot_list2str(team, number)

                if out_of_field:
                    # Creating a top priority task to recover the robot
                    task = tasks.GoToTask(
                        task_name,
                        team,
                        number,
                        (0.0, 0.0, 0.0),
                        skip_old=False,
                        priority=100,
                    )
                    self.add_task(task)
                else:
                    # If the robot is recovered, creating a one-time task to make it stop moving
                    if self.has_task(task_name):
                        task = tasks.StopTask(task_name, team, number, forever=False, priority=100)
                        self.add_task(task)

    def tick_tasks(self) -> set:
        """
        Ticks all the current tasks to be run

        :return set: the robots that were updated during this tick
        """
        self.lock.acquire()
        tasks_to_tick = list(self.tasks.values()).copy()
        self.lock.release()

        # Sorting tasks by priority
        tasks_to_tick = sorted(tasks_to_tick, key=lambda task: -task.priority)
        robots_ticked = set()
        to_delete = []
        available_robots = self.available_robots()

        # Ticking all the tasks
        for task in tasks_to_tick:
            for team, number in task.robots():
                if (team, number) not in robots_ticked and utils.robot_list2str(team, number) in available_robots:
                    # Robot was not ticked yet by an higher-priority task
                    robots_ticked.add((team, number))

                    try:
                        task.tick(self.client.robots[team][number])
                    except client.ClientError as e:
                        self.logger.error(f"Error in control's client: {e}")

            if task.finished(self.client, available_robots):
                to_delete.append(task.name)

        # Removing finished tasks
        self.lock.acquire()
        for task_name in to_delete:
            if task_name in self.tasks:
                del self.tasks[task_name]
        self.lock.release()

        return robots_ticked

    def update_robots_colors(self, robots_ticked: set) -> None:
        """
        Ensure robot LEDs colors, either their team or the preempted color

        :param set robots_ticked: robots that were ticked
        """
        try:
            new_robots_color = {}
            for robot_id in self.robots.robots_by_marker:
                robot = utils.robot_str2list(robot_id)
                color = "preempted" if robot in robots_ticked else robot[0]

                if (
                    (robot not in self.robots_color)
                    or self.robots_color[robot] != color
                    or self.robots.should_restore_leds(robot_id)
                ):
                    self.client.robots[robot[0]][robot[1]].leds(*utils.robot_leds_color(color))
                new_robots_color[robot] = color

            self.robots_color = new_robots_color

        except client.ClientError as e:
            self.logger.error(f"Error while setting leds: {e}")

    def client_thread(self) -> None:
        """
        This thread is used to control the robot, it connects to the local API using the master
        key
        """

        self.client = client.Client(key=self.master_key, wait_ready=False)

        while self.running:
            self.ensure_robots_on_field()
            robots_ticked = self.tick_tasks()
            self.update_robots_colors(robots_ticked)

            time.sleep(0.01)
