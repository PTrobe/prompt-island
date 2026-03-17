"""
Multi-provider LLM routing for Prompt Island.

Routes each agent to the correct LLM provider based on their persona spec:
  - OpenAI     (gpt-4o, gpt-4o-mini)      — Machiavelli, Pedant, Floater
  - Anthropic  (claude-3-5-sonnet-…)      — Empath
  - Groq       (llama-3.1-70b-versatile)  — Chaos, Paranoid

If a provider's API key is not configured, the registry falls back to OpenAI
automatically (see registry.py _resolve_provider). So this module can assume
the provider/model pair it receives is always valid.

All three `_call_*` functions return a validated AgentAction.
Any exception they raise (ValidationError, ValueError, JSONDecodeError, API error)
is caught by the retry loop in controller.py and triggers the next attempt.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from pydantic import ValidationError

from src.agents.schemas import AgentAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy provider singletons — created on first real LLM call
# ---------------------------------------------------------------------------

_openai_client   = None
_anthropic_client = None
_groq_client     = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


# ---------------------------------------------------------------------------
# JSON schema hint injected into Groq system prompts
# (Groq uses JSON mode, not native structured outputs)
# ---------------------------------------------------------------------------

_AGENT_ACTION_SCHEMA_STR = json.dumps(AgentAction.model_json_schema(), indent=2)

_GROQ_SCHEMA_HINT = f"""
You MUST respond with a valid JSON object — no other text, no markdown, no explanation.
The JSON must match this exact schema:
{_AGENT_ACTION_SCHEMA_STR}
"""


# ---------------------------------------------------------------------------
# Public dispatch function
# ---------------------------------------------------------------------------

def call_llm(
    provider:    str,
    model:       str,
    messages:    list[dict],
    temperature: float,
) -> AgentAction:
    """
    Dispatch an LLM call to the correct provider and return a validated AgentAction.

    Args:
        provider:    "openai" | "anthropic" | "groq"
        model:       Provider-specific model name.
        messages:    OpenAI-style [{"role": ..., "content": ...}] list.
                     The system message is always messages[0] with role="system".
        temperature: Sampling temperature.

    Returns:
        Validated AgentAction.

    Raises:
        ValueError, ValidationError, json.JSONDecodeError — caught by retry loop.
    """
    if provider == "openai":
        return _call_openai(model, messages, temperature)
    elif provider == "anthropic":
        return _call_anthropic(model, messages, temperature)
    elif provider == "groq":
        return _call_groq(model, messages, temperature)
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'")


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_openai(
    model:       str,
    messages:    list[dict],
    temperature: float,
) -> AgentAction:
    """
    OpenAI Structured Outputs — guaranteed schema compliance at generation time.
    Uses client.beta.chat.completions.parse() which returns a typed Pydantic object.
    """
    response = _get_openai().beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=AgentAction,
        temperature=temperature,
    )
    action: Optional[AgentAction] = response.choices[0].message.parsed
    if action is None:
        raise ValueError("OpenAI Structured Outputs returned a null parsed response.")
    return action


def _call_anthropic(
    model:       str,
    messages:    list[dict],
    temperature: float,
) -> AgentAction:
    """
    Anthropic tool_use — equivalent to OpenAI function calling for structured outputs.

    Flow:
      1. Separate the system message from the conversation history.
      2. Define a tool whose input_schema mirrors AgentAction's JSON schema.
      3. Force tool use with tool_choice={"type": "tool", "name": "submit_action"}.
      4. Extract and validate the tool_use block from the response.
    """
    # Separate system content from conversation turns
    system_content = ""
    human_messages: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            human_messages.append(msg)

    # Anthropic requires at least one human message
    if not human_messages:
        logger.warning(
            "Anthropic call had no human messages (empty chat history). "
            "Injecting generic prompt — agent will have no working memory context."
        )
        human_messages = [{"role": "user", "content": "What is your next action?"}]

    tool_def = {
        "name":        "submit_action",
        "description": "Submit your action for this turn of Prompt Island.",
        "input_schema": AgentAction.model_json_schema(),
    }

    response = _get_anthropic().messages.create(
        model=model,
        max_tokens=1024,
        system=system_content,
        messages=human_messages,
        tools=[tool_def],
        tool_choice={"type": "tool", "name": "submit_action"},
        temperature=temperature,
    )

    # Extract the tool_use content block
    for block in response.content:
        if block.type == "tool_use":
            return AgentAction.model_validate(block.input)

    raise ValueError(
        "Anthropic response contained no tool_use block. "
        f"Stop reason: {response.stop_reason}. Content: {response.content}"
    )


def _call_groq(
    model:       str,
    messages:    list[dict],
    temperature: float,
) -> AgentAction:
    """
    Groq (Llama) via JSON mode — no native structured outputs, so we inject the
    JSON schema into the system prompt and parse the raw JSON string manually.

    Groq caps temperature at 2.0; we clamp to be safe.
    """
    # Inject schema hint into the system message
    groq_messages: list[dict] = []
    schema_injected = False

    for msg in messages:
        if msg["role"] == "system" and not schema_injected:
            groq_messages.append({
                "role":    "system",
                "content": msg["content"] + "\n\n" + _GROQ_SCHEMA_HINT,
            })
            schema_injected = True
        else:
            groq_messages.append(msg)

    if not schema_injected:
        groq_messages.insert(0, {"role": "system", "content": _GROQ_SCHEMA_HINT})

    response = _get_groq().chat.completions.create(
        model=model,
        messages=groq_messages,
        temperature=min(temperature, 1.99),  # Groq max is 2.0
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("Groq returned an empty response.")

    return AgentAction.model_validate_json(raw)
