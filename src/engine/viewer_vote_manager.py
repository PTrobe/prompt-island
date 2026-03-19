"""
ViewerVoteManager — manages the finale viewer vote window.

Called by GameEngine._run_finale() after the finalist speeches are complete.
Opens a timed voting window, polls the ViewerVote table when it closes, and
returns the winning Agent. Falls back to a random choice if no votes are cast
(allows testing without a live audience).

The vote endpoint (POST /vote) is implemented in src/api/server.py and writes
directly to the ViewerVote table. This class only reads tallies.
"""

from __future__ import annotations

import logging
import random
import time
from collections import Counter
from typing import TYPE_CHECKING

from src.db.database import get_session
from src.db.models import Agent, ViewerVote

if TYPE_CHECKING:
    from src.engine.game_loop import GameEngine

logger = logging.getLogger(__name__)

# Module-level flag — True while the voting window is open
_vote_window_open: bool = False
_vote_window_closes_at: float = 0.0


def is_vote_window_open() -> bool:
    return _vote_window_open and time.time() < _vote_window_closes_at


def seconds_remaining() -> int:
    if not _vote_window_open:
        return 0
    remaining = _vote_window_closes_at - time.time()
    return max(0, int(remaining))


class ViewerVoteManager:

    def __init__(self, engine: "GameEngine", window_seconds: int = 300) -> None:
        self._engine         = engine
        self._window_seconds = window_seconds

    def open_vote(self, finalists: list[Agent]) -> Agent | None:
        """
        Open the viewer vote window for `window_seconds`, then tally and return
        the winning Agent. Blocks the game-loop thread during the window (this is
        intentional — the finale naturally pauses for audience participation).

        Falls back to a random finalist if zero votes are cast.
        """
        global _vote_window_open, _vote_window_closes_at

        engine  = self._engine
        day     = engine._current_day()
        season  = engine.season_id
        names   = [a.display_name for a in finalists]

        _vote_window_open      = True
        _vote_window_closes_at = time.time() + self._window_seconds

        finalist_dicts = [{"agent_id": a.agent_id, "display_name": a.display_name} for a in finalists]

        # Notify the Twitch bot (if running) so it can resolve !vote <name> commands
        try:
            from src.integrations.twitch_bot import get_bot
            bot = get_bot()
            if bot is not None:
                bot.set_finalists(finalist_dicts)
        except Exception:
            pass

        vote_url_hint = "Cast your vote at the stream overlay or type !vote <name> in Twitch chat."
        open_msg = (
            f"VIEWER VOTE IS OPEN for {self._window_seconds} seconds!\n"
            f"Finalists: {' vs '.join(names)}\n"
            f"{vote_url_hint}"
        )
        engine._log_system_event(open_msg, "finale")
        engine.broadcaster.broadcast_system_event(open_msg, day, "finale")

        # Also broadcast a structured vote_open event so the frontend can render the UI
        engine.broadcaster.broadcast_from_thread({
            "action_type":       "vote_window_open",
            "day_number":        day,
            "phase":             "finale",
            "finalists":         finalist_dicts,
            "window_seconds":    self._window_seconds,
            "closes_at_unix":    _vote_window_closes_at,
        })

        logger.info(f"[ViewerVoteManager] Vote window open for {self._window_seconds}s")

        # Sleep until window closes (broadcast_from_thread is non-blocking)
        time.sleep(self._window_seconds)

        _vote_window_open = False

        # Clear finalists from the Twitch bot
        try:
            from src.integrations.twitch_bot import get_bot
            bot = get_bot()
            if bot is not None:
                bot.clear_finalists()
        except Exception:
            pass

        # Tally
        finalist_ids = {a.agent_id: a for a in finalists}
        counts       = self._tally(season, list(finalist_ids.keys()))
        total        = sum(counts.values())

        tally_msg = (
            "Voting is closed! Results:\n"
            + "\n".join(f"  {finalist_ids[aid].display_name}: {v} votes" for aid, v in counts.most_common())
            + f"\n  Total votes cast: {total}"
        )
        engine._log_system_event(tally_msg, "finale")
        engine.broadcaster.broadcast_system_event(tally_msg, day, "finale")

        # Broadcast structured tally for the overlay
        engine.broadcaster.broadcast_from_thread({
            "action_type": "vote_window_closed",
            "day_number":  day,
            "phase":       "finale",
            "counts":      {finalist_ids[aid].display_name: v for aid, v in counts.items()},
            "total":       total,
        })

        logger.info(f"[ViewerVoteManager] Tally: {dict(counts)} ({total} total votes)")

        if total == 0:
            logger.warning("[ViewerVoteManager] No votes cast — picking random winner.")
            return random.choice(finalists) if finalists else None

        winner_id = counts.most_common(1)[0][0]
        return finalist_ids.get(winner_id) or random.choice(finalists)

    def _tally(self, season_id: int | None, finalist_ids: list[str]) -> Counter:
        """Read ViewerVote table and return a Counter of agent_id → vote count."""
        with get_session() as session:
            query = session.query(ViewerVote).filter(
                ViewerVote.agent_id.in_(finalist_ids)
            )
            if season_id is not None:
                query = query.filter(ViewerVote.season_id == season_id)
            rows = query.all()
        return Counter(r.agent_id for r in rows)
