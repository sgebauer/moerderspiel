import random
from datetime import datetime

from db import Mission
from game import GameService

TESTGAME_PLAYERS = [
    {"name": "Enton Quietschie", "info": "Uni Passau"},
    {"name": "Tangente", "info": "Uni Passau"},
    {"name": "Studente", "info": "Uni Passau"},
    {"name": "Ente Wurzel", "info": "Uni Passau"},
    {"name": "Enteger", "info": "Uni Passau"},
    {"name": "Quotiente", "info": "Uni Passau"},
    {"name": "Cybär", "info": "JKU Linz"},
    {"name": "Sobiber", "info": "Uni Passau"},
]


def populate_test_game(service: GameService, num_players: int = len(TESTGAME_PLAYERS)) -> None:
    players = []

    for player_info in random.sample(TESTGAME_PLAYERS, num_players):
        players.append(service.add_player(**player_info))

    # Flush all players in order to get their (autoincrementing) IDs assigned before referencing them
    service.flush_changes()

    for player in players:
        for circle in service.game.circles:
            service.add_player_to_circle(player, circle)


def record_random_murder(service: GameService) -> None:
    mission = random.choice(Mission.achievable_missions_in_game(service.game))

    service.record_murder(
        killer=mission.current_owner,
        victim=mission.victim,
        circle=mission.circle,
        when=datetime.now(),
        reason="Testmord",
        code=mission.code)
