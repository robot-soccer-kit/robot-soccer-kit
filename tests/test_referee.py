import copy
import time

import pytest


def wait_for(condition, timeout=5.0):
    start = time.time()
    while not condition():
        if time.time() - start > timeout:
            return False
        time.sleep(0.02)
    return True


@pytest.fixture
def referee(backend):
    yield backend.referee
    backend.referee.stop_game()


@pytest.fixture
def penalty_spots(referee):
    """
    Restores the penalty spots after the test
    """
    saved = copy.deepcopy(referee.penalty_spot)
    yield referee.penalty_spot
    referee.penalty_spot[:] = saved


def test_penalty_spot_never_reuses_an_assigned_spot(referee, penalty_spots):
    # All spots are recently used, and all but one are assigned to other robots
    for index, spot in enumerate(penalty_spots):
        spot["last_use"] = time.time()
        spot["robot"] = None if index == 5 else "blue2"

    assert referee.find_penalty_spot("green1", (0.0, 0.0), {}) == 5


def test_penalty_spot_prefers_free_spots(referee, penalty_spots):
    for spot in penalty_spots:
        spot["robot"], spot["last_use"] = None, 0

    nearest = min(
        range(len(penalty_spots)),
        key=lambda k: (
            abs(penalty_spots[k]["pos"][0] - 0.3)
            + abs(penalty_spots[k]["pos"][1] - 0.7)
        ),
    )
    # The nearest spot is occupied by another robot
    markers = {
        "blue1": {"position": list(penalty_spots[nearest]["pos"][:2]), "orientation": 0}
    }

    spot = referee.find_penalty_spot("green1", (0.3, 0.7), markers)
    assert spot is not None and spot != nearest

    # Without the other robot, the nearest spot is chosen
    assert referee.find_penalty_spot("green1", (0.3, 0.7), {}) == nearest


def test_validate_goal_without_pending_goal_is_ignored(referee):
    referee.start_game()
    scores = {
        team: referee.game_state["teams"][team]["score"] for team in ("green", "blue")
    }

    referee.validate_goal(False)
    referee.validate_goal(True)

    assert not referee.control.has_task("force-place")
    for team, score in scores.items():
        assert referee.game_state["teams"][team]["score"] == score


def test_goal_cancelled_only_once(backend, referee):
    simulator = backend.simulator
    ball = simulator.objects["ball"]

    # Starting the game, the ball has to be placed at the center
    ball.teleport(0.0, 0.0, 0.0)
    referee.start_game()
    assert wait_for(lambda: not referee.game_state["game_paused"])

    # Shooting the ball in the goal on the positive x side, defended by green
    simulator.objects["green2"].teleport(0.5, 0.5, 0.0)
    ball.teleport(0.6, 0.2, 0.0)
    ball.velocity[:2] = [1.0, 0.0]
    assert wait_for(lambda: referee.game_state["teams"]["blue"]["score"] == 1)
    assert referee.game_state["game_state_msg"] == "Waiting for Goal Validation"

    # Cancelling the goal, a second click (e.g on an old goal) is ignored
    referee.validate_goal(False)
    referee.validate_goal(False)
    assert referee.game_state["teams"]["blue"]["score"] == 0
    # The decision is in the history
    assert [entry[2:] for entry in referee.referee_history[-2:]] == [
        ["blue", "Goal"],
        ["blue", "Goal cancelled"],
    ]
    assert referee.game_state["teams"]["green"]["score"] == 0
