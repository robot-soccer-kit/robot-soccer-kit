from . import api
from . import video, robots, control, field, referee


class Backend():
    def __init__(self):
        super().__init__()

        self.video = video.Video()
        self.detection = self.video.detection
        self.robots = robots.Robots(self.detection)
        self.referee = referee.Referee(self.detection)

    def exit(self):
        self.video.stop()
        self.robots.stop()

    @api.slot()
    def cameras(self):
        return self.video.cameras()

    @api.slot()
    def resolutions(self):
        return self.video.resolutions()

    @api.slot()
    def getCameraSettings(self):
        return self.video.settings

    @api.slot(int, int, result=bool)
    def startCapture(self, index, res):
        return self.video.startCapture(index, res)

    @api.slot()
    def stopCapture(self):
        self.video.stopCapture()

    @api.slot(result=str)
    def getImage(self):
        image = self.video.getImage()
        print(image)
        return image

    @api.slot(bool)
    def getVideo(self, with_image):
        return self.video.getVideo(with_image)

    @api.slot(bool)
    def enableVideoDebug(self, enable=True):
        self.video.debug = enable

    @api.slot()
    def cameraSettings(self, settings):
        self.video.setCameraSettings(settings)
        return True

    @api.slot()
    def ports(self):
        return self.robots.ports()

    @api.slot(str)
    def addRobot(self, port):
        self.robots.addRobot(port)

    @api.slot()
    def getRobots(self):
        return self.robots.getRobots()

    @api.slot(str, str)
    def setMarker(self, port, marker):
        self.robots.setMarker(port, marker)

    @api.slot(str)
    def removeRobot(self, port):
        self.robots.remove(port)

    @api.slot(str)
    def blink(self, port):
        if port in self.robots.robots:
            self.robots.robots[port].blink()

    @api.slot(str)
    def kick(self, port):
        if port in self.robots.robots:
            self.robots.robots[port].kick()

    @api.slot()
    def getGame(self):
        return self.robots.control.status()

    @api.slot(str, bool)
    def allowTeamControl(self, team, allow):
        self.robots.control.allowTeamControl(team, allow)

    @api.slot()
    def emergency(self):
        self.robots.control.emergency()

    @api.slot(str, str)
    def setKey(self, team, key):
        self.robots.control.setKey(team, key) 

    @api.slot()
    def identify(self):
        self.robots.identify()

    @api.slot()
    def startReferee(self):
        self.referee.startReferee()

    @api.slot()
    def stopReferee(self):
        self.referee.stopReferee()
    
    @api.slot(str, int)
    def updateScore(self, team, increment):
        self.referee.updateScore(team, increment)
    
    @api.slot()
    def resetScore(self):
        self.referee.resetScore()
    
    @api.slot(str, result=int)
    def getScore(self, team):
        return self.referee.getScore(team)
    
    @api.slot(list)
    def setDisplaySettings(self, display_settings):
        self.detection.setDisplaySettings(display_settings)
    
    @api.slot()
    def saveDisplaySettings(self):
        self.detection.saveDisplaySettings()
    
    @api.slot(result=list)
    def getDisplaySettings(self):
        return self.detection.getDisplaySettings()

    @api.slot(result=list)
    def getDefaultDisplaySettings(self):
        return self.detection.getDefaultDisplaySettings()

    @api.slot()
    def startGame(self):
        self.referee.startGame()
    
    @api.slot()
    def pauseGame(self):
        self.referee.pauseGame()

    @api.slot()
    def resumeGame(self):
        self.referee.resumeGame()
    
    @api.slot()
    def stopGame(self):
        self.referee.stopGame()

    @api.slot()
    def homographyRefresh(self):
        self.detection.homographyRefresh()

    @api.slot(result = list)
    def getTimer(self):
        return self.referee.getTimer()

    @api.slot(int, result = list)
    def getRefereeHistory(self, slice):
        return self.referee.getRefereeHistory(slice)

    @api.slot()
    def placeGame(self):
        self.referee.placeGame()
    
    @api.slot(result = str)
    def getGameState(self):
        return self.referee.getGameState()
    
    @api.slot(str, str)
    def setTeamNames(self,team,name):
        self.referee.setTeamNames(team,name)

    @api.slot(result = str)
    def MidTimeChangeColorField(self):
        self.detection.MidTimeChangeColorField()
    
    @api.slot(result = str)
    def setTeamSides(self):
        self.referee.setTeamSides()
    
    @api.slot()
    def startHalfTime(self):
        self.referee.startHalfTime()

    @api.slot()
    def startSecondHalfTime(self):
        self.referee.startSecondHalfTime()

    @api.slot(int, str)
    def addPenalty(self, duration, robot):
        self.referee.addPenalty(duration, robot)
    
    @api.slot(str)
    def cancelPenalty(self, robot):
        self.referee.cancelPenalty(robot)

    @api.slot(result = dict)
    def getPenalty(self):
        return self.referee.getPenalty()

    @api.slot(float)
    def setCameraheight(self, camera_height):
        self.detection.setCameraheight(camera_height)

    @api.slot(result = int)
    def getCameraheight(self):
        return self.detection.getCameraheight()
