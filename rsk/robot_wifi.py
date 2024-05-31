from . import robot, robots
from threading import Thread, Lock
import time
import socket
import struct


class RobotWifi(robot.Robot):
    network: str = "192.168.100.0"
    netmask: str = "255.255.255.0"
    thread_broadcast: Thread = None
    thread_local: Thread = None
    lock: Lock = Lock()
    statuses: dict = {}

    def start_service():
        RobotWifi.thread_broadcast = Thread(
            target=lambda: RobotWifi.service_loop(RobotWifi.get_broadcast_ip())
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

    def service_loop(ip: str):
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((ip, 7600))

        # Receive a packet
        while True:
            data, addr = sock.recvfrom(1024)
            RobotWifi.lock.acquire()
            RobotWifi.statuses[addr] = {
                "last_message": time.time()
            }
            RobotWifi.lock.release()

    def available_urls() -> list:
        urls = []
        RobotWifi.lock.acquire()
        for addr in RobotWifi.statuses:
            if time.time() - RobotWifi.statuses[addr]["last_message"] < 10:
                urls.append(addr[0])
        RobotWifi.lock.release()

        return urls
