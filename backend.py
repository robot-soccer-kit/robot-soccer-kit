from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel
from PyQt5.QtCore import QVariant
import video

class Backend(QtCore.QObject):
    @QtCore.pyqtSlot(result=QVariant)
    def cameras(self):
        return QVariant(video.cameras)

    @QtCore.pyqtSlot(int, result=bool)
    def startCapture(self, index):
        return video.startCapture(index)

    @QtCore.pyqtSlot(result=str)
    def getImage(self):
        image = video.getImage()
        return image

    @QtCore.pyqtSlot(int, int, result=bool)
    def cameraSettings(self, brightness, contrast):
        video.setCameraSettings(brightness, contrast)
        return True

