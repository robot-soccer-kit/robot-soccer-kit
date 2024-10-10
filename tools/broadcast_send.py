import time
import socket
import argparse

"""
Send UDP broadcasts at a given frequency
"""

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--frequency", type=int, default=60)
arg_parser.add_argument("--port", type=int, default=9999)
arg_parser.add_argument("--address", type=str, default="192.168.100.255")
args = arg_parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)  # IPTOS_LOWDELAY
sock.bind(("", 9999))
sock.setblocking(False)

frequency = args.frequency
last_packet = time.time()
packet_id = 0

while True:
    if time.time() - last_packet > 1 / frequency:
        last_packet = time.time()
        sock.sendto(b"%d" % packet_id, (args.address, args.port))
        packet_id += 1
    time.sleep(0.001)
