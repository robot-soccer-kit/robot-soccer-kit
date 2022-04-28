from concurrent.futures import thread
import copy
from multiprocessing.dummy.connection import Client
import zmq
import time
import uuid
import threading
from . import robots, utils, client, field_dimensions

class ControlTask:
    def __init__(self, name:str, priority:int=1):
        self.name:str = name
        self.priority:int = priority

    def robots(self) -> list:
        return []

    def tick(self, robot:client.ClientRobot) -> None:
        raise NotImplemented('Task not implemented')

    def finished(self, client:client.Client) -> bool:
        return False

class StopTask(ControlTask):
    def __init__(self, name:str, team:str, number:int, forever=True, **kwargs):
        super().__init__(name, **kwargs)
        self.team:str = team
        self.number:int = number
        self.forever = forever

    def robots(self):
        return [(self.team, self.number)]

    def tick(self, robot:client.ClientRobot):
        client.control(0, 0, 0)

    def finished(self, client:client.Client) -> bool:
        return not self.forever

class GoToTask(ControlTask):
    def __init__(self, name:str, team:str, number:int, target, skip_old=True, **kwargs):
        super().__init__(name, **kwargs)
        self.team:str = team
        self.number:int = number
        self.target = target
        self.skip_old:bool = skip_old

        for team, number, target in client.configurations:
            self.targets[(team, number)] = target

    def robots(self):
        return [(self.team, self.number)]
    
    def tick(self, robot:client.ClientRobot):
        robot.goto(self.target, wait=False, skip_old=self.skip_old)

    def finished(self, client:client.Client) -> bool:
        robot = client.robots[self.team][self.number]
        arrived, _ = robot.compute_order(self.target)

        return arrived

class GoToConfigurationTask(ControlTask):
    def __init__(self, name:str, configuration:str, **kwargs):
        super().__init__(name, **kwargs)
        self.targets = {}

        for team, number, target in client.configurations[configuration]:
            self.targets[(team, number)] = target

    def robots(self):
        return list(self.targets.keys())
    
    def tick(self, robot:client.ClientRobot):
        robot.goto(self.targets[(robot.team, robot.number)], False)

    def finished(self, client:client.Client) -> bool:
        for team, number in self.targets:
            arrived, _ = client.robots[team][number].compute_order(self.targets[(team, number)])

            if not arrived:
                return False

        return True

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
        self.idle = True
        self.lock = threading.Lock()

        self.tasks = {}

        self.teams = {
            color: {
                "allow_control": True,
                "key": "",
                "packets": 0
            }
            for color in utils.robot_teams()
        }

    def add_task(self, task:ControlTask):
        self.lock.acquire()
        self.tasks[task.name] = task
        self.lock.release()

    def has_task(self, task_name:str):
        return task_name in self.tasks
    
    def remove_task(self, name:str):
        del self.tasks[name]

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

                        if key != self.master_key:
                            tasks = self.robot_tasks(team, number)
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
                            marker = "%s%d" % (team, number)
                            if marker in self.robots.robots_by_marker:
                                if type(command) == list:
                                    if command[0] == 'kick' and len(command) == 2:
                                        self.robots.robots_by_marker[marker].kick(
                                            float(command[1]))
                                        response = [True, 'ok']
                                    elif command[0] == 'control' and len(command) == 4:
                                        self.robots.robots_by_marker[marker].control(
                                            float(command[1]), float(command[2]), float(command[3]))
                                        response = [True, 'ok']
                                    else:
                                        response[1] = 'Unknown command'
                            else:
                                response[1] = 'Unknown robot'

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

    def robot_tasks(self, robot) -> list:
        tasks = []
        for task in self.tasks:
            for team, number in task.robots():
                return tasks.append(task)

        return tasks

    def status(self):
        state = copy.deepcopy(self.teams)
        state[team]['preemption_reasons'] = {robot: [] for robot in utils.all_robots()}

        for task in self.tasks:
            for team, number in task.robots():
                state[team]['preemption_reasons'][number].append(task.name)

        return state

    def allowTeamControl(self, team:str, allow:bool):
        self.teams[team]['allow_control'] = allow

    def emergency(self):
        self._set_target_all(None)

        for team in utils.robot_teams():
            self.allowTeamControl(team, False)

        for port in self.robots.robots:
            self.robots.robots[port].control(0, 0, 0)

    def setKey(self, team, key):
        self.teams[team]['key'] = key

    def set_target(self, team:str, number:int, target):
        """
        Sets a target position for a given robot
        """        
        self.lock.acquire()
        self.idle = False
        self.targets_buffer[(team, number)] = target
        self.lock.release()

    def stop(self, team:str, number:int):
        """
        Stops a robot
        """        
        self.set_target(team, number, 'stop')

    def set_target_configuration(self, configuration:str):
        """
        Set a target configuration for all robots
        """        
        self.lock.acquire()
        self.idle = False
        for team, number, target in client.configurations[configuration]:
            self.targets_buffer[(team, number)] = target
        self.lock.release()

    def _set_target_all(self, target):
        """
        Sets a target for all robots
        """     
        self.lock.acquire()
        for robot in utils.all_robots():
            self.targets_buffer[robot] = target
        self.lock.release()

    def stop_all(self):
        """
        Stop all robots (they will stop moving)
        """        
        self._set_target_all('stop')
    
    def client_thread(self):
        self.client = client.Client(key=self.master_key)

        [_, field_DownRight_out, _, field_UpLeft_out] = field_dimensions.fieldCoordMargin(0.25)

        while self.running:
            # Keeping robots on sight
            for team, number in utils.all_robots():
                robot = self.client.robots[team][number]
                if robot.pose is not None:
                    intersect_field_in = not bool((field_UpLeft_out[0]<=robot.pose[0]<=field_DownRight_out[0]) 
                            and 
                            (field_DownRight_out[1]<=robot.pose[1]<=field_UpLeft_out[1]))
                    
                    task_name = 'out-of-game-%s' % utils.robot_list2str(team, number)

                    if intersect_field_in:
                        task = GoToTask(task_name, team, number, (0., 0, 0.))
                        self.add_task(task)
                        
                    else: 
                        if self.has_task(task_name):
                            task = StopTask(task_name, team, number, forever=False)
                            self.add_task(task)

            # Handling robot's goto, since client interaction access network, we can't afford to
            # lock a mutex during client calls, we store order in the temporary buffer list
            self.lock.acquire()
            tasks_to_tick = [task for task in self.tasks.values()]
            self.lock.release()

            # Sorting tasks by priority
            tasks_to_tick = sorted(tasks_to_tick, lambda task: task.priority)
            robots_ticked = set()

            # Ticking all the tasks
            moving = False
            for task in tasks_to_tick:
                for team, number in task.robots():
                    if (team, number) not in robots_ticked:
                        # Robot was not ticked yet by an higher-priority task
                        robots_ticked.add((team, number))
                        task.tick(self.client.robots[team][number])
                        moving = True

                    if task.finished(self.client):
                        to_delete = task.name

            self.idle = not moving

            # Removing finished tasks
            self.lock.acquire()
            for task_name in to_delete:
                del self.tasks[task_name]
            self.lock.relase()

            time.sleep(0.01)
