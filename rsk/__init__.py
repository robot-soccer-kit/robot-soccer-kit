"""
Robot Soccer Kit: the client API used by the teams (rsk.Client), and the Game Controller
(python -m rsk.game_controller)
"""

from . import constants, utils
from .client import Client

__all__ = ["constants", "utils", "Client"]
