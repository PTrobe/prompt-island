"""
Database engine, session factory, initialization, and season helpers.

Usage:
    from src.db.database import init_db, migrate_add_season_columns
    init_db()
    migrate_add_season_columns()   # safe no-op on a fresh DB

    from src.db.database import create_season, get_active_season_id
    season_id = get_active_season_id() or create_season()

    from src.db.database import get_session
    with get_session() as session:
        session.add(some_model_instance)
"""

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session

from src.db.models import Base, Season

load_dotenv()

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./prompt_island.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in models.py if they do not already exist.
    Safe to call multiple times — CREATE TABLE IF NOT EXISTS prevents data loss.
    """
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Migration helper — adds season_id columns to pre-season databases
# ---------------------------------------------------------------------------

def migrate_season_arc_columns() -> None:
    """
    Idempotent migration: add tribe/idol columns to agents and create the
    viewer_votes table if absent. Safe to run on any existing DB.
    """
    with engine.connect() as conn:
        # Add tribe, has_idol, idol_used to agents table
        result = conn.execute(text("PRAGMA table_info(agents)"))
        existing = {row[1] for row in result}
        for col, definition in [
            ("tribe",     "VARCHAR(32)"),
            ("has_idol",  "BOOLEAN NOT NULL DEFAULT 0"),
            ("idol_used", "BOOLEAN NOT NULL DEFAULT 0"),
        ]:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE agents ADD COLUMN {col} {definition}"))

        # Create viewer_votes table if not present
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS viewer_votes (
                vote_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id INTEGER,
                viewer_id VARCHAR(128) NOT NULL,
                agent_id  VARCHAR(64)  NOT NULL,
                voted_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create unique index if not already present
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_viewer_votes_season_viewer
            ON viewer_votes (season_id, viewer_id)
        """))
        conn.commit()


def migrate_add_season_columns() -> None:
    """
    One-shot migration: add season_id column to existing tables if absent.

    Runs automatically at startup. Safe to call on a brand-new DB (the columns
    already exist) or on a legacy DB created before the Season feature was added.
    Existing rows get season_id = NULL, which is harmless — they predate seasons.
    """
    tables_needing_column = [
        "game_state",
        "agents",
        "chat_logs",
        "vote_history",
    ]
    with engine.connect() as conn:
        for table in tables_needing_column:
            # PRAGMA table_info returns rows: (cid, name, type, notnull, dflt, pk)
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            existing_columns = {row[1] for row in result}
            if "season_id" not in existing_columns:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN season_id INTEGER"
                ))
        conn.commit()


# ---------------------------------------------------------------------------
# Season management helpers
# ---------------------------------------------------------------------------

def create_season(label: Optional[str] = None) -> int:
    """
    Create a new Season row, mark it active, deactivate all others.
    Returns the new season's integer id.

    Args:
        label: Optional human-readable label, e.g. "Season 1 – March 2026".
               Auto-generated from timestamp if omitted.
    """
    if label is None:
        label = f"Season started {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"

    with get_session() as session:
        # Deactivate any currently active season
        session.query(Season).filter(Season.is_active.is_(True)).update(
            {"is_active": False}, synchronize_session=False
        )
        season = Season(label=label, is_active=True)
        session.add(season)
        session.flush()  # populate season.id before commit
        season_id = season.id

    return season_id


def get_active_season_id() -> Optional[int]:
    """Return the id of the currently active Season, or None if no active season."""
    with get_session() as session:
        season = session.query(Season).filter(Season.is_active.is_(True)).first()
        return season.id if season else None


def set_season_winner(season_id: int, agent_id: str, display_name: str) -> None:
    """Record the winner of a completed season."""
    with get_session() as session:
        season = session.get(Season, season_id)
        if season:
            season.winner_agent_id    = agent_id
            season.winner_display_name = display_name
            season.is_active          = False


def list_seasons() -> list[dict]:
    """Return all seasons as plain dicts, ordered by id, for CLI/API display."""
    with get_session() as session:
        rows = session.query(Season).order_by(Season.id).all()
        return [
            {
                "id":                  r.id,
                "label":               r.label,
                "is_active":           r.is_active,
                "created_at":          r.created_at.isoformat(),
                "winner_agent_id":     r.winner_agent_id,
                "winner_display_name": r.winner_display_name,
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Provide a transactional database session as a context manager.
    Commits on clean exit; rolls back and re-raises on any exception.
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
