import zmq
import time


class State:
    def __init__(self, frequency_pub=30, simulated=False):
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
        self.frequency_pub = frequency_pub
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

    def publish(self) -> None:
        """
        Publish the detection informations on the network
        """
        info = self.get_state()
        self.socket.send_json(info, flags=zmq.NOBLOCK)

    def _refresh(function):
        def inner_publish(self, *args, **kwargs):
            function(self, *args, **kwargs)

            if self.context is not None:
                if self.last_time is None or (time.time() - self.last_time) > (1 / self.frequency_pub):
                    self.last_time = time.time()
                    self.publish()

        return inner_publish

    @_refresh
    def set_markers(self, markers):
        self.markers = markers
        for marker in markers:
            self.last_updates[marker] = time.time()

    @_refresh
    def set_leds(self, marker, leds):
        self.leds[marker] = leds

    @_refresh
    def set_marker(self, marker, position, orientation):
        if marker not in self.markers:
            self.markers[marker] = {"position": position, "orientation": orientation}
        else:
            self.markers[marker]["position"] = position
            self.markers[marker]["orientation"] = orientation
        self.last_updates[marker] = time.time()

    @_refresh
    def set_ball(self, position):
        self.ball = position

    @_refresh
    def set_referee(self, referee):
        self.referee = referee
