import argparse
import datetime
from typing import List

from sqlalchemy.orm import Session

import moerderspiel.config as config
import moerderspiel.graph as graph
import moerderspiel.pdf as pdf
import moerderspiel.testgame as testgame
from moerderspiel.db import Game, Circle, Player, Mission, database_transaction
from moerderspiel.game import GameService, GameError


def error(message: str):
    print(message)
    exit(1)


def create_game(session: Session, game: str, name: str, description: str, circle: List[str], mail: str, code: str,
                endtime: datetime.datetime, **kwargs):
    GameService.create_new_game(session, game, name, description, mail, code, endtime, circle)


def add_player(game: Game, name: str, circle: List[str], **kwargs):
    pass


def populate_test_game(game: Game, **kwargs):
    testgame.populate_test_game(GameService(game))


def start_game(game: Game, **kwargs):
    GameService(game).start_game()


def generate_mission_sheets(game: Game, **kwargs):
    pdf.generate_game_mission_sheet(game)
    print(pdf.get_game_mission_sheet_cache_path(game))


def generate_graph(game: Game, circle: List[str], **kwargs):
    if circle:
        circles = [Circle.by_game_and_name(game, c) for c in circle]
    else:
        circles = game.circles

    graph.generate_circles_graph(circles)


def record_murder(game: Game, killer: str, victim: str, circle: str, reason: str, when: datetime.datetime,
                  code: str = None, **kwargs):
    GameService(game).record_murder(killer=killer, victim=victim, circle=circle, when=when, reason=reason,
                                    code=code)


def get_missions(game: Game, player: str = None, circle: str = None, **kwargs):
    players = [Player.by_game_and_name(game, player)] if player else Player.by_game(game)
    circles = [Circle.by_game_and_name(game, player)] if circle else Circle.by_game(game)

    for player in players:
        for circle in circles:
            mission = Mission.by_current_owner_in_circle(player, circle)
            if mission:
                print(f"{player.name} in {circle.name}: {mission.victim.name}")


def create_test_game(session: Session, game: str, mail: str, code: str, players: int, circles: int, description: str,
                     endtime: datetime.datetime, name: str = None, murders: int = None, **kwargs):
    name = name or game
    murders = murders or int(players * circles / 2)

    service = GameService.create_new_game(session, id=game, name=name, description=description, mastermail=mail,
                                          mastercode=code, endtime=endtime,
                                          circles=list([f"Circle {i}" for i in range(circles)]))
    testgame.populate_test_game(service, players)
    service.start_game()

    for i in range(murders - 1):
        testgame.record_random_murder(service)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=str, help='The database URI, defaults to the DATABASE_URL environment variable')
    parser.add_argument('--game', type=str, help='The name of the game', required=True)
    subparsers = parser.add_subparsers(dest='command', required=True)

    s = subparsers.add_parser('create-game', help='Create a new game')
    s.set_defaults(function=create_game)
    s.add_argument('name', type=str, help='The fancy name of the game')
    s.add_argument('description', type=str, help='The game description')
    s.add_argument('--circle', type=str, action='append', help='Add a circle with the given name', required=True)
    s.add_argument('--mail', type=str, help='The email address of the game master', required=True)
    s.add_argument('--code', type=str, help='The game master password', required=True)
    s.add_argument('--endtime', type=datetime.datetime, help='When the game ends')

    s = subparsers.add_parser('create-test-game', help='Create a populated and running test game')
    s.set_defaults(function=create_test_game)
    s.add_argument('--mail', type=str, help='The email address of the game master', required=True)
    s.add_argument('--code', type=str, help='The game master password', required=True)
    s.add_argument('--name', type=str, help='The fancy name of the game', default=None)
    s.add_argument('--description', type=str, help='The game description', default="Test Game")
    s.add_argument('--players', type=int, help='The number of players to add to the game',
                   default=len(testgame.TESTGAME_PLAYERS))
    s.add_argument('--circles', type=int, help='The number of circles to create', default=2)
    s.add_argument('--murders', type=int, help='The number of random murders to record')
    s.add_argument('--endtime', type=datetime.datetime, help='When the game ends',
                   default=datetime.datetime.now() + datetime.timedelta(1))

    #    s = subparsers.add_parser('add-player', help='Add a player to a game')
    #    s.set_defaults(function=add_player)
    #    s.add_argument('name', type=str, help='The name of the player')
    #    s.add_argument('--circle', type=str, action='append', help='Add the player to these circles')

    s = subparsers.add_parser('populate-test-game', help='Populate a game with dummy players')
    s.set_defaults(function=populate_test_game)

    s = subparsers.add_parser('start-game', help='Start a game and shuffle all its circles')
    s.set_defaults(function=start_game)

    s = subparsers.add_parser('generate-mission-sheets', help='Generate all mission sheet PDFs for the game')
    s.set_defaults(function=generate_mission_sheets)

    s = subparsers.add_parser('generate-graph', help='Generate a mission graph for the game or a subset of its circles')
    s.set_defaults(function=generate_graph)
    s.add_argument('--circle', type=str, action='append', help='Generate the graph for the given circles only',
                   default=[])

    s = subparsers.add_parser('record-murder', help='Record a murder')
    s.set_defaults(function=record_murder)
    s.add_argument('killer', type=str, help='The name of the player who committed the murder')
    s.add_argument('victim', type=str, help='The name of the player who was murdered')
    s.add_argument('circle', type=str, help='The name of the circle in which the murder was committed')
    s.add_argument('reason', type=str, help='The description of the murder')
    s.add_argument('--when', type=datetime.datetime, help='The time stamp when the murder was committed',
                   default=datetime.datetime.now())

    s = subparsers.add_parser('get-missions', help='Print the current missions')
    s.set_defaults(function=get_missions)
    s.add_argument('--player', type=str, help='The name of the player')
    s.add_argument('--circle', type=str, help='The name of the circle')

    args = parser.parse_args()

    if 'db' in args:
        config.DATABASE_URL = args.db

    with database_transaction() as session:
        if args.function not in [create_game, create_test_game]:
            args.game = Game.by_id(session, str(args.game))

        try:
            args.function(session=session, **vars(args))
            session.commit()
        except GameError as e:
            print(e)


if __name__ == "__main__":
    main()
