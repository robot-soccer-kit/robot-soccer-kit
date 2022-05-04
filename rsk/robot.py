import numpy as np
import threading
import time
import serial
import logging

# Constants for binary protocol
PACKET_ACK = 0
PACKET_MONITOR = 1
PACKET_HOLO = 80
PACKET_HOLO_CONTROL = 2
PACKET_HOLO_BEEP = 3
PACKET_HOLO_LEDS_CUSTOM = 7
PACKET_HOLO_LEDS_BREATH = 8
PACKET_HOLO_KICK = 12
PACKET_MONITOR_DATA = 5

logger: logging.Logger = logging.getLogger("robot")


class Packet:
    """
    Represents a physical packet that is sent or received (binary protocol)
    """

    def __init__(self, type_: int, payload=bytearray()):
        self.type: int = type_
        self.payload = payload.copy()

    def available(self):
        return len(self.payload)

    def append_byte(self, char):
        if type(char) == int:
            self.payload += bytearray((char,))
        else:
            self.payload += bytearray(char)

    def append_short(self, short):
        b1 = (short >> 8) & 0xFF
        b2 = short & 0xFF

        self.payload += bytearray((b1, b2))

    def append_int(self, short):
        b1 = (short >> 24) & 0xFF
        b2 = (short >> 16) & 0xFF
        b3 = (short >> 8) & 0xFF
        b4 = short & 0xFF

        self.payload += bytearray((b1, b2, b3, b4))

    def appendFloat(self, f):
        self.append_int(f * 1000.0)

    def appendSmallFloat(self, f):
        self.append_short(f * 10.0)

    def readByte(self):
        byte = self.payload[0]
        self.payload = self.payload[1:]

        return byte

    def read_int(self):
        n = self.readByte() << 24
        n = n | (self.readByte() << 16)
        n = n | (self.readByte() << 8)
        n = n | (self.readByte() << 0)

        return int(np.int32(n))

    def read_short(self):
        n = (self.readByte() << 8) | self.readByte()

        return int(np.int16(n))

    def read_float(self):
        return self.read_int() / 1000.0

    def read_small_float(self):
        return self.read_short() / 10.0

    def to_raw(self):
        raw = bytearray()
        raw += bytearray((0xFF, 0xAA, self.type, len(self.payload)))
        raw += self.payload
        raw += bytearray((self.checksum(),))

        return raw

    def checksum(self):
        return sum(self.payload) % 256


class Robot:
    """
    Connection with a physical robot
    """

    def __init__(self, port: str):
        # Port name
        self.port: str = port
        # Instance of serial connection
        self.bt = None
        # Is the connection initialized ?
        self.init: bool = True
        # Is the thread running ?
        self.running: bool = True
        # Last message timestamps
        self.last_message = None
        self.last_sent_message = None
        # Last initialization tinestamp
        self.last_init = None
        # State retrieved from the packets
        self.state = {}
        # Marker on the top of this robot
        self.marker = None
        # Should leds be re-set
        self.leds_dirty: bool = False

        # Starting the threads
        self.thread = threading.Thread(target=lambda: self.run_thread())
        self.thread.start()

        # Pending packets queued
        self.pending_packets = {}
        self.lock = threading.Lock()

    def monitor(self, frequency: int) -> None:
        """
        Send a monitor command to the robot

        :param int frequency: monitor frequency (Hz)
        """
        packet = Packet(PACKET_MONITOR)
        packet.append_int(frequency)
        self.add_packet("monitor", packet)

    def blink(self) -> None:
        """
        Gets the robot blinking for a while
        """
        for _ in range(5):
            self.leds(255, 255, 255)
            time.sleep(0.25)
            self.leds(0, 0, 0)
            time.sleep(0.25)
        self.leds_dirty = True

    def set_marker(self, marker: str) -> None:
        """
        Sets the robot's marker

        :param str marker: the robot marker
        """
        self.marker = marker

    def process(self, packet: Packet) -> None:
        """
        Processes a packet

        :param Packet packet: packet to process
        """
        if packet.type == PACKET_MONITOR_DATA:
            self.last_message = time.time()
            state = {}
            version = packet.readByte()
            state["version"] = version

            if version == 11:
                # Version 11, old robots
                state["time"] = packet.read_float()
                state["distance"] = packet.read_small_float()
                state["optics"] = [packet.readByte() for optic in range(7)]
                state["wheels"] = [packet.read_small_float() for w in range(3)]
                state["yaw"] = packet.read_small_float()
                state["gyro_yaw"] = packet.read_small_float()
                state["pitch"] = packet.read_small_float()
                state["roll"] = packet.read_small_float()
                state["odometry"] = {
                    "x": packet.read_short() / 1000.0,
                    "y": packet.read_short() / 1000.0,
                    "yaw": packet.read_small_float(),
                }
                state["battery"] = [packet.readByte() / 40.0, packet.readByte() / 40.0]

            elif version == 2:
                # Version 2, new robots
                state["time"] = packet.read_float()
                state["battery"] = [packet.readByte() / 10.0]
            else:
                logger.error(f"Unknown firmware version {version}")
            self.state = state

    def add_packet(self, name: str, packet: Packet) -> None:
        """
        Adds a packet to the pending packets

        :param str name: the name of the packet, if such a name is in used, it will be overwritten
        :param Packet packet: packet to send
        """
        self.lock.acquire()
        self.pending_packets[name] = packet
        self.lock.release()

    def pop_packet(self):
        """
        Gets the next pending packet to be sent if any

        :return Packet|None: a packet, or None
        """
        packet = None

        self.lock.acquire()
        if len(self.pending_packets) > 0:
            name = next(iter(self.pending_packets))
            packet = self.pending_packets[name]
            del self.pending_packets[name]
        self.lock.release()

        return packet

    def beep(self, frequency: int, duration: int):
        """
        Gets the robot beeping

        :param int frequency: frequency (Hz)
        :param int duration: duration (ms)
        """
        packet = Packet(PACKET_HOLO)
        packet.append_byte(PACKET_HOLO_BEEP)
        packet.append_short(frequency)
        packet.append_short(duration)
        self.add_packet("beep", packet)

    def kick(self, power: float = 1.0):
        """
        Gets the robot kicking

        :param float power: kick intensity (0 to 1), defaults to 1.
        """
        packet = Packet(PACKET_HOLO)
        packet.append_byte(PACKET_HOLO_KICK)
        packet.append_byte(int(100 * power))
        self.add_packet("kick", packet)

    def control(self, dx: float, dy: float, dturn: float):
        """
        Sends some chassis speed order fo the robot

        :param float dx: x speed (m/s)
        :param float dy: y speed (m/s)
        :param float dturn: rotational speed (rad/s)
        """
        packet = Packet(PACKET_HOLO)
        packet.append_byte(PACKET_HOLO_CONTROL)
        packet.append_short(int(1000 * dx))
        packet.append_short(int(1000 * dy))
        packet.append_short(int(np.rad2deg(dturn)))
        self.add_packet("control", packet)

    def leds(self, r: int, g: int, b: int):
        """
        Sets the robot LEDs

        :param int r: R intensity (0-255)
        :param int g: G intensity (0-255)
        :param int b: B intensity (0-255)
        """
        packet = Packet(PACKET_HOLO)
        packet.append_byte(PACKET_HOLO_LEDS_CUSTOM)
        packet.append_byte(r)
        packet.append_byte(g)
        packet.append_byte(b)
        self.add_packet("leds", packet)

    def stop(self):
        """
        Stops the robot from moving
        """
        self.control(0, 0, 0)

    def close(self):
        """
        Stops the robot's thread
        """
        self.running = False

    def run_thread(self):
        """
        Process the main thread
        """
        while self.running:
            try:
                if self.init:
                    logger.info(f"Opening connection with {self.port}")
                    self.init = False
                    if self.bt is not None:
                        self.bt.close()
                        self.bt = None
                    self.bt = serial.Serial(self.port, timeout=0.02)
                    time.sleep(0.1)
                    self.bt.write(b"rhock\r\nrhock\r\nrhock\r\n")
                    time.sleep(0.1)
                    self.monitor(5)
                    self.control(0, 0, 0)
                    self.beep(880, 250)
                    self.last_init = time.time()
                    self.last_sent_message = None
                    state = 0
                    type_, length, payload = 0, 0, bytearray()

                # Receiving data
                byte = self.bt.read(1)
                if len(byte):
                    byte = ord(byte)
                    if state == 0:  # First header
                        if byte == 0xFF:
                            state += 1
                        else:
                            state = 0
                    elif state == 1:  # Second header
                        if byte == 0xAA:
                            state += 1
                        else:
                            state = 0
                    elif state == 2:  # Packet type
                        type_ = byte
                        state += 1
                    elif state == 3:  # Packet length
                        length = byte
                        state += 1
                    elif state == 4:  # Payload
                        payload += bytearray((byte,))
                        if len(payload) >= length:
                            state += 1
                    elif state == 5:  # Checksum
                        if sum(payload) % 256 == byte:
                            self.process(Packet(type_, payload))
                            type_, length, payload = 0, 0, bytearray()
                        state = 0

                # Asking periodically for robot monitor status
                if self.last_sent_message is None or time.time() - self.last_sent_message > 1.0:
                    self.monitor(1)

                # Sending pending packets
                packet = self.pop_packet()
                while packet is not None:
                    self.last_sent_message = time.time()
                    self.last_sent_message = time.time()
                    if self.bt is not None and self.bt.is_open:
                        self.bt.write(packet.to_raw())
                    packet = self.pop_packet()

            except (OSError, serial.serialutil.SerialException) as e:
                # In case of exception, we re-init the connection
                logger.error(f"Error: {e}")

                if "FileNotFoundError" in str(e):
                    time.sleep(1.0)

                self.init = True

            # If we didn't receive a message for more than 5s, we re-init the connection
            no_message = (self.last_message is None) or (time.time() - self.last_message > 5)

            if self.last_init is None:
                old_init = False
            else:
                old_init = time.time() - self.last_init > 5

            if no_message and old_init:
                self.init = True

        if self.bt is not None:
            self.bt.close()


if __name__ == "__main__":
    r = Robot("/dev/rfcomm0")

    while True:
        print(r.state)
        time.sleep(5)
