"""
AgentRegistry — loads and caches all persona configurations from the personas/ directory.

Parses each .md file to extract:
  - agent_id      (from '** ID:**' metadata field)
  - LLM model     (normalized to an OpenAI model name for Phase 2)
  - temperature   (from '** Temperature:**' metadata field)
  - system prompt (the raw text under '## System Prompt')

Display names are assigned here (not in the persona files) so they can be randomized
per-game run in the future.

NOTE (Phase 3): Multi-provider routing (Anthropic for Empath, Groq/Llama for Chaos
and Paranoid) will be added once the provider abstraction layer is built.
For now, all agents fall back to OpenAI models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Display name assignments
# One generic human name per agent (per PERSONA_GUIDELINES.md §1 & §2).
# ---------------------------------------------------------------------------

DISPLAY_NAMES: dict[str, str] = {
    "agent_01_machiavelli": "Alex",
    "agent_02_chaos":       "Jordan",
    "agent_03_empath":      "Sam",
    "agent_04_pedant":      "Morgan",
    "agent_05_paranoid":    "Casey",
    "agent_06_floater":     "Riley",
}

# ---------------------------------------------------------------------------
# Model normalisation
# Maps the free-text LLM Engine field in each persona file to an OpenAI
# model name.  The Literal fallback is gpt-4o.
# Phase 3 will add Anthropic/Groq routing — the registry will return a
# (provider, model) tuple instead of a plain model string.
# ---------------------------------------------------------------------------

_MODEL_MAP: dict[str, str] = {
    "gpt-4o-mini": "gpt-4o-mini",   # Floater — fast, cheap
    "gpt-4o":      "gpt-4o",        # Machiavelli, Pedant — high logic
    # Anthropic Claude → fallback to gpt-4o until Phase 3
    "claude":      "gpt-4o",
    # Meta Llama (Groq) → fallback to gpt-4o-mini until Phase 3
    "llama":       "gpt-4o-mini",
}


def _resolve_model(raw_engine: str) -> str:
    """Map a persona's free-text LLM Engine value to an OpenAI model name."""
    engine_lower = raw_engine.lower()
    for keyword, model in _MODEL_MAP.items():
        if keyword in engine_lower:
            return model
    return "gpt-4o"   # safe default


# ---------------------------------------------------------------------------
# AgentConfig dataclass — everything the Engine needs per agent
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentConfig:
    """Immutable configuration record for a single agent persona."""
    agent_id:         str
    display_name:     str
    model:            str
    temperature:      float
    system_prompt_raw: str   # May contain {display_name} tokens; resolved at call time


# ---------------------------------------------------------------------------
# AgentRegistry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """
    Loads all persona .md files from a directory and exposes them as AgentConfig
    objects.  Called once at GameEngine startup.

    Usage:
        registry = AgentRegistry()                 # loads from ./personas/
        registry = AgentRegistry("path/to/dir")    # custom directory

        config = registry.get("agent_01_machiavelli")
        all_configs = registry.all_agents()
    """

    def __init__(self, personas_dir: str | Path = "personas") -> None:
        self._dir = Path(personas_dir)
        self._configs: dict[str, AgentConfig] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentConfig:
        """Return the config for a specific agent. Raises KeyError if not found."""
        if agent_id not in self._configs:
            raise KeyError(
                f"AgentRegistry: no config for '{agent_id}'. "
                f"Known IDs: {list(self._configs)}"
            )
        return self._configs[agent_id]

    def all_agents(self) -> list[AgentConfig]:
        """Return all loaded AgentConfig objects, sorted by agent_id."""
        return sorted(self._configs.values(), key=lambda c: c.agent_id)

    def all_agent_ids(self) -> list[str]:
        """Return all agent IDs, sorted."""
        return sorted(self._configs)

    # ------------------------------------------------------------------
    # Private loading logic
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Parse all .md files in the personas directory."""
        persona_files = sorted(self._dir.glob("*.md"))
        if not persona_files:
            raise FileNotFoundError(
                f"AgentRegistry: no .md files found in '{self._dir.resolve()}'"
            )
        for path in persona_files:
            config = self._parse_file(path)
            self._configs[config.agent_id] = config

    def _parse_file(self, path: Path) -> AgentConfig:
        """
        Extract agent_id, model, temperature, and system prompt from a persona file.

        Expected markdown structure:
            ## Metadata
            * **ID:** agent_01_machiavelli
            * **LLM Engine:** GPT-4o
            * **Temperature:** 0.4
            ...
            ## System Prompt
            You are ...
        """
        content = path.read_text(encoding="utf-8")

        # --- Required metadata fields ---
        id_match    = re.search(r"\*\*ID:\*\*\s+(\S+)", content)
        engine_match = re.search(r"\*\*LLM Engine:\*\*\s+(.+)", content)
        temp_match  = re.search(r"\*\*Temperature:\*\*\s+([\d.]+)", content)
        prompt_match = re.search(r"## System Prompt\s*\n(.*)", content, re.DOTALL)

        if not id_match:
            raise ValueError(f"Persona file '{path.name}' missing '**ID:**' field")
        if not engine_match:
            raise ValueError(f"Persona file '{path.name}' missing '**LLM Engine:**' field")
        if not temp_match:
            raise ValueError(f"Persona file '{path.name}' missing '**Temperature:**' field")
        if not prompt_match:
            raise ValueError(f"Persona file '{path.name}' missing '## System Prompt' section")

        raw_id     = id_match.group(1).strip()
        raw_engine = engine_match.group(1).strip()
        raw_temp   = float(temp_match.group(1))
        raw_prompt = prompt_match.group(1).strip()

        return AgentConfig(
            agent_id=raw_id,
            display_name=DISPLAY_NAMES.get(raw_id, raw_id),
            model=_resolve_model(raw_engine),
            temperature=raw_temp,
            system_prompt_raw=raw_prompt,
        )
