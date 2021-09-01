from serial.tools import list_ports

ports = [entry.device for entry in list_ports.comports()]
