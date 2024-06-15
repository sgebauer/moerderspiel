import random
from datetime import datetime

from moerderspiel.db import Mission
from moerderspiel.game import GameService

TESTGAME_PLAYERS = [
    {"name": "Enton Quietschie", "group": "Uni Passau"},
    {"name": "Tangente", "group": "Uni Passau"},
    {"name": "Studente", "group": "Uni Passau"},
    {"name": "Ente Wurzel", "group": "Uni Passau"},
    {"name": "Enteger", "group": "Uni Passau"},
    {"name": "Quotiente", "group": "Uni Passau"},
    {"name": "Cybär", "group": "JKU Linz"},
    {"name": "ΦΨ", "group": "Uni Erlangen"},
    {"name": "Emmy", "group": "Uni Regensburg"},
    {"name": "Hilbärt", "group": "HU Berlin"},
    {"name": "Karl der Löwe", "group": "Uni Bremen"},
    {"name": "Owlaf", "group": "Uni Erlangen"},
    {"name": "Sir Dagger", "group": "TU Darmstadt"},
    {"name": "Nugget", "group": "HHU Düsseldorf"},
    {"name": "Rudi Die Halts-Maul-Giraffe", "group": "TU Darmstadt"},
    {"name": "Dr. Chomp", "group": "JKU Linz"},
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
