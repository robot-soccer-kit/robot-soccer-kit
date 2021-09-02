import numpy as np
import threading
import time
import serial

PACKET_ACK = 0
PACKET_MONITOR = 1
PACKET_HOLO = 80
PACKET_HOLO_CONTROL = 2
PACKET_HOLO_KICK = 12
PACKET_HOLO_BEEP = 3
PACKET_MONITOR_DATA = 5

class Packet:
    def __init__(self, type_, payload = bytearray()):
        self.type = type_
        self.payload = payload.copy()

    def available(self):
        return len(self.payload)

    def appendByte(self, char):
        if type(char) == int:
            self.payload += bytearray((char,))
        else:
            self.payload += bytearray(char)

    def appendShort(self, short):
        b1 = (short >> 8) & 0xff
        b2 = short & 0xff

        self.payload += bytearray((b1, b2))

    def appendInt(self, short):
        b1 = (short >> 24) & 0xff
        b2 = (short >> 16) & 0xff
        b3 = (short >> 8) & 0xff
        b4 = short & 0xff

        self.payload += bytearray((b1, b2, b3, b4))

    def appendFloat(self, f):
        self.appendInt(f * 1000.)

    def appendSmallFloat(self, f):
        self.appendShort(f * 10.)

    def readByte(self):
        byte = self.payload[0]
        self.payload = self.payload[1:]

        return byte

    def readInt(self):
        n = (self.readByte() << 24) 
        n = n | (self.readByte() << 16)
        n = n | (self.readByte() << 8)
        n = n | (self.readByte() << 0)

        return int(np.int32(n))

    def readShort(self):
        n = (self.readByte() << 8) | self.readByte()

        return int(np.int16(n))

    def readFloat(self):
        return self.readInt()/1000.

    def readSmallFloat(self):
        return self.readShort()/10.

    def toRaw(self):
        raw = bytearray()
        raw += bytearray((0xff, 0xaa, self.type, len(self.payload)))
        raw += self.payload
        raw += bytearray((self.checksum(),))

        return raw

    def checksum(self):
        return sum(self.payload) % 256

class Robot:
    def __init__(self, port):
        self.port = port
        self.bt = None
        self.init = True
        self.thread = threading.Thread(target=lambda: self.execute())
        self.thread.start()
        self.state = {}

    def send(self, packet):
        self.bt.write(packet.toRaw())

    def monitor(self, frequency):
        packet = Packet(PACKET_MONITOR)
        packet.appendInt(frequency)
        self.send(packet)

    def process(self, packet):
        if packet.type == PACKET_MONITOR_DATA:
            state = {}
            state['version'] = packet.readByte()
            state['time'] = packet.readFloat()
            state['distance'] = packet.readSmallFloat()
            state['optics'] = [packet.readByte() for optic in range(7)]
            state['wheels'] = [packet.readSmallFloat() for w in range(3)]
            state['yaw'] = packet.readSmallFloat()
            state['gyro_yaw'] = packet.readSmallFloat()
            state['pitch'] = packet.readSmallFloat()
            state['roll'] = packet.readSmallFloat()
            state['odometry'] = {
                'x': packet.readShort()/1000.,
                'y': packet.readShort()/1000.,
                'yaw': packet.readSmallFloat()
            }
            state['battery'] = [packet.readByte()/40., packet.readByte()/40.]

            self.state = state

    def beep(self, frequency, duration):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_BEEP)
        packet.appendShort(frequency)
        packet.appendShort(duration)
        self.send(packet)

    def kick(self, power = 1.):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_KICK)
        packet.appendByte(int(100*power))
        print(packet.toRaw())
        self.send(packet)

    def control(self, dx, dy, dturn):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_CONTROL)
        packet.appendShort(int(dx))
        packet.appendShort(int(dy))
        packet.appendShort(int(dturn))
        self.send(packet)

    def stop(self):
        self.control(0, 0, 0)

    def execute(self):
        while True:
            if self.init:
                self.init = False
                if self.bt is not None:
                    self.bt.close()
                self.bt = serial.Serial(self.port, timeout=1)
                time.sleep(0.1)
                self.bt.write(b"rhock\r\nrhock\r\nrhock\r\n")
                time.sleep(0.1)
                self.beep(880, 250)
                self.monitor(5)

                print('Reading...')
                state = 0
                type_, length, payload = 0, 0, bytearray()

            byte = self.bt.read(1)
            if len(byte):
                byte = ord(byte)
                if state == 0: # First header
                    if byte == 0xff:
                        state += 1
                    else:
                        state = 0
                elif state == 1: # Second header
                    if byte == 0xaa:
                        state += 1
                    else:
                        state = 0
                elif state == 2: # Packet type
                    type_ = byte
                    state += 1
                elif state == 3: # Packet length
                    length = byte
                    state += 1
                elif state == 4: # Payload
                    payload += bytearray((byte,))
                    if len(payload) >= length:
                        state += 1
                elif state == 5: # Checksum
                    if sum(payload)%256 == byte:
                        self.process(Packet(type_, payload))
                        type_, length, payload, checksum = 0, 0, bytearray(), 0
                    state = 0             

if __name__ == '__main__':
    r = Robot('/dev/ttyS4')

    while True:
        print(r.state)
        time.sleep(0.1)