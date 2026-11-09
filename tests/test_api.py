import inspect
import json
import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rsk.backend import Backend
from rsk.client import configurations
from rsk.game_controller import create_app

# Methods exposed in the API
API_METHODS = sorted(
    name
    for name, func in inspect.getmembers(Backend)
    if not name.startswith("_") and callable(func)
)


@pytest.fixture(scope="module")
def http(backend):
    app = create_app(backend)
    app.testing = True
    client = app.test_client()

    def call(command: str, raw_args: str):
        response = client.get(
            "/api", query_string={"command": command, "args": raw_args}
        )
        assert response.status_code == 200
        return response.get_json()

    return call


def strict_json(text: str):
    """
    Parses JSON as browsers do (NaN and Infinity are not valid)
    """

    def reject(constant):
        raise ValueError(f"Invalid JSON constant {constant}")

    return json.loads(text, parse_constant=reject)


@pytest.mark.parametrize(
    "command, raw_args",
    [
        ("get_state", "not json"),
        ("get_state", "{}"),
        ("get_state", "null"),
        ("get_state", "[1, 2]"),  # Too many arguments
        ("set_team_name", "[]"),  # Not enough arguments
        ("set_team_name", '["purple", "x"]'),  # Unknown team
        ("increment_score", '["green", "x"]'),  # Not a number
        ("add_penalty", '[NaN, "green1"]'),
        ("teleport", '["green1", NaN, 0, 0]'),
        ("teleport", '["green1", Infinity, 0, 0]'),
        ("teleport", '["green1", [1], 0, 0]'),
        ("validate_goal", '["false"]'),  # bool("false") would be True
        ("place_game", '["unknown"]'),
        ("resolutions", "[]"),  # No camera in simulation
        ("set_display_setting", '["ball", true]'),  # No detection in simulation
        ("startReferee", "[]"),  # Removed (was calling a non-existing method)
        ("unknown_command", "[]"),
    ],
)
def test_invalid_calls_return_an_error(http, command, raw_args):
    assert http(command, raw_args)[0] == 0


def test_valid_calls(http, backend):
    assert http("is_simulated", "[]") == [1, True]
    assert http("set_team_name", '["green", "Rhoban"]') == [1, None]
    assert backend.referee.game_state["teams"]["green"]["name"] == "Rhoban"
    http("set_team_name", '["green", ""]')

    # Optional argument
    assert http("place_game", '["side"]')[0] == 1
    assert http("place_game", '["side", true]')[0] == 1
    backend.control.remove_task("force-place")


def test_nan_teleport_does_not_break_the_state(http, backend):
    green1 = backend.simulator.objects["green1"]
    position = green1.position.copy()

    http("teleport", '["green1", NaN, 0, 0]')
    assert green1.position == pytest.approx(position, abs=0.05)

    response = backend.get_state()
    strict_json(json.dumps(response))


JSON_VALUES = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(-(10**6), 10**6)
    | st.floats(allow_nan=True, allow_infinity=True)
    | st.text(max_size=8)
    | st.sampled_from(["green", "blue", "green1", "ball", "standard", "side"]),
    lambda children: st.lists(children, max_size=3),
    max_leaves=5,
)
# Commands that are too slow, block, or need hardware
SKIPPED = {"identify", "blink", "cameras", "start_capture", "emergency"}


@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    command=st.sampled_from([name for name in API_METHODS if name not in SKIPPED]),
    args=st.lists(JSON_VALUES, max_size=5),
)
def test_fuzz_api(http, backend, command, args):
    """
    Any call returns a proper response, and the state stays valid JSON
    """
    try:
        response = http(command, json.dumps(args))
        assert response[0] in (0, 1)
        strict_json(json.dumps(backend.get_state()))
    finally:
        # Leaving the backend as we found it
        backend.referee.stop_game()
        backend.control.allow_team_control("green", True)
        backend.control.allow_team_control("blue", True)
        for team in ("green", "blue"):
            backend.control.set_key(team, "")
            backend.set_team_name(team, "")
            backend.referee.game_state["teams"][team]["x_positive"] = team == "green"
        backend.reset_score()
        backend.set_ready_to_record(False)
        backend.set_record_commands(False)
        for team, number, (x, y, turn) in configurations["game_green_positive"]:
            backend.teleport(f"{team}{number}", x, y, turn)
        backend.teleport("ball", 0, 0, 0)
        # Waiting for one-time tasks (e.g. the stop-all added when resuming the game) to be run
        start = time.time()
        while backend.control.tasks_snapshot() and time.time() - start < 1:
            time.sleep(0.01)


def test_calibration_board_download(backend):
    import cv2
    import numpy as np

    from rsk import lens_calibration

    app = create_app(backend)
    response = app.test_client().get("/api/calibration_board.png")

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    image = cv2.imdecode(np.frombuffer(response.data, np.uint8), cv2.IMREAD_GRAYSCALE)
    board = lens_calibration.make_board()
    object_points, _ = lens_calibration.detect_board(
        image, cv2.aruco.CharucoDetector(board), board
    )
    squares_x, squares_y = lens_calibration.BOARD_SQUARES
    assert len(object_points) == (squares_x - 1) * (squares_y - 1)


def test_lens_calibration_needs_a_camera(http):
    assert http("lens_calibration_status", "[]") == [
        0,
        "No camera in simulation or replay mode",
    ]
    assert http("start_lens_calibration", "[]")[0] == 0
