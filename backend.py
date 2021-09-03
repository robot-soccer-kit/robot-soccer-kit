from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel
from PyQt5.QtCore import QVariant
import video
import robots
import detection

class Backend(QtCore.QObject):
    @QtCore.pyqtSlot(result=QVariant)
    def cameras(self):
        return QVariant(video.cameras)

    @QtCore.pyqtSlot(int, result=bool)
    def startCapture(self, index):
        return video.startCapture(index)

    @QtCore.pyqtSlot()
    def stopCapture(self):
        video.stopCapture()

    @QtCore.pyqtSlot(result=str)
    def getImage(self):
        image = video.getImage()
        return image

    @QtCore.pyqtSlot(result=QVariant)
    def getVideo(self):
        return QVariant(video.getVideo())

    @QtCore.pyqtSlot(bool)
    def enableVideoDebug(self):
        video.debug = True

    @QtCore.pyqtSlot(int, int, int, result=bool)
    def cameraSettings(self, brightness, contrast, saturation):
        video.setCameraSettings(brightness, contrast, saturation)
        return True

    @QtCore.pyqtSlot(result=QVariant)
    def listPorts(self):
        return robots.ports
    
    @QtCore.pyqtSlot(str)
    def addRobot(self, port):
        robots.addRobot(port)

    @QtCore.pyqtSlot(result=QVariant)
    def getRobots(self):
        return robots.getRobots()

    @QtCore.pyqtSlot(str, str)
    def setMarker(self, port, marker):
        robots.setMarker(port, marker)

    @QtCore.pyqtSlot(str)
    def removeRobot(self, port):
        robots.remove(port)

    @QtCore.pyqtSlot(str)
    def blink(self, port):
        robots.blink(port)
    
