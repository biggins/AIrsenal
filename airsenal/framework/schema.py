"""
Interface to the SQL database.
Use SQLAlchemy to convert between DB tables and python objects.
"""
import os

from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from contextlib import contextmanager

from airsenal.framework.db_config import DB_CONNECTION_STRING

Base = declarative_base()


class Player(Base):
    __tablename__ = "player"
    player_id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    fpl_api_id = Column(Integer, nullable=True)
    name = Column(String(100), nullable=False)
    attributes = relationship("PlayerAttributes", uselist=True, back_populates="player")
    results = relationship("Result", uselist=True, back_populates="player")
    fixtures = relationship("Fixture", uselist=True, back_populates="player")
    predictions = relationship(
        "PlayerPrediction", uselist=True, back_populates="player"
    )
    scores = relationship("PlayerScore", uselist=True, back_populates="player")

    def team(self, season, gameweek):
        """
        Get player's team for given season and gameweek.
        If data not available for specified gameweek but data is available for
        at least one gameweek in specified season, return a best guess value
        based on data nearest to specified gameweek.
        """
        gw_before = 0
        gw_after = 100
        team_before = None
        team_after = None

        for attr in self.attributes:
            if attr.season != season:
                continue

            if attr.gameweek == gameweek:
                return attr.team
            elif (attr.gameweek < gameweek) and (attr.gameweek > gw_before):
                # update last available team before specified gameweek
                gw_before = attr.gameweek
                team_before = attr.team
            elif (attr.gameweek > gameweek) and (attr.gameweek < gw_after):
                # update next available team after specified gameweek
                gw_after = attr.gameweek
                team_after = attr.team

        # ran through all attributes without finding gameweek, return an
        # appropriate estimate
        if not team_before and not team_after:
            print("No team found for", self.name, "in", season, "season.")
            return None
        elif not team_after:
            return team_before
        elif not team_before:
            return team_after
        elif (gw_after - gameweek) >= (gameweek - gw_before):
            return team_before
        else:
            return team_after

    def price(self, season, gameweek):
        """
        get player's price for given season and gameweek
        If data not available for specified gameweek but data is available for
        at least one gameweek in specified season, return a best guess value
        based on data nearest to specified gameweek.
        """
        gw_before = 0
        gw_after = 100
        price_before = None
        price_after = None

        for attr in self.attributes:
            if attr.season != season:
                continue

            if attr.gameweek == gameweek:
                return attr.price
            elif (attr.gameweek < gameweek) and (attr.gameweek > gw_before):
                # update last available price before specified gameweek
                gw_before = attr.gameweek
                price_before = attr.price
            elif (attr.gameweek > gameweek) and (attr.gameweek < gw_after):
                # update next available price after specified gameweek
                gw_after = attr.gameweek
                price_after = attr.price

        # ran through all attributes without finding gameweek, return an
        # appropriate estimate
        if not price_before and not price_after:
            print("No price found for", self.name, "in", season, "season.")
            return None
        elif not price_after:
            return price_before
        elif not price_before:
            return price_after
        else:
            # found a price before and after the requested gameweek,
            # interpolate between the two
            gradient = (price_after - price_before) / (gw_after - gw_before)
            intercept = price_before - gradient * gw_before
            price = gradient * gameweek + intercept
            return round(price)

    def position(self, season):
        """
        get player's position for given season
        """
        for attr in self.attributes:
            if attr.season == season:
                return attr.position
        return None


class PlayerAttributes(Base):
    __tablename__ = "player_attributes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player = relationship("Player", back_populates="attributes")
    player_id = Column(Integer, ForeignKey("player.player_id"))
    season = Column(String(100), nullable=False)
    gameweek = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    team = Column(String(100), nullable=False)
    position = Column(String(100), nullable=False)

    transfers_balance = Column(Integer, nullable=True)
    selected = Column(Integer, nullable=True)
    transfers_in = Column(Integer, nullable=True)
    transfers_out = Column(Integer, nullable=True)


class Result(Base):
    __tablename__ = "result"
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    fixture = relationship("Fixture", uselist=False, back_populates="result")
    fixture_id = Column(Integer, ForeignKey("fixture.fixture_id"))
    home_score = Column(Integer, nullable=False)
    away_score = Column(Integer, nullable=False)
    player = relationship("Player", back_populates="results")
    player_id = Column(Integer, ForeignKey("player.player_id"))


class Fixture(Base):
    __tablename__ = "fixture"
    fixture_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(100), nullable=True)  ### In case fixture not yet scheduled!
    gameweek = Column(Integer, nullable=True)  ### In case fixture not yet scheduled!
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    season = Column(String(100), nullable=False)
    tag = Column(String(100), nullable=False)
    result = relationship("Result", uselist=False, back_populates="fixture")
    player = relationship("Player", back_populates="fixtures")
    player_id = Column(Integer, ForeignKey("player.player_id"))


class PlayerScore(Base):
    __tablename__ = "player_score"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_team = Column(String(100), nullable=False)
    opponent = Column(String(100), nullable=False)
    points = Column(Integer, nullable=False)
    goals = Column(Integer, nullable=False)
    assists = Column(Integer, nullable=False)
    bonus = Column(Integer, nullable=False)
    conceded = Column(Integer, nullable=False)
    minutes = Column(Integer, nullable=False)
    player = relationship("Player", back_populates="scores")
    player_id = Column(Integer, ForeignKey("player.player_id"))
    result = relationship("Result", uselist=False)
    result_id = Column(Integer, ForeignKey("result.result_id"))
    fixture = relationship("Fixture", uselist=False)
    fixture_id = Column(Integer, ForeignKey("fixture.fixture_id"))

    # extended features
    clean_sheets = Column(Integer, nullable=True)
    own_goals = Column(Integer, nullable=True)
    penalties_saved = Column(Integer, nullable=True)
    penalties_missed = Column(Integer, nullable=True)
    yellow_cards = Column(Integer, nullable=True)
    red_cards = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    bps = Column(Integer, nullable=True)
    influence = Column(Float, nullable=True)
    creativity = Column(Float, nullable=True)
    threat = Column(Float, nullable=True)
    ict_index = Column(Float, nullable=True)


class PlayerPrediction(Base):
    __tablename__ = "player_prediction"
    id = Column(Integer, primary_key=True, autoincrement=True)
    fixture = relationship("Fixture", uselist=False)
    fixture_id = Column(Integer, ForeignKey("fixture.fixture_id"))
    predicted_points = Column(Float, nullable=False)
    tag = Column(String(100), nullable=False)
    player = relationship("Player", back_populates="predictions")
    player_id = Column(Integer, ForeignKey("player.player_id"))


class Transaction(Base):
    __tablename__ = "transaction"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, nullable=False)
    gameweek = Column(Integer, nullable=False)
    bought_or_sold = Column(Integer, nullable=False)  # +1 for bought, -1 for sold
    season = Column(String(100), nullable=False)
    tag = Column(String(100), nullable=False)
    price = Column(Integer, nullable=False)
    free_hit = Column(Integer, nullable=False)  # 1 if transfer on Free Hit, 0 otherwise


class TransferSuggestion(Base):
    __tablename__ = "transfer_suggestion"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, nullable=False)
    in_or_out = Column(Integer, nullable=False)  # +1 for buy, -1 for sell
    gameweek = Column(Integer, nullable=False)
    points_gain = Column(Float, nullable=False)
    timestamp = Column(String(100), nullable=False)  # use this to group suggestions
    season = Column(String(100), nullable=False)


class FifaTeamRating(Base):
    __tablename__ = "fifa_rating"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season = Column(String(4), nullable=False)
    team = Column(String(100), nullable=False)
    att = Column(Integer, nullable=False)
    defn = Column(Integer, nullable=False)
    mid = Column(Integer, nullable=False)
    ovr = Column(Integer, nullable=False)


class Team(Base):
    __tablename__ = "team"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(3), nullable=False)
    full_name = Column(String(100), nullable=False)
    season = Column(String(4), nullable=False)
    team_id = Column(
        Integer, nullable=False
    )  # the season-dependent team ID (from alphabetical order)


class SessionSquad(Base):
    __tablename__ = "sessionteam"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    player_id = Column(Integer, nullable=False)


class SessionBudget(Base):
    __tablename__ = "sessionbudget"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    budget = Column(Integer, nullable=False)


engine = create_engine(DB_CONNECTION_STRING)

Base.metadata.create_all(engine)
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine, autoflush=False)
# global database session used by default throughout the package
session = DBSession()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = DBSession()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
