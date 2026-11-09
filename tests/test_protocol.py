import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from rsk import kinematics
from rsk.packets import Packet, PacketReader, decode_control, encode_control
from rsk.robot_wifi import RobotWifi
from rsk.robots import Robots
from rsk.simulator import RobotSim
from rsk.state import State


@pytest.fixture
def sim_robot():
    robot = RobotSim(Robots(State()), "green1")
    robot.initialize([0.0, 0.0, 0.0])
    return robot


def test_encode_control_truncates_toward_zero():
    assert encode_control(0.1239, -0.1239, np.deg2rad(5.9)) == (123, -123, 5)
    assert encode_control(0.0, 0.0, -np.deg2rad(0.9)) == (0, 0, 0)


def test_simulated_robot_orders_are_truncated_like_real_robots(sim_robot):
    # A slow rotation (< 1 deg/s) can't be sent to a real robot
    sim_robot.control(0.0, 0.0, 0.01)
    assert sim_robot.object.control_cmd[2] == 0.0

    sim_robot.control(0.1239, -0.0567, np.deg2rad(30.7))
    assert sim_robot.object.control_cmd == pytest.approx(
        [0.123, -0.056, np.deg2rad(30)]
    )


def test_simulated_robot_uses_firmware_max_wheel_speed(sim_robot):
    sim_robot.control(10.0, 0.0, 0.0)
    wheels = kinematics.inverse_kinematics(sim_robot.object.control_cmd)

    # MAX_WHEEL_SPEEDS in firmware/src/config.h
    assert max(abs(wheels)) == pytest.approx(16.0, rel=1e-3)


def test_real_and_simulated_robots_receive_the_same_order(sim_robot):
    """
    The order sent to a real robot (decoded as the firmware does) is the one applied by the
    simulated robot
    """
    order = (0.4567, -0.2345, 1.2345)
    robot = RobotWifi(Robots(), "10.0.0.6")
    try:
        robot.control(*order)
        _, _, packet = RobotWifi.pending_packets[f"{robot.id}/control"]

        # Skipping the command byte, then reading the values as signed shorts
        received = Packet(packet.type, packet.payload)
        received.readByte()
        values = [received.read_short() for _ in range(3)]

        sim_robot.control(*order)
        assert sim_robot.object.control_cmd == pytest.approx(decode_control(*values))
    finally:
        robot.close()
        RobotWifi.pending_packets.clear()


@pytest.mark.parametrize("value", [0, 1, -1, 123, -123, 32767, -32768])
def test_packet_short_roundtrip(value):
    packet = Packet(0)
    packet.append_short(value)
    assert packet.read_short() == value


@pytest.mark.parametrize("value", [0, 1, -1, 123456, -123456, 2**31 - 1, -(2**31)])
def test_packet_int_roundtrip(value):
    packet = Packet(0)
    packet.append_int(value)
    assert packet.read_int() == value


def read_packets(reader, data):
    packets = []
    for byte in data:
        reader.push(byte)
        while reader.has_packet():
            packet = reader.pop_packet()
            packets.append((packet.type, bytes(packet.payload)))
    return packets


MONITOR = Packet(5, bytearray([2, 0, 0, 5, 220, 78]))


def test_packet_reader_recovers_after_corrupted_packet():
    corrupted = MONITOR.to_raw()
    corrupted[-1] ^= 0xFF

    packets = read_packets(PacketReader(), corrupted + MONITOR.to_raw() * 3)
    assert packets == [(5, bytes(MONITOR.payload))] * 3


def test_packet_reader_recovers_after_packet_for_another_destination():
    other = Packet(5, bytearray([1, 2, 3]), dest=7).to_raw()
    mine = Packet(5, bytearray([9]), dest=0).to_raw()

    assert read_packets(PacketReader(dest=0), other + mine) == [(5, b"\x09")]


def test_packet_reader_empty_packet():
    packets = read_packets(PacketReader(), Packet(7).to_raw() + MONITOR.to_raw())
    assert packets == [(7, b""), (5, bytes(MONITOR.payload))]


@settings(max_examples=300, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.binary(max_size=8).filter(lambda garbage: 0xFF not in garbage),
            st.integers(0, 255),
            st.binary(max_size=40),
        ),
        max_size=6,
    )
)
def test_packet_reader_finds_packets_between_garbage(chunks):
    stream = bytearray()
    expected = []
    for garbage, type_, payload in chunks:
        packet = Packet(type_, bytearray(payload))
        stream += garbage + packet.to_raw()
        expected.append((type_, payload))

    assert read_packets(PacketReader(), stream) == expected
