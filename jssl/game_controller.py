import os
import json
from flask import Flask, send_from_directory, jsonify, request
from .backend import Backend
from . import api

backend = Backend()

static = os.path.dirname(__file__)+'/static/'
app = Flask('Game controller', static_folder=static)

@app.route('/api', methods=['GET'])
def handle_api():
    if 'command' in request.args and 'args' in request.args:
        command = request.args['command']
        args = json.loads(request.args['args'])

        if command in api.methods:
            method = api.methods[command]
            for k in range(len(method['args'])):
                args[k] = method['args'][k](args[k])
            result = method['func'](backend, *args)
            return jsonify(result)
        else:
            return jsonify('Command not found')
    else:
        return jsonify('Error while processing command')

@app.route('/', methods=['GET'])
def main():
    return send_from_directory(static, 'index.html')

app.run('127.0.0.1', 7070)