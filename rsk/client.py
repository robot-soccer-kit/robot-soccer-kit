import signal
import numpy as np
import zmq
import threading
import time
from . import constants, utils

configurations = {
    "dots": [
        ["green", 1, (constants.field_length / 4, -constants.field_width / 4, np.pi)],
        ["green", 2, (constants.field_length / 4, constants.field_width / 4, np.pi)],
        ["blue", 1, (-constants.field_length / 4, constants.field_width / 4, 0)],
        ["blue", 2, (-constants.field_length / 4, -constants.field_width / 4, 0)],
    ],
    "game": [
        ["green", 1, (constants.field_length / 4, 0, np.pi)],
        ["green", 2, (constants.field_length / 2, 0, np.pi)],
        ["blue", 1, (-constants.field_length / 4, 0, 0)],
        ["blue", 2, (-constants.field_length / 2, 0, 0)],
    ],
    "game_green_positive": [
        ["green", 1, (constants.field_length / 4, 0, np.pi)],
        ["green", 2, (constants.field_length / 2, 0, np.pi)],
        ["blue", 1, (-constants.field_length / 4, 0, 0)],
        ["blue", 2, (-constants.field_length / 2, 0, 0)],
    ],
    "game_blue_positive": [
        ["green", 1, (-constants.field_length / 4, 0, 0)],
        ["green", 2, (-constants.field_length / 2, 0, 0)],
        ["blue", 1, (constants.field_length / 4, 0, np.pi)],
        ["blue", 2, (constants.field_length / 2, 0, np.pi)],
    ],
    "side": [
        ["green", 1, (0.2, constants.field_width / 2, -np.pi / 2)],
        ["green", 2, (0.6, constants.field_width / 2, -np.pi / 2)],
        ["blue", 1, (-0.2, constants.field_width / 2, -np.pi / 2)],
        ["blue", 2, (-0.6, constants.field_width / 2, -np.pi / 2)],
    ],
    "swap_covers_green_positive": [
        ["green", 1, (0.09, -0.2, np.pi)],
        ["green", 2, (0.09, 0.2, np.pi)],
        ["blue", 1, (-0.09, -0.2, 0)],
        ["blue", 2, (-0.09, 0.2, 0)],
    ],
    "swap_covers_blue_positive": [
        ["green", 1, (-0.09, -0.2, 0)],
        ["green", 2, (-0.09, 0.2, 0)],
        ["blue", 1, (0.09, -0.2, np.pi)],
        ["blue", 2, (0.09, 0.2, np.pi)],
    ],
    "gently_swap_side": [
        ["green", 1, (0, -0.15, 0)],
        ["green", 2, (0, 0.5, 0)],
        ["blue", 1, (0, -0.5, np.pi)],
        ["blue", 2, (0, 0.15, np.pi)],
    ],
}


class ClientError(Exception):
    pass


class ClientTracked:
    def __init__(self):
        self.position = None
        self.pose = None
        self.orientation = None
        self.last_update = None


class ClientRobot(ClientTracked):
    def __init__(self, color, number, client):
        super().__init__()
        self.moved = False
        self.color = color
        self.team = color
        self.number = number
        self.client = client

        self.x_max = constants.field_length / 2 + constants.border_size / 2.0
        self.x_min = -self.x_max
        self.y_max = constants.field_width / 2 + constants.border_size / 2.0
        self.y_min = -self.y_max

    def ball(self):
        return self.client.ball

    def has_position(self, skip_old):
        seen = (self.position is not None) and (self.orientation is not None)
        if skip_old:
            seen = seen and self.age() < 1

        return seen

    def age(self):
        if self.last_update is None:
            return None

        return time.time() - self.last_update

    def kick(self, power=1):
        return self.client.command(self.color, self.number, "kick", [power])

    def control(self, dx, dy, dturn):
        self.moved = True

        return self.client.command(self.color, self.number, "control", [dx, dy, dturn])

    def leds(self, r, g, b):
        return self.client.command(self.color, self.number, "leds", [r, g, b])

    def goto_compute_order(self, target, skip_old=True):
        if not self.has_position(skip_old):
            return False, (0.0, 0.0, 0.0)

        if callable(target):
            target = target()

        x, y, orientation = target
        x = min(self.x_max, max(self.x_min, x))
        y = min(self.y_max, max(self.y_min, y))
        Ti = utils.frame_inv(utils.robot_frame(self))
        target_in_robot = Ti @ np.array([x, y, 1])

        error_x = target_in_robot[0]
        error_y = target_in_robot[1]
        error_orientation = utils.angle_wrap(orientation - self.orientation)

        arrived = np.linalg.norm([error_x, error_y, error_orientation]) < 0.05
        order = 1.5 * error_x, 1.5 * error_y, 1.5 * error_orientation

        return arrived, order

    def goto(self, target, wait=True, skip_old=True):
        if wait:
            while not self.goto(target, wait=False):
                time.sleep(0.05)
            self.control(0, 0, 0)
            return True

        arrived, order = self.goto_compute_order(target, skip_old)
        self.control(*order)

        return arrived


class Client:
    def __init__(self, host="127.0.0.1", key="", wait_ready=True):
        self.running = True
        self.key = key
        self.lock = threading.Lock()
        self.robots = {}

        # Creating self.green1, self.green2 etc.
        for color, number in utils.all_robots():
            robot_id = utils.robot_list2str(color, number)
            robot = ClientRobot(color, number, self)
            self.__dict__[robot_id] = robot

            if color not in self.robots:
                self.robots[color] = {}
            self.robots[color][number] = robot

        # Custom objects to track
        self.objs = {n: ClientTracked() for n in range(1, 9)}

        self.ball = None

        # ZMQ Context
        self.context = zmq.Context()

        # Creating subscriber connection
        self.sub = self.context.socket(zmq.SUB)
        self.sub.set_hwm(1)
        self.sub.connect("tcp://" + host + ":7557")
        self.sub.subscribe("")
        self.on_update = None
        self.sub_packets = 0
        self.sub_thread = threading.Thread(target=lambda: self.sub_process())
        self.sub_thread.start()

        # Informations from referee
        self.referee = None

        # Creating request connection
        self.req = self.context.socket(zmq.REQ)
        self.req.connect("tcp://" + host + ":7558")

        # Waiting for the first packet to be received, guarantees to have robot state after
        # client creation
        dt = 0.05
        t = 0
        warning_showed = False
        while wait_ready and self.sub_packets < 1:
            t += dt
            time.sleep(dt)
            if t > 3 and not warning_showed:
                warning_showed = True
                print("WARNING: Still no message from vision after 3s")
                print("if you want to operate without vision, pass wait_ready=False to the client")

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.stop()

    def update_position(self, tracked, infos):
        tracked.position = np.array(infos["position"])
        tracked.orientation = infos["orientation"]
        tracked.pose = np.array(list(tracked.position) + [tracked.orientation])
        tracked.last_update = time.time()

    def sub_process(self):
        self.sub.RCVTIMEO = 1000
        last_t = time.time()
        while self.running:
            try:
                json = self.sub.recv_json()
                ts = time.time()
                dt = ts - last_t
                last_t = ts

                if "ball" in json:
                    self.ball = None if json["ball"] is None else np.array(json["ball"])

                if "markers" in json:
                    for entry in json["markers"]:
                        team = entry[:-1]
                        number = int(entry[-1])

                        if team == "obj":
                            self.update_position(self.objs[number], json["markers"][entry])
                        else:
                            self.update_position(self.robots[team][number], json["markers"][entry])

                if "referee" in json:
                    self.referee = json["referee"]

                if self.on_update is not None:
                    self.on_update(self, dt)

                self.sub_packets += 1
            except zmq.error.Again:
                pass

    def stop_motion(self):
        for color in self.robots:
            robots = self.robots[color]
            for index in robots:
                if robots[index].moved:
                    try:
                        robots[index].control(0.0, 0.0, 0.0)
                    except ClientError:
                        pass

    def em(self):
        self.stop_motion()

    def stop(self):
        self.stop_motion()
        self.running = False

    def command(self, color, number, name, parameters):
        if threading.current_thread() is threading.main_thread():
            sigint_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        self.lock.acquire()
        self.req.send_json([self.key, color, number, [name, *parameters]])
        success, message = self.req.recv_json()
        self.lock.release()

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, sigint_handler)

        time.sleep(0.01)

        if not success:
            raise ClientError('Command "' + name + '" failed: ' + message)

    def goto_configuration(self, configuration_name="side", wait=False):
        targets = configurations[configuration_name]

        arrived = False
        while not arrived:
            arrived = True
            for color, index, target in targets:
                robot = self.robots[color][index]
                try:
                    arrived = robot.goto(target, wait=wait) and arrived
                except ClientError:
                    pass

        self.stop_motion()
