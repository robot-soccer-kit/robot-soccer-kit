from . import api
from . import video, robots, control, field, referee, detection


class Backend():
    def __init__(self):
        super().__init__()

        self.video:video.Video = video.Video()
        self.detection:detection.Detection = self.video.detection
        self.robots:robots.Robots = robots.Robots(self.detection)
        self.referee:referee.Referee = referee.Referee(self.detection, self.robots.control)

    def cameras(self):
        return self.video.cameras()

    def resolutions(self):
        return self.video.resolutions()

    def getCameraSettings(self):
        return self.video.settings

    def startCapture(self, index: int, res: int) -> bool:
        return self.video.startCapture(index, res)

    def stopCapture(self):
        self.video.stopCapture()

    def getImage(self) -> str:
        image = self.video.getImage()
        print(image)
        return image

    def getVideo(self, with_image) -> bool:
        return self.video.getVideo(with_image)

    def enableVideoDebug(self, enable=True) -> bool:
        self.video.debug = enable

    def cameraSettings(self, settings):
        self.video.setCameraSettings(settings)
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

    def getGame(self):
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

    def updateScore(self, team: str, increment: int):
        self.referee.updateScore(team, increment)

    def resetScore(self):
        self.referee.resetScore()

    def set_display_settings(self, display_settings: list):
        self.detection.set_display_settings(display_settings)

    def save_display_settings(self):
        self.detection.save_display_settings()

    def get_display_settings(self) -> list:
        return self.detection.get_display_settings()

    def get_default_display_settings(self) -> list:
        return self.detection.get_default_display_settings()

    def startGame(self):
        self.referee.startGame()

    def pauseGame(self):
        self.referee.pauseGame()

    def resumeGame(self):
        self.referee.resumeGame()

    def stopGame(self):
        self.referee.stopGame()

    def calibrate_camera(self):
        self.detection.calibrate_camera()

    def placeGame(self, configuration:str):
        self.referee.placeGame(configuration)

    def setTeamNames(self, team: str, name: str):
        self.referee.setTeamNames(team, name)

    def HalfTimeChangeColorField(self, xpos_goal:str):
        self.detection.HalfTimeChangeColorField(xpos_goal)

    def setTeamSides(self) -> str:
        self.referee.setTeamSides()

    def startHalfTime(self):
        self.referee.startHalfTime()

    def startSecondHalfTime(self):
        self.referee.startSecondHalfTime()

    def addPenalty(self, duration: int, robot: str):
        self.referee.addPenalty(duration, robot)

    def cancelPenalty(self, robot) -> str:
        self.referee.cancelPenalty(robot)
    
    def getFullGameState(self) -> dict:
        return self.referee.getFullGameState()
    
    def validateGoal(self, yes_no:bool):
        self.referee.validateGoal(yes_no)
