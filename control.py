import zmq
import threading
import robots

# Publishing server
context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:7558")

teams = {
    "red": {
        "allow_control": True,
        "key": "",
        "packets": 0
    },
    "blue": {
        "allow_control": True,
        "key": "",
        "packets": 0
    }
}

def thread():
    while True:
        json = socket.recv_json()
        success = False

        if type(json) == list and len(json) == 4:
            key, team, robot, command = json

            if team in teams and teams[team]['key'] == key and teams[team]['allow_control']:
                marker = "%s%d" % (team, robot)
                if marker in robots.robots_by_marker:
                    if type(command) == list:
                        if command[0] == 'kick' and len(command) == 2:
                            robots.robots_by_marker[marker].kick(float(command[1]))
                            success = True
                        if command[0] == 'control' and len(command) == 4:
                            robots.robots_by_marker[marker].control(
                                float(command[1]), float(command[2]), float(command[3]))
                            success = True

            if success:
                teams[team]['packets'] += 1

        socket.send_json(success)

def start():
    control_thread = threading.Thread(target=thread)
    control_thread.start()

def status():
    return teams

def allowControl(team, allow):
    global teams
    teams[team]['allow_control'] = allow

def emergency():
    allowControl('red', False)
    allowControl('blue', False)

    for port in robots.robots:
        robots.robots[port].control(0, 0, 0)

def setKey(team, key):
    teams[team]['key'] = key