import numpy as np
import pytest
from rsk import constants, tasks, utils
from rsk.path_finder import PathFinder


class FakeRobot:
    """
    Records the orders sent to a robot, and tells whether it arrived
    """

    def __init__(self, team, number):
        self.team = team
        self.number = number
        self.arrived = True
        self.orders = []

    def goto_compute_order(self, target, skip_old=True):
        return self.arrived, (0.0, 0.0, 0.0)

    def goto(self, target, wait=True, skip_old=True, avoid_obstacles=False):
        self.orders.append(("goto", target, skip_old))

    def control(self, dx, dy, dturn):
        self.orders.append(("control", dx, dy, dturn))

    def leds(self, r, g, b):
        self.orders.append(("leds", r, g, b))

    def beep(self, frequency, duration):
        self.orders.append(("beep", frequency, duration))


class FakeClient:
    def __init__(self):
        self.robots = {
            team: {number: FakeRobot(team, number) for number in utils.robot_numbers()}
            for team in utils.robot_teams()
        }


AVAILABLE_ROBOTS = utils.all_robots_id()


@pytest.mark.parametrize("robot", utils.all_robots())
def test_goto_task_finished_only_stops_its_robot(robot):
    client = FakeClient()
    task = tasks.GoToTask("goto", *robot, (0.0, 0.0, 0.0))

    assert task.finished(client, AVAILABLE_ROBOTS)

    for team, number in utils.all_robots():
        orders = client.robots[team][number].orders
        if (team, number) == robot:
            assert orders == [("control", 0.0, 0.0, 0.0)]
        else:
            assert orders == []


def test_goto_task_not_finished_while_not_arrived():
    client = FakeClient()
    client.robots["blue"][1].arrived = False
    task = tasks.GoToTask("goto", "blue", 1, (0.0, 0.0, 0.0))

    assert not task.finished(client, AVAILABLE_ROBOTS)
    assert client.robots["blue"][1].orders == []


def test_goto_task_ignores_unavailable_robot():
    client = FakeClient()
    client.robots["green"][1].arrived = False
    task = tasks.GoToTask("goto", "green", 1, (0.0, 0.0, 0.0))

    # green1 is not available, so it can't prevent the task from finishing
    assert task.finished(client, ["blue1", "blue2"])
    assert client.robots["green"][1].orders == []


def test_configuration_end_buzz_only_concerns_targets():
    client = FakeClient()
    task = tasks.GoToConfigurationTask(
        "place", "game", robots_filter=[("green", 1)], end_buzz=True
    )

    assert task.finished(client, AVAILABLE_ROBOTS)
    assert ("beep", 100, 500) in client.robots["green"][1].orders
    assert client.robots["blue"][1].orders == []


@pytest.mark.parametrize("skip_old", [True, False])
def test_goto_task_skip_old(skip_old):
    task = tasks.GoToTask("goto", "green", 1, (0.0, 0.0, 0.0), skip_old=skip_old)
    robot = FakeRobot("green", 1)
    task.tick(robot)

    assert task.skip_old is skip_old
    assert robot.orders == [("goto", (0.0, 0.0, 0.0), skip_old)]


def test_speed_task():
    task = tasks.SpeedTask("speed", "green", 2, dturn=1.0, priority=10)
    robot = FakeRobot("green", 2)
    task.tick(robot)

    assert task.priority == 10
    assert task.robots() == [("green", 2)]
    assert robot.orders == [("control", 0, 0, 1.0)]
    assert not task.finished(FakeClient(), AVAILABLE_ROBOTS)


def test_path_finder_no_path():
    path_finder = PathFinder()
    start = path_finder.add_node(0.0, 0.0)
    goal = path_finder.add_node(1.0, 1.0)
    # Disconnected graph: no path can be found
    path_finder.neighbors = lambda node: []

    assert path_finder.astar(start, goal) is None
    assert path_finder.find_target(start, goal) is None


def test_path_finder_avoids_obstacle():
    path_finder = PathFinder(avoid_margin=0.05)
    start = path_finder.add_node(-0.5, 0.0)
    goal = path_finder.add_node(0.5, 0.0)
    path_finder.add_obstacle(0.0, 0.0, 0.1)

    path = path_finder.astar(start, goal)

    # The path goes around the obstacle instead of crossing it
    assert len(path) > 2
    for point in path[1:-1]:
        assert abs(point[1]) > 0.1


def numpy_distance_between(path_finder, n1, n2):
    # The previous implementation (numpy), as a reference
    node1_xy = path_finder.nodes[n1]
    node2_xy = path_finder.nodes[n2]
    distance = np.linalg.norm(np.array(node1_xy) - np.array(node2_xy))
    intersect_ratio = 0
    for obstacle in path_finder.obstacles:
        segment_dx = node2_xy[0] - node1_xy[0]
        segment_dy = node2_xy[1] - node1_xy[1]
        a = segment_dx**2 + segment_dy**2
        x_ca = node1_xy[0] - obstacle[0]
        y_ca = node1_xy[1] - obstacle[1]
        b = 2 * (x_ca * segment_dx + y_ca * segment_dy)
        c = x_ca**2 + y_ca**2 - (obstacle[2]) ** 2
        d = b**2 - 4 * a * c
        if d > 0:
            d = np.sqrt(d)
            t1 = np.clip((-b - d) / (2 * a), 0, 1)
            t2 = np.clip((-b + d) / (2 * a), 0, 1)
            intersect_ratio = max(intersect_ratio, np.abs(t2 - t1))
    return distance + path_finder.obstacle_penalty * intersect_ratio * distance


@pytest.mark.parametrize("seed", range(10))
def test_path_finder_distances(seed):
    rng = np.random.default_rng(seed)
    path_finder = PathFinder(avoid_margin=0.05)
    for x, y in rng.uniform([-1.3, -1.0], [1.3, 1.0], (4, 2)):
        path_finder.add_node(x, y)
    for x, y in rng.uniform([-0.8, -0.5], [0.8, 0.5], (3, 2)):
        path_finder.add_obstacle(x, y, 0.16)

    for n1 in range(len(path_finder.nodes)):
        for n2 in range(len(path_finder.nodes)):
            if n1 != n2:
                assert path_finder.distance_between(n1, n2) == pytest.approx(
                    numpy_distance_between(path_finder, n1, n2), rel=1e-12, abs=1e-15
                )
    # The nodes are on the carpet
    for x, y in path_finder.nodes:
        assert abs(x) <= constants.carpet_length / 2
        assert abs(y) <= constants.carpet_width / 2
