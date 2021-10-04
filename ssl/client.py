import numpy as np
import zmq
import threading
import time

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

class Client:
    def __init__(self, color='blue', host='127.0.0.1', key=''):
        self.running = True
        self.key = key

        self.color = color
        self.opponent_color = 'red' if color == 'blue' else 'blue'

        self.teams = {
            'red': {
                1: ClientRobot('red', 1, self),
                2: ClientRobot('red', 2, self)
            },
            'blue': {
                1: ClientRobot('blue', 1, self),
                2: ClientRobot('blue', 2, self)
            }
        }

        self.robots = {
            1: self.teams[self.color][1],
            2: self.teams[self.color][2],
        }
        self.opponents = {
            1: self.teams[self.opponent_color][1],
            2: self.teams[self.opponent_color][2],
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
                    self.ball = None if json['ball'] is None else np.array(json['ball'])

                if 'markers' in json:
                    for entry in json['markers']:
                        team = entry[:-1]
                        number = int(entry[-1])

                        if team == self.color:
                            self.update_robot(self.robots[number], json['markers'][entry])
                        else:
                            self.update_robot(self.opponents[number], json['markers'][entry])

                if self.on_sub is not None:
                    self.on_sub(self, dt)

                self.sub_packets += 1
            except zmq.error.Again:
                pass
    
    def stop(self):
        for color in self.teams:
            robots = self.teams[color]
            for index in robots:
                try:
                    robots[index].control(0., 0., 0.)
                except ControlError:
                    pass
        self.running = False

    def command(self, color, number, name, parameters):
        self.req.send_json([self.key, color, number, [name, *parameters]])

        success, message = self.req.recv_json()
        if not success:
            raise ControlError('Command "'+name+'" failed: '+message)

if __name__ == '__main__':
    client = Client()

    try:
        while True:
            for color in 'red', 'blue':
                for index in 1, 2:
                    client.teams[color][index].control(100, 0, 0)
                    time.sleep(1)
                    client.teams[color][index].control(-100, 0, 0)
                    time.sleep(1)
                    client.teams[color][index].control(0, 0, 0)
                    client.teams[color][index].kick()
                    time.sleep(1)

            time.sleep(1)
    except KeyboardInterrupt:
        print('Exiting')
    except ClientError as e:
        print('Fatal error: '+str(e))
    finally:
        client.stop()
