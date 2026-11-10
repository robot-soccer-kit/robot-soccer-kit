import math
import time

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from rsk import constants, simulator
from rsk.robots import Robots

MARKERS = ["green1", "green2", "blue1", "blue2"]


@pytest.fixture
def sim():
    """
    A simulator without thread nor state, stepped manually. Robots are placed away from the center.
    """
    robots = Robots()
    robots.save_robots = False
    Robots.protocols["sim"] = simulator.RobotSim
    sim = simulator.Simulator(robots, None, run_thread=False)
    for k, marker in enumerate(MARKERS):
        sim.objects[marker].teleport(-0.9 + 0.6 * k, 0.8, 0)
    sim.robots = robots
    return sim


def step(sim, duration=1.0, dt=0.01):
    for _ in range(int(duration / dt)):
        sim.loop(dt)


def gap(sim, a, b):
    a, b = sim.objects[a], sim.objects[b]
    return np.linalg.norm(a.position[:2] - b.position[:2]) - (a.radius + b.radius)


def control(sim, marker, dx, dy, dturn):
    sim.robots.robots_by_marker[marker].control(dx, dy, dturn)


def test_robot_reaches_commanded_speed(sim):
    sim.objects["green1"].teleport(-0.5, 0, 0)
    control(sim, "green1", 0.3, 0, 0)
    step(sim, 1.0)

    assert sim.objects["green1"].velocity[:2] == pytest.approx([0.3, 0], abs=1e-6)
    # Accelerating at 3 m/s^2 to 0.3 m/s takes 0.1s
    assert sim.objects["green1"].position[0] == pytest.approx(
        -0.5 + 0.3 * 0.95, abs=0.01
    )


def test_robot_pushes_the_ball(sim):
    sim.objects["green1"].teleport(0, 0, 0)
    sim.objects["ball"].teleport(0.2, 0, 0)
    control(sim, "green1", 0.5, 0, 0)
    step(sim, 1.0)

    assert sim.objects["ball"].position[0] > 0.4
    assert gap(sim, "green1", "ball") > -1e-3


def test_kick(sim):
    sim.objects["green1"].teleport(0, 0, math.pi / 2)
    sim.objects["ball"].teleport(0, constants.robot_radius + constants.ball_radius, 0)
    sim.robots.robots_by_marker["green1"].kick(1.0)
    step(sim, 0.05)

    velocity = sim.objects["ball"].velocity[:2]
    assert velocity[1] > 0.3 and abs(velocity[0]) < 1e-6


def test_no_kick_if_ball_is_not_in_front(sim):
    sim.objects["green1"].teleport(0, 0, 0)
    sim.objects["ball"].teleport(
        -(constants.robot_radius + constants.ball_radius), 0, 0
    )
    sim.robots.robots_by_marker["green1"].kick(1.0)
    step(sim, 0.05)

    assert np.linalg.norm(sim.objects["ball"].velocity) == 0


def test_ball_leaving_the_carpet_is_reset_at_the_center(sim):
    sim.objects["ball"].teleport(constants.carpet_length / 2 - 0.01, 0, 0)
    sim.objects["ball"].velocity[:2] = [1.0, 0.0]
    step(sim, 0.1)

    assert sim.objects["ball"].position[:2] == pytest.approx([0, 0])


def test_ball_reset_at_the_center_does_not_overlap_a_robot(sim):
    sim.objects["green1"].teleport(0.03, 0, 0)
    sim.objects["ball"].teleport(constants.carpet_length, 0, 0)
    step(sim, 0.01)

    assert gap(sim, "green1", "ball") > -1e-6


def test_overlapping_robots_are_separated(sim):
    sim.objects["green1"].teleport(0, 0, 0)
    sim.objects["blue1"].teleport(0.05, 0, 0)
    step(sim, 0.01)

    assert gap(sim, "green1", "blue1") > -1e-6

    # green1 can move again
    control(sim, "green1", -0.5, 0, 0)
    step(sim, 0.5)
    assert sim.objects["green1"].position[0] < -0.1


@settings(max_examples=150, deadline=None)
@given(
    positions=st.lists(
        st.tuples(st.floats(-0.9, 0.9), st.floats(-0.6, 0.6)), min_size=5, max_size=5
    ),
    orders=st.lists(
        st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-6, 6)),
        min_size=4,
        max_size=4,
    ),
    kicks=st.lists(st.booleans(), min_size=4, max_size=4),
)
def test_random_scenes_keep_objects_apart_and_finite(positions, orders, kicks):
    robots = Robots()
    robots.save_robots = False
    Robots.protocols["sim"] = simulator.RobotSim
    sim = simulator.Simulator(robots, None, run_thread=False)

    for marker, (x, y) in zip(MARKERS + ["ball"], positions):
        sim.objects[marker].teleport(x, y, 0)
    for marker, order, kick in zip(MARKERS, orders, kicks):
        robots.robots_by_marker[marker].control(*order)
        if kick:
            robots.robots_by_marker[marker].kick(1.0)

    for _ in range(100):
        sim.loop(0.01)
        for marker in sim.objects:
            assert np.all(np.isfinite(sim.objects[marker].position))

    # Objects can't stay overlapped
    for k, a in enumerate(sim.objects):
        for b in list(sim.objects)[k + 1 :]:
            assert gap(sim, a, b) > -1e-3


def test_simulation_rate():
    # The simulation runs at about fps_limit steps per second (100), sleeping between the steps.
    # The threshold is low: on Windows with Python < 3.11, sleeps last at least ~15.6 ms
    robots = Robots()
    robots.save_robots = False
    Robots.protocols["sim"] = simulator.RobotSim
    sim = simulator.Simulator(robots, None, run_thread=False)
    steps = []
    loop = sim.loop
    sim.loop = lambda dt: (steps.append(dt), loop(dt))

    sim.run_thread()
    try:
        time.sleep(1.0)
        steps.clear()
        time.sleep(1.0)
        count = len(steps)
    finally:
        sim.run = False
        sim.simu_thread.join(timeout=1)

    assert 50 <= count <= 105
