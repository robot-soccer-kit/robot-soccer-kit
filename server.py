import zmq


context = zmq.Context()
socket = context.socket(zmq.PUSH)
socket.bind("tcp://*:" + 7557)