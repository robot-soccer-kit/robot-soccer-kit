import numpy as np
import threading
import time
import serial

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
    def __init__(self, type_, payload=bytearray()):
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
        self.running = True
        self.last_message = None
        self.last_init = None
        self.state = {}
        self.moved = False
        self.marker = None
        self.thread = threading.Thread(target=lambda: self.execute())
        self.thread.start()
        self.ledsColor = None
        self.pending_packets = {}
        self.lock = threading.Lock()

    def monitor(self, frequency):
        packet = Packet(PACKET_MONITOR)
        packet.appendInt(frequency)
        self.add_packet('monitor', packet)

    def applyLeds(self):
        if self.ledsColor is None:
            self.ledsBreath()
        else:
            self.leds(*self.ledsColor)

    def blink(self):
        for x in range(5):
            self.leds(255, 255, 255)
            time.sleep(0.25)
            self.leds(0, 0, 0)
            time.sleep(0.25)
        self.applyLeds()

    def setMarker(self, marker):
        self.marker = marker

        if marker is None:
            self.ledsColor = None
        elif marker.startswith('red'):
            self.ledsColor = [32, 0, 0]
        elif marker.startswith('blue'):
            self.ledsColor = [0, 0, 32]
        else:
            self.ledsColor = None

        self.applyLeds()

    def process(self, packet):
        if packet.type == PACKET_MONITOR_DATA:
            self.last_message = time.time()

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

    def add_packet(self, name, packet):
        self.lock.acquire()
        self.pending_packets[name] = packet
        self.lock.release()

    def pop_packet(self):
        packet = None

        self.lock.acquire()
        if len(self.pending_packets) > 0:
            name = next(iter(self.pending_packets))
            packet = self.pending_packets[name]
            del self.pending_packets[name]
        self.lock.release()

        return packet

    def beep(self, frequency, duration):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_BEEP)
        packet.appendShort(frequency)
        packet.appendShort(duration)
        self.add_packet('beep', packet)

    def kick(self, power=1.):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_KICK)
        packet.appendByte(int(100*power))
        self.add_packet('kick', packet)

    def control(self, dx, dy, dturn):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_CONTROL)
        packet.appendShort(int(1000*dx))
        packet.appendShort(int(1000*dy))
        packet.appendShort(int(np.rad2deg(dturn)))
        self.add_packet('control', packet)

    def ledsBreath(self):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_LEDS_BREATH)
        self.add_packet('leds', packet)

    def leds(self, r, g, b):
        packet = Packet(PACKET_HOLO)
        packet.appendByte(PACKET_HOLO_LEDS_CUSTOM)
        packet.appendByte(r)
        packet.appendByte(g)
        packet.appendByte(b)
        self.add_packet('leds', packet)

    def stop(self):
        self.control(0, 0, 0)

    def close(self):
        self.running = False

    def execute(self):
        while self.running:
            try:
                if self.init:
                    print('Opening connection with ' + self.port)
                    self.init = False
                    if self.bt is not None:
                        self.bt.close()
                        self.bt = None
                    self.bt = serial.Serial(self.port, timeout=0.02)
                    time.sleep(0.1)
                    self.bt.write(b"rhock\r\nrhock\r\nrhock\r\n")
                    time.sleep(0.1)
                    self.monitor(1)
                    self.control(0, 0, 0)
                    self.beep(880, 250)
                    self.applyLeds()
                    self.last_init = time.time()
                    state = 0
                    type_, length, payload = 0, 0, bytearray()

                # Receiving data
                byte = self.bt.read(1)
                if len(byte):
                    byte = ord(byte)
                    if state == 0:  # First header
                        if byte == 0xff:
                            state += 1
                        else:
                            state = 0
                    elif state == 1:  # Second header
                        if byte == 0xaa:
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

                # Sending pending packets
                packet = self.pop_packet()
                while packet is not None:
                    if self.bt is not None and self.bt.is_open:
                        self.bt.write(packet.toRaw())
                    packet = self.pop_packet()

            except (OSError, serial.serialutil.SerialException) as e:
                # In case of exception, we re-init the connection
                print('Error: '+str(e))
                if 'FileNotFoundError' in str(e):
                    time.sleep(1.)
                self.init = True

            # If we didn't receive a message for more than 5s, we re-init the connection
            no_message = ((self.last_message is None) or (
                time.time() - self.last_message > 5))

            if self.last_init is None:
                old_init = False
            else:
                old_init = time.time() - self.last_init > 5

            if no_message and old_init:
                self.init = True

        if self.bt is not None:
            self.bt.close()


if __name__ == '__main__':
    r = Robot('/dev/rfcomm0')

    while True:
        print(r.state)
        time.sleep(5)
