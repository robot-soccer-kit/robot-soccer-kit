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
            try:
                return {
                    "ball": list(SimulatedObject.get_ball().position[:2].tolist()),
                    "markers": self.new_markers(),
                    "calibrated": self.field.calibrated(),
                    "see_whole_field": self.field.see_whole_field,
                    "referee": self.referee.get_game_state(full=False),
                    "printable_point": self.printable_point,
                }
            except Exception as err:
                print("Thread init error : ", err)

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

        SimulatedObject("ball", [0, 0, 0], 0.01, 0.3)
        self.objects = SimulatedObject.get_objects()

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()

        self.lock = threading.Lock()

    def thread(self):
        last_time = time.time()
        while True:
            self.dt = time.time() - last_time
            last_time = time.time()
            # time.sleep(0.005)
            # print("DT : ", self.dt)

            for obj in SimulatedObject.get_objects():
                obj.action()
                speed = obj.speed
                if np.linalg.norm(speed) != 0:
                    futur_pos = obj.position + (speed * self.dt) @ utils.frame_inv(utils.frame(tuple(obj.position)))
                    for check_obj in SimulatedObject.get_objects():
                        if check_obj.marker != obj.marker:
                            if dist(futur_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                                if check_obj.marker == "ball":
                                    print("bam")
                                    check_obj.speed = speed / 4 @ utils.frame_inv(utils.frame(tuple(obj.position)))
                                    check_obj.speed[2] = 0
                                else:
                                    C = (futur_pos[:2] + check_obj.position[:2]) / 2
                                    futur_pos += (*(obj.position[:2] - C) / 6, 0)

                    obj.position = np.array(futur_pos)

                    # obj.speed = speed * (
                    #     1 - (obj.deceleration * self.dt) / np.linalg.norm([speed[:2] if sum(speed[:2]) else speed])
                    # )

                    obj.speed = speed * (hypot(*speed[:2]) - obj.deceleration * self.dt) / hypot(*speed[:2])

                    if np.linalg.norm(obj.speed) < 0.01:
                        obj.speed = np.array([0, 0, 0])

                    if np.isnan(obj.speed[0]):
                        while True:
                            pass
            self.detection.publish()


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
                last_detection = time.time() - self.detection.last_updates[self.robots[entry].marker]

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
    sim_objects = dict()

    def __init__(self, marker, position, radius, deceleration):
        SimulatedObject.sim_objects[marker] = self
        self.marker = marker
        self.position = np.array([float(i) for i in position])
        self.deceleration = deceleration
        self.radius = radius
        self.speed = np.array([0.0, 0.0, 0.0])
        self.action = lambda: 0

    def get_objects():
        return [SimulatedObject.sim_objects[key] for key in SimulatedObject.sim_objects]

    def get_object(marker):
        return SimulatedObject.sim_objects[marker]

    def get_ball():
        return SimulatedObject.sim_objects["ball"]


class Robot(SimulatedObject):
    def __init__(self, marker, position):
        super().__init__(marker, position, kinematics.robot_radius, 0)
        self.kicker_range = [0.05, 0.05]

    def control(self, dx: float, dy: float, dturn: float):
        # print(self.marker, " : ", [dx, dy, dturn])
        self.speed = kinematics.clip_target_order(np.array([dx, dy, dturn]))

    def kick(self, power: float = 1.0):
        self.action = self.compute_kick

    def compute_kick(self):
        print("KICK")
        self.action = lambda: 0
        vector_BR = SimulatedObject.get_ball().position[:2] - self.position[:2]
        ball_position = [*vector_BR, 0] @ utils.frame(tuple(self.position))
        if (
            -self.kicker_range[1] < ball_position[1] < self.kicker_range[1]
            and 0 < (ball_position[0] - self.radius) < self.kicker_range[0]
        ):
            print("kick_valid")

            SimulatedObject.get_ball().speed[:2] = vector_BR[:2] / np.linalg.norm(vector_BR[:2]) * 0.4
            print(np.linalg.norm(SimulatedObject.get_ball().speed))
            # [0.4, 0, 0] @ utils.frame_inv(utils.frame(tuple(self.position)))

    def leds(self, r: int, g: int, b: int):
        pass
