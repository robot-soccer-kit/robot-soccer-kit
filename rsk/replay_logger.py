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

datas_to_log = {"constants" : USEFUL_CANVAS_CONSTANTS}
recording = False
filepath = "rsk/logs/info_logs.json.gz"
lock = threading.Lock()
    
def log_data() -> None:
    json_str = json.dumps(datas_to_log) + "\n"
    json_bytes = json_str.encode('utf-8')

    with gzip.open(filepath, 'w') as fout:
        fout.write(json_bytes)


def register_info(key:str, data) -> None:
    if recording and key != "constants":
        lock.acquire()
        if key not in datas_to_log.keys():
            datas_to_log[key] = []
        if len(datas_to_log[key]) == 0 or datas_to_log[key][-1]["data"] != data or "command" in key:
            datas_to_log[key].append({"data" : copy.deepcopy(data), "timestamp" : time.perf_counter()})
        # if len(datas_to_log[key]) == 0 or datas_to_log[key][-1][0] != data or "command" in key:
        #     datas_to_log[key].append([copy.deepcopy(data),time.perf_counter()])
        lock.release()

def register_infos(keys:list[str], datas:dict, exclude:list[str] = []) -> None:
    for k in keys:
        if k in datas.keys() and k not in exclude:
            register_info(k, datas[k])

def toggle_recording() -> None:
    global recording
    lock.acquire()
    recording = not recording
    lock.release()
    if not recording :
        log_data()
        reset_record_data() # temporary

def reset_record_data() -> None:
    global datas_to_log
    lock.acquire()
    datas_to_log = {"constants" : USEFUL_CANVAS_CONSTANTS}
    lock.release()

# def process_state_info(infos:dict) -> None :
#     if recording:
#         lock.acquire()
#         datas["states"].append({"data" : infos.copy(), "timestamp" : time.time()})
#         lock.release()




# class ReplayLogger :
#     def __init__(self):
#         self.datas = {"states" : [], "commands" : [], "constants" : USEFUL_CANVAS_CONSTANTS}
#         self.recording = False
#         self.filepath = "rsk/logs/info_logs.json.gz"

    
#     def log_data(self) -> None:
#         json_str = json.dumps(self.datas) + "\n"
#         json_bytes = json_str.encode('utf-8')

#         with gzip.open(self.filepath, 'w') as fout:
#             fout.write(json_bytes)

#     def data_from_get_state(self, state: dict) -> dict :
#         data = {}
#         for m in state["markers"]:
#             data[m] = state["markers"][m]["position"] + [ state["markers"][m]["orientation"] ]
#         data["ball"] = state["ball"]
#         data["leds"] = state["leds"].copy()
#         return data
    
#     def data_from_game_state(self, state: dict) -> dict :
#         # data = {}
#         # for team in state["teams"]:
#         #     data[team] = {"score" : state["teams"][team]["score"],"robots" : state["teams"][team]["robots"]}
#         # return data
#         return state
    
#     # def process_command(self, command: str, args:list, result: dict) -> None :

#     #     if command == "start_game":
#     #         self.recording = True
#     #     if self.recording:
#     #         if result == None : # commande d'action et non requête d'état
#     #             received_cmd = command + "("+ ", ".join([str(arg) for arg in args]) + ")"
#     #             self.datas["commands"].append({"data" : received_cmd, "timestamp" : time.time()})
#     #         if command == "get_state" :
#     #             data = self.data_from_get_state(result)
#     #             self.datas["states"].append({"data" : data, "timestamp" : time.time()})
#     #         elif command == "get_game_state":
#     #             data = self.data_from_game_state(result)
#     #             self.datas["states"].append({"data" : data, "timestamp" : time.time()})
#     #         elif command == "stop_game" : 
#     #             self.log_data()
#     #             self.recording = False
    
#     def process_state_info(self, infos:dict) -> None :
#         if self.recording:
#             self.datas["states"].append({"data" : infos.copy(), "timestamp" : time.time()})

#     # def register_consts_in_data(self, constants: dict):
#     #     self.datas["constants"] = {
#     #         key: value 
#     #         for key, value in constants.items() 
#     #         if key in USEFUL_CANVAS_CONSTANTS
#     #     }

#     def toggle_recording(self):
#         self.recording = not self.recording
#         if(not self.recording):
#             self.log_data()


#     # def read_datas(self):
#     #     with gzip.open(self.filepath, 'r') as fin:
#     #         data = json.loads(fin.read().decode('utf-8'))
#             # print(data)
#             # print(len(data))
#             # print(random.sample(data,10))
