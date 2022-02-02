from . import api
from . import video, robots, control


class Backend():
    def __init__(self):
        super().__init__()

        self.video = video.Video()
        self.detection = self.video.detection
        self.robots = robots.Robots(self.detection)

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
    def allowControl(self, team, allow):
        self.robots.control.allowControl(team, allow)

    @api.slot()
    def emergency(self):
        self.robots.control.emergency()

    @api.slot(str, str)
    def setKey(self, team, key):
        self.robots.control.setKey(team, key)

    @api.slot()
    def identify(self):
        self.robots.identify()
