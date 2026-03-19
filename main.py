"""
Prompt Island — entry point.

Starts the FastAPI/uvicorn WebSocket server in a background daemon thread,
then runs the GameEngine in the main thread.

Usage:
    python3 main.py                          # resume active season, or start Season 1
    python3 main.py --new-season             # always start a fresh new season
    python3 main.py --season 2               # resume a specific season by ID
    python3 main.py --list-seasons           # print all seasons and exit
    python3 main.py --days 5 --port 8000     # extra options

Options:
    --days N            Max game days per run (default: 30)
    --port PORT         WebSocket server port (default: 8000)
    --challenges "x"    Comma-separated challenge prompts (overrides built-in schedule)
    --new-season        Create and run a brand new season
    --season N          Resume or run a specific season by its integer ID
    --list-seasons      Print all seasons and exit
    --no-season-arc     Disable tribe/twist/finale arc (run classic flat loop)
    --vote-window N     Viewer vote window in seconds for the finale (default: 300)
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from src.api.server import app, connection_manager  # noqa: E402
from src.broadcast.broadcaster import EventBroadcaster  # noqa: E402
from src.db.database import (  # noqa: E402
    create_season,
    get_active_season_id,
    init_db,
    list_seasons,
    migrate_add_season_columns,
    migrate_season_arc_columns,
)
from src.engine.game_loop import GameEngine  # noqa: E402
from src.engine.season_config import SeasonConfig  # noqa: E402
from src.memory.chroma_store import ChromaMemoryStore  # noqa: E402
from src.memory.manager import MemoryManager  # noqa: E402
from src.utils.logger import setup_logging  # noqa: E402


def _start_api_server(port: int) -> None:
    """Run uvicorn in a daemon thread so it dies with the main process."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Prompt Island game")
    parser.add_argument("--days",           type=int,  default=30,   help="Max game days (default: 30)")
    parser.add_argument("--port",           type=int,  default=8000, help="WebSocket server port (default: 8000)")
    parser.add_argument("--challenges",     type=str,  default="",   help="Comma-separated challenge prompts (overrides built-in schedule)")
    parser.add_argument("--new-season",     action="store_true",     help="Start a brand new season")
    parser.add_argument("--season",         type=int,  default=None, help="Resume a specific season by ID")
    parser.add_argument("--list-seasons",   action="store_true",     help="Print all seasons and exit")
    parser.add_argument("--no-season-arc",  action="store_true",     help="Disable tribe/twist/finale arc (classic flat loop)")
    parser.add_argument("--vote-window",    type=int,  default=300,  help="Viewer vote window in seconds (default: 300)")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    # Ensure DB tables and season columns exist (safe no-ops on a fresh DB)
    init_db()
    migrate_add_season_columns()
    migrate_season_arc_columns()

    # --list-seasons: read-only, no server needed
    if args.list_seasons:
        seasons = list_seasons()
        if not seasons:
            print("No seasons found.")
        else:
            print(f"\n{'ID':>4}  {'Active':>6}  {'Winner':<20}  Label")
            print(f"{'─'*4}  {'─'*6}  {'─'*20}  {'─'*40}")
            for s in seasons:
                active = "YES" if s["is_active"] else "—"
                winner = s["winner_display_name"] or "—"
                label  = s["label"] or "(unlabeled)"
                print(f"{s['id']:>4}  {active:>6}  {winner:<20}  {label}")
            print()
        return

    # Resolve which season to run
    if args.new_season:
        season_id = create_season()
        logger.info(f"Created new Season {season_id}")
    elif args.season is not None:
        season_id = args.season
        logger.info(f"Resuming Season {season_id}")
    else:
        # Default: resume the active season, or create Season 1 if none exists
        season_id = get_active_season_id()
        if season_id is None:
            season_id = create_season()
            logger.info(f"No active season — created Season {season_id}")
        else:
            logger.info(f"Resuming active Season {season_id}")

    # Build challenge list
    # Priority: --challenges flag > built-in SEASON_1_CHALLENGES > [None] fallback
    if args.challenges.strip():
        challenges = [c.strip() for c in args.challenges.split(",")]
    else:
        try:
            from challenges import SEASON_1_CHALLENGES  # noqa: E402
            challenges = SEASON_1_CHALLENGES
        except ImportError:
            challenges = [None]

    # Build SeasonConfig (tribe/twist/finale arc) unless disabled
    season_config: SeasonConfig | None = None
    if not args.no_season_arc:
        from src.db.database import get_session  # noqa: E402
        from src.db.models import Agent  # noqa: E402
        with get_session() as _session:
            agent_ids = [
                a.agent_id
                for a in _session.query(Agent)
                .filter(Agent.season_id == season_id, Agent.agent_id != "game_master")
                .order_by(Agent.agent_id)
                .all()
            ]
        if agent_ids:
            season_config = SeasonConfig.default(
                all_agent_ids=agent_ids,
                finale_vote_window_seconds=args.vote_window,
            )
            logger.info(
                f"Season arc enabled — Tribe {season_config.tribe_name_a}: "
                f"{season_config.tribe_a} | Tribe {season_config.tribe_name_b}: {season_config.tribe_b}"
            )
        else:
            logger.warning("No agents found for season_id=%s — season arc disabled", season_id)

    # Start uvicorn in a daemon thread
    api_thread = threading.Thread(
        target=_start_api_server,
        args=(args.port,),
        daemon=True,
        name="uvicorn",
    )
    api_thread.start()
    logger.info(f"API server starting on http://0.0.0.0:{args.port}")

    # Give uvicorn a moment to start and register its event loop
    time.sleep(1.0)

    # Start Twitch IRC bot (no-op if TWITCH_BOT_TOKEN / TWITCH_CHANNEL not set)
    from src.integrations.twitch_bot import start_twitch_bot  # noqa: E402
    start_twitch_bot()

    # Wire everything together with the resolved season_id
    broadcaster = EventBroadcaster(connection_manager=connection_manager)
    chroma      = ChromaMemoryStore(season_id=season_id)
    memory      = MemoryManager(chroma_store=chroma, season_id=season_id)
    engine      = GameEngine(
        broadcaster=broadcaster,
        memory=memory,
        season_id=season_id,
        season_config=season_config,
    )

    logger.info(
        f"Starting Prompt Island — Season {season_id} | "
        f"max_days={args.days} | arc={'ON' if season_config else 'OFF'} | "
        f"stream=ws://localhost:{args.port}/ws"
    )

    engine.initialize_game()
    engine.run_game(max_days=args.days, challenges=challenges)


if __name__ == "__main__":
    main()
