from . import robot, robots

class RobotWifi(robot.Robot):
    def available_urls() -> list:
        return ["192.168.1.102", "192.168.1.103"]