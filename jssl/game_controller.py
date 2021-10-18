from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets, QtWebChannel
import os, sys
from .backend import Backend
from . import robots

os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '5422'

app = QtWidgets.QApplication(sys.argv)
app.setApplicationName("Junior SSL - Game Controller")
dirname = os.path.dirname(__file__)
app_icon = QtGui.QIcon()
app_icon.addFile(dirname+'/imgs/ball_16x16.png', QtCore.QSize(16,16))
app_icon.addFile(dirname+'/imgs/ball_24x24.png', QtCore.QSize(24,24))
app_icon.addFile(dirname+'/imgs/ball_32x32.png', QtCore.QSize(32,32))
app_icon.addFile(dirname+'/imgs/ball_48x48.png', QtCore.QSize(48,48))
app_icon.addFile(dirname+'/imgs/ball_256x256.png', QtCore.QSize(256,256))
print(dirname+'/imgs/256x256.png')
app.setWindowIcon(app_icon)

backend = Backend()

view = QtWebEngineWidgets.QWebEngineView()

channel = QtWebChannel.QWebChannel()
view.page().setWebChannel(channel)
channel.registerObject("backend", backend)

current_dir = os.path.dirname(os.path.realpath(__file__))
filename = os.path.join(current_dir, "index.html")
url = QtCore.QUrl.fromLocalFile(filename)
view.load(url)

view.resize(1024, 720)
view.show()

r = app.exec_()
backend.exit()
sys.exit(r)
