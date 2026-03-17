"""
Prompt Island — entry point.

Starts the FastAPI/uvicorn WebSocket server in a background daemon thread,
then runs the GameEngine in the main thread.

Usage:
    python main.py [--days N] [--port PORT] [--challenges "prompt1,prompt2,..."]

Example:
    python main.py --days 5 --port 8000 --challenges "Build a raft,Trivia quiz"
    python main.py --days 10 --port 8000                     # no challenges
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from src.api.server import app, connection_manager
from src.broadcast.broadcaster import EventBroadcaster
from src.engine.game_loop import GameEngine
from src.utils.logger import setup_logging


def _start_api_server(port: int) -> None:
    """Run uvicorn in a daemon thread so it dies with the main process."""
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Prompt Island game")
    parser.add_argument("--days",       type=int,   default=30,   help="Max game days (default: 30)")
    parser.add_argument("--port",       type=int,   default=8000, help="WebSocket server port (default: 8000)")
    parser.add_argument("--challenges", type=str,   default="",   help="Comma-separated challenge prompts")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    # Parse challenge list; empty string → [None] → no challenges
    if args.challenges.strip():
        challenges = [c.strip() for c in args.challenges.split(",")]
    else:
        challenges = [None]

    # Start uvicorn in a daemon thread (stops automatically when main exits)
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

    # Wire WebSocket manager into the broadcaster
    broadcaster = EventBroadcaster(connection_manager=connection_manager)

    # Build and run the game engine
    engine = GameEngine(broadcaster=broadcaster)
    engine.initialize_game()

    logger.info(
        f"Starting Prompt Island — max_days={args.days}, "
        f"challenges={challenges}, "
        f"stream=ws://localhost:{args.port}/ws"
    )

    engine.run_game(max_days=args.days, challenges=challenges)


if __name__ == "__main__":
    main()
