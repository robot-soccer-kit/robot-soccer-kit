import time
import os
from datetime import datetime
from . import constants
import json
import gzip
import threading

import copy

USEFUL_CANVAS_CONSTANTS = {
    "field_length": constants.field_length,
    "field_width": constants.field_width,
    "carpet_length": constants.carpet_length,
    "carpet_width": constants.carpet_width,
    "goal_width": constants.goal_width,
    "border_size": constants.border_size,
    "dots_x": constants.dots_x,
    "dots_y": constants.dots_y,
    "defense_area_width": constants.defense_area_width,
    "defense_area_length": constants.defense_area_length,
    "robot_tag_size": constants.robot_tag_size,
    "ball_radius": constants.ball_radius,
    "robot_radius": constants.robot_radius,
    "team_colors": ["green", "blue"],
}

ARUCO_MARKERS_IDS = ["c1", "c2", "c3", "c4", "green1", "green2", "blue1", "blue2"]

datas_to_log = {"constants": USEFUL_CANVAS_CONSTANTS}
ready_to_record = False
record_commands = False
path = os.path.join(os.getcwd(), "rsk_recorder", "")
filepath = ""
lock = threading.Lock()

recording = False


def log_data() -> None:
    json_str = json.dumps(datas_to_log) + "\n"
    json_bytes = json_str.encode("utf-8")

    if not os.path.exists(path):
        os.makedirs(path)
    filename = (
        "match_logs" + datetime.now().strftime("%Y_%m_%d_%H_%M_%S_%f")[:-3] + ".json.gz"
    )
    global filepath
    filepath = os.path.join(path, filename)
    print(f"Logging data to {filepath}")

    with gzip.open(filepath, "w") as fout:
        fout.write(json_bytes)


def register_info(key: str, data, prev_key: str = "", allow_repeat=False) -> None:
    if recording and key != "constants":
        lock.acquire()

        if prev_key != "":
            if prev_key not in datas_to_log.keys():
                datas_to_log[prev_key] = {key: []}
            elif key not in datas_to_log[prev_key].keys():
                datas_to_log[prev_key][key] = []

            if (
                len(datas_to_log[prev_key][key]) == 0
                or datas_to_log[prev_key][key][-1]["data"] != data
                or allow_repeat
            ):
                datas_to_log[prev_key][key].append(
                    {"data": copy.deepcopy(data), "timestamp": time.perf_counter()}
                )
        else:
            if key not in datas_to_log.keys():
                datas_to_log[key] = []

            if (
                len(datas_to_log[key]) == 0
                or datas_to_log[key][-1]["data"] != data
                or allow_repeat
            ):
                datas_to_log[key].append(
                    {"data": copy.deepcopy(data), "timestamp": time.perf_counter()}
                )

        lock.release()


def register_infos(
    keys: list[str],
    datas: dict,
    prev_key: str = "",
    exclude: list[str] = [],
    allow_repeat=False,
) -> None:
    for k in keys:
        if k in datas.keys() and k not in exclude:
            register_info(k, datas[k], prev_key, allow_repeat)


def register_position_frame(markers: dict, ball) -> None:
    """
    Register a complete position frame with all detected markers and ball.

    Args:
        markers: dict of detected markers {name: {position, orientation}}
        ball: ball position [x, y, z] or None
    """
    if recording:
        lock.acquire()

        if "positions" not in datas_to_log:
            datas_to_log["positions"] = []

        # Build frame entry
        frame_entry = {
            "timestamp": time.perf_counter(),
            "markers": copy.deepcopy(markers),
        }

        # Only include ball if detected (not None)
        if ball is not None:
            frame_entry["ball"] = copy.deepcopy(ball)

        datas_to_log["positions"].append(frame_entry)

        lock.release()


def register_detection_info(aruco_ids):
    try:
        for i in range(len(ARUCO_MARKERS_IDS)):
            register_info(ARUCO_MARKERS_IDS[i], i in aruco_ids, "detection_markers")
    except TypeError:
        pass


def register_command_info(key: str, data, prev_key: str = "", allow_repeat=False):
    if record_commands:
        register_info(key, data, prev_key, allow_repeat)


def set_ready_to_record(ready: bool) -> None:
    global ready_to_record
    lock.acquire()
    ready_to_record = ready
    lock.release()


def set_record_commands(yes_no: bool):
    global record_commands
    record_commands = yes_no


def set_recording(rec: bool) -> None:
    lock.acquire()
    global recording
    was_recording = recording
    recording = rec and ready_to_record
    lock.release()
    if recording:
        reset_filename()
    if not recording and was_recording:
        log_data()
        reset_record_data()


def reset_record_data() -> None:
    global datas_to_log
    lock.acquire()
    datas_to_log = {"constants": USEFUL_CANVAS_CONSTANTS}
    lock.release()


def reset_filename() -> None:
    global filepath
    lock.acquire()
    filepath = ""
    lock.release()
