import zmq
import threading
from . import robots


class Control:
    def __init__(self, robots):
        self.robots = robots

        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:7558")

        self.teams = {
            "red": {
                "allow_control": True,
                "key": "",
                "packets": 0
            },
            "blue": {
                "allow_control": True,
                "key": "",
                "packets": 0
            }
        }

    def thread(self):
        while self.running:
            self.socket.RCVTIMEO = 1000
            try:
                json = self.socket.recv_json()
                response = [False, 'Unknown error']

                if type(json) == list and len(json) == 4:
                    key, team, robot, command = json

                    if team in self.teams:
                        if not self.teams[team]['allow_control']:
                            response[1] = 'You are not allowed to control the robots of team '+team
                        elif self.teams[team]['key'] != key:
                            response[1] = 'Bad key for team '+team
                        else:
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

    def stop(self):
        self.running = False

    def status(self):
        return self.teams

    def allowControl(self, team, allow):
        self.teams[team]['allow_control'] = allow

    def emergency(self):
        self.allowControl('red', False)
        self.allowControl('blue', False)

        for port in self.robots.robots:
            self.robots.robots[port].control(0, 0, 0)

    def setKey(self, team, key):
        self.teams[team]['key'] = key
