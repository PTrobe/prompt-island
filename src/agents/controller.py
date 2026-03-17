"""
Agent Controller — the core LLM orchestration layer for Prompt Island.

Responsibilities (per ARCHITECTURE.md §2):
  1. Load persona system prompts from the personas/ directory.
  2. Inject the agent's display_name into the prompt (PERSONA_GUIDELINES.md §2).
  3. Construct the full message list (system prompt + chat history context).
  4. Call the LLM API and parse the response into a validated AgentAction.
  5. Enforce the 3-attempt retry loop with escalating corrections (ERROR_HANDLING.md §2).
  6. Inject the Brain Freeze FALLBACK_ACTION if all retries are exhausted (ERROR_HANDLING.md §3).
  7. Validate the parsed action against live game rules (hallucination detection).

Public API
----------
  get_agent_action(...)  — The single entry point called by the Game Engine each turn.
  load_persona_system_prompt(...)  — Utility to parse persona markdown files.
  build_full_system_prompt(...)    — Composes the final system prompt per guidelines.
"""

from __future__ import annotations  # enables str | Path, list[str] on Python < 3.10

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from src.agents.schemas import AgentAction, FALLBACK_ACTION, VALID_ACTION_TYPES

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (per ERROR_HANDLING.md §2)
# ---------------------------------------------------------------------------

# Total LLM call attempts before giving up and injecting the fallback action.
MAX_RETRIES: int = 3

# The correction directive appended to the system prompt on Attempts 2 and 3.
# Quoted verbatim from ERROR_HANDLING.md §2.
CORRECTION_SYSTEM_MESSAGE: str = (
    "SYSTEM ERROR: Your previous output was invalid. You must respond ONLY with valid JSON "
    "matching the exact schema. Do not include markdown formatting or conversational text."
)

# ---------------------------------------------------------------------------
# Persona loading utilities
# ---------------------------------------------------------------------------

def load_persona_system_prompt(persona_file: str | Path) -> str:
    """
    Read a persona markdown file and extract only the '## System Prompt' section.

    The personas/ files each contain metadata (ID, LLM Engine, Temperature, Voice)
    and a '## System Prompt' section. We extract only the prompt body so the
    metadata never leaks into the LLM context.

    Args:
        persona_file: Absolute or relative path to a .md file in personas/.

    Returns:
        The raw system prompt text (may contain '{display_name}' placeholders).

    Raises:
        ValueError: If the file has no '## System Prompt' section.
        FileNotFoundError: If the file does not exist.
    """
    content = Path(persona_file).read_text(encoding="utf-8")
    match = re.search(r"## System Prompt\s*\n(.*)", content, re.DOTALL)
    if not match:
        raise ValueError(
            f"No '## System Prompt' section found in '{persona_file}'. "
            "All persona files must include this section."
        )
    return match.group(1).strip()


def build_full_system_prompt(display_name: str, persona_system_prompt: str) -> str:
    """
    Compose the complete system prompt for an LLM call.

    Per PERSONA_GUIDELINES.md §2, the system prompt MUST begin with the
    identity header that establishes the in-game name and forbids archetype
    disclosure. The persona-specific rules are appended after.

    Any literal '{display_name}' tokens in the persona prompt are replaced
    with the actual display_name so each agent has a consistent identity.

    Args:
        display_name:          The in-game human name (e.g., 'Alex', 'Sam').
        persona_system_prompt: The raw prompt text loaded from the persona file.

    Returns:
        The fully composed system prompt string, ready for the LLM.
    """
    # Mandatory identity header (verbatim from PERSONA_GUIDELINES.md §2)
    identity_header = (
        f"You are playing the role of a contestant named {display_name} in an AI reality show "
        f"called Prompt Island. Do NOT ever refer to your underlying archetype out loud. "
        f"You are simply {display_name}."
    )

    # Replace template tokens in personas that use {display_name} (e.g., empath.md)
    resolved_persona = persona_system_prompt.replace("{display_name}", display_name)

    return f"{identity_header}\n\n{resolved_persona}"


# ---------------------------------------------------------------------------
# Game-rule hallucination validator
# ---------------------------------------------------------------------------

def validate_action_against_game_rules(
    action: AgentAction,
    active_agent_ids: list[str],
) -> None:
    """
    Validate a parsed AgentAction against live game rules to catch hallucinations.

    Pydantic's Literal constraint already rejects invalid action_type values, but
    this function adds game-context checks that Pydantic cannot know about:
      - speak_private and vote MUST name a real, active target.
      - The target cannot be an eliminated or invented agent.

    Args:
        action:            The parsed AgentAction to validate.
        active_agent_ids:  The current list of non-eliminated agent IDs.

    Raises:
        ValueError: If any game rule is violated (treated as a hallucination).
    """

    # 1. Redundant safety check — Pydantic Literal already enforces this.
    #    Kept here so the validator is self-contained and testable independently.
    if action.action_type not in VALID_ACTION_TYPES:
        raise ValueError(
            f"Hallucination: action_type='{action.action_type}' is not valid. "
            f"Must be one of {sorted(VALID_ACTION_TYPES)}."
        )

    # 2. Targeted actions require an explicit target.
    if action.action_type in ("speak_private", "vote") and not action.target_agent_id:
        raise ValueError(
            f"Hallucination: action_type='{action.action_type}' requires a "
            f"target_agent_id, but none was provided."
        )

    # 3. Target must be a real, currently-active agent.
    #    This prevents an agent from voting for an eliminated contestant or
    #    inventing a fictional player that doesn't exist.
    if action.target_agent_id and active_agent_ids:
        if action.target_agent_id not in active_agent_ids:
            raise ValueError(
                f"Hallucination: target_agent_id='{action.target_agent_id}' is not "
                f"in the list of active agents: {active_agent_ids}. "
                "The agent may be targeting an eliminated contestant or a made-up player."
            )


# ---------------------------------------------------------------------------
# Core entry point
# ---------------------------------------------------------------------------

def get_agent_action(
    agent_id: str,
    display_name: str,
    persona_system_prompt: str,
    chat_history: list[dict],
    active_agent_ids: Optional[list[str]] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> AgentAction:
    """
    Get a validated AgentAction from an LLM agent. This is the single function
    called by the Game Engine for every agent turn.

    Implements the complete retry architecture from ERROR_HANDLING.md §2–3:

      Attempt 1 — Standard call at the persona's base temperature.
      Attempt 2 — Same prompt + CORRECTION_SYSTEM_MESSAGE appended to system.
                  (Triggered by: JSONDecodeError, ValidationError, ValueError)
      Attempt 3 — Same as Attempt 2 but temperature forced to 0.1 to maximise
                  structural determinism.
      Fallback  — FALLBACK_ACTION ("Brain Freeze") returned if all 3 fail.
                  The Game Engine never sees an exception; the show goes on.

    Args:
        agent_id:              Unique identifier (e.g. 'agent_01_machiavelli').
        display_name:          In-game human name (e.g. 'Alex').
        persona_system_prompt: Raw persona prompt from the personas/ file
                               (use load_persona_system_prompt() to obtain it).
        chat_history:          List of {"role": "user"|"assistant", "content": "..."}
                               dicts representing the recent conversation window.
                               Built by the Game Engine from the ChatLog table,
                               filtered by current day and phase (per DB_SCHEMA §4).
        active_agent_ids:      List of agent_ids still in the game. Used to validate
                               that vote/DM targets are real, active contestants.
        model:                 OpenAI model name. Default: 'gpt-4o'.
                               Set per-agent based on persona metadata (e.g., gpt-4o-mini
                               for the Floater, gpt-4o for Machiavelli).
        temperature:           Base sampling temperature for Attempts 1 & 2.
                               Loaded from persona metadata. Attempt 3 overrides to 0.1.

    Returns:
        A fully validated AgentAction. NEVER raises; returns FALLBACK_ACTION on total failure.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    active_agent_ids = active_agent_ids or []

    # Build the complete system prompt once; reused (with possible correction appended)
    # across all retry attempts.
    base_system_content = build_full_system_prompt(display_name, persona_system_prompt)

    last_exception: Optional[Exception] = None

    # -----------------------------------------------------------------------
    # Retry loop — up to MAX_RETRIES (3) attempts
    # -----------------------------------------------------------------------
    for attempt in range(1, MAX_RETRIES + 1):

        # Determine temperature for this attempt.
        # Attempt 3 forces 0.1 to maximise structural output quality.
        call_temperature = temperature if attempt < 3 else 0.1

        # Attempt 2+ appends the correction directive to the system prompt.
        if attempt == 1:
            system_content = base_system_content
        else:
            system_content = f"{base_system_content}\n\n{CORRECTION_SYSTEM_MESSAGE}"

        logger.info(
            f"[{agent_id}] LLM attempt {attempt}/{MAX_RETRIES} | "
            f"model={model} | temp={call_temperature}"
        )

        try:
            # -----------------------------------------------------------
            # LLM API call — OpenAI Structured Outputs
            #
            # client.beta.chat.completions.parse() uses JSON Schema mode
            # to force the model to emit valid JSON matching AgentAction.
            # The parsed field gives us a fully-instantiated Pydantic object
            # without any manual json.loads() or model_validate() call.
            # -----------------------------------------------------------
            response = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    *chat_history,
                ],
                response_format=AgentAction,
                temperature=call_temperature,
            )

            action: Optional[AgentAction] = response.choices[0].message.parsed

            # The API can return None if the model refuses or emits an empty response.
            if action is None:
                raise ValueError(
                    "OpenAI Structured Outputs returned a null parsed object. "
                    "The model may have refused or emitted an empty response."
                )

            # -----------------------------------------------------------
            # Game-rule hallucination validation
            # (schema validity was already enforced by Pydantic above)
            # -----------------------------------------------------------
            validate_action_against_game_rules(action, active_agent_ids)

            # Success — log and return
            logger.info(
                f"[{agent_id}] ✓ Valid action on attempt {attempt}: "
                f"action_type='{action.action_type}' target='{action.target_agent_id}'"
            )
            return action

        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            # Expected failure modes:
            #   ValidationError   — Pydantic schema mismatch (shouldn't happen with
            #                       Structured Outputs, but kept as safety net).
            #   ValueError        — Game-rule violation caught by our validator.
            #   JSONDecodeError   — Malformed JSON slipped through (e.g., markdown fences).
            last_exception = exc
            logger.warning(
                f"[{agent_id}] ✗ Attempt {attempt} failed "
                f"({type(exc).__name__}): {exc}"
            )

        except Exception as exc:
            # Unexpected failures: network errors, API rate limits, timeouts, etc.
            # We still retry rather than crashing, but log at ERROR level.
            last_exception = exc
            logger.error(
                f"[{agent_id}] ✗ Attempt {attempt} unexpected error "
                f"({type(exc).__name__}): {exc}"
            )

    # -----------------------------------------------------------------------
    # FALLBACK — "Brain Freeze" (ERROR_HANDLING.md §3)
    #
    # All 3 attempts failed. Return the pre-built fallback action so the Game
    # Engine can continue without interruption. The failure is logged at ERROR
    # level for post-game debugging.
    # -----------------------------------------------------------------------
    logger.error(
        f"[{agent_id}] ✗✗✗ All {MAX_RETRIES} attempts failed. "
        f"Injecting Brain Freeze fallback action. "
        f"Last error: {type(last_exception).__name__}: {last_exception}"
    )
    return FALLBACK_ACTION
