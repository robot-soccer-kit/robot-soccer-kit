from . import robot, robots
from threading import Thread, Lock
import time
import socket
import struct
from .packets import *


class RobotWifi(robot.Robot):
    udp_port: int = 7600
    broadcast_frequency: float = 60

    thread_broadcast: Thread = None
    thread_local: Thread = None
    pending_packets: dict = {}
    lock: Lock = Lock()
    statuses: dict = {}
    robots: dict = {}

    def start_service():
        RobotWifi.thread_broadcast = Thread(target=lambda: RobotWifi.service_loop())
        RobotWifi.thread_broadcast.start()

    def ip_to_int(ip: str) -> int:
        packedIP = socket.inet_aton(ip)
        return struct.unpack("!L", packedIP)[0]

    def int_to_ip(ip: int) -> str:
        return socket.inet_ntoa(struct.pack("!L", ip))

    def service_loop():
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
                rcv_ip = addr[0]
                RobotWifi.lock.acquire()
                RobotWifi.statuses[rcv_ip] = {"last_message": time.time()}

                if rcv_ip in RobotWifi.robots:
                    RobotWifi.robots[rcv_ip].process(data)

                RobotWifi.lock.release()
            except Exception as e:
                time.sleep(0.001)

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

                RobotWifi.lock.acquire()
                for key in RobotWifi.pending_packets:
                    robot, ip, packet = RobotWifi.pending_packets[key]
                    append_data(ip, packet.to_raw())
                    robot.last_sent_message = time.time()
                RobotWifi.pending_packets = {}

                # Ensure the robots get a packet every 1s
                for ip in RobotWifi.robots:
                    if (
                        RobotWifi.robots[ip].last_sent_message is None
                        or time.time() - RobotWifi.robots[ip].last_sent_message > 1.0
                    ):
                        RobotWifi.robots[ip].last_sent_message = time.time()
                        packet = Packet(PACKET_HEARTBEAT, dest=RobotWifi.robots[ip].id)
                        append_data(ip, packet.to_raw())
                RobotWifi.lock.release()

                for ip in robots_data:
                    try:
                        sock.sendto(robots_data[ip], (ip, RobotWifi.udp_port))
                    except Exception:
                        print(f"WARNING: Can't send unicast to {ip}")

    def available_urls() -> list:
        return RobotWifi.robots_ips()

    def robots_ips() -> list:
        ips = []
        RobotWifi.lock.acquire()
        for ip in RobotWifi.statuses:
            if time.time() - RobotWifi.statuses[ip]["last_message"] < 10:
                ips.append(ip)
        RobotWifi.lock.release()

        return ips

    def __init__(self, url: str):
        print(f"Adding a robot with url {url}")
        super().__init__(url)

        self.packet_reader = PacketReader(dest=0)
        self.id = int(url.split(".")[-1])
        self.ip = url
        self.last_sent_message = None
        self.last_received_message = None
        self.packet_lock = True

        RobotWifi.lock.acquire()
        RobotWifi.robots[url] = self
        RobotWifi.lock.release()

    def close(self):
        RobotWifi.lock.acquire()
        del RobotWifi.robots[self.url]
        RobotWifi.lock.release()

    def process(self, data: bytes):
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

                version = packet.readByte()
                self.state["time"] = packet.read_float()
                self.state["battery"] = [packet.readByte() / 10.0]

    def add_packet(self, type_: str, packet: Packet, lock: bool = True):
        if lock:
            RobotWifi.lock.acquire()
        RobotWifi.pending_packets[f"{self.id}/{type_}"] = (self, self.ip, packet)
        if lock:
            RobotWifi.lock.release()

    def kick(self, power: float = 1.0, lock: bool = True) -> None:
        """
        Kicks

        :param float power: kick power (0-1)
        :raises RobotError: if the operation is not supported
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
        :raises RobotError: if the operation is not supported
        """
        packet = Packet(PACKET_ROBOT, dest=self.id)
        packet.append_byte(PACKET_ROBOT_CONTROL)
        packet.append_short(int(1000 * dx))
        packet.append_short(int(1000 * dy))
        packet.append_short(int(np.rad2deg(dturn)))
        self.add_packet("control", packet, lock)

    def leds(self, red: int, green: int, blue: int, lock: bool = True) -> None:
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
        self.add_packet("leds", packet, lock)

    def beep(self, frequency: int, duration: int, lock: bool = True) -> None:
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
