from concurrent.futures import thread
import copy
from multiprocessing.dummy.connection import Client
import zmq
import time
import uuid
import threading
from . import robots, utils, client, field_dimensions, tasks

class Control:
    def __init__(self, robots):
        self.robots = robots

        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:7558")
        self.master_key = str(uuid.uuid4())

        # Target for client
        self.targets = {
            robot: None
            for robot in utils.all_robots()
        }
        self.targets_buffer = {}
        self.lock = threading.Lock()

        self.tasks = {}
        self.robots_color = {}

        self.teams = {
            team: {
                "allow_control": True,
                "key": "",
                "packets": 0
            }
            for team in utils.robot_teams()
        }

    def add_task(self, task:tasks.ControlTask):
        self.lock.acquire()
        self.tasks[task.name] = task
        self.lock.release()

    def has_task(self, task_name:str):
        return task_name in self.tasks
    
    def remove_task(self, name:str):
        self.lock.acquire()
        if name in self.tasks:
            del self.tasks[name]
        self.lock.release()

    def thread(self):
        while self.running:
            self.socket.RCVTIMEO = 1000
            try:
                json = self.socket.recv_json()
                response = [False, 'Unknown error']

                if type(json) == list and len(json) == 4:
                    key, team, number, command = json

                    if team in self.teams:
                        allow_control = True
                        is_master = key == self.master_key

                        if not is_master:
                            tasks = [task.name for task in self.robot_tasks(team, number)]
                            if self.teams[team]['key'] != key:
                                response[1] = f"Bad key for team {team}"
                                allow_control = False
                            elif not self.teams[team]['allow_control']:
                                response[1] = f"You are not allowed to control the robots of team {team}"
                                allow_control = False
                            elif len(tasks):
                                reasons = str(tasks)
                                response[1] = f"Robot {number} of team {team} is preempted: {reasons}"
                                allow_control = False
                        
                        if allow_control:
                            marker = utils.robot_list2str(team, number)
                            if marker in self.robots.robots_by_marker:
                                if type(command) == list:
                                    robot = self.robots.robots_by_marker[marker]

                                    if command[0] == 'kick' and len(command) == 2:
                                        robot.kick(float(command[1]))
                                        response = [True, 'ok']
                                    elif command[0] == 'control' and len(command) == 4:
                                        robot.control(float(command[1]), float(command[2]), float(command[3]))
                                        response = [True, 'ok']
                                    elif command[0] == 'leds' and len(command) == 4:
                                        if is_master:
                                            robot.leds(int(command[1]), int(command[2]), int(command[3]))
                                            response = [True, 'ok']
                                        else:
                                            response[1] = 'Only master can set the LEDs'
                                    else:
                                        response[1] = 'Unknown command'
                            else:
                                response[1] = f"Unknown robot: {marker}"

                        self.teams[team]['packets'] += 1

                self.socket.send_json(response)
            except zmq.error.Again:
                pass

    def start(self):
        self.running = True
        control_thread = threading.Thread(target=lambda: self.thread())
        control_thread.start()

        client_thread = threading.Thread(target=lambda: self.client_thread())
        client_thread.start()

    def stop(self):
        self.running = False

    def robot_tasks(self, team:str, number:int) -> list:
        tasks = []
        for task in self.tasks.values():
            for task_team, task_number in task.robots():
                if (team, number) == (task_team, task_number):
                    tasks.append(task)

        return tasks

    def status(self):
        state = copy.deepcopy(self.teams)

        for team in utils.robot_teams():
            state[team]['preemption_reasons'] = {number: [] for number in utils.robot_numbers()}

        for task in self.tasks.values():
            for team, number in task.robots():
                state[team]['preemption_reasons'][number].append(task.name)

        return state

    def allowTeamControl(self, team:str, allow:bool):
        self.teams[team]['allow_control'] = allow

    def emergency(self):
        self.tasks.clear()

        for team in utils.robot_teams():
            self.allowTeamControl(team, False)

        for port in self.robots.robots:
            self.robots.robots[port].control(0, 0, 0)

    def setKey(self, team, key):
        self.teams[team]['key'] = key

    def client_thread(self):
        self.client = client.Client(key=self.master_key)

        [_, field_DownRight_out, _, field_UpLeft_out] = field_dimensions.fieldCoord(0.25)

        while self.running:
            # Keeping robots on sight
            for team, number in utils.all_robots():
                robot = self.client.robots[team][number]
                if robot.pose is not None:
                    # Field here refers to the green area
                    out_of_field = not bool((field_UpLeft_out[0]<=robot.pose[0]<=field_DownRight_out[0]) 
                            and 
                            (field_DownRight_out[1]<=robot.pose[1]<=field_UpLeft_out[1]))
                    
                    task_name = 'out-of-game-%s' % utils.robot_list2str(team, number)

                    if out_of_field:
                        task = tasks.GoToTask(task_name, team, number, (0., 0., 0.), skip_old=False, priority=100)
                        self.add_task(task)
                    else: 
                        if self.has_task(task_name):
                            task = tasks.StopTask(task_name, team, number, forever=False, priority=100)
                            self.add_task(task)

            # Handling robot's goto, since client interaction access network, we can't afford to
            # lock a mutex during client calls, we store order in the temporary buffer list
            self.lock.acquire()
            tasks_to_tick = list(self.tasks.values()).copy()
            self.lock.release()

            # Sorting tasks by priority
            tasks_to_tick = sorted(tasks_to_tick, key=lambda task: -task.priority)
            robots_ticked = set()
            to_delete = []

            # Ticking all the tasks
            for task in tasks_to_tick:
                for team, number in task.robots():
                    if (team, number) not in robots_ticked:
                        # Robot was not ticked yet by an higher-priority task
                        robots_ticked.add((team, number))

                        try:
                            task.tick(self.client.robots[team][number])
                        except client.ClientError:
                            print("Error in control's client")

                if task.finished(self.client):
                    to_delete.append(task.name)

            # Ensuring robots colors
            try:
                new_robots_color = {}
                for robot_id in self.robots.robots_by_marker:
                    robot = utils.robot_str2list(robot_id)
                    color = 'preempted' if robot in robots_ticked else robot[0]

                    if (robot not in self.robots_color) or self.robots_color[robot] != color:
                        self.client.robots[robot[0]][robot[1]].leds(*utils.robot_leds_color(color))
                    new_robots_color[robot] = color

                self.robots_color = new_robots_color

            except client.ClientError as e:
                print(f"Error while setting leds: {e}")

            # Removing finished tasks
            self.lock.acquire()
            for task_name in to_delete:
                if task_name in self.tasks:
                    del self.tasks[task_name]
            self.lock.release()

            time.sleep(0.01)
