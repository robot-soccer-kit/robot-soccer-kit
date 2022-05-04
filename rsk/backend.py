from . import api
from . import video, robots, control, field, referee, detection, utils, constants


class Backend:
    def __init__(self):
        super().__init__()

        self.video: video.Video = video.Video()
        self.detection: detection.Detection = self.video.detection
        self.robots: robots.Robots = robots.Robots(self.detection)
        self.referee: referee.Referee = referee.Referee(self.robots.control)
        self.detection.referee = self.referee

    def cameras(self):
        return self.video.cameras()

    def constants(self) -> dict:
        return {"team_colors": utils.robot_teams(), "default_penalty": constants.default_penalty}

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

    def get_video(self, with_image) -> bool:
        return self.video.get_video(with_image)

    def enableVideoDebug(self, enable=True) -> bool:
        self.video.debug = enable

    def cameraSettings(self, settings):
        self.video.set_camera_settings(settings)
        return True

    def ports(self):
        return self.robots.ports()

    def add_robot(self, port: str):
        self.robots.add_robot(port)

    def get_robots(self):
        return self.robots.get_robots()

    def set_marker(self, port: str, marker):
        self.robots.set_marker(port, marker)

    def removeRobot(self, port: str):
        self.robots.remove(port)

    def blink(self, port: str):
        if port in self.robots.robots:
            self.robots.robots[port].blink()

    def kick(self, port: str):
        if port in self.robots.robots:
            self.robots.robots[port].kick()

    def control_status(self):
        return self.robots.control.status()

    def allow_team_control(self, team: str, allow: bool):
        self.robots.control.allow_team_control(team, allow)

    def emergency(self):
        self.robots.control.emergency()

    def set_key(self, team: str, key: str):
        self.robots.control.set_key(team, key)

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

    def set_display_settings(self, display_settings: list):
        self.detection.set_display_settings(display_settings)

    def save_display_settings(self):
        self.detection.save_display_settings()

    def get_display_settings(self) -> list:
        return self.detection.get_display_settings()

    def get_default_display_settings(self) -> list:
        return self.detection.get_default_display_settings()

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

    def place_game(self, configuration: str):
        self.referee.place_game(configuration)

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

    def validate_goal(self, yes_no: bool):
        self.referee.validate_goal(yes_no)
