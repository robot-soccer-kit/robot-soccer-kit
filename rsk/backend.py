from . import api
from . import video, robots, control, field, referee


class Backend():
    def __init__(self):
        super().__init__()

        self.video = video.Video()
        self.detection = self.video.detection
        self.robots = robots.Robots(self.detection)
        self.referee = referee.Referee(self.detection, self.robots)

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

    def addRobot(self, port: str):
        self.robots.addRobot(port)

    def getRobots(self):
        return self.robots.getRobots()

    def setMarker(self, port: str, marker: str):
        self.robots.setMarker(port, marker)

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

    def allowTeamControl(self, team: str, allow: bool):
        self.robots.control.allowTeamControl(team, allow)

    def emergency(self):
        self.robots.control.emergency()

    def setKey(self, team: str, key: str):
        self.robots.control.setKey(team, key)

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

    def setDisplaySettings(self, display_settings: list):
        self.detection.setDisplaySettings(display_settings)

    def saveDisplaySettings(self):
        self.detection.saveDisplaySettings()

    def getDisplaySettings(self) -> list:
        return self.detection.getDisplaySettings()

    def getDefaultDisplaySettings(self) -> list:
        return self.detection.getDefaultDisplaySettings()

    def startGame(self):
        self.referee.startGame()

    def pauseGame(self):
        self.referee.pauseGame()

    def resumeGame(self):
        self.referee.resumeGame()

    def stopGame(self):
        self.referee.stopGame()

    def calibrateCamera(self):
        self.detection.calibrateCamera()

    def placeGame(self):
        self.referee.placeGame()

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
