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
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import socket
from .backend import Backend
from . import api


# Setting up the logger
logging.basicConfig(format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s", level=logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
logging.getLogger("robot-soccer-kit").info("Starting robot-soccer-kit Game Controller")

parser = argparse.ArgumentParser()
parser.add_argument("--port", "-p", type=str, default="7070")
parser.add_argument("--ip", "-ip", type=str, default="127.0.0.1")
parser.add_argument("--simulated", "-s", action="store_true")
parser.add_argument("--remote", "-r", action="store_true")
parser.add_argument("--competition", "-c", action="store_true")
args = parser.parse_args()

auth = HTTPBasicAuth()
users = {
    "admin": "scrypt:32768:8:1$j9gQIiONIsQ6wenA$7da7778a7ff169a35426ccbb3fc7b5bb5d766a59bb60273d0e08d63d1c36d95c6522b61a8320d5ba6d43ecc247d14fffc367fe2634e9f31311e53f7b09f288d1",
}


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username


has_client: bool = False
backend: Backend = Backend(args.simulated, args.competition)
api.register(backend)

# Starting a Flask app serving API requests and files of static/ directory

static = os.path.dirname(__file__) + "/static/"
app = Flask("Game controller", static_folder=static)
CORS(app)


static_pub = os.path.dirname(__file__) + "/static/"
app_public = Flask("Game controller", static_folder=static_pub)
CORS(app_public)

static_pub = os.path.dirname(__file__) + "/static/"


def create_app_and_send(ip):
    with open(static_pub + "/js/appModel.js", "r") as f:
        data = f.read()
        data = data.replace("IP_HERE", ip)
    with open(static_pub + "/js/app.js", "w") as f:
        f.write(data)

    return send_from_directory(static_pub, "index.html")


@app.route("/api", methods=["GET"])
@app_public.route("/api", methods=["GET"])
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


@app_public.route("/", methods=["GET"])
@auth.login_required
def mainPub():
    return create_app_and_send(socket.gethostbyname(socket.gethostname()))


@app.route("/", methods=["GET"])
def main():
    return create_app_and_send(args.ip)


def run_browser():
    # If no request arrived for 3s, starting a browser interface on local
    time.sleep(3)
    if not has_client:
        webbrowser.open(f"http://{args.ip}:{args.port}")


def run_waitress_public():
    waitress.serve(app_public, listen="%s:%s" % (socket.gethostbyname(socket.gethostname()), args.port), threads=8)


thread = threading.Thread(target=run_browser)
thread.start()

if args.remote:
    thread = threading.Thread(target=run_waitress_public)
    thread.start()

# Serving forever
waitress.serve(app, listen="%s:%s" % (args.ip, args.port), threads=8)
