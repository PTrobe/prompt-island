"""
MemoryManager — dual-tier memory system for Prompt Island agents.

Implements MEMORY_AND_RAG.md §2:

  Tier 1 — Working Memory (short-term, context window):
    Queries the ChatLog table for the recent conversation in the current phase.
    Per DATABASE_SCHEMA.md §4: filtered by day_number and phase.
    Cleared implicitly each day since queries are scoped to the current day.

  Tier 2 — Episodic Memory (long-term, vector DB):
    [PHASE 3 STUB] Returns an empty list until ChromaDB integration is built.
    The injection format is already implemented so it slots in with zero changes.

The output of both tiers is injected into the LLM system prompt by the GameEngine
before every agent turn (via _run_agent_turn → build_full_system_prompt).
"""

from __future__ import annotations

import logging

from src.db.database import get_session
from src.db.models import ChatLog

logger = logging.getLogger(__name__)

# Max messages to pull per working memory fetch.
# Keeps token costs bounded while giving the agent enough recent context.
WORKING_MEMORY_LIMIT = 30


class MemoryManager:
    """
    Provides memory context for agent turns.

    Tier 1 (working) is read from the SQLite ChatLog table.
    Tier 2 (episodic) is a stub until Phase 3 (ChromaDB).
    """

    # ------------------------------------------------------------------
    # Tier 1: Working Memory
    # ------------------------------------------------------------------

    def get_working_memory(
        self,
        agent_id: str,
        day_number: int,
        phase: str,
        limit: int = WORKING_MEMORY_LIMIT,
    ) -> list[dict]:
        """
        Return the last `limit` messages from the current phase as OpenAI-style
        {"role": ..., "content": ...} dicts.

        Visibility rules (per game logic):
          - speak_public messages:  always visible to everyone.
          - system_event messages:  always visible (Game Master announcements).
          - speak_private messages: visible only if agent_id is sender OR receiver.
          - vote messages:          visible to everyone (votes are public at Tribal).

        Args:
            agent_id:    The agent whose perspective we're building context for.
            day_number:  The current game day (filters ChatLog rows).
            phase:       The current phase string (filters ChatLog rows).
            limit:       Maximum number of messages to return.

        Returns:
            List of {"role": "user"|"assistant", "content": "..."} dicts.
        """
        with get_session() as session:
            logs = (
                session.query(ChatLog)
                .filter(
                    ChatLog.day_number == day_number,
                    ChatLog.phase == phase,
                    # Include public speech, system events, and this agent's DMs
                    (
                        ChatLog.action_type.in_(["speak_public", "system_event", "vote"])
                        | (ChatLog.agent_id == agent_id)
                        | (ChatLog.target_agent_id == agent_id)
                    ),
                )
                .order_by(ChatLog.timestamp.asc())
                .limit(limit)
                .all()
            )
            return self._format_as_chat_history(logs, agent_id)

    # ------------------------------------------------------------------
    # Tier 2: Episodic / Long-Term Memory  [PHASE 3 STUB]
    # ------------------------------------------------------------------

    def get_long_term_memories(
        self,
        agent_id: str,
        context_query: str,
        top_k: int = 5,
    ) -> list[str]:
        """
        [PHASE 3 STUB] Retrieve the Top-K most relevant episodic memories for an
        agent from the vector database.

        Per MEMORY_AND_RAG.md §3:
          1. Search ChromaDB for documents belonging to `agent_id`.
          2. Rank by semantic similarity to `context_query`.
          3. Return the `top_k` most relevant memory strings.

        Returns an empty list until ChromaDB is integrated in Phase 3.
        """
        # TODO Phase 3: replace with ChromaDB query
        # collection = chroma_client.get_collection("episodic_memories")
        # results = collection.query(
        #     query_texts=[context_query],
        #     n_results=top_k,
        #     where={"agent_id": agent_id},
        # )
        # return results["documents"][0] if results["documents"] else []
        return []

    def format_memories_for_prompt(self, memories: list[str]) -> str:
        """
        Format retrieved long-term memories into the standard injection block
        defined in MEMORY_AND_RAG.md §4.

        Returns an empty string if no memories exist (nothing is injected into
        the system prompt, keeping the Phase 2 token footprint clean).

        Example output:
            [SYSTEM: LONG-TERM MEMORY RETRIEVAL]
            Here are relevant things you remember from past days:
            1. "Day 2: I formed a secret alliance with Riley."
            2. "Day 4: Morgan annoyed me by correcting my logic."
            [END MEMORY RETRIEVAL]
        """
        if not memories:
            return ""

        numbered = "\n".join(f'{i + 1}. "{m}"' for i, m in enumerate(memories))
        return (
            "[SYSTEM: LONG-TERM MEMORY RETRIEVAL]\n"
            "Here are relevant things you remember from past days:\n"
            f"{numbered}\n"
            "[END MEMORY RETRIEVAL]"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_as_chat_history(
        self,
        logs: list[ChatLog],
        viewer_agent_id: str,
    ) -> list[dict]:
        """
        Convert ChatLog ORM rows into OpenAI-style message dicts.

        Mapping logic:
          - viewer's own messages          → role: "assistant"   (what I said)
          - other agents' public messages  → role: "user"         (prefixed with display name)
          - system events (Game Master)    → role: "user"         ("[GAME MASTER]:" prefix)

        This framing tells the LLM: "here is what you said, here is what others said."
        """
        messages: list[dict] = []

        for log in logs:
            if log.action_type == "system_event":
                messages.append({
                    "role": "user",
                    "content": f"[GAME MASTER]: {log.message}",
                })
            elif log.agent_id == viewer_agent_id:
                # This agent's own previous speech — frame as assistant turn
                messages.append({
                    "role": "assistant",
                    "content": log.message,
                })
            else:
                # Another agent speaking — prefix with their agent_id so the LLM
                # can track who said what (display names are in the system prompt context)
                messages.append({
                    "role": "user",
                    "content": f"{log.agent_id}: {log.message}",
                })

        return messages
