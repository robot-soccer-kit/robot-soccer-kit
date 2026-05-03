import time
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
        "team_colors": [
            "green",
            "blue"
        ]
    }

ARUCO_MARKERS_IDS = ["c1", "c2", "c3", "c4", "green1", "green2", "blue1", "blue2"]

datas_to_log = {"constants" : USEFUL_CANVAS_CONSTANTS}
ready_to_record = False
recording = False
filepath = "rsk/logs/info_logs.json.gz"
lock = threading.Lock()
    
def log_data() -> None:
    json_str = json.dumps(datas_to_log) + "\n"
    json_bytes = json_str.encode('utf-8')

    with gzip.open(filepath, 'w') as fout:
        fout.write(json_bytes)


def register_info(key:str, data, key_prec:str = "") -> None:
    if recording and key != "constants":
        lock.acquire()

        if key_prec != "":
            if key_prec not in datas_to_log.keys():
                datas_to_log[key_prec] = {key : []}
            elif key not in datas_to_log[key_prec].keys():
                datas_to_log[key_prec][key] = []

            if len(datas_to_log[key_prec][key]) == 0 or datas_to_log[key_prec][key][-1]["data"] != data or "command" in key:
                datas_to_log[key_prec][key].append({"data" : copy.deepcopy(data), "timestamp" : time.perf_counter()})
        else:
            if key not in datas_to_log.keys():
                datas_to_log[key] = []
                
            if len(datas_to_log[key]) == 0 or datas_to_log[key][-1]["data"] != data or "command" in key:
                datas_to_log[key].append({"data" : copy.deepcopy(data), "timestamp" : time.perf_counter()})
        
        # if len(datas_to_log[key]) == 0 or datas_to_log[key][-1][0] != data or "command" in key:
        #     datas_to_log[key].append([copy.deepcopy(data),time.perf_counter()])
        lock.release()

def register_infos(keys:list[str], datas:dict, key_prec:str="", exclude:list[str] = []) -> None:
    for k in keys:
        if k in datas.keys() and k not in exclude:
            register_info(k, datas[k], key_prec)

def register_detection_info(aruco_ids):
    for i in range(len(ARUCO_MARKERS_IDS)):
        register_info(ARUCO_MARKERS_IDS[i], i in aruco_ids, "detection_markers")

def set_ready_to_record(ready:bool) -> None :
    global ready_to_record
    lock.acquire()
    ready_to_record = ready
    lock.release()

def set_recording(rec:bool) -> None:
    lock.acquire()
    global recording
    was_recording = recording
    recording = rec and ready_to_record
    lock.release()
    if not recording and was_recording:
        log_data()
        reset_record_data() # temporary

def reset_record_data() -> None:
    global datas_to_log
    lock.acquire()
    datas_to_log = {"constants" : USEFUL_CANVAS_CONSTANTS}
    lock.release()