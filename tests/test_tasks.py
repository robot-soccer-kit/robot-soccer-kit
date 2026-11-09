import pytest
from rsk import tasks, utils
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
