import argparse
import numpy as np
import time
import rsk


parser = argparse.ArgumentParser()
parser.add_argument("--team", "-t", type=str, default="blue")
parser.add_argument("--game-controller", "-g", type=str, default="127.0.0.1")
parser.add_argument("--key", "-k", type=str, default="")
args = parser.parse_args()
team = args.team

with rsk.Client(args.game_controller, args.key) as client:
    start = time.time()

    def try_goto(team, number, x, y):
        try:
            client.robots[team][number].goto((x, y, orientation), wait=False)
        except rsk.client.ClientError as e:
            pass

    while True:
        positive = client.referee["teams"][team]["x_positive"]
        sign = 1 if positive else -1
        orientation = np.pi if positive else 0
        t = time.time() - start

        try_goto(team, 1, sign * rsk.constants.field_length / 4, np.sin(t * 1.1 + 1) * rsk.constants.goal_width / 2)
        try_goto(team, 2, sign * rsk.constants.field_length / 2, np.sin(t) * rsk.constants.goal_width / 2)

        time.sleep(0.01)
