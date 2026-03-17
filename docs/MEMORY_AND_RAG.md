# Memory System & RAG (Retrieval-Augmented Generation)

## 1. Overview
For "Prompt Island" to function as a reality show, agents must hold grudges, remember alliances, and recall past betrayals. We achieve this using a dual-tier memory system: Working Memory (short-term) and Episodic Memory (long-term via a Vector Database).

## 2. The Two-Tier Memory Architecture

### Tier 1: Working Memory (Context Window)
* **What it is:** The immediate, raw transcript of the current "Phase" (e.g., today's Morning Chat or a current DM conversation).
* **Implementation:** An in-memory array or simple database query that pulls the last `N` messages (e.g., the last 30 messages in the main chat). This is injected directly into the LLM prompt as standard chat history.
* **Wipe Cycle:** Working memory is cleared at the end of each "Day" to prevent context window overflow and save token costs.

### Tier 2: Episodic Memory (Long-Term Vector DB)
* **What it is:** Summarized, searchable memories of past days, stored as embeddings.
* **Implementation:** We will use `ChromaDB` (local, easy to set up with Python) or `Pinecone`.
* **The "Nightly Consolidation":** At the end of every "Day" in the Game Loop, the `Game Engine` triggers a summarization job. 
    * A smaller LLM (e.g., GPT-4o-mini) reads the full daily transcript.
    * It generates a summary *specifically from the perspective of each surviving agent*. 
    * Example: Instead of a generic summary "Player A voted for Player B", the summary for Player B will be: "Player A betrayed me today and voted for me at Tribal Council. I can no longer trust Player A."

## 3. The RAG Pipeline (Retrieval Process)

Before the `Agent Controller` calls the LLM for an action, it must fetch relevant long-term memories.

1.  **Context Analysis:** Determine what the agent is currently doing (e.g., "Talking to The Empath in a DM").
2.  **Query Generation:** The system searches the Vector DB for the specific Agent's ID using a contextual query string (e.g., "Relationships, past interactions, and feelings regarding The Empath").
3.  **Retrieval:** Fetch the Top K (e.g., 3-5) most relevant memory chunks from ChromaDB.
4.  **Injection:** Append these memories to the System Prompt.

## 4. Prompt Injection Formatting
When Claude Code builds the prompt constructor in Python, it must format the injected memories clearly so the agent understands they are past events.

**Injection Template:**
```text
[SYSTEM: LONG-TERM MEMORY RETRIEVAL]
Here are relevant things you remember from past days:
1. "Day 2: I formed a secret alliance with The Floater."
2. "Day 4: The Pedant annoyed me by correcting my logic during the challenge."
3. "Day 5: I suspect The Paranoid is targeting me."
[END MEMORY RETRIEVAL]
