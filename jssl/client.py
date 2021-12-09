import signal
import numpy as np
import zmq
import threading
import time
from . import field_dimensions, utils

configurations = {
    'dots': [
        ['red', 1, (field_dimensions.length/4, -field_dimensions.width/4, np.pi)],
        ['red', 2, (field_dimensions.length/4, field_dimensions.width/4, np.pi)],
        ['blue', 1, (-field_dimensions.length/4, field_dimensions.width/4, 0)],
        ['blue', 2, (-field_dimensions.length/4, -field_dimensions.width/4, 0)],
    ],

    'game': [
        ['red', 1, (field_dimensions.length/4, 0, np.pi)],
        ['red', 2, (field_dimensions.length/2, 0, np.pi)],
        ['blue', 1, (-field_dimensions.length/4, 0, 0)],
        ['blue', 2, (-field_dimensions.length/2, 0, 0)],
    ],

    'side': [
        ['red', 1, (0.2, field_dimensions.width/2, -np.pi/2)],
        ['red', 2, (0.6, field_dimensions.width/2, -np.pi/2)],
        ['blue', 1, (-0.2, field_dimensions.width/2, -np.pi/2)],
        ['blue', 2, (-0.6, field_dimensions.width/2, -np.pi/2)],
    ]
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

        self.x_max = field_dimensions.length/2 + field_dimensions.border_size/2.
        self.x_min = -self.x_max
        self.y_max = field_dimensions.width/2 + field_dimensions.border_size/2.
        self.y_min = -self.y_max

    def ball(self):
        return self.client.ball

    def has_position(self):
        return (self.position is not None) and (self.orientation is not None) and self.age() < 1

    def age(self):
        if self.last_update is None:
            return None

        return time.time() - self.last_update

    def kick(self, power=1):
        return self.client.command(self.color, self.number, 'kick', [power])

    def control(self, dx, dy, dturn):
        self.moved = True

        return self.client.command(self.color, self.number, 'control', [dx, dy, dturn])

    def goto(self, target, wait=True):
        if wait:
            while not self.goto(target, wait=False):
                time.sleep(0.05)
            self.control(0, 0, 0)
            return True

        if self.has_position():
            if callable(target):
                target = target()

            x, y, orientation = target
            x = min(self.x_max, max(self.x_min, x))
            y = min(self.y_max, max(self.y_min, y))
            Ti = utils.frame_inv(utils.robot_frame(self))
            target_in_robot = Ti @ np.array([x, y, 1])

            error_x = target_in_robot[0]
            error_y = target_in_robot[1]
            error_orientation = utils.angle_wrap(
                orientation - self.orientation)

            self.control(1.5*error_x, 1.5*error_y, 1.5*error_orientation)

            return np.linalg.norm([error_x, error_y, error_orientation]) < 0.05
        else:
            self.control(0, 0, 0)
            return False


class Client:
    def __init__(self, host='127.0.0.1', key=''):
        self.running = True
        self.key = key
        self.lock = threading.Lock()

        self.red1 = ClientRobot('red', 1, self)
        self.red2 = ClientRobot('red', 2, self)
        self.blue1 = ClientRobot('blue', 1, self)
        self.blue2 = ClientRobot('blue', 2, self)

        self.robots = {
            'red': {
                1: self.red1,
                2: self.red2,
            },
            'blue': {
                1: self.blue1,
                2: self.blue2,
            }
        }

        # Custom objects to track
        self.objs = {n: ClientTracked() for n in range(1, 9)}

        self.ball = None

        # ZMQ Context
        self.context = zmq.Context()

        # Creating subscriber connection
        self.sub = self.context.socket(zmq.SUB)
        self.sub.set_hwm(1)
        self.sub.connect('tcp://'+host+':7557')
        self.sub.subscribe('')
        self.on_sub = None
        self.sub_packets = 0
        self.sub_thread = threading.Thread(target=lambda: self.sub_process())
        self.sub_thread.start()

        # Creating request connection
        self.req = self.context.socket(zmq.REQ)
        self.req.connect('tcp://'+host+':7558')

        # Waiting for the first packet to be received, guarantees to have robot state after
        # client creation
        while self.sub_packets < 1:
            time.sleep(0.05)

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.stop()

    def update_position(self, tracked, infos):
        tracked.position = np.array(infos['position'])
        tracked.orientation = infos['orientation']
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

                if 'ball' in json:
                    self.ball = None if json['ball'] is None else np.array(
                        json['ball'])

                if 'markers' in json:
                    for entry in json['markers']:
                        team = entry[:-1]
                        number = int(entry[-1])

                        if team == 'obj':
                            self.update_position(
                                self.objs[number], json['markers'][entry])
                        else:
                            self.update_position(
                                self.robots[team][number], json['markers'][entry])

                if self.on_sub is not None:
                    self.on_sub(self, dt)

                self.sub_packets += 1
            except zmq.error.Again:
                pass

    def stop_motion(self):
        for color in self.robots:
            robots = self.robots[color]
            for index in robots:
                if robots[index].moved:
                    try:
                        robots[index].control(0., 0., 0.)
                    except ClientError:
                        pass

    def em(self):
        self.stop_motion()

    def stop(self):
        self.stop_motion()
        self.running = False

    def command(self, color, number, name, parameters):
        sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.lock.acquire()
        self.req.send_json([self.key, color, number, [name, *parameters]])
        success, message = self.req.recv_json()
        self.lock.release()
        signal.signal(signal.SIGINT, sigint_handler)

        time.sleep(0.01)

        if not success:
            raise ClientError('Command "'+name+'" failed: '+message)

    def goto_configuration(self, configuration_name='side'):
        targets = configurations[configuration_name]

        arrived = False
        while not arrived:
            arrived = True
            for color, index, target in targets:
                robot = self.robots[color][index]
                try:
                    arrived = robot.goto(target, wait=False) and arrived
                except ClientError:
                    pass

        self.stop_motion()
