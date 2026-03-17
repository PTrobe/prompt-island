"""
SQLAlchemy ORM models for the Prompt Island relational database.

Five tables:
  - Season       : Groups a full game run; multiple seasons coexist in one DB.
  - GameState    : Tracks day number, current phase, and simulation on/off status.
  - Agent        : Each contestant's identity and elimination status.
  - ChatLog      : Immutable chronological record of all public/private speech and events.
  - VoteHistory  : Official votes cast during each Tribal Council.

season_id is added to GameState, Agent, ChatLog, and VoteHistory as a plain
integer column (no FK constraint) so composite PKs are not needed. Application-
layer filtering by season_id is sufficient for correct multi-season queries.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ---------------------------------------------------------------------------
# Base class shared by all models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All models inherit from this."""
    pass


# ---------------------------------------------------------------------------
# Season — groups a complete game run
# ---------------------------------------------------------------------------

class Season(Base):
    """
    Represents a single playthrough of Prompt Island.

    Multiple seasons can coexist in the database. Only one season is active
    at a time (is_active=True). All other tables carry a season_id column so
    data from any past season can be queried independently.
    """

    __tablename__ = "seasons"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    label      = Column(String(128), nullable=True)  # e.g. "Season 1 – March 2026"
    is_active  = Column(Boolean, default=False, nullable=False)
    winner_agent_id    = Column(String(64), nullable=True)
    winner_display_name = Column(String(64), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Season id={self.id} active={self.is_active} "
            f"label={self.label!r} winner={self.winner_agent_id!r}>"
        )


# ---------------------------------------------------------------------------
# GameState — the global clock and phase tracker
# ---------------------------------------------------------------------------

class GameState(Base):
    """
    Tracks the overarching progression of the reality show.

    There should be exactly ONE active row per season at any time (is_active=True).
    The Game Engine reads/writes this row to advance the simulation.

    Phases (current_phase values, per GAME_LOOP.md):
      'morning_chat'        — Phase 1: Socializing / public discussion
      'challenge'           — Phase 2: Daily challenge
      'scramble'            — Phase 3: DMs & private plotting
      'tribal_council'      — Phase 4: Voting
      'night_consolidation' — Phase 5: Memory summarization & embedding
    """

    __tablename__ = "game_state"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    season_id     = Column(Integer, nullable=True, index=True)
    current_day   = Column(Integer, default=1, nullable=False)
    current_phase = Column(String(64), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<GameState id={self.id} season={self.season_id} day={self.current_day} "
            f"phase='{self.current_phase}' active={self.is_active}>"
        )


# ---------------------------------------------------------------------------
# Agent — each contestant's identity and survival status
# ---------------------------------------------------------------------------

class Agent(Base):
    """
    Tracks the identity and survival status of each contestant.

    agent_id follows the naming convention from personas/:
      'agent_01_machiavelli', 'agent_02_chaos', ..., 'agent_06_floater'

    season_id scopes the row to a specific season. The PK remains agent_id
    (string) for backward compatibility with all existing FK references.
    Multi-season isolation is enforced at the application layer via season_id
    filters on all queries.
    """

    __tablename__ = "agents"

    agent_id          = Column(String(64), primary_key=True)
    season_id         = Column(Integer, nullable=True, index=True)
    display_name      = Column(String(64), nullable=False)
    is_eliminated     = Column(Boolean, default=False, nullable=False)
    eliminated_on_day = Column(Integer, nullable=True)

    # Relationships — used for ORM queries; lazy-loaded by default
    chat_logs = relationship(
        "ChatLog",
        foreign_keys="ChatLog.agent_id",
        back_populates="agent",
    )
    votes_cast = relationship(
        "VoteHistory",
        foreign_keys="VoteHistory.voter_agent_id",
        back_populates="voter",
    )
    votes_received = relationship(
        "VoteHistory",
        foreign_keys="VoteHistory.target_agent_id",
        back_populates="target",
    )

    def __repr__(self) -> str:
        status = "ELIMINATED" if self.is_eliminated else "active"
        return (
            f"<Agent id='{self.agent_id}' season={self.season_id} "
            f"name='{self.display_name}' {status}>"
        )


# ---------------------------------------------------------------------------
# ChatLog — immutable transcript of everything said and thought
# ---------------------------------------------------------------------------

class ChatLog(Base):
    """
    The immutable, chronological record of everything said and thought.

    season_id scopes each row to a specific season so transcripts from
    multiple seasons can coexist without collision.
    """

    __tablename__ = "chat_logs"

    message_id      = Column(Integer, primary_key=True, autoincrement=True)
    season_id       = Column(Integer, nullable=True, index=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, nullable=False)
    day_number      = Column(Integer, nullable=False)
    phase           = Column(String(64), nullable=False)
    agent_id        = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    action_type     = Column(String(32), nullable=False)
    target_agent_id = Column(String(64), nullable=True)
    message         = Column(Text, nullable=False)
    inner_thought   = Column(Text, nullable=True)

    agent = relationship("Agent", foreign_keys=[agent_id], back_populates="chat_logs")

    def __repr__(self) -> str:
        return (
            f"<ChatLog id={self.message_id} season={self.season_id} day={self.day_number} "
            f"phase='{self.phase}' agent='{self.agent_id}' type='{self.action_type}'>"
        )


# ---------------------------------------------------------------------------
# VoteHistory — official votes cast at Tribal Council
# ---------------------------------------------------------------------------

class VoteHistory(Base):
    """
    Tracks the official votes cast during each Tribal Council (Phase 4).
    season_id scopes votes to their originating season.
    """

    __tablename__ = "vote_history"

    vote_id         = Column(Integer, primary_key=True, autoincrement=True)
    season_id       = Column(Integer, nullable=True, index=True)
    day_number      = Column(Integer, nullable=False)
    voter_agent_id  = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    target_agent_id = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    reason          = Column(Text, nullable=False)

    voter  = relationship("Agent", foreign_keys=[voter_agent_id], back_populates="votes_cast")
    target = relationship("Agent", foreign_keys=[target_agent_id], back_populates="votes_received")

    def __repr__(self) -> str:
        return (
            f"<VoteHistory id={self.vote_id} season={self.season_id} day={self.day_number} "
            f"voter='{self.voter_agent_id}' → target='{self.target_agent_id}'>"
        )


# Composite index for fast per-season day lookups on the largest table
Index("ix_chat_logs_season_day", ChatLog.season_id, ChatLog.day_number)
