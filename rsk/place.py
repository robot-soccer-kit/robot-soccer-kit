import argparse
import rsk
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument("--target", "-t", type=str, default="side")
parser.add_argument("--game-controller", "-g", type=str, default="127.0.0.1")
args = parser.parse_args()
with rsk.Client(args.game_controller) as client:
    if args.target not in rsk.client.configurations:
        print("Unknown target: " + args.target)
        exit()
    else:
        print("Placing to: " + args.target)

    try:
        client.goto_configuration(args.target)
    except KeyboardInterrupt:
        print("Interrupt, stopping robots")
