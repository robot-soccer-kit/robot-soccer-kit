import sys
import threading
import time
import numpy as np
from numpy.linalg import norm
from math import dist
from . import kinematics, utils, constants, state, robot, robots, client

from collections.abc import Callable


class SimulatedObject:
    def __init__(self, marker: str, position: np.ndarray, radius: int, deceleration: float = 0, mass: float = 1) -> None:
        self.marker: str = marker
        self.radius: int = radius

        self.mass: float = mass
        self.position: np.ndarray = np.array([float(i) for i in position])

        self.velocity: np.ndarray = np.array([0.0, 0.0, 0.0])
        self.deceleration: float = deceleration

        self.pending_actions: list(Callable) = []
        self.sim: Simulator = None

    def execute_actions(self) -> None:
        for action in self.pending_actions:
            action()
        self.pending_actions = []

    def teleport(self, x: float, y: float, turn: float):
        self.position = np.array((x, y, turn))
        self.velocity = np.array([0.0, 0.0, 0.0])

    def update_velocity(self, dt) -> None:
        self.velocity[:2] = utils.update_limit_variation(self.velocity[:2], np.array([0.0, 0.0]), self.deceleration * dt)

    def collision_R(self, obj):
        """
        Given another object, computes the collision frame.
        It returns R_collision_world
        """

        # Computing unit vectors normal and tangent to contact (self to obj)
        normal = obj.position[:2] - self.position[:2]

        normal = (normal / norm(normal)) if norm(normal) != 0 else (0, 0)
        tangent = np.array([[0, -1], [1, 0]]) @ normal

        return np.vstack((normal, tangent))

    def collision(self, obj) -> None:
        R_collision_world = self.collision_R(obj)

        # Velocities expressed in the collision frame
        self_velocity_collision = R_collision_world @ self.velocity[:2]
        obj_velocity_collision = R_collision_world @ obj.velocity[:2]

        # Updating velocities using elastic collision
        u1 = self_velocity_collision[0]
        u2 = obj_velocity_collision[0]
        m1 = self.mass
        m2 = obj.mass
        Cr = 0.25

        # If the objects are not getting closer to each other, don't proceed
        if u2 - u1 > 0:
            return

        self_velocity_collision[0] = (m1 * u1 + m2 * u2 + m2 * Cr * (u2 - u1)) / (m1 + m2)
        obj_velocity_collision[0] = (m1 * u1 + m2 * u2 + m1 * Cr * (u1 - u2)) / (m1 + m2)

        # Velocities back in the world frame
        self.velocity[:2] = R_collision_world.T @ self_velocity_collision
        obj.velocity[:2] = R_collision_world.T @ obj_velocity_collision


class SimulatedRobot(SimulatedObject):
    def __init__(self, name: str, position: np.ndarray) -> None:
        super().__init__(name, position, constants.robot_radius, 0, constants.robot_mass)
        self.control_cmd: np.ndarray = np.array([0.0, 0.0, 0.0])
        self.leds = None  # [R,G,B] (0-255) None for off

    def compute_kick(self, power: float) -> None:
        # Robot to ball vector, expressed in world
        ball_world = self.sim.objects["ball"].position[:2]
        T_world_robot = utils.frame(tuple(self.position))
        T_robot_world = utils.frame_inv(T_world_robot)
        ball_robot = utils.frame_transform(T_robot_world, ball_world)

        if utils.in_rectangle(
            ball_robot,
            [self.radius + constants.ball_radius - constants.kicker_x_tolerance, -constants.kicker_y_tolerance],
            [self.radius + constants.ball_radius + constants.kicker_x_tolerance, constants.kicker_y_tolerance],
        ):
            # TODO: Move the ball kicking velocity to constants
            # TODO: We should not set the ball velocity to 0 in the y direction but keep its velocity
            ball_speed_robot = [np.clip(power, 0, 1) * np.random.normal(0.8, 0.1), 0]
            self.sim.objects["ball"].velocity[:2] = T_world_robot[:2, :2] @ ball_speed_robot

    def update_velocity(self, dt: float) -> None:
        target_velocity_robot = self.control_cmd

        T_world_robot = utils.frame(tuple(self.position))
        target_velocity_world = T_world_robot[:2, :2] @ target_velocity_robot[:2]

        self.velocity[:2] = utils.update_limit_variation(
            self.velocity[:2], target_velocity_world, constants.max_linear_acceleration * dt
        )
        self.velocity[2:] = utils.update_limit_variation(
            self.velocity[2:], target_velocity_robot[2:], constants.max_angular_accceleration * dt
        )

    def control_leds(self, r: int, g: int, b: int) -> None:
        self.leds = [r, g, b]


class RobotSim(robot.Robot):
    def __init__(self, url: str):
        super().__init__(url)
        self.set_marker(url)

        self.object: SimulatedRobot = None

    def initialize(self, position: np.ndarray) -> None:
        self.object = SimulatedRobot(self.marker, position)

    def teleport(self, x: float, y: float, turn: float) -> None:
        """
        Teleports the robot to a given position/orientation

        :param float x: x position [m]
        :param float y: y position [m]
        :param float turn: orientation [rad]
        """
        self.object.teleport(x, y, turn)

    def control(self, dx: float, dy: float, dturn: float) -> None:
        self.object.control_cmd = kinematics.clip_target_order(np.array([dx, dy, dturn]))

    def kick(self, power: float = 1.0) -> None:
        self.object.pending_actions.append(lambda: self.object.compute_kick(power))

    def leds(self, red: int, green: int, blue: int) -> None:
        """
        Controls the robot LEDs

        :param int red: red brightness (0-255)
        :param int green: green brightness (0-255)
        :param int blue: blue brightness (0-255)
        """
        self.object.pending_actions.append(lambda: self.object.control_leds(red, green, blue))


class Simulator:
    def __init__(self, robots: robots.Robots, state: state.State = None, run_thread=True):
        self.state: state.State = state
        self.robots: robots.Robots = robots

        # Creating the robots
        for configuration in client.configurations["game_green_positive"]:
            robot: RobotSim = self.robots.add_robot(f"sim://{utils.robot_list2str(*configuration[:2])}")
            robot.initialize(configuration[2])

        self.robots.update()

        self.objects: dict = {}

        # Creating the ball
        self.add_object(
            SimulatedObject("ball", [0, 0, 0], constants.ball_radius, constants.ball_deceleration, constants.ball_mass)
        )
        self.add_robot_objects()
        self.robots.ball = self.objects["ball"]

        self.fps_limit = 100

        if run_thread:
            self.run_thread()

    def run_thread(self):
        self.run = True
        self.simu_thread: threading.Thread = threading.Thread(target=lambda: self.thread())
        self.simu_thread.start()
        self.lock: threading.Lock = threading.Lock()

    def add_object(self, object: SimulatedObject) -> None:
        self.objects[object.marker] = object
        object.sim = self

    def add_robot_objects(self) -> None:
        for robot in self.robots.robots_by_marker.values():
            self.add_object(robot.object)

    def thread(self) -> None:
        last_time = time.time()
        while self.run:
            self.dt = -last_time + (last_time := time.time())
            self.loop(self.dt)

            while (self.fps_limit is not None) and (time.time() - last_time < 1 / self.fps_limit):
                time.sleep(1e-3)

    def loop(self, dt):
        # Simulator proceed in two steps:
        # 1) We handle future collisions as elastic collisions and change the velocity vectors
        #    accordingly.
        # 2) We apply the object velocities, removing all the components in the velocities that would
        #    create collision.

        for obj in self.objects.values():
            # Execute actions (e.g: kick)

            # Update object velocity (e.g: deceleration, taking commands in account)
            obj.update_velocity(dt)

            if norm(obj.velocity) > 0:
                # Where the object would arrive without collisions
                future_pos = obj.position + obj.velocity * dt

                # Check for collisions
                for marker in self.objects:
                    if marker != obj.marker:
                        check_obj = self.objects[marker]
                        if dist(future_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                            obj.collision(check_obj)

        for obj in self.objects.values():
            # Check for collisions
            for marker in self.objects:
                if marker != obj.marker:
                    check_obj = self.objects[marker]
                    future_pos = obj.position + obj.velocity * dt

                    if dist(future_pos[:2], check_obj.position[:2]) < (obj.radius + check_obj.radius):
                        R_collision_world = obj.collision_R(check_obj)
                        velocity_collision = R_collision_world @ obj.velocity[:2]
                        velocity_collision[0] = min(0, velocity_collision[0])
                        obj.velocity[:2] = R_collision_world.T @ velocity_collision

            obj.position = obj.position + (obj.velocity * dt)
            obj.execute_actions()
        if "ball" in self.objects and not utils.in_rectangle(
            self.objects["ball"].position[:2],
            [-constants.carpet_length / 2, -constants.carpet_width / 2],
            [constants.carpet_length / 2, constants.carpet_width / 2],
        ):
            self.objects["ball"].position[:3] = [0.0, 0.0, 0.0]
            self.objects["ball"].velocity[:3] = [0.0, 0.0, 0.0]

        self.push()

    def push(self) -> None:
        if self.state is not None:
            for marker in self.objects:
                pos = self.objects[marker].position
                if marker == "ball":
                    self.state.set_ball(pos[:2].tolist())
                else:
                    self.state.set_marker(marker, pos[:2].tolist(), pos[2])
                    self.state.set_leds(marker, self.objects[marker].leds)
