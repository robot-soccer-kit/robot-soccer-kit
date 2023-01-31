from . import control
from .field import Field
import threading
import time
import zmq
import copy
import numpy as np
from math import cos, sin, hypot


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

        self.printable_point = list()
        self.ball = [0, 0]
        self.markers = {
            "green1": {"position": [0.5, 0.5], "orientation": 0},
            "green2": {"position": [-0.5, 0.5], "orientation": 0},
            "blue1": {"position": [0.5, -0.5], "orientation": 0},
            "blue2": {"position": [-0.5, -0.5], "orientation": 0},
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
                    "printable_point": self.printable_point,
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

        self.ball_deceleration = 0.3
        self.ball_speed = np.array([0, 0])
        self.kicker_power = 0.3
        self.a = [None]
        self.b = [None]

        self.bot_radius = 0.09
        self.kicker_range = [0.03, 0.04]

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()

    def thread(self):
        last_time = time.time()
        last_markers = copy.deepcopy(self.detection.markers)
        while 1:
            time.sleep(0.03)
            self.dt = time.time() - last_time
            last_time = time.time()
            # print(self.dt)
            for marker in self.robots.robots_by_marker:

                if self.robots.robots_by_marker[marker].command:

                    command = self.robots.robots_by_marker[marker].command.pop(0)
                    if command[0] == "control":
                        robot = self.detection.markers[marker]
                        x, y, o = command = self.compute_mouv(robot, command)
                        if self.mouv_is_valid(marker, command):
                            robot["position"][0] += x
                            robot["position"][1] += y
                            robot["orientation"] += o

                    elif command[0] == "kick":
                        if self.compute_kick(marker):
                            print("ok")

            if sum(self.ball_speed) != 0:
                self.detection.ball = [
                    self.detection.ball[0] + self.ball_speed[0] * self.dt,
                    self.detection.ball[1] + self.ball_speed[1] * self.dt,
                ]

                if self.a[0] == None:
                    self.a = copy.deepcopy(self.ball_speed)
                    self.b = copy.deepcopy(self.ball_speed)

                self.ball_speed *= (
                    hypot(*self.ball_speed) - self.ball_deceleration * self.dt
                ) / hypot(*self.ball_speed)

                if -0.01 < self.ball_speed[0] < 0.01:
                    self.ball_speed[0] = 0
                if -0.01 < self.ball_speed[1] < 0.01:
                    self.ball_speed[1] = 0

            last_markers = copy.deepcopy(self.detection.markers)
            self.detection.publish()

    def mouv_is_valid(self, marker, command):
        robot = self.detection.markers[marker]
        new_pos = (
            robot["position"][0] + command[0],
            robot["position"][1] + command[1],
        )
        for mark in self.robots.robots_by_marker:
            if marker != mark:
                pos = self.detection.markers[mark]["position"]
                distance_xy = np.array(new_pos) - np.array(pos)
                distance = hypot(distance_xy[0], distance_xy[1])
                if distance < 0.15:
                    return False

        return True

    def compute_mouv(self, robot, command):
        x_r, y_r = command[1][:2]
        o_r = robot["orientation"] + command[1][2] * self.dt

        x = (x_r * cos(-o_r) + y_r * sin(-o_r)) * self.dt
        y = (y_r * cos(-o_r) - x_r * sin(-o_r)) * self.dt

        return (x, y, command[1][2] * self.dt)

    def compute_kick(self, marker):
        robot = self.detection.markers[marker]
        ball = self.detection.ball
        distance_xy = np.array(robot["position"]) - np.array(self.detection.ball)
        distance = hypot(distance_xy[0], distance_xy[1])

        o_r = robot["orientation"]

        ball_R = [0, 0]
        _ = np.array(ball) - np.array(robot["position"])
        ball_R[0] = (_[0]) * cos(o_r) + (_[1]) * sin(o_r)
        ball_R[1] = (_[1]) * cos(o_r) - (_[0]) * sin(o_r)

        if (
            -self.kicker_range[1] < (ball_R[1]) < self.kicker_range[1]
            and 0 < (ball_R[0] - self.bot_radius) < self.kicker_range[0]
        ):

            vecteur = (np.array(distance_xy) / hypot(*distance_xy)) * self.kicker_power
            self.ball_speed = -vecteur

    def compute_ball_acceleration(self):
        if self.ball_acc != [0, 0]:
            self.ball_acc


class Robots:
    def __init__(self, detection: Detection):
        self.control = control.Control(self)
        self.control.start()
        self.detection: simulator.Detection = detection
        self.robots: dict = {}
        self.vitesse = [0, 0, 0]

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
