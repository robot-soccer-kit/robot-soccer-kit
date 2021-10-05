import argparse
from .client import Client, ClientError, configurations
import numpy as np
import time
from .client import Client, ClientError
from . import field


with Client() as client:
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', '-t', type=str, default='side')
    args = parser.parse_args()

    if args.target not in configurations:
        print('Unknown target: '+args.target)
        exit()
    else:
        print('Placing to: '+args.target)

    try:
        client.goto_configuration(args.target)
    except KeyboardInterrupt:
        print('Interrupt, stopping robots')
