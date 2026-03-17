"""
SQLAlchemy ORM models for the Prompt Island relational database.

Strictly follows DATABASE_SCHEMA.md. Four tables:
  - GameState    : Tracks day number, current phase, and simulation on/off status.
  - Agent        : Each contestant's identity and elimination status.
  - ChatLog      : Immutable chronological record of all public/private speech and events.
  - VoteHistory  : Official votes cast during each Tribal Council.

Foreign-key rule (from DATABASE_SCHEMA.md §4):
  An eliminated agent (is_eliminated=True) CANNOT be inserted into ChatLog as a speaker
  unless the action_type is 'final_words'. This is enforced at the application layer in
  the Agent Controller and Game Engine, not at the DB level, to keep the schema flexible.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
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
# GameState — the global clock and phase tracker
# ---------------------------------------------------------------------------

class GameState(Base):
    """
    Tracks the overarching progression of the reality show.

    There should be exactly ONE active row at any time (is_active=True).
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
    current_day   = Column(Integer, default=1, nullable=False)
    current_phase = Column(String(64), nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<GameState id={self.id} day={self.current_day} "
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

    display_name is the generic human name shown to other agents and the audience
    (e.g., 'Alex', 'Sam'). The underlying archetype is NEVER stored here — it
    lives only in the system prompt files under personas/.
    """

    __tablename__ = "agents"

    agent_id         = Column(String(64), primary_key=True)
    display_name     = Column(String(64), nullable=False)
    is_eliminated    = Column(Boolean, default=False, nullable=False)
    eliminated_on_day = Column(Integer, nullable=True)

    # Relationships — used for ORM queries; lazy-loaded by default
    chat_logs      = relationship(
        "ChatLog",
        foreign_keys="ChatLog.agent_id",
        back_populates="agent",
    )
    votes_cast     = relationship(
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
        return f"<Agent id='{self.agent_id}' name='{self.display_name}' {status}>"


# ---------------------------------------------------------------------------
# ChatLog — immutable transcript of everything said and thought
# ---------------------------------------------------------------------------

class ChatLog(Base):
    """
    The immutable, chronological record of everything said and thought.

    The Frontend/Stream reads from this table to drive the live broadcast UI.
    It stores both the public 'message' and the hidden 'inner_thought' so the
    stream overlay can display the agents' secret reasoning to the audience.

    action_type values:
      'speak_public'  — Said aloud to all agents.
      'speak_private' — A DM directed at target_agent_id.
      'vote'          — A vote cast during Tribal Council.
      'use_power'     — Activating a special power / immunity idol.
      'system_event'  — Injected by the Game Engine (e.g., challenge results).
      'final_words'   — The only action_type permitted for eliminated agents.
    """

    __tablename__ = "chat_logs"

    message_id     = Column(Integer, primary_key=True, autoincrement=True)
    timestamp      = Column(DateTime, default=datetime.utcnow, nullable=False)
    day_number     = Column(Integer, nullable=False)
    phase          = Column(String(64), nullable=False)
    agent_id       = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    action_type    = Column(String(32), nullable=False)
    target_agent_id = Column(String(64), nullable=True)   # Used for DMs and votes
    message        = Column(Text, nullable=False)
    inner_thought  = Column(Text, nullable=True)           # Hidden; shown only on stream

    # Relationship back to the speaking agent
    agent = relationship("Agent", foreign_keys=[agent_id], back_populates="chat_logs")

    def __repr__(self) -> str:
        return (
            f"<ChatLog id={self.message_id} day={self.day_number} "
            f"phase='{self.phase}' agent='{self.agent_id}' type='{self.action_type}'>"
        )


# ---------------------------------------------------------------------------
# VoteHistory — official votes cast at Tribal Council
# ---------------------------------------------------------------------------

class VoteHistory(Base):
    """
    Tracks the official votes cast during each Tribal Council (Phase 4).

    Both voter_agent_id and target_agent_id are foreign-keyed to agents.agent_id.
    The Game Engine tallies these rows to determine who is eliminated each day.

    'reason' is the LLM-generated justification from the agent's vote action,
    stored here for post-game analysis and stream display.
    """

    __tablename__ = "vote_history"

    vote_id         = Column(Integer, primary_key=True, autoincrement=True)
    day_number      = Column(Integer, nullable=False)
    voter_agent_id  = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    target_agent_id = Column(String(64), ForeignKey("agents.agent_id"), nullable=False)
    reason          = Column(Text, nullable=False)

    # Relationships
    voter  = relationship("Agent", foreign_keys=[voter_agent_id], back_populates="votes_cast")
    target = relationship("Agent", foreign_keys=[target_agent_id], back_populates="votes_received")

    def __repr__(self) -> str:
        return (
            f"<VoteHistory id={self.vote_id} day={self.day_number} "
            f"voter='{self.voter_agent_id}' → target='{self.target_agent_id}'>"
        )
