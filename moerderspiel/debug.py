from moerderspiel.db import *
from moerderspiel.game import *

session = Session(connect_to_database())


def game_service(name: str) -> GameService:
    return GameService(Game.by_id(session, name))
