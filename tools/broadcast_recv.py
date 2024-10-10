import time
import socket
import argparse

"""
Receive packets through UDP broadcasts and calculate packet loss
"""

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--port", type=int, default=9999)
args = arg_parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10)  # IPTOS_LOWDELAY
sock.bind(("", args.port))
sock.setblocking(False)

start = time.time()
packets = 0
first_packet = None

while True:
    try:
        data, addr = sock.recvfrom(1024)
        packets += 1

        packet_id = int(data)
        if first_packet is None:
            first_packet = packet_id

        expected_packets = packet_id - first_packet + 1

        loss = ((expected_packets - packets) / expected_packets) * 100
        print("Packets: %d / %d, Loss: %d (pct)" % (packets, expected_packets, loss))
    except Exception as e:
        time.sleep(0.001)
