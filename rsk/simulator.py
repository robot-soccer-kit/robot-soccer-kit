from . import control
from .field import Field
import threading
import time
import zmq
import copy
import numpy as np
from math import cos, sin, hypot, dist
from . import kinematics, utils


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
            return {
                "ball": list(SimulatedObject.get_ball().position[:2].tolist()),
                "markers": self.new_markers(),
                "calibrated": self.field.calibrated(),
                "see_whole_field": self.field.see_whole_field,
                "referee": self.referee.get_game_state(full=False),
                "printable_point": self.printable_point,
            }

    def new_markers(self):
        markers = dict()
        for marker in ["green1", "green2", "blue1", "blue2"]:
            pos = SimulatedObject.get_object(marker).position.tolist()
            markers[marker] = {"position": pos[:2], "orientation": pos[2]}
        return markers

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

        SimulatedObject("ball", [0, 0, 0], 0.1, 0.3)
        self.objects = SimulatedObject.get_objects()

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()

    def thread(self):
        last_time = time.time()
        last_markers = copy.deepcopy(self.detection.markers)
        while 1:
            time.sleep(0.01)
            self.dt = time.time() - last_time
            last_time = time.time()

            for obj in self.objects:
                if np.linalg.norm(obj.speed) != 0:
                    futur_pos = obj.position + utils.frame(tuple(obj.position)) @ (
                        obj.speed * self.dt
                    )
                    for check_obj in self.objects:
                        if check_obj != obj:
                            if dist(futur_pos, check_obj.position) < (
                                obj.radius + check_obj.radius
                            ):
                                if check_obj.marker == "ball":
                                    check_obj.speed = obj.speed
                                else:
                                    futur_pos = obj.position

                    obj.position = futur_pos
                    obj.speed = obj.speed / np.linalg.norm(obj.speed) * obj.deceleration

            self.detection.publish()

            # for marker in self.robots.robots_by_marker:

            #     if self.robots.robots_by_marker[marker].command:

            #         command = self.robots.robots_by_marker[marker].command.pop(0)
            #         if command[0] == "control":
            #             robot = self.detection.markers[marker]
            #             x, y, o = command = self.compute_mouv(marker, command)
            #             robot["position"][0] += x
            #             robot["position"][1] += y
            #             robot["orientation"] += o

            #         elif command[0] == "kick":
            #             print("kick")
            #             if self.compute_kick(marker):
            #                 print("ok")

            # if sum(self.ball_speed) != 0:
            #     self.detection.ball = [
            #         self.detection.ball[0] + self.ball_speed[0] * self.dt,
            #         self.detection.ball[1] + self.ball_speed[1] * self.dt,
            #     ]

            #     self.ball_speed *= (
            #         hypot(*self.ball_speed) - self.ball_deceleration * self.dt
            #     ) / hypot(*self.ball_speed)

            #     if -0.01 < self.ball_speed[0] < 0.01:
            #         self.ball_speed[0] = 0
            #     if -0.01 < self.ball_speed[1] < 0.01:
            #         self.ball_speed[1] = 0

            # last_markers = copy.deepcopy(self.detection.markers)
            # self.detection.publish()

    def distance_obj(self, posA, posB):
        distance_xy = np.array(posA) - np.array(posB)
        distance = hypot(distance_xy[0], distance_xy[1])
        return distance

    def compute_mouv(self, marker, command):
        robot = self.detection.markers[marker]

        command[1] = kinematics.clip_target_order(np.array(command[1]))

        x_r, y_r = command[1][:2]
        o_r = robot["orientation"]  # + command[1][2] * self.dt

        x = (x_r * cos(-o_r) + y_r * sin(-o_r)) * self.dt
        y = (y_r * cos(-o_r) - x_r * sin(-o_r)) * self.dt

        command = [x, y, command[1][2] * self.dt]
        new_pos = (
            robot["position"][0] + command[0],
            robot["position"][1] + command[1],
        )

        for mark in self.robots.robots_by_marker:
            if marker != mark:
                pos = self.detection.markers[mark]["position"]
                distance_xy = np.array(new_pos) - np.array(pos)
                distance = hypot(distance_xy[0], distance_xy[1])
                if distance < kinematics.robot_radius * 2:
                    command = [-command[1], -command[0], command[2]]

        if (
            self.distance_obj(new_pos, self.detection.ball)
            < 0.021 + kinematics.robot_radius
        ):
            self.ball_speed = np.array(command[:2])

        return command

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
            -self.kicker_range[1] < ball_R[1] < self.kicker_range[1]
            and 0 < (ball_R[0] - kinematics.robot_radius) < self.kicker_range[0]
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
        self.robots_by_marker: dict = {}

        for marker, position in zip(
            ["green1", "green2", "blue1", "blue2"],
            [[-0.5, 0.5, 0], [-0.5, -0.5, 0], [0.5, 0.5, 0], [0.5, -0.5, 0]],
        ):
            robot = Robot(marker, position)
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


class SimulatedObject:
    sim_object = dict()

    def __init__(self, marker, position, radius, deceleration):
        SimulatedObject.sim_object[marker] = self
        self.marker = marker
        self.position = np.array([float(i) for i in position])
        self.deceleration = deceleration
        self.radius = radius
        self.speed = np.array([0.0, 0.0, 0.0])
        self.action = None

    def get_objects():
        return [
            SimulatedObject.sim_object[marker] for marker in SimulatedObject.sim_object
        ]

    def get_object(marker):
        return SimulatedObject.sim_object[marker]

    def get_ball():
        return SimulatedObject.sim_object["ball"]


class Robot(SimulatedObject):
    def __init__(self, marker, position):

        super().__init__(marker, position, kinematics.robot_radius, 1)

    def control(self, dx: float, dy: float, dturn: float):
        self.speed = kinematics.clip_target_order(np.array([dx, dy, dturn]))

    def kick(self, power: float = 1.0):
        self.action = self.compute_kick()

    def compute_kick(self):
        pass

    def leds(self, r: int, g: int, b: int):
        pass
