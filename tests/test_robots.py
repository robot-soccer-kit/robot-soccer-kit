import threading

from rsk.detection import Detection
from rsk.packets import Packet
from rsk.robot_wifi import RobotWifi
from rsk.robots import Robots
from rsk.simulator import SimulatedObject
from rsk.state import State


def test_simulator_actions_are_not_lost():
    """
    Actions (e.g: kicks) are added by the control thread while the simulator executes them
    """
    obj = SimulatedObject("ball", [0, 0, 0], 0.021)
    executed = []
    added = 20000

    def producer():
        for k in range(added):
            obj.add_action(lambda k=k: executed.append(k))

    thread = threading.Thread(target=producer)
    thread.start()
    while thread.is_alive():
        obj.execute_actions()
    thread.join()
    obj.execute_actions()

    assert sorted(executed) == list(range(added))


def test_robot_wifi_ignores_short_packets():
    robot = RobotWifi(Robots(), "10.0.0.5")
    try:
        # Valid checksum, but payload too short
        robot.process(Packet(5, bytearray([2]), dest=0).to_raw())
        assert "battery" not in robot.state

        # Valid monitor packet: version, time (ms), battery (1/10 V)
        packet = Packet(5, dest=0)
        packet.append_byte(2)
        packet.append_int(1500)
        packet.append_byte(78)
        robot.process(packet.to_raw())
        assert robot.state == {"time": 1.5, "battery": [7.8]}
    finally:
        robot.close()


def test_detection_returns_detected_markers():
    detection = Detection()
    detection.state = State()
    markers = {"green1": {"position": [0.1, 0.2], "orientation": 0.3}}
    detection.state.set_markers(markers)

    assert detection.get_detection()["markers"] == markers
