from . import control
from .field import Field
import threading
import time
import zmq
import copy
import numpy as np
from math import cos, sin


class Video:
    def __init__(self):
        self.detection = Detection()
        self.capture = None
        self.period = None

        self.running = False
        # self.simu_thread = threading.Thread(target=lambda: self.thread())
        # self.simu_thread.start()

        self.command = None

    def get_video(self, with_image: bool):
        data = {
            "running": self.capture is not None,
            "fps": round(1 / self.period, 1) if self.period is not None else 0,
            "detection": self.detection.get_detection(),
        }
        return data


class Detection:
    def __init__(self):
        self.referee = None

        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.set_hwm(1)
        self.socket.bind("tcp://*:7557")

        self.ball = [0, 0]
        self.markers = {
            "green1": {"position": [0, 0], "orientation": 0},
            "green2": {"position": [0, 0], "orientation": 0},
            "blue1": {"position": [0, 0], "orientation": 0},
            "blue2": {"position": [0, 0], "orientation": 0},
        }
        self.field = Field()

        self.command = list()

    def get_detection(self):
        while True:
            try:
                return {
                    "ball": self.ball,
                    "markers": self.markers,
                    "calibrated": self.field.calibrated(),
                    "see_whole_field": self.field.see_whole_field,
                    "referee": self.referee.get_game_state(full=False),
                }
            except AttributeError:
                print("oups")

    def publish(self) -> None:
        """
        Publish the detection informations on the network
        """
        info = self.get_detection()

        self.socket.send_json(info, flags=zmq.NOBLOCK)

        if self.referee is not None:
            self.referee.set_detection_info(info)


class Simulator:
    def __init__(self, detection, robots):

        self.robots = robots
        self.detection = detection

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()

    def thread(self):
        last_time = time.time()
        last_markers = copy.deepcopy(self.detection.markers)

        while 1:
            time.sleep(0.05)
            self.dt = time.time() - last_time
            last_time = time.time()
            # print(self.dt)
            for marker in self.robots.robots_by_marker:

                if self.robots.robots_by_marker[marker].command:

                    command = self.robots.robots_by_marker[marker].command.pop(0)
                    print(command)
                    if command[0] == "control":
                        x, y, o = self.compute_mouv(
                            self.detection.markers[marker], command
                        )
                        self.detection.markers[marker]["position"][0] += x
                        self.detection.markers[marker]["position"][1] += y
                        self.detection.markers[marker]["orientation"] += o

                    elif command[0] == "kick":
                        self.detection.ball[0] += 0.5

            last_markers = copy.deepcopy(self.detection.markers)
            self.detection.publish()

    def compute_mouv(self, robot, command):
        x_r, y_r = command[1][:2]
        o_r = robot["orientation"] + command[1][2] * self.dt

        x = (x_r * cos(-o_r) + y_r * sin(-o_r)) * self.dt
        y = (y_r * cos(-o_r) - x_r * sin(-o_r)) * self.dt

        return (x, y, command[1][2] * self.dt)


class Robots:
    def __init__(self, detection: Detection):
        self.control = control.Control(self)
        self.control.start()
        self.detection: simulator.Detection = detection
        self.robots: dict = {}

        self.robots_by_marker: dict = {}
        for marker in ["green1", "green2", "blue1", "blue2"]:
            robot = Robot()
            robot.marker = marker
            self.robots_by_marker[marker] = robot

    def should_restore_leds(self, robot: str) -> bool:
        pass

    def ports(self):
        return [0, 0, 0, 0]

    def get_robots(self) -> dict:
        """
        Gets robots informations.

        :return dict: information about robots
        """
        data = {}
        for entry in self.robots:
            last_detection = None
            if self.robots[entry].marker in self.detection.last_updates:
                last_detection = (
                    time.time() - self.detection.last_updates[self.robots[entry].marker]
                )

            data[entry] = {
                "state": self.robots[entry].state,
                "marker": self.robots[entry].marker,
                "last_detection": last_detection,
                "last_message": time.time() - self.robots[entry].last_message
                if self.robots[entry].last_message is not None
                else None,
            }

        return data


class Robot:
    def __init__(self):
        # Marker on the top of this robot
        self.marker = None

        self.command = list()

    def control(self, dx: float, dy: float, dturn: float):
        self.command.append(["control", [dx, dy, dturn]])

    def kick(self, power: float = 1.0):
        self.command.append(["kick", power])

    def leds(self, r: int, g: int, b: int):
        pass
