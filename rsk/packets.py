"""
Binary protocol with the robots (as implemented by their firmware): packets
0xFF 0xAA [destination] type size payload checksum
"""

import numpy as np

# Types of the packets
PACKET_ACK = 0
PACKET_MONITOR = 1
PACKET_HEARTBEAT = 7
PACKET_ROBOT = 80
PACKET_MONITOR_DATA = 5

# Commands to the robots: first byte of the payload of a PACKET_ROBOT packet (they can have the
# same values as the packet types)
PACKET_ROBOT_CONTROL = 2
PACKET_ROBOT_BEEP = 3
PACKET_ROBOT_LEDS_CUSTOM = 7
PACKET_ROBOT_LEDS_BREATH = 8
PACKET_ROBOT_KICK = 12


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
        """
        :return int: number of bytes of the payload not read yet
        """
        return len(self.payload)

    def append_byte(self, char):
        """
        Appends a byte (int) or bytes to the payload
        """
        char = char & 0xFF
        if type(char) is int:
            self.payload += bytearray((char,))
        else:
            self.payload += bytearray(char)

    def append_short(self, short):
        """
        Appends a 16 bits integer (big endian)
        """
        b1 = (short >> 8) & 0xFF
        b2 = short & 0xFF

        self.payload += bytearray((b1, b2))

    def append_int(self, short):
        """
        Appends a 32 bits integer (big endian)
        """
        b1 = (short >> 24) & 0xFF
        b2 = (short >> 16) & 0xFF
        b3 = (short >> 8) & 0xFF
        b4 = short & 0xFF

        self.payload += bytearray((b1, b2, b3, b4))

    def appendFloat(self, f):
        """
        Appends a float as a 32 bits integer of thousandths (see read_float)
        """
        self.append_int(int(f * 1000.0))

    def appendSmallFloat(self, f):
        """
        Appends a float as a 16 bits integer of tenths (see read_small_float)
        """
        self.append_short(int(f * 10.0))

    def readByte(self):
        """
        Reads (and removes) the first byte of the payload
        """
        byte = self.payload[0]
        self.payload = self.payload[1:]

        return byte

    def read_int(self):
        """
        Reads a signed 32 bits integer (big endian)
        """
        n = self.readByte() << 24
        n = n | (self.readByte() << 16)
        n = n | (self.readByte() << 8)
        n = n | (self.readByte() << 0)

        # Two's complement (signed 32 bits)
        return n - (1 << 32) if n & (1 << 31) else n

    def read_short(self):
        """
        Reads a signed 16 bits integer (big endian)
        """
        n = (self.readByte() << 8) | self.readByte()

        # Two's complement (signed 16 bits)
        return n - (1 << 16) if n & (1 << 15) else n

    def read_float(self):
        """
        Reads a float sent as a 32 bits integer of thousandths
        """
        return self.read_int() / 1000.0

    def read_small_float(self):
        """
        Reads a float sent as a 16 bits integer of tenths
        """
        return self.read_short() / 10.0

    def to_raw(self):
        """
        :return bytearray: the packet, as sent
        """
        raw = bytearray()
        raw += bytearray((0xFF, 0xAA))
        if self.dest is not None:
            raw += bytearray((self.dest,))
        raw += bytearray((self.type, len(self.payload)))
        raw += self.payload
        raw += bytearray((self.checksum(),))

        return raw

    def checksum(self):
        """
        :return int: the checksum of the payload (sum modulo 256)
        """
        return sum(self.payload) % 256


class PacketReader:
    """
    Reads the packets from a stream of bytes (push the bytes, then pop the packets)
    """

    def __init__(self, dest=None):
        """
        :param dest: not None if the packets have a destination byte (packets to the robots)
        """
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
        """
        Forgets the packet being read (waits for the next header)
        """
        self.state = 0
        self.type_, self.length, self.packet_dest, self.payload = (
            0,
            0,
            None,
            bytearray(),
        )

    def push(self, byte: int):
        """
        Reads a byte of the stream (a packet is available when it is complete and valid)
        """
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
            # Empty packets have no payload, the next byte is the checksum
            self.state = self.STATE_DATA if self.length > 0 else self.STATE_CHECKSUM
        elif self.state == self.STATE_DATA:  # Payload
            self.payload += bytearray((byte,))
            if len(self.payload) >= self.length:
                self.state += 1
        elif self.state == self.STATE_CHECKSUM:  # Checksum
            if sum(self.payload) % 256 == byte and self.dest == self.packet_dest:
                self.packets.append(Packet(self.type_, self.payload))
            # Whether the packet is valid or not, we wait for a new one
            self.reset()

    def has_packet(self):
        """
        :return bool: whether a packet was read
        """
        return len(self.packets) > 0

    def pop_packet(self) -> Packet:
        """
        :return Packet: the oldest packet read (removed)
        """
        return self.packets.pop(0)
