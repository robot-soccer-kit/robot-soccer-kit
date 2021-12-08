import numpy as np
from serial.tools import list_ports
import time
import math
from . import config, control, robot, utils


class Robots:
    def __init__(self, detection):
        self.detection = detection
        self.robots = {}
        self.robots_by_marker = {}

        self.control = control.Control(self)
        self.control.start()

        if 'robots' in config.config:
            for port, marker in config.config['robots']:
                self.robots[port] = robot.Robot(port)
                if marker != "":
                    self.robots[port].setMarker(marker)
                    self.robots_by_marker[marker] = self.robots[port]

    def identify(self):
        for entry in self.robots:
            before = self.detection.getDetection().copy()
            self.robots[entry].beep(200, 100)
            self.robots[entry].control(0, 0, math.radians(30))
            time.sleep(1)
            self.robots[entry].control(0, 0, 0)
            after = self.detection.getDetection().copy()
            for marker in before['markers']:
                if marker in after['markers']:
                    a = before['markers'][marker]['orientation']
                    b = after['markers'][marker]['orientation']
                    delta = np.rad2deg(utils.angle_wrap(b-a))
                    if delta > 10 and delta < 40:
                        self.setMarker(entry, marker)

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
            if port in self.robots_by_marker:
                self.robots_by_marker[marker].setMarker(None)
            self.robots[port].setMarker(marker)
            self.robots_by_marker[marker] = self.robots[port]
            self.saveConfig()

    def remove(self, port):
        self.robots[port].close()
        del self.robots[port]
        self.saveConfig()

    def stop(self):
        self.control.stop()
        for port in self.robots:
            self.robots[port].close()
