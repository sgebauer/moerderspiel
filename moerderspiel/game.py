import random

from moerderspiel import notification, pdf
from moerderspiel.db import GameState, Game, Circle, Player, Mission, NotificationAddressType, NotificationAddress

from datetime import datetime
from sqlalchemy.orm import Session
from typing import List


class GameError(RuntimeError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class GameService:
    def __init__(self, game: Game):
        self.game = game

    def get_player(self, player: str | Player) -> Player:
        if isinstance(player, Player) and player.game != self.game:
            raise RuntimeError("Got player from another game")
        elif isinstance(player, Player):
            return player
        else:
            player = Player.by_game_and_name(self.game, player)
            if not player:
                raise GameError("Player does not exist")
            return player

    def get_circle(self, circle: str | Circle) -> Circle:
        if isinstance(circle, Circle) and circle.game != self.game:
            raise RuntimeError("Got circle from another game")
        elif isinstance(circle, Circle):
            return circle
        else:
            circle = Circle.by_game_and_name(self.game, circle)
            if not circle:
                raise GameError("Circle does not exist")
            return circle

    def add_player(self, name: str, **kwargs) -> Player:
        if self.game.state != GameState.new:
            raise GameError("Game has already been started")
        elif Player.by_game_and_name(self.game, name):
            raise GameError(f"A player named {name} already exists in this game")

        player = Player(game=self.game, name=name, **kwargs)
        self.game.add(player)
        return player

    def add_notification_address(self, player: str | Player, type: NotificationAddressType, address: str):
        self.game.add(NotificationAddress(
            player=self.get_player(player),
            type=type,
            address=address,
            active=True
        ))

        if self.game.state == GameState.running:
            send_mission_update(player)

    def add_circle(self, name: str, **kwargs) -> Circle:
        if self.game.state != GameState.new:
            raise GameError("Game has already been started")
        elif Circle.by_game_and_name(self.game, name):
            raise GameError(f"A circle named {name} already exists in this game")

        circle = Circle(game=self.game, name=name, **kwargs)
        self.game.add(circle)
        return circle

    def add_player_to_circle(self, player: str | Player, circle: str | Circle):
        player = self.get_player(player)
        circle = self.get_circle(circle)

        if Mission.by_victim_in_circle(player, circle):
            raise GameError(f"Player '{player.name}' is already part of circle '{circle.name}'")

        self.game.add(Mission(circle=circle, victim=player))

    def shuffle_circle(self, circle: str | Circle) -> None:
        if self.game.state != GameState.new:
            raise GameError("Game has already been started")

        missions = list(self.get_circle(circle).missions)
        random.shuffle(missions)

        previous_mission = None
        for position in range(len(missions)):
            mission = None

            # Avoid placing players from the same group next to each other in the circle. In our (already shuffled) list
            # of missions-to-place, try to find the first one that belongs to a different group than the previous
            # mission we placed.
            for i in range(len(missions)):
                mission = missions[i]
                if not previous_mission or not previous_mission.victim.group \
                        or mission.victim.group != previous_mission.victim.group:
                    del missions[i]
                    break

            mission.position = position
            previous_mission = mission

    def start_game(self):
        if self.game.state != GameState.new:
            raise GameError("Game has already been started")
        elif not self.game.circles:
            raise GameError("Game does not have any circles")
        elif not self.game.players:
            raise GameError("Game does not have any players")

        for circle in self.game.circles:
            self.shuffle_circle(circle)

        self.game.state = GameState.running

        for player in self.game.players:
            send_mission_update(player)

    def record_murder(self, killer: str | Player, victim: str | Player, circle: str | Circle, when: datetime,
                      reason: str, code: str) -> None:
        killer = self.get_player(killer)
        victim = self.get_player(victim)
        circle = self.get_circle(circle)

        if self.game.state != GameState.running:
            raise GameError("Game is not running")
        if killer == victim:
            raise GameError("Suicide is not allowed")

        mission = Mission.by_victim_in_circle(victim, circle)
        if not mission:
            raise GameError("Victim is not part of this circle")
        elif mission.completed:
            raise GameError("Victim is already dead in this circle")
        elif code and code != mission.code:
            raise GameError("Validation code does not match")

        killer_mission = Mission.by_victim_in_circle(killer, circle)
        if not killer_mission:
            raise GameError("Killer is not part of this circle")
        elif killer_mission.completed and killer_mission.completion_date < when:
            raise GameError("Killer was already dead at that time")

        owner = mission.current_owner
        mission.complete(killer, when, reason)
        send_mission_update(owner)
        send_mission_update(victim)

    def end_game(self):
        if self.game.state != GameState.running:
            raise GameError("Game is not running")

        self.game.state = GameState.ended

    def check_gamemaster_password(self, password) -> bool:
        return self.game.check_gamemaster_password(password)

    def flush_changes(self):
        self.game.flush_changes()

    @classmethod
    def create_new_game(cls, session: Session, id: str, title: str, gamemaster_password: str,
                        circles: List[str] = None, **kwargs) -> 'GameService':
        if Game.exists_by_id(session, id):
            raise GameError(f"A game with ID '{id}' already exists")

        game = Game(
            state=GameState.new,
            id=id,
            title=title,
            gamemaster_password=gamemaster_password,
            **kwargs
        )
        session.add(game)
        service = cls(game)

        if circles:
            for circle in circles:
                service.add_circle(name=circle)

        return service


def send_mission_update(player: Player):
    missions = sorted(Mission.achievable_missions_by_current_owner(player), key=lambda m: m.circle_id)
    if missions:
        for address in player.notification_addresses:
            if address.active:
                notification.email.send_mission_update(address.address, pdf.generate_mission_sheets(missions), player.game.title)
