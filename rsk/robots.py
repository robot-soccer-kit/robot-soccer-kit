import numpy as np
from serial.tools import list_ports
import time
import math
import logging
from . import config, control, robot, utils, detection


class Robots:
    """
    This class contains the instance of robots, each of them being a separate connection to a
    physical robot.
    """

    def __init__(self, detection: detection.Detection):
        self.logger: logging.Logger = logging.getLogger("robots")

        self.detection: detection.Detection = detection

        # Robots (indexed by physical port)
        self.robots: dict = {}
        # Robots (indexed by marker strings)
        self.robots_by_marker: dict = {}

        self.control = control.Control(self)
        self.control.start()

        # Loading robots from the configuration
        if "robots" in config.config:
            for port, marker in config.config["robots"]:
                self.robots[port] = robot.Robot(port)
                if marker != "":
                    self.robots[port].set_marker(marker)

        self.update()

    def update(self):
        """
        Updates robots_by_marker for it to be consistent with robots
        """
        new_robots_by_marker = {}
        for port in self.robots:
            if self.robots[port].marker is not None:
                new_robots_by_marker[self.robots[port].marker] = self.robots[port]
        self.robots_by_marker = new_robots_by_marker

    def identify(self):
        """
        Starts the identification procedure, to detect markers on the top of each robots
        """
        for port in self.robots:
            # Detection before the robot moves
            before = self.detection.get_detection().copy()

            # Makes the robot rotating at 50°/s for 1s
            self.set_marker(port, None)
            self.robots[port].beep(200, 100)
            self.robots[port].control(0, 0, math.radians(50))
            time.sleep(1)
            self.robots[port].control(0, 0, 0)
            after = self.detection.get_detection().copy()

            # We assign the marker to the robot that moved
            for marker in before["markers"]:
                if marker in after["markers"]:
                    a = before["markers"][marker]["orientation"]
                    b = after["markers"][marker]["orientation"]
                    delta = np.rad2deg(utils.angle_wrap(b - a))
                    if delta > 25 and delta < 90:
                        logging.info(f"Identified port {port} to be {marker}")
                        self.set_marker(port, marker)

    def ports(self) -> list:
        """
        Retrieve a list of physical ports available

        :return list: a list of (str) com ports
        """
        return [entry.device for entry in list_ports.comports()]

    def save_config(self) -> None:
        """
        Save the configuration file
        """
        config.config["robots"] = []
        for port in self.robots:
            config.config["robots"].append([port, self.robots[port].marker])
        config.save()

    def add_robot(self, port: str) -> None:
        """
        Adds a port to the robots list

        :param str port: the port name
        """
        if port not in self.robots:
            self.robots[port] = robot.Robot(port)
            self.save_config()

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

    def set_marker(self, port: str, marker: str) -> None:
        """
        Sets the marker for a robot on a given port

        :param str port: the port name
        :param str marker: the marker
        """
        if port in self.robots:
            self.robots[port].set_marker(marker)
            self.save_config()
            self.update()

    def remove(self, port: str) -> None:
        """
        Removes a port from

        :param str port: the port name
        """
        self.robots[port].close()
        del self.robots[port]
        self.save_config()
        self.update()

    def stop(self):
        """
        Stops execution and closes all the ports
        """
        self.control.stop()
        for port in self.robots:
            self.robots[port].close()
