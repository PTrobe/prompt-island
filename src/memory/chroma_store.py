"""
ChromaDB episodic memory store for Prompt Island.

Implements Tier 2 (long-term) memory from MEMORY_AND_RAG.md §2 and the
EpisodicMemory schema from DATABASE_SCHEMA.md §3.

Architecture:
  - One persistent ChromaDB collection: "episodic_memories"
  - Embeddings: OpenAI text-embedding-3-small (1536 dimensions, cosine similarity)
  - Each document = one nightly summary from one agent's perspective
  - Metadata filter on agent_id ensures agents NEVER retrieve each other's memories

RAG pipeline (MEMORY_AND_RAG.md §3):
  1. GameEngine calls store_memory() during Phase 5 (Night Consolidation)
  2. GameEngine calls retrieve_memories() at the start of every agent turn
  3. MemoryManager formats the results and appends them to the system prompt
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMA_PERSIST_DIR: str  = "chroma_db"
COLLECTION_NAME:    str  = "episodic_memories"
EMBEDDING_MODEL:    str  = "text-embedding-3-small"   # per DATABASE_SCHEMA.md §3

# Valid memory categories from DATABASE_SCHEMA.md §3
VALID_CATEGORIES: frozenset[str] = frozenset(
    {"alliance", "betrayal", "challenge_result", "general_observation"}
)


class ChromaMemoryStore:
    """
    Persistent ChromaDB store for agent episodic memories.

    Usage:
        store = ChromaMemoryStore()
        store.store_memory("agent_01_machiavelli", day=2, content="...", category="alliance")
        memories = store.retrieve_memories("agent_01_machiavelli", "Alex betrayal vote", top_k=5)
    """

    def __init__(
        self,
        persist_dir: str | Path = CHROMA_PERSIST_DIR,
        season_id:   int | None = None,
    ) -> None:
        persist_path = str(Path(persist_dir).resolve())

        # Each season gets its own ChromaDB collection so memories are fully
        # isolated — no cross-season leakage, no extra metadata filters needed.
        collection_name = (
            f"episodic_memories_s{season_id}" if season_id is not None
            else COLLECTION_NAME
        )

        # Persistent client — survives process restarts; the DB is stored on disk
        self._client = chromadb.PersistentClient(path=persist_path)

        # OpenAI embedding function — same model specified in DATABASE_SCHEMA.md.
        # ChromaDB 1.x looks for CHROMA_OPENAI_API_KEY; also accept OPENAI_API_KEY.
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHROMA_OPENAI_API_KEY")
        embed_fn = OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=EMBEDDING_MODEL,
        )

        # Get or create the per-season collection.
        # hnsw:space=cosine gives semantic similarity (vs L2 distance).
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"ChromaDB ready at '{persist_path}' "
            f"(collection='{collection_name}', "
            f"stored memories={self._collection.count()})"
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_memory(
        self,
        agent_id:  str,
        day_number: int,
        content:   str,
        category:  str = "general_observation",
        memory_id: str | None = None,
    ) -> str:
        """
        Embed and persist a single episodic memory.

        The embedding is generated automatically by the OpenAIEmbeddingFunction
        attached to the collection — no manual embed() call needed.

        Args:
            agent_id:   Owner of the memory (strict filter on retrieval).
            day_number: The game day this memory summarises.
            content:    The first-person summary text.
            category:   One of VALID_CATEGORIES (defaults to 'general_observation').
            memory_id:  Optional explicit ID; auto-generated if omitted.

        Returns:
            The memory_id used.
        """
        if category not in VALID_CATEGORIES:
            logger.warning(
                f"Unknown category '{category}' for {agent_id} day {day_number}; "
                "defaulting to 'general_observation'"
            )
            category = "general_observation"

        if memory_id is None:
            memory_id = f"{agent_id}_day{day_number}"

        self._collection.upsert(
            ids=[memory_id],
            documents=[content],
            metadatas=[{
                "agent_id":        agent_id,
                "day_number":      day_number,
                "memory_category": category,
            }],
        )
        logger.debug(
            f"Stored memory '{memory_id}' for {agent_id} "
            f"(day={day_number}, category={category})"
        )
        return memory_id

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def retrieve_memories(
        self,
        agent_id:      str,
        context_query: str,
        top_k:         int = 5,
    ) -> list[str]:
        """
        Semantic retrieval of the Top-K most relevant memories for an agent.

        Per MEMORY_AND_RAG.md §3:
          - Filters strictly by agent_id so agents never read each other's thoughts.
          - Ranks by cosine similarity to context_query.
          - Prefixes each result with "Day N:" for prompt clarity.

        Returns an empty list if the store is empty or retrieval fails.
        """
        # Use the per-agent count so n_results never exceeds the number of
        # matching documents (ChromaDB raises if n_results > matching docs).
        agent_count = self.count_for_agent(agent_id)
        if agent_count == 0:
            return []

        try:
            results = self._collection.query(
                query_texts=[context_query],
                n_results=min(top_k, agent_count),
                where={"agent_id": agent_id},
            )

            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            # Prefix each memory with its day number for temporal context
            memories = []
            for doc, meta in zip(documents, metadatas):
                day = meta.get("day_number", "?")
                memories.append(f"Day {day}: {doc}")

            return memories

        except Exception as exc:
            # Never crash the game loop — log and return empty
            logger.error(f"ChromaDB retrieval failed for {agent_id}: {exc}")
            return []

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return total number of stored memories across all agents."""
        return self._collection.count()

    def count_for_agent(self, agent_id: str) -> int:
        """Return memory count for a specific agent."""
        try:
            result = self._collection.get(where={"agent_id": agent_id})
            return len(result["ids"])
        except Exception:
            return 0
