import os
import argparse
import webbrowser
import json
import time
import logging
import threading
import waitress
from flask import Flask, send_from_directory, jsonify, request, make_response
from flask_cors import CORS
from .backend import Backend
from . import api, robot_wifi, config

static = os.path.dirname(__file__) + "/static/"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ip",
        "-ip",
        type=str,
        default="127.0.0.1",
        help="IP address for the server to listen on",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=str,
        default="7070",
        help="Port for the server to listen on",
    )
    parser.add_argument(
        "--simulated", "-s", action="store_true", help="Enables simulation mode"
    )
    parser.add_argument(
        "--competition", "-c", action="store_true", help="Enables competition mode"
    )
    parser.add_argument(
        "--scheduler", "-S", type=str, default="", help="Game scheduler URL"
    )
    parser.add_argument(
        "--reset", "-r", action="store_true", help="Reset the configuration file"
    )
    parser.add_argument(
        "--dry", "-d", action="store_true", help="Dry run without starting the server"
    )
    parser.add_argument(
        "--replay", "-R", type=str, default="", help="Enable replay mode"
    )
    return parser.parse_args(argv)


def send_file_response(filepath, mimetype, gzip=False):
    directory = os.path.dirname(os.path.abspath(filepath))
    filename = os.path.basename(filepath)
    response = make_response(
        send_from_directory(directory, filename, mimetype=mimetype)
    )
    if gzip:
        response.headers["Content-Encoding"] = "gzip"
    return response


def create_app(backend: Backend) -> Flask:
    """
    Creates the Flask app serving API requests and files of static/ directory

    :param Backend backend: the backend whose methods are exposed in the API
    :return Flask: the app
    """
    api.register(backend)

    app = Flask("Game controller", static_folder=static)
    CORS(app)

    # Set as soon as a client (browser) requested the API
    app.config["HAS_CLIENT"] = False

    @app.route("/api/recorded_data", methods=["GET"])
    def get_recorded_data():
        fp = backend.get_record_filepath()
        logging.info(f"get_record_filepath: '{fp}'")
        if fp == "" or not os.path.isfile(fp):
            return jsonify({"error": "No record file available"}), 404
        return send_file_response(fp, mimetype="application/octet-stream")

    if backend.replay_mode_file() != "":
        if not os.path.isfile(backend.replay_mode_file()):
            logging.error("replay file not found")
        else:

            @app.route("/api/replay_data", methods=["GET"])
            def get_replay_data():
                fp = backend.replay_mode_file()
                return send_file_response(fp, mimetype="application/json", gzip=True)

    @app.route("/api", methods=["GET"])
    def handle_api():
        app.config["HAS_CLIENT"] = True
        if "command" not in request.args or "args" not in request.args:
            return jsonify([0, "Error while processing command"])

        command = request.args["command"]
        try:
            args = json.loads(request.args["args"])
        except ValueError:
            return jsonify([0, f"Arguments for command {command} are not valid JSON"])

        return jsonify(api.call(command, args))

    @app.route("/api/calibration_board.png", methods=["GET"])
    def get_calibration_board():
        # Imported here: the lens calibration needs OpenCV (only for the real vision)
        import cv2
        from . import lens_calibration

        _, data = cv2.imencode(".png", lens_calibration.board_image())
        response = make_response(data.tobytes())
        response.headers["Content-Type"] = "image/png"
        response.headers["Content-Disposition"] = (
            'attachment; filename="calibration_board.png"'
        )
        return response

    @app.route("/", methods=["GET"])
    def main():
        return send_from_directory(static, "index.html")

    return app


def start_and_serve(argv=None):
    # Setting up the logger
    logging.basicConfig(
        format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("werkzeug").setLevel(logging.CRITICAL)
    logging.getLogger("robot-soccer-kit").info(
        "Starting robot-soccer-kit Game Controller"
    )

    args = parse_args(argv)

    if args.reset:
        config.reset()

    if (not args.dry) and (not args.simulated) and (args.replay == ""):
        robot_wifi.RobotWifi.start_service()

    backend = Backend(args.simulated, args.competition, args.scheduler, args.replay)
    app = create_app(backend)

    if args.dry:
        return

    def run_browser():
        # If no request arrived for 3s, starting a browser interface on local
        time.sleep(3)
        if not app.config["HAS_CLIENT"]:
            webbrowser.open(f"http://{args.ip}:{args.port}")

    # Starting browser thread
    thread = threading.Thread(target=run_browser, daemon=True, name="BrowserThread")
    thread.start()

    # Serving forever
    waitress.serve(app, listen="%s:%s" % (args.ip, args.port), threads=8)


if __name__ == "__main__":
    start_and_serve()
