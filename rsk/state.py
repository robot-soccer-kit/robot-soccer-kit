import zmq
import time


class State:
    def __init__(self, simulated=False):
        """Summary

        Args:
            frequency_pub (int, optional): publication frequency [Hz]
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
        return {
            "markers": self.markers,
            "ball": self.ball,
            "referee": self.referee,
            "leds": self.leds,
            "simulated": self.simulated,
        }

    def start_pub(self):
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
        self.socket.send_json(info, flags=zmq.NOBLOCK)

    def set_markers(self, markers):
        self.markers = markers
        for marker in markers:
            self.last_updates[marker] = time.time()

    def set_leds(self, marker, leds):
        self.leds[marker] = leds

    def set_marker(self, marker, position, orientation):
        if marker not in self.markers:
            self.markers[marker] = {"position": position, "orientation": orientation}
        else:
            self.markers[marker]["position"] = position
            self.markers[marker]["orientation"] = orientation
        self.last_updates[marker] = time.time()

    def set_ball(self, position):
        self.ball = position

    def set_referee(self, referee):
        self.referee = referee
