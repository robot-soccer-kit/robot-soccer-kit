import numpy as np

# Constants for binary protocol
PACKET_ACK = 0
PACKET_MONITOR = 1
PACKET_HEARTBEAT = 7
PACKET_ROBOT = 80
PACKET_ROBOT_CONTROL = 2
PACKET_ROBOT_BEEP = 3
PACKET_ROBOT_LEDS_CUSTOM = 7
PACKET_ROBOT_LEDS_BREATH = 8
PACKET_ROBOT_KICK = 12
PACKET_MONITOR_DATA = 5


def encode_control(dx: float, dy: float, dturn: float) -> tuple:
    """
    Values sent to the robot for a control order. They are truncated (toward zero) to integers:
    [mm/s], [mm/s] and [deg/s]

    :param float dx: x speed [m/s]
    :param float dy: y speed [m/s]
    :param float dturn: rotation speed [rad/s]
    :return tuple: the integer values sent to the robot
    """
    return int(1000 * dx), int(1000 * dy), int(np.rad2deg(dturn))


def decode_control(dx: int, dy: int, dturn: int) -> tuple:
    """
    Decodes the control order values, as the robot firmware does

    :param int dx: x speed [mm/s]
    :param int dy: y speed [mm/s]
    :param int dturn: rotation speed [deg/s]
    :return tuple: (dx [m/s], dy [m/s], dturn [rad/s])
    """
    return dx / 1000.0, dy / 1000.0, float(np.deg2rad(dturn))


class Packet:
    """
    Represents a physical packet that is sent or received (binary protocol)
    """

    def __init__(self, type_: int, payload=bytearray(), dest=None):
        self.type: int = type_
        self.payload = payload.copy()
        self.dest = dest

    def available(self):
        return len(self.payload)

    def append_byte(self, char):
        char = char & 0xFF
        if type(char) is int:
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

        # Two's complement (signed 32 bits)
        return n - (1 << 32) if n & (1 << 31) else n

    def read_short(self):
        n = (self.readByte() << 8) | self.readByte()

        # Two's complement (signed 16 bits)
        return n - (1 << 16) if n & (1 << 15) else n

    def read_float(self):
        return self.read_int() / 1000.0

    def read_small_float(self):
        return self.read_short() / 10.0

    def to_raw(self):
        raw = bytearray()
        raw += bytearray((0xFF, 0xAA))
        if self.dest is not None:
            raw += bytearray((self.dest,))
        raw += bytearray((self.type, len(self.payload)))
        raw += self.payload
        raw += bytearray((self.checksum(),))

        return raw

    def checksum(self):
        return sum(self.payload) % 256


class PacketReader:
    def __init__(self, dest=None):
        self.reset()
        self.packets = []
        self.dest = dest

        self.STATE_HEADER1 = 0
        self.STATE_HEADER2 = 1

        if dest is not None:
            self.STATE_DEST = 2
            self.STATE_TYPE = 3
            self.STATE_SIZE = 4
            self.STATE_DATA = 5
            self.STATE_CHECKSUM = 6
        else:
            self.STATE_TYPE = 2
            self.STATE_SIZE = 3
            self.STATE_DATA = 4
            self.STATE_CHECKSUM = 5

    def reset(self):
        self.state = 0
        self.type_, self.length, self.packet_dest, self.payload = (
            0,
            0,
            None,
            bytearray(),
        )

    def push(self, byte: int):
        if self.state == self.STATE_HEADER1:  # First header
            if byte == 0xFF:
                self.state += 1
            else:
                self.state = self.STATE_HEADER1
        elif self.state == self.STATE_HEADER2:  # Second header
            if byte == 0xAA:
                self.state += 1
            else:
                self.state = self.STATE_HEADER1
        elif self.dest is not None and self.state == self.STATE_DEST:  # Destination
            self.packet_dest = byte
            self.state += 1
        elif self.state == self.STATE_TYPE:  # Packet type
            self.type_ = byte
            self.state += 1
        elif self.state == self.STATE_SIZE:  # Packet length
            self.length = byte
            self.state += 1
        elif self.state == self.STATE_DATA:  # Payload
            self.payload += bytearray((byte,))
            if len(self.payload) >= self.length:
                self.state += 1
        elif self.state == self.STATE_CHECKSUM:  # Checksum
            if sum(self.payload) % 256 == byte and self.dest == self.packet_dest:
                self.packets.append(Packet(self.type_, self.payload))
                self.reset()
            self.state = self.STATE_HEADER1

    def has_packet(self):
        return len(self.packets) > 0

    def pop_packet(self) -> Packet:
        return self.packets.pop(0)
