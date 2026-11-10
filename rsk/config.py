"""
Configuration of the Game Controller (robots, camera, display settings...), saved in a JSON
file. Modules read and change the `config` dict, then call save().
"""

import json
import logging
import os
import threading

logger = logging.getLogger("config")

config = {}
filename = os.path.dirname(__file__) + "/../config.json"
# Saves can come from several threads (API requests)
lock = threading.Lock()


def load():
    """
    Loads the configuration file (done when this module is imported). If it can't be read, the
    default configuration is used, and the file is kept aside (renamed, not overwritten)
    """
    global config
    config = {}
    if not os.path.exists(filename):
        return
    try:
        with open(filename, "r") as file:
            config = json.load(file)
    except (OSError, ValueError) as error:
        logger.warning(
            f"The configuration file {filename} can't be read ({error}): it is renamed to "
            f"{filename}.broken, the default configuration is used"
        )
        try:
            os.replace(filename, filename + ".broken")
        except OSError:
            pass


def save():
    """
    Saves the configuration. The file is written then renamed: an interrupted save never leaves
    an invalid file
    """
    with lock:
        temporary = filename + ".tmp"
        with open(temporary, "w") as file:
            json.dump(config, file)
        os.replace(temporary, filename)


def reset():
    """
    Resets (and saves) the configuration
    """
    global config
    config = {}
    save()


load()
