from serial.tools import list_ports
import time
import robot
import control
import config


class Robots:
    def __init__(self, detection):
        self.detection = detection
        self.robots = {}
        self.robots_by_marker = {}

        self.control = control.Control(self)
        self.control.start()

        for port, marker in config.config['robots']:
            self.robots[port] = robot.Robot(port, marker)
            if marker is not None:
                self.robots_by_marker[marker] = self.robots[port]

    def ports(self):
        return [entry.device for entry in list_ports.comports()]

    def saveConfig(self):
        config.config['robots'] = []
        for port in self.robots:
            config.config['robots'].append([port, self.robots[port].marker])
        config.save()
        
    def addRobot(self, port):
        if port not in self.robots:
            self.robots[port] = robot.Robot(port)
            self.saveConfig()

    def getRobots(self):
        data = {}
        for entry in self.robots:
            last_detection = None
            if self.robots[entry].marker in self.detection.last_updates:
                last_detection = time.time() - \
                    self.detection.last_updates[self.robots[entry].marker]

            data[entry] = {
                'state': self.robots[entry].state,
                'marker': self.robots[entry].marker,
                'last_detection': last_detection,
                'last_message': time.time() - self.robots[entry].last_message if self.robots[entry].last_message is not None else None
            }

        return data

    def setMarker(self, port, marker):
        if port in self.robots:
            self.robots[port].setMarker(marker)
            self.robots_by_marker[marker] = self.robots[port]
            self.saveConfig()

    def remove(self, port):
        self.robots[port].close()
        del self.robots[port]
        self.saveConfig()
