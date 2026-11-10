"""
A robot (base class of the robots of each protocol)
"""


class RobotError(Exception):
    """
    An operation not supported by a robot
    """


from .robots import Robots


class Robot:
    """
    A robot, controlled through a protocol (see the subclasses: RobotWifi, RobotSerial,
    RobotSim). By default, the operations are not supported
    """

    def __init__(self, robots: Robots, url: str):
        # Robots manager
        self.robots = robots

        # Port name
        self.url: str = url

        # Robot state (e.g: battery level)
        self.state: dict = {}

        # Should leds be re-set
        self.leds_dirty: bool = False

        # Timestamp of the last received packet from the robot
        self.last_message = None

        # Marker on the top of this robot
        self.marker = None

    def available_urls() -> list:
        """
        :return list: the urls of the robots that can be added with this protocol
        """
        return []

    def close(self) -> None:
        """
        Stops the communication with the robot (when it is removed)
        """

    def set_marker(self, marker: str) -> None:
        """
        Sets the robot's marker

        :param str marker: the robot marker
        """
        self.marker = marker

    def kick(self, power: float = 1.0) -> None:
        """
        Kicks

        :param float power: kick power (0-1)
        :raises RobotError: if the operation is not supported
        """
        raise RobotError("This robot can't kick")

    def control(self, dx: float, dy: float, dturn: float) -> None:
        """
        Controls the robot velocity

        :param float dx: x axis (robot frame) velocity [m/s]
        :param float dy: y axis (robot frame) velocity [m/s]
        :param float dturn: rotation (robot frame) velocity [rad/s]
        :raises RobotError: if the operation is not supported
        """
        raise RobotError("This robot can't move")

    def leds(self, red: int, green: int, blue: int) -> None:
        """
        Controls the robot LEDs

        :param int red: red brightness (0-255)
        :param int green: green brightness (0-255)
        :param int blue: blue brightness (0-255)
        """
        # Recorded in the state (shown by the interface), sent by the subclasses
        if self.marker is not None:
            self.robots.state.set_leds(self.marker, (red, green, blue))

    def beep(self, frequency: int, duration: int) -> None:
        """
        Gets the robot beeping

        :param int frequency: frequency (Hz)
        :param int duration: duration (ms)
        """
        # Nothing by default (e.g. no buzzer)

    def teleport(self, x: float, y: float, theta: float) -> None:
        """
        Teleports the robot to a given position/orientation

        :param float x: x position [m]
        :param float y: y position [m]
        :param float theta: orientation [rad]
        :raises RobotError: if the operation is not supported
        """
        raise RobotError("This robot can't be teleported")
