"""
EventBroadcaster — writes game events to JSONL and pushes to WebSocket clients.

Each game event is:
  1. Appended to broadcast/events.jsonl for persistence / log-tailing.
  2. Pushed to all connected WebSocket clients via ConnectionManager
     (thread-safe via asyncio.run_coroutine_threadsafe).

Schema per event line:
  {
    "timestamp":       ISO 8601 UTC string,
    "day_number":      int,
    "phase":           str,
    "agent_id":        str,
    "display_name":    str,
    "action_type":     str,
    "target_agent_id": str | null,
    "message":         str,
    "inner_thought":   str | null
  }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.agents.schemas import AgentAction

if TYPE_CHECKING:
    from src.api.server import ConnectionManager

logger = logging.getLogger(__name__)

# Default output path — relative to working directory
DEFAULT_OUTPUT_FILE = Path("broadcast/events.jsonl")


class EventBroadcaster:
    """
    Writes structured game events to a JSONL file and optionally pushes
    them to connected WebSocket clients.

    Args:
        output_file:        Path to the JSONL event log.
        connection_manager: Optional ConnectionManager from api/server.py.
                            When provided, every event is also sent over WebSocket.
    """

    def __init__(
        self,
        output_file: str | Path = DEFAULT_OUTPUT_FILE,
        connection_manager: Optional["ConnectionManager"] = None,
    ) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._ws = connection_manager

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def broadcast(
        self,
        agent_id: str,
        display_name: str,
        action: AgentAction,
        day_number: int,
        phase: str,
    ) -> None:
        """
        Write a single agent action event.

        Called by GameEngine._run_agent_turn() after every validated LLM response.
        Both the public `message` and the hidden `inner_thought` are written —
        the stream UI decides which to show to the audience.
        """
        event = {
            "timestamp":       datetime.utcnow().isoformat(),
            "day_number":      day_number,
            "phase":           phase,
            "agent_id":        agent_id,
            "display_name":    display_name,
            "action_type":     action.action_type,
            "target_agent_id": action.target_agent_id,
            "message":         action.message,
            "inner_thought":   action.inner_thought,
        }
        self._write(event)
        logger.info(
            f"[BROADCAST] Day {day_number} | {phase:20s} | "
            f"{display_name:8s} ({action.action_type}): "
            f"{action.message[:70]}"
        )

    def broadcast_system_event(
        self,
        message: str,
        day_number: int,
        phase: str,
    ) -> None:
        """
        Write a Game Master system announcement event.

        Called for challenge reveals, elimination announcements, and game
        start/end messages.
        """
        event = {
            "timestamp":       datetime.utcnow().isoformat(),
            "day_number":      day_number,
            "phase":           phase,
            "agent_id":        "game_master",
            "display_name":    "Game Master",
            "action_type":     "system_event",
            "target_agent_id": None,
            "message":         message,
            "inner_thought":   None,
        }
        self._write(event)
        logger.info(f"[BROADCAST] Day {day_number} | {phase:20s} | [GAME MASTER]: {message[:70]}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, event: dict) -> None:
        """Append event to JSONL file and push to WebSocket clients."""
        with self.output_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        if self._ws is not None:
            self._ws.broadcast_from_thread(event)
