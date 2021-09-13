import numpy as np
import zmq
import threading
import time

class ControllerRobot:
    def __init__(self, color, number, controller):
        self.color = color
        self.number = number
        self.controller = controller

        self.position = None
        self.orientation = None
        self.last_update = None

    def age(self):
        if self.last_update is None:
            return None

        return time.time() - self.last_update

    def kick(self, power=1):
        return self.controller.command(self.color, self.number, 'kick', [power])

    def control(self, dx, dy, dturn):
        return self.controller.command(self.color, self.number, 'control', [dx, dy, dturn])

class Controller:
    def __init__(self, color, host='127.0.0.1', key=''):
        self.running = True
        self.context = zmq.Context()
        self.key = key
        self.color = color
        self.opponent_color = 'red' if color == 'blue' else 'blue'
        self.robots = {
            1: ControllerRobot(self.color, 1, self),
            2: ControllerRobot(self.color, 2, self)
        }
        self.opponents = {
            1: ControllerRobot(self.opponent_color, 1, self),
            2: ControllerRobot(self.opponent_color, 2, self)
        }
        self.ball = None

        # Creating subscriber connection
        self.sub = self.context.socket(zmq.SUB)
        self.sub.connect('tcp://'+host+':7557')
        self.sub.subscribe('')
        self.sub_thread = threading.Thread(target=lambda: self.sub_process())
        self.sub_thread.start()

        # Creating request connection
        self.req = self.context.socket(zmq.REQ)
        self.req.connect('tcp://'+host+':7558')

    def update_robot(self, robot, infos):
        robot.position = infos['position']
        robot.orientation = infos['orientation']
        robot.last_update = time.time()

    def sub_process(self):
        self.sub.RCVTIMEO = 1000
        while self.running:
            try:
                json = self.sub.recv_json()
                if 'ball' in json:
                    self.ball = np.array(json['ball'])

                if 'markers' in json:
                    for entry in json['markers']:
                        team = entry[:-1]
                        number = int(entry[-1])

                        if team == self.color:
                            self.update_robot(self.robots[number], json['markers'][entry])
                        else:
                            self.update_robot(self.opponents[number], json['markers'][entry])
            except zmq.error.Again:
                pass

    def command(self, color, number, name, parameters):
        self.req.send_json([self.key, color, number, [name, *parameters]])

        success, message = self.req.recv_json()
        if not success:
            raise Exception('Command "'+name+'" failed: '+message)


if __name__ == '__main__':
    controller = Controller('blue')

    try:
        while True:
            controller.robots[1].control(100, 0, 0)
            time.sleep(1)
            controller.robots[1].control(0, 0, 0)
            controller.robots[1].kick()

            time.sleep(1)
    except KeyboardInterrupt:
        print('Exiting')
    except Exception as e:
        print('Fatal error: '+str(e))
    finally:
        controller.running = False
