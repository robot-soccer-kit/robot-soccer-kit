from serial.tools import list_ports
import robot

robots = []

def addRobot(port):
    global robots

    print('Creating robot for '+port)
    robots += robot.Robot(port)

ports = [entry.device for entry in list_ports.comports()]
