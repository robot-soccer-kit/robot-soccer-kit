import numpy as np

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
        char = char & 0xFF
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


class PacketReader:
    def __init__(self):
        self.reset()
        self.packets = []

    def reset(self):
        self.state = 0
        self.type_, self.length, self.payload = 0, 0, bytearray()

    def push(self, byte: int):
        if self.state == 0:  # First header
            if byte == 0xFF:
                self.state += 1
            else:
                self.state = 0
        elif self.state == 1:  # Second header
            if byte == 0xAA:
                self.state += 1
            else:
                self.state = 0
        elif self.state == 2:  # Packet type
            self.type_ = byte
            self.state += 1
        elif self.state == 3:  # Packet length
            self.length = byte
            self.state += 1
        elif self.state == 4:  # Payload
            self.payload += bytearray((byte,))
            if len(self.payload) >= self.length:
                self.state += 1
        elif self.state == 5:  # Checksum
            if sum(self.payload) % 256 == byte:
                self.packets.append(Packet(self.type_, self.payload))
                self.reset()
            self.state = 0
    
    def has_packet(self):
        return len(self.packets) > 0
    
    def pop_packet(self) -> Packet:
        return self.packets.pop(0)