import random
import string
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
    {"name": "Gert-Doris", "group": "KIT"},
]

TESTGAME_REASONS = [
    "Mit USB-Kabel erwürgt",
    "Zu Tode geflauscht",
    "Von der Klippe geschubst",
    "Im Keller vergessen worden",
]


def populate_test_game(service: GameService, num_players: int = len(TESTGAME_PLAYERS)) -> None:
    for player_info in random.sample(TESTGAME_PLAYERS, num_players):
        service.add_player(**player_info)


def record_random_murder(service: GameService) -> None:
    mission = random.choice(Mission.achievable_missions_in_game(service.game))

    service.record_murder(
        killer=mission.current_owner,
        victim=mission.victim,
        circle=mission.circle,
        when=datetime.now(),
        reason=random.choice(TESTGAME_REASONS),
        code=mission.code)


def create_test_game(session, name: str = None, num_players: int = len(TESTGAME_PLAYERS), num_circles: int = 2,
                     started: bool = True, num_murders: int = None, gamemaster_password: str = '') -> GameService:
    if name is None:
        name = 'test-' + ''.join(random.choices(string.hexdigits, k=4))
    if num_murders is None:
        num_murders = int(num_circles * num_players / 3)

    service = GameService.create_new_game(session, id=name, title=name, gamemaster_password=gamemaster_password,
                                          circles=list('Circle ' + str(i) for i in range(num_circles)))
    populate_test_game(service, num_players)

    if started:
        service.start_game()
        for i in range(num_murders):
            record_random_murder(service)

    return service
