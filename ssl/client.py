import numpy as np
import zmq
import threading
import time
from . import field

configurations = {
    'dots': [
        ['red', 1, (field.length/4, -field.width/4, np.pi)],
        ['red', 2, (field.length/4, field.width/4, np.pi)],
        ['blue', 1, (-field.length/4, field.width/4, 0)],
        ['blue', 2, (-field.length/4, -field.width/4, 0)],
    ],

    'game': [
        ['red', 1, (field.length/4, 0, np.pi)],
        ['red', 2, (field.length/2, 0, np.pi)],
        ['blue', 1, (-field.length/4, 0, 0)],
        ['blue', 2, (-field.length/2, 0, 0)],
    ],

    'side': [
        ['red', 1, (0.2, field.width/2, -np.pi/2)],
        ['red', 2, (0.6, field.width/2, -np.pi/2)],
        ['blue', 1, (-0.2, field.width/2, -np.pi/2)],
        ['blue', 2, (-0.6, field.width/2, -np.pi/2)],
    ]
}


def frame(x, y=0, orientation=0):
    if type(x) is tuple:
        x, y, orientation = x

    cos, sin = np.cos(orientation), np.sin(orientation)

    return np.array([[cos, -sin, x],
                     [sin,  cos, y],
                     [0,   0,  1]])


def frame_inv(frame):
    frame_inv = np.eye(3)
    R = frame[:2, :2]
    frame_inv[:2, :2] = R.T
    frame_inv[:2, 2] = -R.T @ frame[:2, 2]
    return frame_inv


def robot_frame(robot):
    pos = robot.position
    return frame(pos[0], pos[1], robot.orientation)


def angle_wrap(alpha):
    return (alpha + np.pi) % (2 * np.pi) - np.pi


class ClientError(Exception):
    pass


class ClientRobot:
    def __init__(self, color, number, client):
        self.color = color
        self.team = color
        self.number = number
        self.client = client

        self.position = None
        self.orientation = None
        self.last_update = None

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
            Ti = frame_inv(robot_frame(self))
            target_in_robot = Ti @ np.array([x, y, 1])

            error_x = target_in_robot[0]
            error_y = target_in_robot[1]
            error_orientation = angle_wrap(orientation - self.orientation)

            self.control(2500*error_x, 2500*error_y, 2.5 *
                         np.rad2deg(error_orientation))

            return np.linalg.norm([error_x, error_y, error_orientation]) < 0.05
        else:
            self.control(0, 0, 0)
            return False


class Client:
    def __init__(self, color='blue', host='127.0.0.1', key=''):
        self.running = True
        self.key = key

        self.color = color
        self.opponent_color = 'red' if color == 'blue' else 'blue'

        self.robots = {
            'red': {
                1: ClientRobot('red', 1, self),
                2: ClientRobot('red', 2, self)
            },
            'blue': {
                1: ClientRobot('blue', 1, self),
                2: ClientRobot('blue', 2, self)
            }
        }

        self.team = {
            1: self.robots[self.color][1],
            2: self.robots[self.color][2],
        }
        self.opponents = {
            1: self.robots[self.opponent_color][1],
            2: self.robots[self.opponent_color][2],
        }
        self.ball = None

        # ZMQ Context
        self.context = zmq.Context()

        # Creating subscriber connection
        self.sub = self.context.socket(zmq.SUB)
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

    def update_robot(self, robot, infos):
        robot.position = infos['position']
        robot.orientation = infos['orientation']
        robot.last_update = time.time()

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

                        self.update_robot(self.robots[team][number], json['markers'][entry])

                if self.on_sub is not None:
                    self.on_sub(self, dt)

                self.sub_packets += 1
            except zmq.error.Again:
                pass

    def stop_motion(self):
        for color in self.robots:
            robots = self.robots[color]
            for index in robots:
                try:
                    robots[index].control(0., 0., 0.)
                except ClientError:
                    pass

    def stop(self):
        self.stop_motion()
        self.running = False

    def command(self, color, number, name, parameters):
        self.req.send_json([self.key, color, number, [name, *parameters]])

        success, message = self.req.recv_json()
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

            time.sleep(0.05)

        self.stop_motion()


if __name__ == '__main__':
    client = Client()

    try:
        while True:
            for color in 'red', 'blue':
                for index in 1, 2:
                    client.robots[color][index].control(100, 0, 0)
                    time.sleep(1)
                    client.robots[color][index].control(-100, 0, 0)
                    time.sleep(1)
                    client.robots[color][index].control(0, 0, 0)
                    client.robots[color][index].kick()
                    time.sleep(1)

            time.sleep(1)
    except KeyboardInterrupt:
        print('Exiting')
    except ClientError as e:
        print('Fatal error: '+str(e))
    finally:
        client.stop()
