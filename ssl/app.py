from PyQt5 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets, QtWebChannel
import os, sys
from .backend import Backend
from . import robots

os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '5422'

app = QtWidgets.QApplication(sys.argv)
app.setApplicationName("Junior SSL")
app.setWindowIcon(QtGui.QIcon('ball.png'))

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
