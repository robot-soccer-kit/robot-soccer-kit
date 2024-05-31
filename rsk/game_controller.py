import os
import argparse
import webbrowser
import json
import time
import logging
import threading
import waitress
from flask import Flask, send_from_directory, jsonify, request
from flask_cors import CORS
from .backend import Backend
from . import api, robot_wifi


# Setting up the logger
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s", level=logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
logging.getLogger("robot-soccer-kit").info("Starting robot-soccer-kit Game Controller")

parser = argparse.ArgumentParser()
parser.add_argument("--port", "-p", type=str, default="7070")
parser.add_argument("--ip", "-ip", type=str, default="127.0.0.1")
parser.add_argument("--simulated", "-s", action="store_true")
parser.add_argument("--competition", "-c", action="store_true")
parser.add_argument("--wifi-network", "-w", type=str, default="192.168.100.0")
parser.add_argument("--wifi-subnet", "-ws", type=str, default="255.255.255.0")
args = parser.parse_args()

robot_wifi.RobotWifi.network = args.wifi_network
robot_wifi.RobotWifi.netmask = args.wifi_subnet
robot_wifi.RobotWifi.start_service()

has_client: bool = False
backend: Backend = Backend(args.simulated, args.competition)
api.register(backend)

# Starting a Flask app serving API requests and files of static/ directory
static = os.path.dirname(__file__) + "/static/"
app = Flask("Game controller", static_folder=static)
CORS(app)


@app.route("/api", methods=["GET"])
def handle_api():
    global has_client
    has_client = True
    if "command" in request.args and "args" in request.args:
        command = request.args["command"]
        args = json.loads(request.args["args"])

        if command in api.methods:
            try:
                method = api.methods[command]
                for k in range(len(method["args"])):
                    if method["args"][k] is not None:
                        args[k] = method["args"][k](args[k])
                result = method["func"](*args)

                return jsonify([1, result])
            except ValueError:
                return jsonify([0, "Bad argument type for command %s" % command])
        else:
            return jsonify([0, "Command %s not found" % command])
    else:
        return jsonify([0, "Error while processing command"])


@app.route("/", methods=["GET"])
def main():
    return send_from_directory(static, "index.html")


def run_browser():
    # If no request arrived for 3s, starting a browser interface on local
    time.sleep(3)
    if not has_client:
        webbrowser.open(f"http://{args.ip}:{args.port}")


thread = threading.Thread(target=run_browser)
thread.start()

# Serving forever
waitress.serve(app, listen="%s:%s" % (args.ip, args.port), threads=8)
