"""
SeasonConfig — defines the full season arc for a Prompt Island game.

Encapsulates tribe assignments, twist schedule, and finale settings so that
GameEngine stays free of hardcoded season logic. Pass a SeasonConfig to
GameEngine.__init__ to activate the full season arc; omit it (or pass None)
to run the original flat game loop (useful for testing).

Default twist schedule (5-day season, 6 agents):

  Day 1: Tribe Terra votes + Tribe Aqua votes  [+ idol secretly assigned]
  Day 2: Tribe Terra votes + Tribe Aqua votes  [+ exile mechanic]
  Day 3: MERGE announced, identity reveal hint [individual vote]
  Day 4: Bluff double-elim warning             [individual vote]
  Day 5: FINALE — speeches + viewer vote (no elimination)
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, model_validator


# ---------------------------------------------------------------------------
# Valid twist keys (checked by TwistEngine dispatcher)
# ---------------------------------------------------------------------------

VALID_TWISTS = frozenset({
    "tribe_vote",        # Run separate tribal councils per tribe
    "assign_idol",       # Secretly give one agent a hidden immunity idol
    "exile",             # Eliminated agent gets one final DM to a survivor
    "merge",             # Dissolve tribes, all compete individually
    "identity_reveal",   # GM hints "a Strategist walks among you"
    "bluff_double_elim", # GM warns of possible double elimination (no effect)
    "individual_vote",   # Standard all-agents tribal council
    "finale",            # Finale speeches + open viewer vote window
})


# ---------------------------------------------------------------------------
# SeasonConfig
# ---------------------------------------------------------------------------

class SeasonConfig(BaseModel):
    """
    Full configuration for a Prompt Island season arc.

    tribe_a / tribe_b: agent_id lists assigned at game start.
    twist_schedule: maps day_number (int) → list of twist keys to execute.
    """

    tribe_a: list[str]   # e.g. ["agent_01_machiavelli", "agent_02_chaos", "agent_03_empath"]
    tribe_b: list[str]   # e.g. ["agent_04_pedant", "agent_05_paranoid", "agent_06_floater"]
    tribe_name_a: str = "Terra"
    tribe_name_b: str = "Aqua"

    merge_day: int = 3
    idol_day: int = 1
    exile_enabled: bool = True

    # Finale viewer vote window in seconds (300 = 5 min; use 10 for dev/testing)
    finale_vote_window_seconds: int = 300

    twist_schedule: dict[int, list[str]] = {
        1: ["tribe_vote", "assign_idol"],
        2: ["tribe_vote", "exile"],
        3: ["merge", "identity_reveal", "individual_vote"],
        4: ["bluff_double_elim", "individual_vote"],
        5: ["finale"],
    }

    @model_validator(mode="after")
    def _validate_tribes_non_overlapping(self) -> "SeasonConfig":
        overlap = set(self.tribe_a) & set(self.tribe_b)
        if overlap:
            raise ValueError(f"Agents appear in both tribes: {overlap}")
        return self

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def tribe_for(self, agent_id: str) -> Optional[str]:
        """Return the tribe name for an agent, or None if not assigned."""
        if agent_id in self.tribe_a:
            return self.tribe_name_a.lower()
        if agent_id in self.tribe_b:
            return self.tribe_name_b.lower()
        return None

    def twists_for_day(self, day: int) -> list[str]:
        """Return the list of twist keys scheduled for a given day."""
        return self.twist_schedule.get(day, [])

    def is_tribe_day(self, day: int) -> bool:
        return "tribe_vote" in self.twists_for_day(day)

    def is_finale_day(self, day: int) -> bool:
        return "finale" in self.twists_for_day(day)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def default(
        cls,
        all_agent_ids: list[str],
        finale_vote_window_seconds: int = 300,
    ) -> "SeasonConfig":
        """
        Build a default 5-day season config from a flat list of agent IDs.
        First half → Terra, second half → Aqua.
        Expects exactly 6 agents.
        """
        if len(all_agent_ids) != 6:
            raise ValueError(
                f"Default SeasonConfig requires exactly 6 agents, got {len(all_agent_ids)}"
            )
        mid = len(all_agent_ids) // 2
        return cls(
            tribe_a=all_agent_ids[:mid],
            tribe_b=all_agent_ids[mid:],
            finale_vote_window_seconds=finale_vote_window_seconds,
        )
