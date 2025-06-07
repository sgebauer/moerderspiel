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

    #TODO

    # def get_player(self, player: str | Player) -> Player:
    #     if isinstance(player, Player) and player.game != self.game:
    #         raise RuntimeError("Got player from another game")
    #     elif isinstance(player, Player):
    #         return player
    #     else:
    #         player = Player.by_game_and_name(self.game, player)
    #         if not player:
    #             raise GameError("Player does not exist")
    #         return player
    #
    # def add_notification_address(self, player: str | Player, type: NotificationAddressType, address: str):
    #     self.game.add(NotificationAddress(
    #         player=self.get_player(player),
    #         type=type,
    #         address=address,
    #         active=True
    #     ))
    #
    #     if self.game.state == GameState.running:
    #         self.send_mission_update(player)
    #
    #
    # def delete_player_from_circle(self, circle: Circle | str):
    #     if self.game.started:
    #         raise GameError("Game has already been started")
    #
    #     self.get_circle(circle).delete()
    #
    # def add_player_to_circle(self, player: str | Player, circle: str | Circle):
    #     player = self.get_player(player)
    #     circle = self.get_circle(circle)
    #
    #     if Mission.by_victim_in_circle(player, circle):
    #         raise GameError(f"Player '{player.name}' is already part of circle '{circle.name}'")
    #
    #     self.playergame.add(Mission(circle=circle, victim=player))




