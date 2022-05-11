import yaml
import rsk
import sys
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--team", "-t", type=str, default="side")
parser.add_argument("--game-controller", "-g", type=str, default="127.0.0.1")
args = parser.parse_args()

with rsk.Client(args.game_controller) as client:

    def show(client, elapsed):
        data = "\n" * 8 + yaml.dump(client.referee, allow_unicode=True, default_flow_style=False)
        sys.stdout.write(data)
        sys.stdout.flush()

    client.on_update = show

    while True:
        time.sleep(1)
