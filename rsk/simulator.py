from .field import Field
import threading
import time
import zmq
import numpy as np
from math import dist
from . import kinematics, utils, control




class Detection:
    def __init__(self):

        # Video attribute
        self.detection = self
        self.capture = None
        self.period = None


        self.referee = None
        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.set_hwm(1)
        self.socket.bind("tcp://*:7557")

        self.field = Field()

    def get_detection(self):
        while True:
            try:
                return {
                    "ball": list(SimulatedObject.get_ball().position[:2].tolist()),
                    "markers": self.new_markers(),
                    "calibrated": self.field.calibrated(),
                    "see_whole_field": self.field.see_whole_field,
                    "referee": self.referee.get_game_state(full=False),
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

    # Video method
    def get_video(self, with_image: bool):
        data = {
            "running": self.capture is not None,
            "fps": round(1 / self.period, 1) if self.period is not None else 0,
            "detection": self.detection.get_detection(),
        }
        return data


class Simulator:
    def __init__(self, detection, robots):

        self.robots = robots
        self.detection = detection

        SimulatedObject("ball", [0, 0, 0], 0.01, 0.3)
        self.objects = SimulatedObject.get_objects

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()
        self.period = None
        self.lock = threading.Lock()

    def thread(self):
        last_time = time.time()
        while True:
            self.dt = time.time() - last_time
            last_time = time.time()

            for obj in self.objects():
                obj.action()
                speed = obj.speed
                if np.linalg.norm(speed) != 0:
                    futur_pos = obj.position + (speed * self.dt) @ utils.frame_inv(utils.frame(tuple(obj.position)))
                    for check_obj in self.objects():
                        if check_obj.marker != obj.marker:
                            if dist(futur_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                                if check_obj.marker == "ball":
                                    check_obj.speed = speed / 4 @ utils.frame_inv(utils.frame(tuple(obj.position)))
                                    check_obj.speed[2] = 0
                                else:
                                    C = (futur_pos[:2] + check_obj.position[:2]) / 2
                                    futur_pos += (*(obj.position[:2] - C) / 6, 0)

                    obj.position = np.array(futur_pos)

                    obj.speed = speed * (
                        1 - (obj.deceleration * self.dt) / np.linalg.norm([speed[:2] if sum(speed[:2]) else speed])
                    )

                    if np.linalg.norm(obj.speed) < 0.01:
                        obj.speed = np.array([0, 0, 0])

            self.detection.publish()


class Robots:
    def __init__(self, detection: Detection):
        self.control = control.Control(self)
        self.control.start()

        self.detection: Detection = detection
        self.robots: dict = {}
        self.robots_by_marker: dict = {}


        for marker, position in zip(
            ["green1", "green2", "blue1", "blue2"],
            [[-0.5, 0.5, 0], [-0.5, -0.5, 0], [0.5, 0.5, 0], [0.5, -0.5, 0]],
        ):
            robot = Robot(marker, position)
            self.robots_by_marker[marker] = robot

    def should_restore_leds(self, robot: str):
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
        self.speed = kinematics.clip_target_order(np.array([dx, dy, dturn]))

    def kick(self, power: float = 1.0):
        self.action = self.compute_kick

    def compute_kick(self):
        self.action = lambda: 0

        vector_BR = SimulatedObject.get_ball().position[:2] - self.position[:2]

        ball_position = [*vector_BR, 0] @ utils.frame(tuple(self.position))
        if (
            -self.kicker_range[1] < ball_position[1] < self.kicker_range[1]
            and 0 < (ball_position[0] - self.radius) < self.kicker_range[0]
        ):
            print("Kick_Valid")
            vector = (self.kicker_range[0], 0, 0) @ utils.frame(tuple(self.position))
            SimulatedObject.get_ball().position[2] = self.position[2]
            SimulatedObject.get_ball().speed = np.array([0.7,0,0])

            # SimulatedObject.get_ball().speed = np.array([*(vector[:2] / np.linalg.norm(vector[:2]) * 0.4), 0])


    def leds(self, r: int, g: int, b: int):
        pass
