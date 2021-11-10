from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel
from PyQt5.QtCore import QVariant
from . import video, robots, control


class Backend(QtCore.QObject):
    def __init__(self):
        super().__init__()

        self.video = video.Video()
        self.detection = self.video.detection
        self.robots = robots.Robots(self.detection)

    def exit(self):
        self.video.stop()
        self.robots.stop()

    @QtCore.pyqtSlot(result=QVariant)
    def cameras(self):
        return QVariant(self.video.cameras())

    @QtCore.pyqtSlot(result=QVariant)
    def resolutions(self):
        return QVariant(self.video.resolutions())

    @QtCore.pyqtSlot(result=QVariant)
    def getCameraSettings(self):
        return QVariant(self.video.settings)

    @QtCore.pyqtSlot(int, int, result=bool)
    def startCapture(self, index, res):
        return self.video.startCapture(index, res)

    @QtCore.pyqtSlot()
    def stopCapture(self):
        self.video.stopCapture()

    @QtCore.pyqtSlot(result=str)
    def getImage(self):
        image = self.video.getImage()
        return image

    @QtCore.pyqtSlot(bool, result=QVariant)
    def getVideo(self, with_image):
        return QVariant(self.video.getVideo(with_image))

    @QtCore.pyqtSlot(bool)
    def enableVideoDebug(self):
        self.video.debug = True

    @QtCore.pyqtSlot(QVariant, result=bool)
    def cameraSettings(self, settings):
        self.video.setCameraSettings(settings)
        return True

    @QtCore.pyqtSlot(result=QVariant)
    def ports(self):
        return self.robots.ports()

    @QtCore.pyqtSlot(str)
    def addRobot(self, port):
        self.robots.addRobot(port)

    @QtCore.pyqtSlot(result=QVariant)
    def getRobots(self):
        return self.robots.getRobots()

    @QtCore.pyqtSlot(str, str)
    def setMarker(self, port, marker):
        self.robots.setMarker(port, marker)

    @QtCore.pyqtSlot(str)
    def removeRobot(self, port):
        self.robots.remove(port)

    @QtCore.pyqtSlot(str)
    def blink(self, port):
        if port in self.robots.robots:
            self.robots.robots[port].blink()

    @QtCore.pyqtSlot(str)
    def kick(self, port):
        if port in self.robots.robots:
            self.robots.robots[port].kick()

    @QtCore.pyqtSlot(result=QVariant)
    def getGame(self):
        return self.robots.control.status()

    @QtCore.pyqtSlot(str, bool)
    def allowControl(self, team, allow):
        self.robots.control.allowControl(team, allow)

    @QtCore.pyqtSlot()
    def emergency(self):
        self.robots.control.emergency()

    @QtCore.pyqtSlot(str, str)
    def setKey(self, team, key):
        self.robots.control.setKey(team, key)

    @QtCore.pyqtSlot()
    def identify(self):
        self.robots.identify()
