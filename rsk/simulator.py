from .field import Field
import threading
import time
import zmq
import numpy as np
from numpy.linalg import norm
from math import dist
from . import kinematics, utils, control, constants
import abc


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
                    "ball": self.get_ball(),
                    "markers": self.get_markers(),
                    "calibrated": self.field.calibrated(),
                    "see_whole_field": self.field.see_whole_field,
                    "referee": None if self.referee is None else self.referee.get_game_state(full=False),
                }
            except Exception as err:
                print("Thread init error : ", err)

    @abc.abstractmethod
    def get_ball() -> list:
        ...

    @abc.abstractmethod
    def get_markers(self) -> dict:
        ...

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


class Simulator(Detection):
    def __init__(self, robots):
        super().__init__()
        self.objects: dict = {}

        # Creating the ball
        self.add_object(
            SimulatedObject("ball", [0, 0, 0], constants.ball_radius, constants.ball_deceleration, constants.ball_mass)
        )

        # Adding the robots
        for object in robots.robots_by_marker.values():
            self.add_object(object)

        self.on_tick = None

        self.simu_thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()

        self.period = None
        self.lock = threading.Lock()

    def get_ball(self) -> list:
        return list(self.objects["ball"].position[:2])

    def get_markers(self) -> dict:
        markers = dict()
        for marker in ["green1", "green2", "blue1", "blue2"]:
            pos = self.objects[marker].position.tolist()
            markers[marker] = {"position": pos[:2], "orientation": pos[2]}

        return markers

    def add_object(self, object) -> None:
        self.objects[object.marker] = object
        object.sim = self

    def thread(self):
        last_time = time.time()
        while True:
            self.dt = -(last_time - (last_time := time.time()))

            for obj in self.objects.values():
                # Execute actions (e.g: kick)
                obj.execute_actions()

                # Update object velocity (e.g: deceleration, taking commands in account)
                obj.update_velocity(self.dt)

                if norm(obj.velocity) > 0:
                    # Where the object would arrive without collisions
                    future_pos = obj.position + obj.velocity * self.dt

                    # Check for collisions
                    for marker in self.objects:
                        if marker != obj.marker:
                            check_obj = self.objects[marker]
                            if dist(future_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                                obj.collision(check_obj)
                                has_collision = True

            for obj in self.objects.values():
                # Check for collisions
                for marker in self.objects:
                    if marker != obj.marker:
                        check_obj = self.objects[marker]
                        future_pos = obj.position + obj.velocity * self.dt

                        if dist(future_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                            R_collision_world = obj.collision_R(check_obj)
                            velocity_collision = R_collision_world @ obj.velocity[:2]
                            velocity_collision[0] = min(0, velocity_collision[0])
                            obj.velocity[:2] = R_collision_world.T @ velocity_collision

                obj.position = obj.position + (obj.velocity * self.dt)

            # TODO: Remove this
            if np.linalg.norm(self.objects["ball"].position[:2]) > 1.5:
                self.objects["ball"].position[:3] = [0.0, 0.0, 0.0]
                self.objects["ball"].velocity[:3] = [0.0, 0.0, 0.0]

            if self.on_tick is not None:
                self.on_tick()

            self.detection.publish()

            # TODO: Configure the frequency
            time.sleep(0.01)


class Robots:
    def __init__(self):
        self.control = control.Control(self)
        self.control.start()

        self.detection: Detection = None
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
    def __init__(self, marker, position, radius, deceleration: float = 0, mass: float = 1):
        self.marker = marker
        self.radius = radius

        self.mass = mass
        self.position = np.array([float(i) for i in position])

        self.velocity = np.array([0.0, 0.0, 0.0])
        self.deceleration = deceleration

        self.pending_actions = []
        self.sim: Simulator = None

    def execute_actions(self):
        for action in self.pending_actions:
            action()
        self.pending_actions = []

    def update_velocity(self, dt):
        self.velocity[:2] = utils.update_limit_variation(self.velocity[:2], np.array([0.0, 0.0]), self.deceleration * dt)

    def collision_R(self, obj):
        """
        Given another object, computes the collision frame.
        It returns R_collision_world
        """

        # Computing unit vectors normal and tangent to contact (self to obj)
        normal = obj.position[:2] - self.position[:2]
        normal = normal / norm(normal)
        tangent = np.array([[0, -1], [1, 0]]) @ normal

        return np.vstack((normal, tangent))

    def collision(self, obj):
        print("Collision")

        R_collision_world = self.collision_R(obj)

        # Velocities expressed in the collision frame
        self_velocity_collision = R_collision_world @ self.velocity[:2]
        obj_velocity_collision = R_collision_world @ obj.velocity[:2]

        # Updating velocities using elastic collision
        u1 = self_velocity_collision[0]
        u2 = obj_velocity_collision[0]
        m1 = self.mass
        m2 = obj.mass
        Cr = 0.5

        self_velocity_collision[0] = (m1 * u1 + m2 * u2 + m2 * Cr * (u2 - u1)) / (m1 + m2)
        obj_velocity_collision[0] = (m1 * u1 + m2 * u2 + m1 * Cr * (u1 - u2)) / (m1 + m2)

        # Velocities back in the world frame
        self.velocity[:2] = R_collision_world.T @ self_velocity_collision
        obj.velocity[:2] = R_collision_world.T @ obj_velocity_collision


class Robot(SimulatedObject):
    def __init__(self, marker, position):
        super().__init__(marker, position, kinematics.robot_radius, 0, constants.robot_mass)
        self.control_cmd = np.array([0.0, 0.0, 0.0])

    def control(self, dx: float, dy: float, dturn: float):
        self.control_cmd = kinematics.clip_target_order(np.array([dx, dy, dturn]))

    def kick(self, power: float = 1.0):
        self.pending_actions.append(lambda: self.compute_kick(power))

    def compute_kick(self, power):
        # Robot to ball vector, expressed in world
        ball_world = self.sim.objects["ball"].position[:2]
        T_world_robot = utils.frame(tuple(self.position))
        T_robot_world = utils.frame_inv(T_world_robot)
        ball_robot = utils.frame_transform(T_robot_world, ball_world)

        if utils.in_rectangle(
            ball_robot,
            [self.radius - constants.kicker_x_tolerance, -constants.kicker_y_tolerance],
            [self.radius + constants.kicker_x_tolerance, constants.kicker_y_tolerance],
        ):
            print("Kick_Valid")

            # TODO: Move in constants
            ball_speed_robot = [np.clip(power, 0, 1) * np.random.normal(0.8, 0.1), 0]
            self.sim.objects["ball"].velocity[:2] = T_world_robot[:2, :2] @ ball_speed_robot

    def update_velocity(self, dt):
        target_velocity_robot = self.control_cmd

        T_world_robot = utils.frame(tuple(self.position))
        target_velocity_world = T_world_robot[:2, :2] @ target_velocity_robot[:2]

        self.velocity[:2] = utils.update_limit_variation(
            self.velocity[:2], target_velocity_world, constants.max_linear_acceleration * dt
        )
        self.velocity[2:] = utils.update_limit_variation(
            self.velocity[2:], target_velocity_robot[2:], constants.max_angular_accceleration * dt
        )

    def leds(self, r: int, g: int, b: int):
        pass
