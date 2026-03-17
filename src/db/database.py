"""
Database engine, session factory, and initialization for Prompt Island.

Usage:
    # One-time setup at startup (creates all tables if they don't exist):
    from src.db.database import init_db
    init_db()

    # Per-operation transactional session:
    from src.db.database import get_session
    with get_session() as session:
        session.add(some_model_instance)
        # commit happens automatically on __exit__ if no exception
"""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from src.db.models import Base

load_dotenv()

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./prompt_island.db")

# SQLite requires check_same_thread=False when used across threads (which the
# Game Engine will do). This flag is harmless and ignored for other DB backends.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,          # Set to True to log all SQL — helpful for debugging
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    # Keeps attribute values accessible after the session is closed/committed.
    # Without this, accessing any column on a returned ORM object raises
    # DetachedInstanceError because SQLAlchemy marks them as expired on commit.
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in models.py if they do not already exist.

    Call this exactly once at application startup before the Game Engine runs.
    Safe to call multiple times — SQLAlchemy's CREATE TABLE IF NOT EXISTS
    prevents data loss on re-runs.
    """
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Provide a transactional database session as a context manager.

    Commits automatically on clean exit; rolls back on any exception and
    re-raises the original error so the caller can handle it.

    Example:
        with get_session() as session:
            agent = session.get(Agent, "agent_01_machiavelli")
            agent.is_eliminated = True
            # Auto-committed here
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
