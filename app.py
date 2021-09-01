import robots
from PyQt5 import QtCore, QtWidgets, QtWebEngineWidgets, QtWebChannel
from backend import Backend
import os, sys

os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '5422'

app = QtWidgets.QApplication(sys.argv)
app.setApplicationName("Junior SSL")

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
sys.exit(app.exec_())