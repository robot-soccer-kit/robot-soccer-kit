import os
import json

config = {}

if os.path.exists('config.json'):
    with open('config.json', 'r') as file:
        config = json.load(file)

def save():
    with open('config.json', 'w') as file:
        json.dump(config, file)


