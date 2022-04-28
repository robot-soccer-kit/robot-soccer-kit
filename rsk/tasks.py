from . import control, client, utils


class ControlTask:
    """
    A task to be managed by the control
    """    
    def __init__(self, name: str, priority: int = 0):
        self.name: str = name
        self.priority: int = priority

    def robots(self) -> list:
        return []

    def tick(self, robot: client.ClientRobot) -> None:
        raise NotImplemented("Task not implemented")

    def finished(self, client: client.Client) -> bool:
        return False


class StopAllTask(ControlTask):
    """
    Stops all robots from moving, can be done once or forever
    """    
    def __init__(self, name: str, forever=True, **kwargs):
        super().__init__(name, **kwargs)
        self.forever = forever

    def robots(self):
        return utils.all_robots()

    def tick(self, robot: client.ClientRobot):
        robot.control(0.0, 0.0, 0.0)

    def finished(self, client: client.Client) -> bool:
        return not self.forever


class StopTask(StopAllTask):
    """
    Stops one robot from moving
    """    
    def __init__(self, name: str, team: str, number: int, **kwargs):
        super().__init__(name, **kwargs)
        self.team: str = team
        self.number: int = number

    def robots(self):
        return [(self.team, self.number)]


class GoToConfigurationTask(ControlTask):
    """
    Send all robots to a given configuration
    """    
    def __init__(self, name: str, configuration=None, skip_old=True, **kwargs):
        super().__init__(name, **kwargs)
        self.targets = {}
        self.skip_old: bool = skip_old

        if configuration is not None:
            for team, number, target in client.configurations[configuration]:
                self.targets[(team, number)] = target

    def robots(self):
        return list(self.targets.keys())

    def tick(self, robot: client.ClientRobot):
        robot.goto(
            self.targets[(robot.team, robot.number)], False, skip_old=self.skip_old
        )

    def finished(self, client: client.Client) -> bool:
        for team, number in self.targets:
            arrived, _ = client.robots[team][number].goto_compute_order(
                self.targets[(team, number)], skip_old=self.skip_old
            )

            if not arrived:
                return False

        return True


class GoToTask(GoToConfigurationTask):
    """
    Send one robot to a position
    """    
    def __init__(
        self, name: str, team: str, number: int, target, skip_old=True, **kwargs
    ):
        super().__init__(name, **kwargs)
        self.targets[(team, number)] = target
