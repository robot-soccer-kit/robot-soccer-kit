from . import robot, robots
from threading import Thread, Lock
import time
import socket
import struct
from .packets import *


class RobotWifi(robot.Robot):
    network: str = "192.168.100.0"
    netmask: str = "255.255.255.0"
    udp_port: int = 7600
    broadcast_frequency: float = 60

    thread_broadcast: Thread = None
    thread_local: Thread = None
    pending_packets: dict = {}
    lock: Lock = Lock()
    statuses: dict = {}
    robots: dict = {}

    def start_service():
        RobotWifi.thread_broadcast = Thread(
            target=lambda: RobotWifi.service_loop(RobotWifi.get_broadcast_ip(), True)
        )
        RobotWifi.thread_broadcast.start()

        RobotWifi.thread_local = Thread(
            target=lambda: RobotWifi.service_loop(RobotWifi.get_ip())
        )
        RobotWifi.thread_local.start()

    def ip_to_int(ip: str) -> int:
        packedIP = socket.inet_aton(ip)
        return struct.unpack("!L", packedIP)[0]

    def int_to_ip(ip: int) -> str:
        return socket.inet_ntoa(struct.pack("!L", ip))

    def get_broadcast_ip() -> str:
        return RobotWifi.int_to_ip(
            (
                RobotWifi.ip_to_int(RobotWifi.network)
                | ~RobotWifi.ip_to_int(RobotWifi.netmask)
            )
            & 0xFFFFFFFF
        )

    def get_ip() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((RobotWifi.network, 80))
        return s.getsockname()[0]

    def service_loop(ip: str, broadcast: bool = False):
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind((ip, RobotWifi.udp_port))
        sock.setblocking(False)
        next_broadcast = time.time()
        broadcast_period = 1 / RobotWifi.broadcast_frequency

        # Receive a packet
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                rcv_ip = addr[0]
                RobotWifi.lock.acquire()
                RobotWifi.statuses[rcv_ip] = {"last_message": time.time()}

                if rcv_ip in RobotWifi.robots:
                    RobotWifi.robots[rcv_ip].process(data)

                RobotWifi.lock.release()
            except Exception as e:
                time.sleep(0.001)

            if broadcast:
                time_now = time.time()
                if time_now > next_broadcast:
                    next_broadcast += broadcast_period
                    if time_now > next_broadcast:
                        print("WARNING: Current time exceeds next broadcast period, that should be in the future")
                        next_broadcast = time.time() + broadcast_period

                    data = b""
                    RobotWifi.lock.acquire()
                    for key in RobotWifi.pending_packets:
                        data += RobotWifi.pending_packets[key].to_raw()
                    RobotWifi.pending_packets = {}
                    RobotWifi.lock.release()

                    if len(data):
                        sock.sendto(data, (ip, RobotWifi.udp_port))

    def available_urls() -> list:
        urls = []
        RobotWifi.lock.acquire()
        for ip in RobotWifi.statuses:
            if time.time() - RobotWifi.statuses[ip]["last_message"] < 10:
                urls.append(ip)
        RobotWifi.lock.release()

        return urls

    def __init__(self, url: str):
        print(f"Adding a robot with url {url}")
        super().__init__(url)

        self.packet_reader = PacketReader(dest=0)
        self.id = int(url.split(".")[-1])

        RobotWifi.lock.acquire()
        RobotWifi.robots[url] = self
        RobotWifi.lock.release()

    def close(self):
        RobotWifi.lock.acquire()
        del RobotWifi.robots[self.url]
        RobotWifi.lock.release()

    def process(self, data: bytes):
        for byte in data:
            self.packet_reader.push(byte)
            if self.packet_reader.has_packet():
                packet = self.packet_reader.pop_packet()
                self.last_message = time.time()

                version = packet.readByte()
                self.state["time"] = packet.read_float()
                self.state["battery"] = [packet.readByte() / 10.0]

    def add_packet(self, id: int, type_: str, packet: Packet):
        RobotWifi.lock.acquire()
        RobotWifi.pending_packets[f"{id}/{type_}"] = packet
        RobotWifi.lock.release()

    def kick(self, power: float = 1.0) -> None:
        """
        Kicks

        :param float power: kick power (0-1)
        :raises RobotError: if the operation is not supported
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_KICK)
        packet.append_byte(int(100 * power))
        self.add_packet(self.id, "kick", packet)

    def control(self, dx: float, dy: float, dturn: float) -> None:
        """
        Controls the robot velocity

        :param float dx: x axis (robot frame) velocity [m/s]
        :param float dy: y axis (robot frame) velocity [m/s]
        :param float dturn: rotation (robot frame) velocity [rad/s]
        :raises RobotError: if the operation is not supported
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_CONTROL)
        packet.append_short(int(1000 * dx))
        packet.append_short(int(1000 * dy))
        packet.append_short(int(np.rad2deg(dturn)))
        self.add_packet(self.id, "control", packet)

    def leds(self, red: int, green: int, blue: int) -> None:
        """
        Controls the robot LEDs

        :param int red: red brightness (0-255)
        :param int green: green brightness (0-255)
        :param int blue: blue brightness (0-255)
        :raises RobotError: if the operation is not supported
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_LEDS_CUSTOM)
        packet.append_byte(red)
        packet.append_byte(green)
        packet.append_byte(blue)
        self.add_packet(self.id, "leds", packet)

    def beep(self, frequency: int, duration: int) -> None:
        """
        Gets the robot beeping

        :param int frequency: frequency (Hz)
        :param int duration: duration (ms)
        :raises RobotError: if the operation is not supported
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_BEEP)
        packet.append_short(frequency)
        packet.append_short(duration)
        self.add_packet(self.id, "beep", packet)

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