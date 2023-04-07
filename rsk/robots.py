import numpy as np
import time
import copy
import math
import logging
from . import config, control, robot, utils, state


class Robots:
    """
    This class contains the instance of robots, each of them being a separate connection to a
    physical robot.
    """

    def __init__(self, state=None):
        self.logger: logging.Logger = logging.getLogger("robots")

        self.state: state.State = state

        # Robots (indexed by urls)
        self.robots: dict = {}

        # Robots (indexed by marker strings)
        self.robots_by_marker: dict = {}

    def load_config(self) -> None:
        # Loading robots from the configuration
        if "robots" in config.config:
            for url, marker in config.config["robots"]:
                config_robot = self.add_robot(url)
                if config_robot and marker != "":
                    config_robot.set_marker(marker)

        self.update()

    # Registered protocols
    protocols: dict = {}

    def update(self):
        """
        Updates robots_by_marker for it to be consistent with robots
        """
        new_robots_by_marker = {}
        for url in self.robots:
            if self.robots[url].marker is not None:
                new_robots_by_marker[self.robots[url].marker] = self.robots[url]
        self.robots_by_marker = new_robots_by_marker

    def should_restore_leds(self, robot: str) -> bool:
        """
        Checking if a robot should have its LEDs resetted

        :param str robot: robot name
        :return bool: True if the LEDs should be restored
        """
        if robot in self.robots_by_marker and self.robots_by_marker[robot].leds_dirty:
            self.robots_by_marker[robot].leds_dirty = False
            return True

        return False

    def identify(self):
        """
        Starts the identification procedure, to detect markers on the top of each robots
        """
        for url in self.robots:
            self.logger.info(f"Identifying {url}...")
            # Detection before the robot moves
            before = copy.deepcopy(self.state.get_state())["markers"]
            after = copy.deepcopy(before)

            # Makes the robot rotating at 50°/s for 1s
            self.set_marker(url, None)
            self.robots[url].beep(200, 100)
            self.robots[url].control(0, 0, math.radians(50))
            for _ in range(100):
                markers = copy.deepcopy(self.state.get_state())["markers"]
                before = {**markers, **before}
                after = {**after, **markers}
                time.sleep(0.01)
            self.robots[url].control(0, 0, 0)

            # We assign the marker to the robot that moved
            for marker in before:
                a = before[marker]["orientation"]
                b = after[marker]["orientation"]
                delta = np.rad2deg(utils.angle_wrap(b - a))

                self.logger.info(f"marker={marker}, url={url}, delta={delta}")
                if delta > 25 and delta < 90:
                    logging.info(f"Identified robot {url} to be {marker}")
                    self.set_marker(url, marker)

    def available_urls(self) -> list:
        """
        Retrieve a list of available URLs

        :return list: a list of (str) urls
        """
        urls: list = []
        for protocol in self.protocols:
            urls += [f"{protocol}://{url}" for url in self.protocols[protocol].available_urls()]

        return urls

    def save_config(self) -> None:
        """
        Save the configuration file
        """
        config.config["robots"] = []
        for url in self.robots:
            config.config["robots"].append([url, self.robots[url].marker])
        config.save()

    def add_robot(self, full_url: str):
        """
        Adds an url to the robots list

        :param str url: the robot's url
        """
        if full_url not in self.robots:
            result = full_url.split("://", 1)
            if len(result) == 2:
                protocol, url = result
                if protocol in self.protocols:
                    self.robots[full_url] = self.protocols[protocol](url)
                    self.save_config()
                    return self.robots[full_url]
                else:
                    print(f'Unknown protocol: {protocol} in robot URL "{full_url}"')
            else:
                print(f"Bad url: {full_url}")

        return None

    def get_robots(self) -> dict:
        """
        Gets robots informations.

        :return dict: information about robots
        """
        data = {}
        for entry in self.robots:
            last_detection = None
            if self.robots[entry].marker in self.state.last_updates:
                last_detection = time.time() - self.state.last_updates[self.robots[entry].marker]

            data[entry] = {
                "state": self.robots[entry].state,
                "marker": self.robots[entry].marker,
                "last_detection": last_detection,
                "last_message": time.time() - self.robots[entry].last_message
                if self.robots[entry].last_message is not None
                else None,
            }

        return data

    def set_marker(self, url: str, marker: str) -> None:
        """
        Sets the marker for a robot on a given url

        :param str url: the url
        :param str marker: the marker
        """
        if url in self.robots:
            self.robots[url].set_marker(marker)
            self.save_config()
            self.update()

    def remove(self, url: str) -> None:
        """
        Removes a url from

        :param str url: the url
        """
        if url in self.robots:
            self.robots[url].close()
            del self.robots[url]
            self.save_config()
            self.update()

    def stop(self):
        """
        Stops execution and closes all the connections
        """
        self.control.stop()
        for url in self.robots:
            self.robots[url].close()
