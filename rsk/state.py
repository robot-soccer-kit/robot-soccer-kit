"""
State of the game (positions of the markers and the ball, LEDs, referee), published by the Game
Controller to the clients (ZMQ, port 7557)
"""

import zmq
import time
from . import replay_logger


class State:
    """
    State of the game: positions of the markers {marker: {"position": [x, y] [m],
    "orientation": [rad]}} and of the ball [x, y] [m], LEDs of the robots and referee information
    """

    def __init__(self, simulated=False):
        """
        :param bool simulated: whether the positions come from the simulator (sent to the
            clients)
        """
        self.markers: dict = {}
        self.ball = None
        self.last_updates: dict = {}
        self.referee: dict = {}
        self.simulated = simulated

        self.context = None
        self.last_time = None
        self.leds: dict = {}

    def get_state(self):
        """
        :return dict: the state, as published
        """
        return {
            "markers": self.markers,
            "ball": self.ball,
            "referee": self.referee,
            "leds": self.leds,
            "simulated": self.simulated,
        }

    def start_pub(self):
        """
        Starts the publication server (binds the port 7557)
        """
        # Publishing server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.set_hwm(1)
        self.socket.bind("tcp://*:7557")
        self.last_pub = time.time()

    def publish(self) -> None:
        """
        Publish the detection informations on the network
        """
        self.last_time = time.time()
        info = self.get_state()

        # Log position frame with unified timestamp and detected markers/ball
        replay_logger.register_position_frame(info["markers"], info["ball"])

        # Log LED states (separate from positions)
        replay_logger.register_infos(info["leds"].keys(), info["leds"], "leds_state")

        # Publish to ZMQ
        self.socket.send_json(info, flags=zmq.NOBLOCK)

    def set_markers(self, markers):
        """
        Sets the positions of all the markers (seen by the vision)
        """
        self.markers = markers
        for marker in markers:
            self.last_updates[marker] = time.time()

    def set_leds(self, marker, leds):
        """
        Sets the LEDs color (r, g, b) of a robot
        """
        self.leds[marker] = leds

    def set_marker(self, marker, position, orientation):
        """
        Sets the position [x, y] [m] and orientation [rad] of a marker
        """
        if marker not in self.markers:
            self.markers[marker] = {"position": position, "orientation": orientation}
        else:
            self.markers[marker]["position"] = position
            self.markers[marker]["orientation"] = orientation
        self.last_updates[marker] = time.time()

    def set_ball(self, position):
        """
        Sets the position [x, y] [m] of the ball (None if it is not seen)
        """
        self.ball = position

    def set_referee(self, referee):
        """
        Sets the referee information (game state)
        """
        self.referee = referee
