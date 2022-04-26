from concurrent.futures import thread
import copy
import zmq
import time
import uuid
import threading
from . import robots, utils, client, field_dimensions


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

        self.teams = {
            color: {
                "allow_control": True,
                "preemption_reasons": {number: set() for number in utils.robot_numbers()},
                "key": "",
                "packets": 0
            }
            for color in utils.robot_teams()
        }

    def preempt_robot(self, team:str, number:int, reason:str):
        self.teams[team]["preemption_reasons"][number].add(reason)

    def is_preempted(self, team:str, number:int, reason:str):
        return reason in self.teams[team]["preemption_reasons"][number]

    def unpreempt_robot(self, team:str, number:int, reason:str):
        if self.is_preempted(team, number, reason):
            self.teams[team]["preemption_reasons"][number].remove(reason)

    def preempt_all_robots(self, reason:str):
        for team, number in utils.all_robots():
            self.preempt_robot(team, number, reason)

    def unpreempt_all_robots(self, reason:str):
        for team, number in utils.all_robots():
            self.unpreempt_robot(team, number, reason)

    def thread(self):
        while self.running:
            self.socket.RCVTIMEO = 1000
            try:
                json = self.socket.recv_json()
                response = [False, 'Unknown error']

                if type(json) == list and len(json) == 4:
                    key, team, robot, command = json

                    if team in self.teams:
                        allow_control = True

                        if key != self.master_key:
                            if self.teams[team]['key'] != key:
                                response[1] = f"Bad key for team {team}"
                                allow_control = False
                            elif not self.teams[team]['allow_control']:
                                response[1] = f"You are not allowed to control the robots of team {team}"
                                allow_control = False
                            elif self.teams[team]['preemption_reasons'][robot]:
                                reasons = str(self.teams[team]['preemption_reasons'][robot])
                                response[1] = f"Robot {robot} of team {team} is preempted: {reasons}"
                                allow_control = False
                        
                        if allow_control:
                            marker = "%s%d" % (team, robot)
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

    def status(self):
        state = copy.deepcopy(self.teams)
        for team in state:
            for number in state[team]['preemption_reasons']:
                state[team]['preemption_reasons'][number] = list(state[team]['preemption_reasons'][number])
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

    def robots_idle(self) -> bool:
        """
        Are all the robots idle? (if they reached their target)
        """        
        return self.idle
    
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

                    if intersect_field_in:
                        self.preempt_robot(team, number, 'out-of-game')
                        self.targets[(team, number)] = (0., 0., 0.)
                        
                    else: 
                        if self.is_preempted(team, number, 'out-of-game'):
                            self.targets[(team, number)] = 'stop'
                            self.unpreempt_robot(team, number, 'out-of-game')

                # if robot.age() is not None and robot.age() > 1. and robot.age() < 10:
                #     self.preempt_robot(team, number, 'out-of-game')
                #     self.targets[(team, number)] = (0., 0., 0.)
                # else:
                #     if self.is_preempted(team, number, 'out-of-game'):
                #         self.targets[(team, number)] = 'stop'
                #         self.unpreempt_robot(team, number, 'out-of-game')

            # Handling robot's goto, since client interaction access network, we can't afford to
            # lock a mutex during client calls, we store order in the temporary buffer list
            self.lock.acquire()
            self.targets = {**self.targets, **self.targets_buffer}
            self.targets_buffer = {}
            self.lock.release()

            moving = False
            for robot in self.targets:
                team, number = robot
                target = self.targets[robot]
                if target is not None:
                    if target == 'stop' or self.client.robots[team][number].goto(target, wait=False, skip_old=False):
                        self.client.robots[team][number].control(0, 0, 0)
                        self.targets[robot] = None
                    else:
                        moving = True
            self.idle = not moving

            time.sleep(0.01)
