import numpy as np
import pytest

from rsk import kinematics
from rsk.packets import Packet, decode_control, encode_control
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
