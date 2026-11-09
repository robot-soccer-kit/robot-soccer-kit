import threading
import time

import pytest
import zmq
from rsk import tasks


@pytest.fixture
def request_control():
    """
    Sends a raw request to the control socket and returns the response (or None on timeout)
    """
    context = zmq.Context()
    sockets = []

    def send(payload: bytes):
        socket = context.socket(zmq.REQ)
        socket.RCVTIMEO = 2000
        socket.connect("tcp://127.0.0.1:7558")
        sockets.append(socket)
        socket.send(payload)
        try:
            return socket.recv_json()
        except zmq.error.Again:
            return None

    yield send

    for socket in sockets:
        socket.close(linger=0)
    context.term()


MALFORMED_REQUESTS = [
    b'["", "green", "x", ["control", 0, 0, 0]]',  # Robot number is not an int
    b'["", "green", 1.5, ["control", 0, 0, 0]]',  # Robot number is a float
    b'["", "green", 99, ["control", 0, 0, 0]]',  # Unknown robot number
    b'["", "green", 1, []]',  # Empty command
    b'["", "green", 1, "kick"]',  # Command is not a list
    b'["", "ball", 0, []]',  # Empty ball command
    b'["", ["green"], 1, ["kick", 1]]',  # Unhashable team
    b'{"not": "a list"}',
    b"not json at all",
    b"",
]


@pytest.mark.parametrize("payload", MALFORMED_REQUESTS)
def test_malformed_request_gets_error_response(control, request_control, payload):
    response = request_control(payload)

    assert response is not None, "The control server did not answer"
    assert response[0] is False

    # The control server should still answer valid requests afterwards
    response = request_control(b'["", "green", 1, ["kick", 1]]')
    assert response is not None, "The control server is dead after a malformed request"
    assert response == [True, "ok"]


def test_concurrent_task_access(control):
    """
    Tasks are modified by several threads (API, referee, control client) while being read
    """
    errors = []
    stop = threading.Event()

    def writer():
        k = 0
        while not stop.is_set():
            control.add_task(tasks.StopTask(f"test-{k % 50}", "green", 1))
            control.remove_task(f"test-{(k + 25) % 50}")
            k += 1

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()

    start = time.time()
    try:
        while time.time() - start < 1.0:
            try:
                control.status()
                control.robot_tasks("green", 1)
                control.has_task("test-0")
            except RuntimeError as e:
                errors.append(e)
    finally:
        stop.set()
        thread.join()
        for k in range(50):
            control.remove_task(f"test-{k}")

    assert errors == []


def test_finished_task_replaced_is_not_removed(control):
    """
    If a task is replaced (same name) while being ticked, the new task should not be removed
    when the old one finishes
    """

    class ReplacingTask(tasks.StopAllTask):
        def finished(self, client, available_robots):
            control.add_task(tasks.StopAllTask("replaced"))
            return True

    control.add_task(ReplacingTask("replaced"))
    control.tick_tasks()

    assert control.has_task("replaced")
    assert type(control.tasks["replaced"]) is tasks.StopAllTask
    control.remove_task("replaced")


def test_ball_teleport_keeps_float_coordinates(backend):
    ball = backend.simulator.objects["ball"]
    try:
        response = backend.control.process_command(
            "ball", ["teleport", 0.3, -0.4, 0.5], False
        )

        assert response == [True, "ok"]
        assert ball.position == pytest.approx([0.3, -0.4, 0.5])
    finally:
        ball.teleport(0, 0, 0)


def test_ball_rejects_other_commands(backend):
    ball = backend.simulator.objects["ball"]
    response = backend.control.process_command("ball", ["kick", 0.3, -0.4, 0.5], False)

    assert response[0] is False
    assert ball.position == pytest.approx([0, 0, 0])


def test_ball_teleport_without_simulator(backend, monkeypatch):
    monkeypatch.delattr(backend.robots, "ball")
    response = backend.control.process_command(
        "ball", ["teleport", 0.3, -0.4, 0.5], False
    )

    assert response == [False, "The ball can only be teleported in simulation"]
