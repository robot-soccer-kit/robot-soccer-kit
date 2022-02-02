import argparse
from .client import Client, ClientError, configurations
import numpy as np
import time
from .client import Client, ClientError
from . import field


parser = argparse.ArgumentParser()
parser.add_argument('--target', '-t', type=str, default='side')
parser.add_argument('--game-controller', '-g', type=str, default='127.0.0.1')
args = parser.parse_args()
with Client(args.game_controller) as client:
    if args.target not in configurations:
        print('Unknown target: '+args.target)
        exit()
    else:
        print('Placing to: '+args.target)

    try:
        client.goto_configuration(args.target)
    except KeyboardInterrupt:
        print('Interrupt, stopping robots')
