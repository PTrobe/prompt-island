"""
Pydantic data models for Prompt Island agent outputs and memory structures.

Strictly follows CONSTRAINTS_AND_MODELS.md and DATABASE_SCHEMA.md §3.

Every LLM response MUST deserialize into AgentAction. This model is passed
directly to OpenAI's Structured Outputs API (response_format=AgentAction) so
the LLM is schema-constrained at the generation level, not just at parse time.

Key design decisions:
  - action_type uses Literal so Pydantic rejects invalid values at parse time,
    meaning the retry loop triggers automatically on hallucinated action types.
  - FALLBACK_ACTION is a module-level constant — a pre-built AgentAction that
    the controller injects when all retries are exhausted ("Brain Freeze").
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The set of valid action types. Kept as a frozenset for O(1) membership
# checks inside the hallucination validator in controller.py.
VALID_ACTION_TYPES: frozenset[str] = frozenset(
    {"speak_public", "speak_private", "vote", "use_power"}
)

# ---------------------------------------------------------------------------
# AgentAction — the canonical output schema for every agent turn
# ---------------------------------------------------------------------------

class AgentAction(BaseModel):
    """
    The standard, validated output structure for every agent action.

    Enforced via:
      1. Pydantic validation at parse time (schema mismatch raises ValidationError).
      2. OpenAI Structured Outputs (response_format=AgentAction) at generation time.
      3. Game-rule hallucination checks in controller.validate_action_against_game_rules().

    Fields
    ------
    inner_thought:
        The agent's hidden internal monologue — their true intentions, suspicions,
        and strategies. NOT shown to other agents. Displayed to the stream audience
        as a "confessional" overlay. Crucial for entertainment value.

    action_type:
        What kind of action the agent is taking this turn. Must be one of the four
        valid values; Pydantic's Literal type rejects anything else automatically.
          - 'speak_public'  : Addressed to the whole group (morning chat, scramble).
          - 'speak_private' : A DM; requires target_agent_id.
          - 'vote'          : A Tribal Council vote; requires target_agent_id.
          - 'use_power'     : Activating a special power or immunity idol.

    target_agent_id:
        The agent_id of the recipient/target. Nullable for speak_public and
        use_power, but REQUIRED for speak_private and vote (validated in
        controller.validate_action_against_game_rules).

    message:
        The actual words spoken aloud, or the vote justification.
        This is the public-facing text logged to ChatLog and broadcast to the UI.
    """

    inner_thought: str = Field(
        description=(
            "The internal reasoning and true intentions of the agent. "
            "Hidden from other agents. Shown to the stream audience as a confessional."
        )
    )
    action_type: Literal["speak_public", "speak_private", "vote", "use_power"] = Field(
        description=(
            "The type of action. Must be exactly one of: "
            "'speak_public', 'speak_private', 'vote', 'use_power'."
        )
    )
    target_agent_id: Optional[str] = Field(
        default=None,
        description=(
            "The agent_id of the target agent. "
            "Required for 'speak_private' and 'vote'. Null for 'speak_public' and 'use_power'."
        ),
    )
    message: str = Field(
        description=(
            "The actual words spoken out loud, or the justification for a vote. "
            "This is the public-facing text. Do NOT include inner thoughts here."
        )
    )

    model_config = {
        # Allow the model to be used as an OpenAI response_format target.
        # strict=True is set at the OpenAI call level, not here.
        "json_schema_extra": {
            "examples": [
                {
                    "inner_thought": "Sam keeps staring at me — she knows I flipped the vote.",
                    "action_type": "speak_public",
                    "target_agent_id": None,
                    "message": "Good morning everyone! Ready for another great day?",
                },
                {
                    "inner_thought": "I need to secure Jordan's vote before Tribal.",
                    "action_type": "speak_private",
                    "target_agent_id": "agent_03_empath",
                    "message": "Hey, can we talk? I think we should vote out Alex tonight.",
                },
            ]
        }
    }


# ---------------------------------------------------------------------------
# EpisodicMemory — long-term vector DB schema (DATABASE_SCHEMA.md §3)
# ---------------------------------------------------------------------------

class EpisodicMemory(BaseModel):
    """
    Represents a summarized memory from a specific agent's perspective.
    Stored in ChromaDB for semantic retrieval during RAG.

    The `agent_id` filter is CRITICAL — agents must never retrieve each
    other's memories (they cannot read minds).
    """
    memory_id:       str                    = Field(description="Unique identifier for this memory chunk.")
    agent_id:        str                    = Field(description="The owner of this memory. Used as a ChromaDB where-filter.")
    day_number:      int                    = Field(description="The game day this memory refers to.")
    memory_category: Literal[
        "alliance", "betrayal", "challenge_result", "general_observation"
    ]                                       = Field(description="Primary category of this memory.")
    content:         str                    = Field(description="The summarized first-person memory text.")
    embedding:       Optional[List[float]]  = Field(default=None, description="Vector from text-embedding-3-small (set by ChromaDB).")


# ---------------------------------------------------------------------------
# NightSummaryResult — structured output for the nightly LLM summarization
# ---------------------------------------------------------------------------

class NightSummaryResult(BaseModel):
    """
    Structured output from the nightly consolidation LLM call.
    Combines the first-person summary with a memory category classification
    in a single structured output call, saving an extra LLM round-trip.
    """
    summary: str = Field(
        description=(
            "3–5 sentence first-person summary of the day's key events from this "
            "agent's perspective. Focus on alliances, betrayals, and important conversations."
        )
    )
    category: Literal[
        "alliance", "betrayal", "challenge_result", "general_observation"
    ] = Field(
        description=(
            "The primary memory category. Use 'alliance' if a new alliance formed or broke, "
            "'betrayal' if someone lied or backstabbed, 'challenge_result' if a challenge "
            "was the main event, otherwise 'general_observation'."
        )
    )


# ---------------------------------------------------------------------------
# FALLBACK_ACTION — "The Brain Freeze"
# ---------------------------------------------------------------------------

# Injected by the Agent Controller when all 3 retry attempts fail.
# Per ERROR_HANDLING.md §3: the game must NEVER halt due to a bad LLM response.
# This action keeps the simulation moving without disrupting the narrative.
FALLBACK_ACTION = AgentAction(
    inner_thought=(
        "I am experiencing a severe system glitch and cannot think clearly right now."
    ),
    action_type="speak_public",
    target_agent_id=None,
    message="*stares blankly into space* I... I need a moment to process everything.",
)
