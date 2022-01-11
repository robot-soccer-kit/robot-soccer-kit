import os
import webbrowser
import json
import time
import logging
import threading
import waitress
from flask import Flask, send_from_directory, jsonify, request
from .backend import Backend
from . import api

has_client = False
backend = Backend()

static = os.path.dirname(__file__)+'/static/'
app = Flask('Game controller', static_folder=static)


@app.route('/api', methods=['GET'])
def handle_api():
    global has_client
    has_client = True
    if 'command' in request.args and 'args' in request.args:
        command = request.args['command']
        args = json.loads(request.args['args'])

        if command in api.methods:
            method = api.methods[command]
            for k in range(len(method['args'])):
                args[k] = method['args'][k](args[k])
            result = method['func'](backend, *args)
            return jsonify([1,result])
        else:
            return jsonify([0,'Command %s not found' % command])
    else:
        return jsonify([0,'Error while processing command'])


@app.route('/', methods=['GET'])
def main():
    return send_from_directory(static, 'index.html')

logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(name)s - %(message)s', level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.CRITICAL)
logging.getLogger('junior-ssl').info('Starting Junior-SSL Game Controller')

def run_browser():
    time.sleep(3)
    if not has_client:
        webbrowser.open('http://127.0.0.1:7070')


t = threading.Thread(target=run_browser)
t.start()

waitress.serve(app, listen='127.0.0.1:7070')