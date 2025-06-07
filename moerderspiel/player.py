from __future__ import annotations

import random

from moerderspiel import notification, pdf
from moerderspiel.db import GameState, Game, Circle, Player, Mission, NotificationAddressType, NotificationAddress
from moerderspiel.game import GameError

from datetime import datetime
from sqlalchemy.orm import Session
from typing import List

class PlayerService:
    def __init__(self, player: Player):
        self.player = player

    #TODO t.b.c




