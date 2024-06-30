from contextlib import contextmanager

from werkzeug.security import generate_password_hash, check_password_hash

from moerderspiel.config import DATABASE_URL

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Engine, Enum, ForeignKey, inspect, select, desc, Select, create_engine, func, event
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from sqlalchemy.schema import CheckConstraint, UniqueConstraint


class Base(DeclarativeBase):
    def _query(self, query):
        return inspect(self).session.scalars(query)

    def flush_changes(self):
        return inspect(self).session.flush()


class GameState(enum.IntEnum):
    new = 0,
    running = 1,
    ended = 2


class Game(Base):
    __tablename__ = "game"

    """
    The unique ID of the game. This string will be visible to players and used in URLs, etc.
    """
    id: Mapped[str] = mapped_column(primary_key=True)

    """
    The current state of the game.
    """
    state: Mapped[GameState] = mapped_column(Enum(GameState))  # TODO Get this mapped to an int in the database

    """
    The fancy title of the game.
    """
    title: Mapped[str]

    """
    Contact information of the game master. Used for notifications, but not disclosed to players.
    """
    gamemaster_contact: Mapped[Optional[str]]

    """
    The game master's password.
    """
    gamemaster_password: Mapped[str]

    endtime: Mapped[Optional[datetime]]

    circles: Mapped[List["Circle"]] = relationship(back_populates="game")
    players: Mapped[List["Player"]] = relationship(back_populates="game")

    @property
    def started(self) -> bool:
        return self.state in [GameState.running, GameState.ended]

    @property
    def ended(self) -> bool:
        return self.state == GameState.ended

    @classmethod
    def exists_by_id(cls, session: Session, id: str) -> bool:
        return len(session.scalars(select(cls).where(cls.id == id)).all()) > 0

    @classmethod
    def by_id(cls, session: Session, id: str) -> 'Game':
        return session.scalars(select(cls).where(cls.id == id)).one()

    def add(self, something: Base) -> None:
        inspect(self).session.add(something)

    def check_gamemaster_password(self, password: str) -> bool:
        return check_password_hash(self.gamemaster_password, password)


class Player(Base):
    __tablename__ = "player"

    """
    The globally unique ID of the player. While a player is also uniquely identifiable by its game and name, the single
    ID makes some database operations much easier.
    """
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    """
    The ID of the game to which this player belongs.
    """
    game_id: Mapped[int] = mapped_column(ForeignKey(Game.id))

    """
    The human-readable, 'fancy' name of the player.
    """
    name: Mapped[str]

    """
    The group (e.g. school) that this player belongs to.
    """
    group: Mapped[str]

    """
    The player's contact information for notifications.
    """
    #contact: Mapped[Optional[JSON]]

    __table_args__ = (
        UniqueConstraint('game_id', 'name'),
    )

    game: Mapped[Game] = relationship(back_populates="players")
    victim_missions: Mapped[List["Mission"]] = relationship(back_populates="victim",
                                                            primaryjoin="Player.id == Mission.victim_id")
    completed_missions: Mapped[List["Mission"]] = relationship(back_populates="killer",
                                                               primaryjoin="Player.id == Mission.killer_id")

    @property
    def alive(self):
        return any(m for m in self.victim_missions if not m.completed)

    @classmethod
    def by_game_and_name(cls, game: Game, name: str) -> 'Player':
        return game._query(select(cls).where(cls.game == game).where(cls.name == name)).one_or_none()

    @classmethod
    def by_game(cls, game: Game) -> List['Player']:
        return list(game._query(select(cls).where(cls.game == game)).all())


class Circle(Base):
    __tablename__ = "circle"

    """
    The globally unique ID of the circle. While a circle is also uniquely identifiable by its game and name, the single
    ID makes some database operations much easier.
    """
    id: Mapped[int] = mapped_column(primary_key=True)

    """
    The ID of the game to which this circle belongs.
    """
    game_id: Mapped[int] = mapped_column(ForeignKey(Game.id))

    """
    The unique name of this circle in its game. The name is visible to players.
    """
    name: Mapped[str]

    """
    The 'circle set' to which this circle belongs. This is used for multi-games where different subsets of players
    play in different subsets of circles.
    """
    set: Mapped[Optional[str]]

    __table_args__ = (
        UniqueConstraint('game_id', 'name'),
    )

    game: Mapped[Game] = relationship(back_populates="circles")
    missions: Mapped[List["Mission"]] = relationship(back_populates="circle", order_by="Mission.position",
                                                     collection_class=ordering_list("position"))

    @classmethod
    def by_game_and_name(cls, game: Game, name: str) -> 'Circle':
        return game._query(select(cls).where(cls.game == game).where(cls.name == name)).one_or_none()

    @classmethod
    def by_game(cls, game: Game) -> List['Circle']:
        return list(game._query(select(cls).where(cls.game == game)).all())


class Mission(Base):
    """
    A mission represents a player as a potential murder victim in a circle.

    If some Player p plays in a Circle c, then there is exactly one Mission in c with p as the victim.
    p is still alive in c as long as m is not completed. When m is completed, it also stores who killed p, and when, and
    how.

    Missions in a Circle are ordered through a position number (modulo the number of missions in the circle). These
    position numbers are assigned randomly when the game is started. In order to find p's current potential victim
    (or killer), we can start at p's mission and "walk forward" (or backward) in the circle until we find the next
    mission that has not been completed yet.
    """

    __tablename__ = "mission"

    """
    The ID of the circle to which this mission belongs.
    """
    circle_id: Mapped[int] = mapped_column(ForeignKey(Circle.id), primary_key=True)

    """
    The ID of the victim of this mission.
    """
    victim_id: Mapped[int] = mapped_column(ForeignKey(Player.id), primary_key=True)

    """
    The position of this mission in its circle. This is None if and only if the game has not been started yet.
    """
    position: Mapped[Optional[int]] = mapped_column()

    """
    The ID of the player who completed this mission.
    """
    killer_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Player.id))

    """
    The timestamp when this mission was completed.
    """
    completion_date: Mapped[Optional[datetime]]

    """
    The description of how this mission was completed.
    """
    completion_reason: Mapped[Optional[str]]

    __table_args__ = (
        UniqueConstraint(circle_id, position),

        # A completed mission must have both a completion date and reason. The killer is optional here;
        # killer_id == NULL on a completed mission indicates a kick or other administrative action.
        CheckConstraint("(completion_date == NULL and completion_reason == NULL)"
                        "or (completion_date <> NULL and completion_reason <> NULL)"),
    )

    circle: Mapped[Circle] = relationship(back_populates="missions")
    victim: Mapped[Player] = relationship(back_populates="victim_missions", foreign_keys=victim_id)
    killer: Mapped[Optional[Player]] = relationship(back_populates="completed_missions", foreign_keys=killer_id)

    def _previous(self, query: Select) -> 'Mission':
        """
        Get the previous mission in the same circle based on the given query.
        """
        basequery = query.where(Mission.circle == self.circle).order_by(desc(Mission.position)).limit(1)

        return self._query(basequery.where(Mission.position < self.position)).one_or_none() \
            or self._query(basequery.where(Mission.position > self.position)).one_or_none()

    def _next(self, query: Select) -> 'Mission':
        """
        Get the next mission in the same circle based on the given query.
        """
        basequery = query.where(Mission.circle == self.circle).order_by(Mission.position).limit(1)

        return self._query(basequery.where(Mission.position > self.position)).one_or_none() \
            or self._query(basequery.where(Mission.position < self.position)).one_or_none()

    # TODO: Previous and next should probably be reflexive relationships instead
    @property
    def previous(self) -> 'Mission':
        """
        The previous mission in the circle.
        """
        return self._previous(select(Mission))

    @property
    def next(self) -> 'Mission':
        """
        The next mission in the circle.
        """
        return self._next(select(Mission))

    def get_next_uncompleted(self) -> 'Mission':
        return self._next(select(Mission).where(Mission.completion_date == None))

    def get_previous_uncompleted(self) -> 'Mission':
        return self._previous(select(Mission).where(Mission.completion_date == None))

    @property
    def initial_owner(self) -> Player:
        """
        The initial owner of this mission, i.e. the player who got this mission at the start of the game.
        """
        return self.previous.victim

    @property
    def current_owner(self) -> Player:
        """
        The current owner of this mission, i.e. the player who currently has to complete this mission.
        """
        return self.get_previous_uncompleted().victim

    @property
    def code(self) -> str:
        return "dummycode"  # TODO

    @property
    def completed(self) -> bool:
        """
        Whether this mission has been completed yet.
        """
        return self.completion_date != None

    @property
    def game(self) -> Game:
        return self.circle.game

    def complete(self, killer: Player, when: datetime, reason: str) -> None:
        self.killer = killer
        self.completion_date = when
        self.completion_reason = reason

    @classmethod
    def by_victim_in_circle(cls, victim: Player, circle: Circle) -> 'Mission':
        """
        Get the mission that targets this victim in this circle.
        Return None if the victim is not part of the circle.
        """
        return victim._query(select(cls).where(cls.victim == victim).where(cls.circle == circle)).one_or_none()

    @classmethod
    def by_current_owner_in_circle(cls, owner: Player, circle: Circle) -> 'Mission':
        """
        Get this player's current mission in this circle.
        Return None if the player is not currently alive in this circle.
        May return the player's own victim mission if the circle is completed.
        """
        victim_mission = cls.by_victim_in_circle(owner, circle)
        if not victim_mission or victim_mission.completed:
            return None
        else:
            return victim_mission.get_next_uncompleted()

    @classmethod
    def achievable_missions_in_circle(cls, circle: Circle) -> List['Mission']:
        open_missions = circle._query(select(cls).where(cls.circle == circle).where(cls.completion_date == None)).all()
        # If the circle is completed, the last remaining open mission is not actually achievable
        return open_missions if len(open_missions) > 1 else []

    @classmethod
    def achievable_missions_in_game(cls, game: Game) -> List['Mission']:
        return sum([cls.achievable_missions_in_circle(c) for c in game.circles], [])

    @classmethod
    def completed_missions_in_circle(cls, circle: Circle) -> List['Mission']:
        return list(circle._query(select(cls).where(cls.circle == circle).where(cls.completion_date != None)).all())

    @classmethod
    def completed_missions_in_game(cls, game: Game) -> List['Mission']:
        # TODO: This can be done in a single query
        return sum([cls.completed_missions_in_circle(c) for c in game.circles], [])

    @classmethod
    def by_killer(cls, killer: Player) -> List['Mission']:
        return list(killer._query(select(cls).where(cls.killer == killer)).all())

    @classmethod
    def mass_murderers_by_game(cls, game: Game) -> List[Player]:
        max_kill_count = game._query(
            select(func.count()).select_from(Mission).where(Mission.killer_id != None).group_by(
                Mission.killer_id).order_by(desc(func.count())).limit(1)).one_or_none()

        if not max_kill_count:
            return []
        else:
            return list(p for p in game.players if len(cls.by_killer(p)) == max_kill_count)


@event.listens_for(Game.gamemaster_password, 'set', named=True, retval=True)
def hash_user_password(value: str, oldvalue: str, **kwargs):
    return value if value == oldvalue else generate_password_hash(value)


def connect_to_database() -> Engine:
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def database_session():
    with Session(connect_to_database()) as session:
        yield session


@contextmanager
def database_transaction():
    with database_session() as session, session.begin():
        yield session
