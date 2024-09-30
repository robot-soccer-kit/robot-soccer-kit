from . import api
from . import (
    state,
    video,
    robots,
    robot_serial,
    robot_wifi,
    control,
    referee,
    detection,
    utils,
    constants,
    simulator,
)


class Backend:
    def __init__(self, simulated=False, competition=False):
        super().__init__()
        robots.Robots.protocols["serial"] = robot_serial.RobotSerial
        robots.Robots.protocols["wifi"] = robot_wifi.RobotWifi

        self.simulated = simulated
        self.competition = competition

        self.state: state.State = state.State(30, self.simulated)
        self.state.start_pub()

        self.referee: referee.Referee = referee.Referee(self.state)
        self.control: control.Control = self.referee.control
        self.robots: robots.Robots = robots.Robots(self.state)

        if simulated:
            robots.Robots.protocols["sim"] = simulator.RobotSim
            self.simulator: simulator.Simulator = simulator.Simulator(self.robots, self.state)
        else:
            self.robots.load_config()
            self.video: video.Video = video.Video()

            self.detection: detection.Detection = self.video.detection
            self.detection.state = self.state
            self.detection.referee = self.referee

        self.control.robots = self.robots
        self.control.start()

    def is_competition(self):
        return self.competition

    def is_simulated(self):
        return self.simulated

    def cameras(self):
        return self.video.cameras()

    def constants(self) -> dict:
        # Retrieving all values declared in constants.py
        values: dict = {}
        constant_variables = vars(constants)

        for name in constant_variables:
            if type(constant_variables[name]) in [int, bool, float]:
                values[name] = constant_variables[name]

        # Adding team colors
        values["team_colors"] = utils.robot_teams()

        return values

    def get_state(self):
        state = self.state.get_state()
        state["referee"] = {
            "wait_ball_position": self.referee.wait_ball_position,
        }
        return state

    def resolutions(self):
        return self.video.resolutions()

    def getCameraSettings(self):
        return self.video.settings

    def start_capture(self, index: int, res: int) -> bool:
        return self.video.start_capture(index, res)

    def stop_capture(self):
        self.video.stop_capture()

    def get_image(self) -> str:
        image = self.video.get_image()
        return image

    def get_video(self, with_image: bool) -> dict:
        return self.video.get_video(with_image)

    def enableVideoDebug(self, enable=True) -> bool:
        self.video.debug = enable

    def cameraSettings(self, settings):
        self.video.set_camera_settings(settings)
        return True

    def available_urls(self):
        return self.robots.available_urls()

    def add_robot(self, url: str):
        self.robots.add_robot(url)

    def get_robots(self):
        return self.robots.get_robots()

    def set_marker(self, url: str, marker):
        self.robots.set_marker(url, marker)

    def removeRobot(self, url: str):
        self.robots.remove(url)

    def blink(self, url: str):
        if url in self.robots.robots:
            self.robots.robots[url].blink()

    def kick(self, url: str):
        if url in self.robots.robots:
            self.robots.robots[url].kick()

    def teleport(self, marker: str, x: float, y: float, turn: float):
        if marker in self.robots.robots_by_marker or marker == "ball":
            self.simulator.objects[marker].teleport(x, y, turn)

    def control_status(self):
        return self.control.status()

    def allow_team_control(self, team: str, allow: bool):
        self.control.allow_team_control(team, allow)

    def emergency(self):
        self.control.emergency()

    def set_key(self, team: str, key: str):
        self.control.set_key(team, key)

    def identify(self):
        self.robots.identify()

    def startReferee(self):
        self.referee.startReferee()

    def stopReferee(self):
        self.referee.stopReferee()

    def increment_score(self, team: str, increment: int):
        self.referee.increment_score(team, increment)

    def reset_score(self):
        self.referee.reset_score()

    def set_display_setting(self, entry: str, value: bool):
        self.detection.set_display_setting(entry, value)

    def get_display_settings(self, reset: bool = False) -> list:
        return self.detection.get_display_settings(reset)

    def start_game(self):
        self.referee.start_game()

    def pause_game(self):
        self.referee.pause_game()

    def resume_game(self):
        self.referee.resume_game()

    def stop_game(self):
        self.referee.stop_game()

    def calibrate_camera(self):
        self.detection.calibrate_camera()

    def place_game(self, configuration: str, end_buzz=False):
        self.referee.place_game(configuration, end_buzz=end_buzz)

    def set_team_name(self, team: str, name: str):
        self.referee.set_team_name(team, name)

    def swap_team_sides(self) -> str:
        self.referee.swap_team_sides()

    def start_half_time(self):
        self.referee.start_half_time()

    def start_second_half_time(self):
        self.referee.start_second_half_time()

    def add_penalty(self, duration: int, robot: str):
        self.referee.add_penalty(duration, robot)

    def cancel_penalty(self, robot) -> str:
        self.referee.cancel_penalty(robot)

    def get_game_state(self) -> dict:
        return self.referee.get_game_state()

    def get_wait_ball_position(self):
        return self.referee.wait_ball_position

    def validate_goal(self, yes_no: bool):
        self.referee.validate_goal(yes_no)
