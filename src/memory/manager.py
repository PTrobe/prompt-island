"""
MemoryManager — dual-tier memory system for Prompt Island agents.

Implements MEMORY_AND_RAG.md §2:

  Tier 1 — Working Memory (short-term, context window):
    Queries the ChatLog table for the full current day's conversation.
    Cleared implicitly each day since queries are scoped to the current day.

  Tier 2 — Episodic Memory (long-term, ChromaDB vector DB):
    Nightly summaries embedded with text-embedding-3-small and stored in
    ChromaDB. Retrieved via semantic search before every agent turn.

The output of both tiers is injected into the LLM system prompt by the GameEngine
before every agent turn (via _run_agent_turn → build_full_system_prompt).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.db.database import get_session
from src.db.models import ChatLog

if TYPE_CHECKING:
    from src.memory.chroma_store import ChromaMemoryStore

logger = logging.getLogger(__name__)

# Max messages to pull per working memory fetch.
# Keeps token costs bounded while giving the agent enough recent context.
WORKING_MEMORY_LIMIT = 30


class MemoryManager:
    """
    Provides memory context for agent turns.

    Tier 1 (working) is read from the SQLite ChatLog table.
    Tier 2 (episodic) is served by a ChromaMemoryStore (optional — falls back
    to an empty list if no store is provided, e.g. in tests).
    """

    def __init__(
        self,
        chroma_store: ChromaMemoryStore | None = None,
        season_id:    int | None = None,
    ) -> None:
        self._chroma    = chroma_store
        self._season_id = season_id

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
        Return the last `limit` messages from the entire current day as
        OpenAI-style {"role": ..., "content": ...} dicts.

        Fetches across ALL phases of the day (not just the current one) so agents
        remember what happened in Morning Chat and the Scramble when it comes time
        to vote at Tribal Council. Per MEMORY_AND_RAG.md §2: working memory is
        cleared at the end of each *Day*, not each phase.

        The `phase` parameter is accepted for API compatibility but is not used
        to filter — that was the original bug (agents voted with no context from
        earlier phases of the same day).

        Visibility rules:
          - speak_public, system_event, vote → always visible.
          - speak_private → visible only if agent_id is sender OR receiver.

        Args:
            agent_id:    The agent whose perspective we're building context for.
            day_number:  The current game day (filters ChatLog rows).
            phase:       Accepted for compatibility; not used as a DB filter.
            limit:       Maximum number of messages to return (most recent N).

        Returns:
            List of {"role": "user"|"assistant", "content": "..."} dicts.
        """
        with get_session() as session:
            query = session.query(ChatLog).filter(
                ChatLog.day_number == day_number,
                # Include public speech, system events, votes, and this agent's DMs.
                # Exclude speak_private between other agents.
                (
                    ChatLog.action_type.in_(["speak_public", "system_event", "vote"])
                    | (ChatLog.agent_id == agent_id)
                    | (ChatLog.target_agent_id == agent_id)
                ),
            )
            if self._season_id is not None:
                query = query.filter(ChatLog.season_id == self._season_id)
            logs = (
                query
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
        Retrieve the Top-K most relevant episodic memories for an agent from ChromaDB.

        Per MEMORY_AND_RAG.md §3:
          1. Query ChromaDB with a where-filter on agent_id (strict isolation).
          2. Rank by cosine similarity to context_query.
          3. Return the top_k most relevant memory strings, prefixed with day number.

        Returns an empty list if no ChromaMemoryStore is attached (e.g. in tests).
        """
        if self._chroma is None:
            return []
        return self._chroma.retrieve_memories(agent_id, context_query, top_k)

    def store_memory(
        self,
        agent_id:   str,
        day_number: int,
        content:    str,
        category:   str = "general_observation",
    ) -> None:
        """
        Persist an episodic memory to ChromaDB (called during Night Consolidation).
        No-op if no ChromaMemoryStore is attached.
        """
        if self._chroma is not None:
            self._chroma.store_memory(agent_id, day_number, content, category)

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
                # Another agent speaking — prefix with their display name so the LLM
                # sees "Alex: ..." rather than "agent_01_machiavelli: ..."
                speaker = log.agent.display_name if log.agent else log.agent_id
                messages.append({
                    "role": "user",
                    "content": f"{speaker}: {log.message}",
                })

        return messages
