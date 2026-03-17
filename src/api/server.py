"""
FastAPI WebSocket server for Prompt Island.

Provides real-time event streaming to browser frontends and observer clients.

Endpoints:
  GET  /state  — current game state (day, phase, active agents, standings)
  GET  /logs   — last N events from the JSONL broadcast file
  WS   /ws     — WebSocket stream; every game event is pushed here in real time

Thread safety:
  The GameEngine runs in a synchronous thread (blocking I/O against SQLite).
  WebSocket broadcasts use asyncio.run_coroutine_threadsafe() to hop from
  the game-loop thread into the uvicorn event loop without blocking either.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.db.database import get_session
from src.db.models import Agent, ChatLog, GameState

logger = logging.getLogger(__name__)

app = FastAPI(title="Prompt Island API", version="0.1.0")

# ---------------------------------------------------------------------------
# ConnectionManager — tracks active WebSocket clients + thread-safe broadcast
# ---------------------------------------------------------------------------


class ConnectionManager:
    """
    Manages all active WebSocket connections and provides a thread-safe
    broadcast method for use from the synchronous game-loop thread.

    Usage (from game thread):
        manager.broadcast_from_thread(event_dict, loop)

    Usage (from async context):
        await manager.broadcast(event_dict)
    """

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the uvicorn event loop so game thread can schedule coroutines."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.append(websocket)
        logger.info(f"WebSocket client connected ({len(self._clients)} total)")

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(self._clients)} remaining)")

    async def broadcast(self, event: dict) -> None:
        """Send event JSON to all connected clients (async context)."""
        payload = json.dumps(event, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.remove(ws)

    def broadcast_from_thread(self, event: dict) -> None:
        """
        Schedule a broadcast from the synchronous game-loop thread.

        Uses asyncio.run_coroutine_threadsafe() to submit the coroutine
        to the uvicorn event loop without blocking the caller.
        """
        if self._loop is None or not self._clients:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)


# Module-level singleton — imported by broadcaster.py and main.py
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Startup hook — capture the running event loop
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _on_startup() -> None:
    connection_manager.set_loop(asyncio.get_running_loop())
    logger.info("Prompt Island API started — WebSocket manager ready")


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


@app.get("/state")
async def get_state() -> JSONResponse:
    """Return current game state: day, phase, active agents, eliminated agents."""
    with get_session() as session:
        gs = session.query(GameState).filter(GameState.is_active.is_(True)).first()
        agents = (
            session.query(Agent)
            .filter(Agent.agent_id != "game_master")
            .order_by(Agent.agent_id)
            .all()
        )
        state = {
            "current_day":   gs.current_day   if gs else None,
            "current_phase": gs.current_phase if gs else None,
            "contestants": [
                {
                    "agent_id":         a.agent_id,
                    "display_name":     a.display_name,
                    "is_eliminated":    a.is_eliminated,
                    "eliminated_on_day": a.eliminated_on_day,
                }
                for a in agents
            ],
        }
    return JSONResponse(state)


@app.get("/logs")
async def get_logs(limit: int = 50) -> JSONResponse:
    """Return the last `limit` ChatLog rows as a list of event dicts."""
    with get_session() as session:
        logs = (
            session.query(ChatLog)
            .order_by(ChatLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows = [
            {
                "timestamp":       log.timestamp.isoformat(),
                "day_number":      log.day_number,
                "phase":           log.phase,
                "agent_id":        log.agent_id,
                "action_type":     log.action_type,
                "target_agent_id": log.target_agent_id,
                "message":         log.message,
            }
            for log in reversed(logs)
        ]
    return JSONResponse(rows)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Real-time event stream.

    On connect, replays the last 20 JSONL events from the broadcast file so
    new clients catch up instantly. Then keeps the connection open to receive
    live pushes from the game loop.
    """
    await connection_manager.connect(websocket)
    try:
        # Replay recent history from JSONL file so late-joining clients catch up
        jsonl_path = Path("broadcast/events.jsonl")
        if jsonl_path.exists():
            lines = jsonl_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-20:]:
                if line.strip():
                    await websocket.send_text(line)

        # Hold the connection open — game events arrive via broadcast_from_thread
        while True:
            await websocket.receive_text()   # keep-alive; clients can send pings
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
