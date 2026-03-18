"""
GameEngine — central state machine for Prompt Island.

Drives the full daily loop per GAME_LOOP.md §2:

  Phase 1: Morning Chat       — round-robin public socializing (2-3 cycles)
  Phase 2: Challenge          — optional Game Master challenge with LLM judge
  Phase 3: Scramble           — private DMs, max 2 per agent per day
  Phase 4: Tribal Council     — every agent votes; plurality is eliminated
  Phase 5: Night Consolidation — per-agent LLM summaries; vector DB stub (Phase 3)

The Engine:
  - Is the ONLY writer to the DB during a game run (single-writer rule).
  - Delegates ALL LLM calls to agents.controller.get_agent_action() which
    enforces the 3-retry + fallback guarantee — the game loop NEVER crashes
    due to a bad LLM response (ERROR_HANDLING.md §1).
  - Delegates memory context to MemoryManager.
  - Writes every event to the EventBroadcaster (JSONL for Phase 3 frontend).
"""

from __future__ import annotations

import logging
import random
from collections import Counter, defaultdict
from datetime import datetime

from openai import OpenAI

from src.agents.controller import get_agent_action
from src.db.database import set_season_winner

# Lazy singleton — same pattern as controller.py; defers instantiation until first use.
_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client
from src.agents.registry import AgentConfig, AgentRegistry
from src.agents.schemas import AgentAction, NightSummaryResult
from src.memory.chroma_store import ChromaMemoryStore
from src.broadcast.broadcaster import EventBroadcaster
from src.db.database import get_session, init_db
from src.db.models import Agent, ChatLog, GameState, VoteHistory
from src.memory.manager import MemoryManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Game-loop constants (per GAME_LOOP.md §2)
# ---------------------------------------------------------------------------

MORNING_CHAT_CYCLES: int = 2    # Number of round-robin speaking cycles each morning
MAX_DMS_PER_AGENT:   int = 2    # Max DM initiations per agent per day (Phase 3)
DM_REPLY_TURNS:      int = 1    # How many reply turns the DM target gets

# System prompt for the LLM challenge judge
_CHALLENGE_JUDGE_PROMPT = """\
You are the impartial Game Master of a reality show called Prompt Island.
Below are the contestant responses to today's challenge.
Choose the single best response based on creativity and relevance to the challenge.
Reply with ONLY the agent_id of the winner — for example: agent_01_machiavelli

Challenge: {challenge_prompt}

Contestant responses:
{responses}
"""

# System prompt for the per-agent nightly summary (structured output → NightSummaryResult)
_NIGHT_SUMMARY_PROMPT = """\
You are {display_name}, a contestant on Prompt Island.
Below is the complete transcript of Day {day} that you witnessed:

{transcript}

Respond with a JSON object containing:
  "summary":  3–5 sentences summarising the day's key events from YOUR first-person perspective.
              Focus on alliances, betrayals, suspicions, and important conversations.
              Write as {display_name} — use "I", "me", "my".
  "category": The single most relevant memory type for today:
              "alliance"          — a new alliance formed or an existing one broke
              "betrayal"          — someone lied to you, backstabbed you, or voted against you
              "challenge_result"  — a challenge was the defining event of the day
              "general_observation" — none of the above
"""


class GameEngine:
    """
    Orchestrates the full Prompt Island game loop.

    Typical usage:
        engine = GameEngine()
        engine.initialize_game()
        engine.run_game(max_days=10, challenges=["Build a raft", None, "Trivia quiz"])
    """

    def __init__(
        self,
        registry:    AgentRegistry    | None = None,
        memory:      MemoryManager    | None = None,
        broadcaster: EventBroadcaster | None = None,
        chroma_store: ChromaMemoryStore | None = None,
        season_id:   int | None = None,
    ) -> None:
        self.season_id   = season_id
        self.registry    = registry or AgentRegistry()
        # Wire ChromaDB into memory — create a default store unless one is injected.
        # Pass memory=MemoryManager() (no args) to disable long-term memory in tests.
        if memory is not None:
            self.memory = memory
        else:
            store = chroma_store or ChromaMemoryStore(season_id=season_id)
            self.memory = MemoryManager(chroma_store=store, season_id=season_id)
        self.broadcaster = broadcaster or EventBroadcaster()

        # Set by run_challenge(); cleared after run_tribal_council()
        self._immune_agent_id: str | None = None

        # Ensure DB tables exist
        init_db()

    # =========================================================================
    # Initialization
    # =========================================================================

    def initialize_game(self) -> None:
        """
        Seed the database and announce the game start.
        Called ONCE before the first run_day().

        Per GAME_LOOP.md §1:
          - Load all active agents from personas/.
          - Initialize database connections.
          - Announce the start of the game in the Public Chat.
        """
        # Idempotency guard — scoped to this season so a new season can be
        # initialized even when rows from previous seasons exist.
        with get_session() as session:
            query = session.query(Agent)
            if self.season_id is not None:
                query = query.filter(Agent.season_id == self.season_id)
            if query.first():
                logger.warning(
                    f"initialize_game() called on a non-empty database for season "
                    f"{self.season_id} — skipping seed. Use --new-season to start fresh."
                )
                return

        with get_session() as session:
            # GameState row (one active row per season)
            gs = GameState(
                season_id=self.season_id,
                current_day=1,
                current_phase="morning_chat",
                is_active=True,
            )
            session.add(gs)

            # Seed the 'game_master' pseudo-agent so ChatLog FK constraint is satisfied
            # when we write system_event rows.  Marked as eliminated so it never
            # appears in active-agent queries.
            gm = Agent(
                agent_id="game_master",
                season_id=self.season_id,
                display_name="Game Master",
                is_eliminated=True,
            )
            session.add(gm)

            # Seed all real contestant agents from the registry
            for config in self.registry.all_agents():
                agent = Agent(
                    agent_id=config.agent_id,
                    season_id=self.season_id,
                    display_name=config.display_name,
                    is_eliminated=False,
                )
                session.add(agent)

        announcement = (
            "Welcome to Prompt Island! The social experiment has begun. "
            "6 contestants. 1 winner. Trust no one."
        )
        self._log_system_event(announcement, "morning_chat")
        self.broadcaster.broadcast_system_event(announcement, day_number=1, phase="morning_chat")
        logger.info("=" * 60)
        logger.info("=== PROMPT ISLAND — GAME INITIALIZED ===")
        logger.info(f"    Contestants: {[c.display_name for c in self.registry.all_agents()]}")
        logger.info("=" * 60)

    # =========================================================================
    # Phase 1: Morning Chat
    # =========================================================================

    def run_morning_chat(self) -> None:
        """
        Round-robin public socializing for MORNING_CHAT_CYCLES cycles.
        Every active agent speaks_public once per cycle in a shuffled order.
        Per GAME_LOOP.md §2 Phase 1.
        """
        day   = self._current_day()
        phase = "morning_chat"
        self._set_phase(phase)

        active = self._active_agents()
        if len(active) < 2:
            return

        logger.info(f"\n--- Day {day} | Phase 1: Morning Chat ({MORNING_CHAT_CYCLES} cycles) ---")

        for cycle in range(1, MORNING_CHAT_CYCLES + 1):
            order = active.copy()
            random.shuffle(order)
            logger.info(f"  Cycle {cycle}/{MORNING_CHAT_CYCLES}")
            for agent in order:
                self._run_agent_turn(agent, phase, force_action_type="speak_public")

    # =========================================================================
    # Phase 2: Challenge
    # =========================================================================

    def run_challenge(self, challenge_prompt: str | None = None) -> str | None:
        """
        Optional daily challenge. Skipped when challenge_prompt is None.
        Per GAME_LOOP.md §2 Phase 2.

        Args:
            challenge_prompt: The challenge description from the Game Master.
                              Pass None to skip.

        Returns:
            The agent_id of the winner (granted immunity), or None if skipped.
        """
        if not challenge_prompt:
            logger.info(f"\n--- Day {self._current_day()} | Phase 2: Challenge — SKIPPED ---")
            return None

        day   = self._current_day()
        phase = "challenge"
        self._set_phase(phase)

        logger.info(f"\n--- Day {day} | Phase 2: Challenge ---")
        logger.info(f"  Prompt: {challenge_prompt}")

        # Announce challenge to all agents via system event
        self._log_system_event(f"CHALLENGE: {challenge_prompt}", phase)
        self.broadcaster.broadcast_system_event(f"CHALLENGE: {challenge_prompt}", day, phase)

        # Collect all agents' responses
        active = self._active_agents()
        responses: dict[str, AgentAction] = {}
        for agent in active:
            action = self._run_agent_turn(
                agent,
                phase,
                extra_system_hint=(
                    f"The Game Master has issued a challenge: '{challenge_prompt}'. "
                    "Respond with your best answer or strategy using speak_public."
                ),
            )
            responses[agent.agent_id] = action

        # LLM judge picks the winner
        winner_id = self._judge_challenge(challenge_prompt, responses)
        winner_config = self.registry.get(winner_id)

        # Announce immunity
        immune_msg = (
            f"{winner_config.display_name} wins the challenge and is IMMUNE "
            "from elimination today!"
        )
        self._log_system_event(immune_msg, phase)
        self.broadcaster.broadcast_system_event(immune_msg, day, phase)
        logger.info(f"  Winner: {winner_id} ({winner_config.display_name}) — IMMUNE")

        self._immune_agent_id = winner_id
        return winner_id

    def _judge_challenge(
        self,
        challenge_prompt: str,
        responses: dict[str, AgentAction],
    ) -> str:
        """
        Use GPT-4o-mini to evaluate challenge responses and pick the best one.
        Falls back to a random choice if the judge call fails.
        """
        response_lines = "\n".join(
            f'- {agent_id}: "{action.message}"'
            for agent_id, action in responses.items()
        )
        try:
            result = _get_openai_client().chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": _CHALLENGE_JUDGE_PROMPT.format(
                        challenge_prompt=challenge_prompt,
                        responses=response_lines,
                    ),
                }],
                temperature=0.0,
                max_tokens=60,
            )
            raw = result.choices[0].message.content.strip()
            # The judge should return an agent_id; scan for the first match
            for agent_id in responses:
                if agent_id in raw:
                    return agent_id
        except Exception as exc:
            logger.warning(f"  Challenge judge LLM call failed ({exc}). Picking random winner.")

        return random.choice(list(responses.keys()))

    # =========================================================================
    # Phase 3: Scramble (DMs)
    # =========================================================================

    def run_scramble(self) -> None:
        """
        Private plotting phase. Each agent may initiate up to MAX_DMS_PER_AGENT
        private conversations per day.
        Per GAME_LOOP.md §2 Phase 3.

        Flow per initiating agent:
          1. Agent submits a speak_private action, choosing their target.
          2. If both parties are within their DM limit, the DM runs.
          3. Target replies once (speak_private back to initiator).
          4. Counts are incremented for both parties.
        """
        day   = self._current_day()
        phase = "scramble"
        self._set_phase(phase)

        active     = self._active_agents()
        active_ids = [a.agent_id for a in active]

        logger.info(f"\n--- Day {day} | Phase 3: Scramble (max {MAX_DMS_PER_AGENT} DMs/agent) ---")

        # Track DM participation count per agent for this day
        dm_counts: dict[str, int] = defaultdict(int)

        # Random order prevents the first agent always getting first choice
        initiators = active.copy()
        random.shuffle(initiators)

        for initiator in initiators:
            if dm_counts[initiator.agent_id] >= MAX_DMS_PER_AGENT:
                continue  # This agent has exhausted their DMs today

            # Agent decides who to approach for a private chat
            active_names_map = ", ".join(
                f"{a.display_name} (id: {a.agent_id})"
                for a in active if a.agent_id != initiator.agent_id
            )
            initiation_action = self._run_agent_turn(
                initiator,
                phase,
                force_action_type="speak_private",
                extra_system_hint=(
                    "You are in The Scramble. Choose one other contestant to DM about "
                    "voting strategy. Set action_type='speak_private' and target_agent_id "
                    f"to their id. Other contestants: {active_names_map}"
                ),
            )

            target_id = initiation_action.target_agent_id

            # --- Validate DM target ---
            if not target_id:
                logger.warning(f"  {initiator.agent_id} provided no target_agent_id — DM skipped")
                continue
            if target_id == initiator.agent_id:
                logger.warning(f"  {initiator.agent_id} tried to DM themselves — DM skipped")
                continue
            if target_id not in active_ids:
                logger.warning(
                    f"  {initiator.agent_id} targeted non-active agent '{target_id}' — DM skipped"
                )
                continue
            if dm_counts[target_id] >= MAX_DMS_PER_AGENT:
                logger.info(f"  {target_id} has maxed their DMs — {initiator.agent_id}'s request dropped")
                continue

            # Increment counts for both parties before the exchange runs
            dm_counts[initiator.agent_id] += 1
            dm_counts[target_id]           += 1

            logger.info(f"  DM: {initiator.agent_id} → {target_id}")

            # The target replies to the initiator's opening message
            target_agent = next(a for a in active if a.agent_id == target_id)
            for _ in range(DM_REPLY_TURNS):
                self._run_agent_turn(
                    target_agent,
                    phase,
                    force_action_type="speak_private",
                    extra_system_hint=(
                        f"{initiator.display_name} just messaged you privately: "
                        f'"{initiation_action.message}". Reply to them privately.'
                    ),
                )

    # =========================================================================
    # Phase 4: Tribal Council (Voting)
    # =========================================================================

    def run_tribal_council(self) -> str:
        """
        All active agents cast a vote. The plurality is eliminated.
        Ties are broken randomly.
        Per GAME_LOOP.md §2 Phase 4.

        The immune agent (set by run_challenge) cannot be voted out but may
        still cast a vote.

        Returns:
            The agent_id of the eliminated contestant.
        """
        day   = self._current_day()
        phase = "tribal_council"
        self._set_phase(phase)

        active      = self._active_agents()
        active_ids  = [a.agent_id for a in active]
        # Immune agent is excluded from the target pool only
        votable_ids = [
            aid for aid in active_ids
            if aid != self._immune_agent_id
        ]

        logger.info(f"\n--- Day {day} | Phase 4: Tribal Council ---")
        if self._immune_agent_id:
            logger.info(f"  Immune (cannot be voted out): {self._immune_agent_id}")

        self._log_system_event(
            "Tribal Council has begun. Each contestant will now cast their vote in secret.",
            phase,
        )

        vote_tally: Counter = Counter()

        # Build a name→id reference for agents to use when voting
        votable_agents = [a for a in active if a.agent_id in votable_ids]
        for agent in active:
            targets_str = ", ".join(
                f"{a.display_name} (id: {a.agent_id})"
                for a in votable_agents if a.agent_id != agent.agent_id
            )
            immune_note = ""
            if self._immune_agent_id:
                immune_name = next(
                    (a.display_name for a in active if a.agent_id == self._immune_agent_id),
                    self._immune_agent_id,
                )
                immune_note = f"  NOTE: {immune_name} is immune and cannot be voted out."

            action = self._run_agent_turn(
                agent,
                phase,
                force_action_type="vote",
                extra_system_hint=(
                    "It is Tribal Council. You MUST cast a vote right now. "
                    "Set action_type='vote', target_agent_id to the id of the contestant "
                    "you are voting for, and message to your public reason. "
                    f"Eligible targets: {targets_str}"
                    + immune_note
                ),
            )

            vote_target = action.target_agent_id

            # --- Sanitise vote target ---
            # If the agent hallucinated an invalid target, redirect to a random eligible one
            if not vote_target or vote_target not in votable_ids or vote_target == agent.agent_id:
                eligible = [vid for vid in votable_ids if vid != agent.agent_id]
                if not eligible:
                    eligible = votable_ids
                corrected = random.choice(eligible)
                logger.warning(
                    f"  {agent.agent_id} invalid vote '{vote_target}' → corrected to {corrected}"
                )
                vote_target = corrected

            vote_tally[vote_target] += 1

            # Persist vote to VoteHistory table
            self._log_vote(
                voter_agent_id=agent.agent_id,
                target_agent_id=vote_target,
                reason=action.message,
                day=day,
            )
            logger.info(f"  VOTE: {agent.agent_id} → {vote_target}")

        # --- Tally and eliminate ---
        logger.info(f"  Tally: {dict(vote_tally)}")
        max_votes   = max(vote_tally.values())
        candidates  = [aid for aid, v in vote_tally.items() if v == max_votes]
        eliminated  = random.choice(candidates)  # random tie-break

        # Mark eliminated in DB
        with get_session() as session:
            row = session.get(Agent, eliminated)
            row.is_eliminated     = True
            row.eliminated_on_day = day

        elim_config  = self.registry.get(eliminated)
        elim_message = (
            f"The votes have been read. With {max_votes} vote(s), "
            f"{elim_config.display_name} has been eliminated from Prompt Island."
        )
        self._log_system_event(elim_message, phase)
        self.broadcaster.broadcast_system_event(elim_message, day, phase)
        self.broadcaster.broadcast_elimination(eliminated, elim_config.display_name, day, phase)
        logger.info(f"  ELIMINATED: {eliminated} ({elim_config.display_name})")

        # Reset immunity for the next day
        self._immune_agent_id = None

        return eliminated

    # =========================================================================
    # Phase 5: Night Consolidation
    # =========================================================================

    def run_night_consolidation(self) -> None:
        """
        Per-agent LLM summarization of the day's transcript.
        Per GAME_LOOP.md §2 Phase 5 and MEMORY_AND_RAG.md §2.

        1. Fetch the full day's ChatLog transcript.
        2. For each surviving agent, call GPT-4o-mini for a first-person summary.
        3. [STUB] Store in vector DB — Phase 3 will implement ChromaDB persistence.
        4. Advance day counter and reset phase to morning_chat.
        """
        day   = self._current_day()
        phase = "night_consolidation"
        self._set_phase(phase)

        logger.info(f"\n--- Day {day} | Phase 5: Night Consolidation ---")

        # Pull complete day transcript from ChatLog once; filter per-agent below
        with get_session() as session:
            query = session.query(ChatLog).filter(ChatLog.day_number == day)
            if self.season_id is not None:
                query = query.filter(ChatLog.season_id == self.season_id)
            all_logs = query.order_by(ChatLog.timestamp.asc()).all()
            # Detach-safe: capture needed fields before session closes
            log_snapshots = [
                {
                    "phase":           log.phase,
                    "agent_id":        log.agent_id,
                    "target_agent_id": log.target_agent_id,
                    "action_type":     log.action_type,
                    "message":         log.message,
                }
                for log in all_logs
            ]

        # Summarize from each surviving agent's first-person perspective
        for agent in self._active_agents():
            config = self.registry.get(agent.agent_id)

            # Build an agent-specific transcript that respects DM secrecy:
            #   - speak_public, vote, system_event → always visible
            #   - speak_private → only visible if this agent was sender or receiver
            agent_lines = [
                f"[{s['phase']}] {s['agent_id']}: {s['message']}"
                for s in log_snapshots
                if s["action_type"] in ("speak_public", "vote", "system_event")
                or s["agent_id"] == agent.agent_id
                or s["target_agent_id"] == agent.agent_id
            ]
            transcript = "\n".join(agent_lines) or "(No dialogue recorded today.)"

            try:
                # Single structured output call: get summary + memory category together.
                # Using NightSummaryResult avoids a second LLM call just for classification.
                # Intentionally always uses OpenAI gpt-4o-mini here (not the agent's own
                # provider): gpt-4o-mini is cheap, reliable for summarisation, and
                # Structured Outputs guarantee schema compliance without provider-specific
                # adaptation logic in the night phase.
                summary_resp = _get_openai_client().beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": _NIGHT_SUMMARY_PROMPT.format(
                            display_name=config.display_name,
                            day=day,
                            transcript=transcript,
                        ),
                    }],
                    response_format=NightSummaryResult,
                    temperature=0.3,
                )
                result: NightSummaryResult | None = summary_resp.choices[0].message.parsed
                if result is None:
                    raise ValueError("Night summary returned null parsed response")

                logger.info(
                    f"  [{agent.agent_id}] Summary ({result.category}): "
                    f"{result.summary[:100]}..."
                )

                # Persist to ChromaDB — enables RAG retrieval from Day 2 onwards
                self.memory.store_memory(
                    agent_id=agent.agent_id,
                    day_number=day,
                    content=result.summary,
                    category=result.category,
                )

            except Exception as exc:
                logger.error(f"  Night summary failed for {agent.agent_id}: {exc}")

        # Advance the game day
        with get_session() as session:
            query = session.query(GameState).filter(GameState.is_active.is_(True))
            if self.season_id is not None:
                query = query.filter(GameState.season_id == self.season_id)
            gs = query.first()
            gs.current_day  += 1
            gs.current_phase = "morning_chat"

        logger.info(f"  Day {day} complete → advancing to Day {day + 1}")

    # =========================================================================
    # Daily loop orchestrator
    # =========================================================================

    def run_day(self, challenge_prompt: str | None = None) -> bool:
        """
        Execute all 5 phases for one game day.

        Args:
            challenge_prompt: Optional challenge text for Phase 2. None = skip.

        Returns:
            True  → game continues (≥ 2 agents remain).
            False → game is over (≤ 1 agent remains).
        """
        day    = self._current_day()
        active = self._active_agents()

        logger.info(f"\n{'=' * 60}")
        logger.info(f"=== DAY {day} BEGIN — {len(active)} contestants active ===")
        logger.info(f"{'=' * 60}")

        self.run_morning_chat()
        self.run_challenge(challenge_prompt)
        self.run_scramble()
        self.run_tribal_council()
        self.run_night_consolidation()

        # Win-condition check
        survivors = self._active_agents()
        if len(survivors) <= 1:
            if survivors:
                winner = self.registry.get(survivors[0].agent_id)
                victory_msg = (
                    f"{winner.display_name} is the last contestant standing "
                    "and wins Prompt Island!"
                )
                self._log_system_event(victory_msg, "night_consolidation")
                self.broadcaster.broadcast_system_event(
                    victory_msg, day, "night_consolidation"
                )
                # Record the winner on the Season row
                if self.season_id is not None:
                    set_season_winner(
                        self.season_id,
                        winner.agent_id,
                        winner.display_name,
                    )
                logger.info(
                    f"\n{'=' * 60}\n"
                    f"=== GAME OVER — WINNER: {winner.display_name} ({winner.agent_id}) ===\n"
                    f"{'=' * 60}"
                )
            return False   # Stop the game loop

        return True   # Continue to the next day

    def run_game(
        self,
        max_days: int = 30,
        challenges: list[str | None] | None = None,
    ) -> None:
        """
        Full game loop from Day 1 until one winner remains or max_days is hit.

        Args:
            max_days:   Safety ceiling to prevent infinite loops. Default: 30.
            challenges: Optional list of challenge prompts, one per day.
                        None entries skip the challenge that day.
                        The list is cycled if shorter than max_days.
        """
        challenges = challenges or [None]

        for day_index in range(max_days):
            challenge = challenges[day_index % len(challenges)]
            should_continue = self.run_day(challenge_prompt=challenge)
            if not should_continue:
                return

        logger.warning(
            f"Game reached max_days={max_days} safety ceiling without a winner. "
            "Increase max_days or check for stalled elimination logic."
        )

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _run_agent_turn(
        self,
        agent: Agent,
        phase: str,
        force_action_type: str | None = None,
        extra_system_hint: str = "",
    ) -> AgentAction:
        """
        Orchestrate a single agent turn end-to-end:
          1. Fetch working memory (ChatLog context for this phase/day).
          2. Fetch long-term memories (Phase 3 stub — currently empty).
          3. Compose the full system prompt (persona + memory + hints).
          4. Call get_agent_action() — 3-retry + Brain Freeze fallback guaranteed.
          5. Enforce force_action_type override if the agent disobeyed the hint.
          6. Persist to ChatLog and broadcast.

        Returns the validated (and possibly corrected) AgentAction.
        """
        day    = self._current_day()
        config = self.registry.get(agent.agent_id)
        active_ids = [a.agent_id for a in self._active_agents()]

        # 1. Working memory — recent phase transcript
        chat_history = self.memory.get_working_memory(agent.agent_id, day, phase)

        # 2. Long-term memory — Phase 3 stub
        lt_memories  = self.memory.get_long_term_memories(
            agent.agent_id,
            context_query=f"Day {day} {phase} social interactions and alliances",
        )
        memory_block = self.memory.format_memories_for_prompt(lt_memories)

        # 3. Compose system prompt
        persona = config.system_prompt_raw
        if memory_block:
            persona += f"\n\n{memory_block}"
        if extra_system_hint:
            persona += f"\n\n[GAME CONTEXT]: {extra_system_hint}"
        if force_action_type:
            persona += (
                f"\n\n[MANDATORY]: Your response MUST use action_type='{force_action_type}'. "
                "No other action_type is permitted this turn."
            )

        # 4. LLM call — never raises (Brain Freeze guarantees a response)
        action = get_agent_action(
            agent_id=agent.agent_id,
            display_name=config.display_name,
            persona_system_prompt=persona,
            chat_history=chat_history,
            active_agent_ids=active_ids,
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
        )

        # 5. Force-type override — if the agent disobeyed a mandatory action type,
        #    patch the action so the Engine's phase logic is never broken.
        if force_action_type and action.action_type != force_action_type:
            logger.warning(
                f"  [{agent.agent_id}] disobeyed force_action_type='{force_action_type}' "
                f"(got '{action.action_type}') — overriding."
            )
            action = action.model_copy(update={"action_type": force_action_type})

        # 6. Persist to DB
        self._log_action(action, agent, phase, day)

        # 7. Broadcast
        self.broadcaster.broadcast(
            agent_id=agent.agent_id,
            display_name=config.display_name,
            action=action,
            day_number=day,
            phase=phase,
        )

        return action

    # ------------------------------------------------------------------
    # DB read helpers
    # ------------------------------------------------------------------

    def _active_agents(self) -> list[Agent]:
        """Return all non-eliminated, non-game_master agents for the current season."""
        with get_session() as session:
            query = session.query(Agent).filter(
                Agent.is_eliminated.is_(False),
                Agent.agent_id != "game_master",
            )
            if self.season_id is not None:
                query = query.filter(Agent.season_id == self.season_id)
            return query.order_by(Agent.agent_id).all()

    def _current_day(self) -> int:
        """Return current_day from the active GameState row for this season."""
        with get_session() as session:
            query = session.query(GameState).filter(GameState.is_active.is_(True))
            if self.season_id is not None:
                query = query.filter(GameState.season_id == self.season_id)
            gs = query.first()
            return gs.current_day if gs else 1

    # ------------------------------------------------------------------
    # DB write helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: str) -> None:
        """Update GameState.current_phase and broadcast the transition."""
        with get_session() as session:
            query = session.query(GameState).filter(GameState.is_active.is_(True))
            if self.season_id is not None:
                query = query.filter(GameState.season_id == self.season_id)
            gs = query.first()
            if gs:
                gs.current_phase = phase
        self.broadcaster.broadcast_phase_change(phase, self._current_day())

    def _log_action(
        self,
        action: AgentAction,
        agent: Agent,
        phase: str,
        day: int,
    ) -> None:
        """Insert a ChatLog row for a completed agent action."""
        with get_session() as session:
            session.add(ChatLog(
                season_id=self.season_id,
                timestamp=datetime.utcnow(),
                day_number=day,
                phase=phase,
                agent_id=agent.agent_id,
                action_type=action.action_type,
                target_agent_id=action.target_agent_id,
                message=action.message,
                inner_thought=action.inner_thought,
            ))

    def _log_system_event(self, message: str, phase: str) -> None:
        """Insert a system_event ChatLog row (Game Master announcement)."""
        with get_session() as session:
            session.add(ChatLog(
                season_id=self.season_id,
                timestamp=datetime.utcnow(),
                day_number=self._current_day(),
                phase=phase,
                agent_id="game_master",
                action_type="system_event",
                message=message,
                inner_thought=None,
            ))

    def _log_vote(
        self,
        voter_agent_id: str,
        target_agent_id: str,
        reason: str,
        day: int,
    ) -> None:
        """Insert a VoteHistory row."""
        with get_session() as session:
            session.add(VoteHistory(
                season_id=self.season_id,
                day_number=day,
                voter_agent_id=voter_agent_id,
                target_agent_id=target_agent_id,
                reason=reason,
            ))
