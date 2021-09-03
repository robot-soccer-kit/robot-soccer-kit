from serial.tools import list_ports
import time
import robot

robots = {}

def addRobot(port):
    global robots

    if port not in robots:
        robots[port] = robot.Robot(port)

def getRobots():
    data = {}
    for entry in robots:
        data[entry] = {
            'state': robots[entry].state,
            'marker': robots[entry].marker,
            'last_message': time.time() - robots[entry].last_message if robots[entry].last_message is not None else None
        }

    return data

def setMarker(port, marker):
    if port in robots:
        robots[port].setMarker(marker)

def remove(port):
    global robots

    robots[port].close()
    del robots[port]

ports = [entry.device for entry in list_ports.comports()]
