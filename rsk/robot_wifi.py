"""
Robots reached through WiFi (UDP, see the protocol in packets.py)
"""

from . import robot
from threading import Thread, Lock
import time
import socket
import struct
from .packets import (
    Packet,
    PacketReader,
    PACKET_HEARTBEAT,
    PACKET_ROBOT,
    PACKET_ROBOT_CONTROL,
    PACKET_ROBOT_BEEP,
    PACKET_ROBOT_LEDS_CUSTOM,
    PACKET_ROBOT_KICK,
    encode_control,
)
import logging
from .robots import Robots

logger: logging.Logger = logging.getLogger("robot_wifi")


class RobotWifi(robot.Robot):
    """
    A robot reached through WiFi (UDP). The packets of all the robots are sent by one thread
    (service_loop), at most at broadcast_frequency: the orders given meanwhile to a robot are
    coalesced (only the last one of each type is sent)
    """

    udp_port: int = 7600
    # Maximum rate of the packets sent to each robot [Hz] (the WiFi bands are often saturated)
    broadcast_frequency: float = 60

    thread_broadcast: Thread = None
    thread_local: Thread = None
    pending_packets: dict = {}
    lock: Lock = Lock()
    # IP => time of the last message received, for the robots found on the network
    statuses: dict = {}
    # IP => RobotWifi, for the robots added (class attribute, the instance attribute
    # self.robots is the Robots manager)
    robots: dict = {}

    def start_service():
        """
        Starts the thread sending and receiving the packets of the robots
        """
        RobotWifi.thread_broadcast = Thread(
            target=lambda: RobotWifi.service_loop(), daemon=True, name="RobotWifiThread"
        )
        RobotWifi.thread_broadcast.start()

    def ip_to_int(ip: str) -> int:
        """
        :return int: the IP address as an integer
        """
        packedIP = socket.inet_aton(ip)
        return struct.unpack("!L", packedIP)[0]

    def int_to_ip(ip: int) -> str:
        """
        :return str: the IP address of an integer
        """
        return socket.inet_ntoa(struct.pack("!L", ip))

    def service_loop():
        """
        Thread receiving the packets of the robots, and sending them the pending packets (at
        broadcast_frequency at most), and a heartbeat every second
        """
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)  # IPTOS_LOWDELAY
        sock.bind(("", RobotWifi.udp_port))
        sock.setblocking(False)
        next_broadcast = time.time()
        broadcast_period = 1 / RobotWifi.broadcast_frequency

        # Receive a packet
        while True:
            try:
                data, addr = sock.recvfrom(1024)
            except OSError:
                # No data available (non-blocking socket)
                data = None
                time.sleep(0.001)

            if data is not None:
                rcv_ip = addr[0]
                with RobotWifi.lock:
                    RobotWifi.statuses[rcv_ip] = {"last_message": time.time()}

                    if rcv_ip in RobotWifi.robots:
                        try:
                            RobotWifi.robots[rcv_ip].process(data)
                        except Exception:
                            logger.exception(
                                f"Error while processing data from {rcv_ip}"
                            )

            time_now = time.time()
            if time_now > next_broadcast:
                next_broadcast += broadcast_period
                if time_now > next_broadcast:
                    print(
                        "WARNING: Current time exceeds next broadcast period, that should be in the future"
                    )
                    next_broadcast = time.time() + broadcast_period

                robots_data = {}

                def append_data(ip: str, data: bytes):
                    if ip not in robots_data:
                        robots_data[ip] = b""

                    robots_data[ip] += data

                with RobotWifi.lock:
                    for key in RobotWifi.pending_packets:
                        robot, ip, packet = RobotWifi.pending_packets[key]
                        append_data(ip, packet.to_raw())
                        robot.last_sent_message = time.time()
                    RobotWifi.pending_packets = {}

                    # Ensure the robots get a packet every 1s
                    for ip in RobotWifi.robots:
                        if (
                            RobotWifi.robots[ip].last_sent_message is None
                            or time.time() - RobotWifi.robots[ip].last_sent_message
                            > 1.0
                        ):
                            RobotWifi.robots[ip].last_sent_message = time.time()
                            packet = Packet(
                                PACKET_HEARTBEAT, dest=RobotWifi.robots[ip].id
                            )
                            append_data(ip, packet.to_raw())

                for ip in robots_data:
                    try:
                        sock.sendto(robots_data[ip], (ip, RobotWifi.udp_port))
                    except Exception:
                        print(f"WARNING: Can't send unicast to {ip}")

    def available_urls() -> list:
        """
        :return list: the IP addresses of the robots found on the network
        """
        return RobotWifi.robots_ips()

    def robots_ips() -> list:
        """
        :return list: the IP addresses of the robots that sent a message during the last 10 s
        """
        ips = []
        RobotWifi.lock.acquire()
        for ip in RobotWifi.statuses:
            if time.time() - RobotWifi.statuses[ip]["last_message"] < 10:
                ips.append(ip)
        RobotWifi.lock.release()

        return ips

    def __init__(self, robot: Robots, url: str):
        print(f"Adding a robot with url {url}")
        super().__init__(robot, url)

        self.packet_reader = PacketReader(dest=0)
        self.id = int(url.split(".")[-1])
        self.ip = url
        self.last_sent_message = None
        self.last_received_message = None

        RobotWifi.lock.acquire()
        RobotWifi.robots[url] = self
        RobotWifi.lock.release()

    def close(self):
        """
        The robot is not reached anymore
        """
        with RobotWifi.lock:
            RobotWifi.robots.pop(self.url, None)

    def process(self, data: bytes):
        """
        Processes data received from the robot (monitor packets: time and battery). The robot
        beeps when it is reached again after 10 s
        """
        if (
            self.last_received_message is None
            or (time.time() - self.last_received_message) > 10.0
        ):
            self.beep(880, 250, lock=False)
        self.last_received_message = time.time()

        for byte in data:
            self.packet_reader.push(byte)
            if self.packet_reader.has_packet():
                packet = self.packet_reader.pop_packet()
                self.last_message = time.time()

                # Monitor packet: version (1 byte), time (4 bytes), battery (1 byte)
                if packet.available() < 6:
                    logger.warning(f"Ignoring too short packet from {self.ip}")
                    continue

                _ = packet.readByte()
                self.state["time"] = packet.read_float()
                self.state["battery"] = [packet.readByte() / 10.0]

    def add_packet(self, type_: str, packet: Packet, lock: bool = True):
        """
        Adds a packet to send: it replaces a pending packet of the same type

        :param str type_: type of the packet (e.g. "control")
        :param Packet packet: the packet
        :param bool lock: whether RobotWifi.lock is taken (False when it is already held)
        """
        if lock:
            RobotWifi.lock.acquire()
        RobotWifi.pending_packets[f"{self.id}/{type_}"] = (self, self.ip, packet)
        if lock:
            RobotWifi.lock.release()

    def kick(self, power: float = 1.0, lock: bool = True) -> None:
        """
        Kicks

        :param float power: kick power (0-1)
        :param bool lock: whether RobotWifi.lock is taken (False when it is already held)
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_KICK)
        packet.append_byte(int(100 * power))
        self.add_packet("kick", packet, lock)

    def control(self, dx: float, dy: float, dturn: float, lock: bool = True) -> None:
        """
        Controls the robot velocity

        :param float dx: x axis (robot frame) velocity [m/s]
        :param float dy: y axis (robot frame) velocity [m/s]
        :param float dturn: rotation (robot frame) velocity [rad/s]
        :param bool lock: whether RobotWifi.lock is taken (False when it is already held)
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_CONTROL)
        for value in encode_control(dx, dy, dturn):
            packet.append_short(value)
        self.add_packet("control", packet, lock)

    def leds(self, red: int, green: int, blue: int, lock: bool = True) -> None:
        """
        Controls the robot LEDs

        :param int red: red brightness (0-255)
        :param int green: green brightness (0-255)
        :param int blue: blue brightness (0-255)
        :param bool lock: whether RobotWifi.lock is taken (False when it is already held)
        """
        super().leds(red, green, blue)

        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_LEDS_CUSTOM)
        packet.append_byte(red)
        packet.append_byte(green)
        packet.append_byte(blue)
        self.add_packet("leds", packet, lock)

    def beep(self, frequency: int, duration: int, lock: bool = True) -> None:
        """
        Gets the robot beeping

        :param int frequency: frequency (Hz)
        :param int duration: duration (ms)
        :param bool lock: whether RobotWifi.lock is taken (False when it is already held)
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_BEEP)
        packet.append_short(frequency)
        packet.append_short(duration)
        self.add_packet("beep", packet, lock)

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
