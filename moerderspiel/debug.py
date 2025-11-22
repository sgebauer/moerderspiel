from moerderspiel.db import *
from moerderspiel.game import *

session = Session(connect_to_database())


def game_service(name: str) -> GameService:
    return GameService(Game.by_id(session, name))

def list_games() -> List[Game]:
    return session.scalars(select(Game)).all()