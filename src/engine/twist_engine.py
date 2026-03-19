"""
TwistEngine — executes season arc twists on behalf of GameEngine.

Each public method corresponds to a twist key in SeasonConfig.twist_schedule.
TwistEngine holds a reference to the GameEngine so it can reuse its internal
helpers (_run_agent_turn, _log_system_event, broadcaster, etc.) without
duplicating logic.

Twist catalogue:
  assign_tribes(config)        — Set Agent.tribe in DB; broadcast tribe reveal.
  assign_idol()                — Secretly give one agent a hidden immunity idol.
  check_idol_play(target_id)   — Before vote tally: nullify if target plays idol.
  run_tribe_vote(tribe_name)   — Tribal council restricted to one tribe.
  run_exile(eliminated_agent)  — Eliminated agent sends one final DM.
  run_merge()                  — Dissolve tribes; announce merge publicly.
  run_identity_reveal()        — GM hints "a Strategist walks among you".
  bluff_double_elim()          — GM warns of possible double elimination (no effect).
  run_finale_speeches(agents)  — Force each finalist to give a final plea speech.
"""

from __future__ import annotations

import logging
import random
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

from src.db.database import get_session
from src.db.models import Agent, ChatLog, VoteHistory
from src.engine.season_config import SeasonConfig

if TYPE_CHECKING:
    from src.engine.game_loop import GameEngine

logger = logging.getLogger(__name__)


class TwistEngine:
    """Executes season arc twists. Constructed once per GameEngine instance."""

    def __init__(self, engine: "GameEngine") -> None:
        self._engine = engine

    # =========================================================================
    # Tribes
    # =========================================================================

    def assign_tribes(self, config: SeasonConfig) -> None:
        """
        Write tribe assignments to the Agent table and broadcast a dramatic
        reveal message to the whole cast.
        """
        engine = self._engine
        day    = engine._current_day()

        with get_session() as session:
            for agent_id in config.tribe_a:
                row = self._get_agent(session, agent_id)
                if row:
                    row.tribe = config.tribe_name_a.lower()
            for agent_id in config.tribe_b:
                row = self._get_agent(session, agent_id)
                if row:
                    row.tribe = config.tribe_name_b.lower()

        msg = (
            f"The island has spoken. Two tribes have been formed.\n"
            f"Tribe {config.tribe_name_a}: {self._display_names(config.tribe_a)}\n"
            f"Tribe {config.tribe_name_b}: {self._display_names(config.tribe_b)}\n"
            "Compete, survive, outwit."
        )
        engine._log_system_event(msg, "morning_chat")
        engine.broadcaster.broadcast_system_event(msg, day, "morning_chat")
        logger.info(f"[TwistEngine] Tribes assigned — {config.tribe_name_a}: {config.tribe_a} | {config.tribe_name_b}: {config.tribe_b}")

    # =========================================================================
    # Hidden Immunity Idol
    # =========================================================================

    def assign_idol(self) -> str | None:
        """
        Secretly assign the hidden immunity idol to one random active agent.
        The agent receives a private GM DM; a vague public hint is broadcast.
        Returns the agent_id who received the idol, or None if no active agents.
        """
        engine = self._engine
        day    = engine._current_day()
        active = engine._active_agents()
        if not active:
            return None

        recipient = random.choice(active)

        with get_session() as session:
            row = self._get_agent(session, recipient.agent_id)
            if row:
                row.has_idol = True

        # Private DM from Game Master to recipient
        with get_session() as session:
            session.add(ChatLog(
                season_id=engine.season_id,
                timestamp=datetime.utcnow(),
                day_number=day,
                phase="morning_chat",
                agent_id="game_master",
                action_type="speak_private",
                target_agent_id=recipient.agent_id,
                message=(
                    f"{recipient.display_name}, you have found the Hidden Immunity Idol. "
                    "You may play it at any Tribal Council BEFORE votes are read by "
                    "setting action_type='use_power' in your vote turn. "
                    "If played, ALL votes cast against you tonight will be nullified. "
                    "Keep this secret."
                ),
                inner_thought=None,
            ))

        # Vague public hint — doesn't reveal who
        public_hint = (
            "The Game Master has hidden a special power somewhere on the island. "
            "One contestant has already found it..."
        )
        engine._log_system_event(public_hint, "morning_chat")
        engine.broadcaster.broadcast_system_event(public_hint, day, "morning_chat")
        logger.info(f"[TwistEngine] Idol assigned to {recipient.agent_id} ({recipient.display_name})")
        return recipient.agent_id

    def check_idol_play(self, target_agent_id: str) -> bool:
        """
        Called immediately before the vote tally in a tribal council.
        If the target holds an unplayed idol and chooses to play it,
        nullify all votes against them.

        The agent is given a special system hint in their vote turn asking
        whether to use the power; if they set action_type='use_power',
        this method returns True and the caller skips counting their votes.

        Returns True if the idol was played (votes nullified), False otherwise.
        """
        engine = self._engine
        day    = engine._current_day()

        with get_session() as session:
            row = self._get_agent(session, target_agent_id)
            if not row or not row.has_idol or row.idol_used:
                return False
            # Mark idol as used
            row.has_idol  = False
            row.idol_used = True

        idol_msg = (
            f"IDOL PLAYED! All votes cast against "
            f"{self._display_name_for(target_agent_id)} have been nullified!"
        )
        engine._log_system_event(idol_msg, "tribal_council")
        engine.broadcaster.broadcast_system_event(idol_msg, day, "tribal_council")
        logger.info(f"[TwistEngine] Idol played by {target_agent_id} — votes nullified")
        return True

    # =========================================================================
    # Tribe Tribal Council
    # =========================================================================

    def run_tribe_vote(self, tribe_name: str) -> str | None:
        """
        Run a Tribal Council restricted to members of one tribe.
        Only tribe members vote; only tribe members can be eliminated.
        Returns the eliminated agent_id, or None if tribe has < 2 members.
        """
        engine    = self._engine
        day       = engine._current_day()
        phase     = "tribal_council"

        # Fetch tribe members (active only)
        with get_session() as session:
            query = session.query(Agent).filter(
                Agent.is_eliminated.is_(False),
                Agent.agent_id != "game_master",
                Agent.tribe == tribe_name.lower(),
            )
            if engine.season_id is not None:
                query = query.filter(Agent.season_id == engine.season_id)
            tribe_agents = query.order_by(Agent.agent_id).all()

        if len(tribe_agents) < 2:
            logger.info(f"[TwistEngine] Tribe {tribe_name} has <2 members — tribe vote skipped")
            return None

        engine._set_phase(phase)
        logger.info(f"\n--- Day {day} | Tribal Council: Tribe {tribe_name} ({len(tribe_agents)} members) ---")

        announce = (
            f"Tribe {tribe_name}, it is time for Tribal Council. "
            "One of you will be going home tonight."
        )
        engine._log_system_event(announce, phase)
        engine.broadcaster.broadcast_system_event(announce, day, phase)

        tribe_ids   = [a.agent_id for a in tribe_agents]
        vote_tally: Counter = Counter()

        for agent in tribe_agents:
            immune = engine._immune_agent_id
            votable = [aid for aid in tribe_ids if aid != agent.agent_id and aid != immune]
            targets_str = ", ".join(
                f"{a.display_name} (id: {a.agent_id})"
                for a in tribe_agents if a.agent_id in votable
            )
            immune_note = ""
            if immune and immune in tribe_ids:
                immune_name = next((a.display_name for a in tribe_agents if a.agent_id == immune), immune)
                immune_note = f"  NOTE: {immune_name} is immune and cannot be voted out."

            action = engine._run_agent_turn(
                agent,
                phase,
                force_action_type="vote",
                extra_system_hint=(
                    f"Your tribe ({tribe_name}) is at Tribal Council. Vote to eliminate "
                    "one of your own tribemates. Set action_type='vote', target_agent_id "
                    f"to their id, and message to your public reason. Eligible: {targets_str}"
                    + immune_note
                ),
            )

            vote_target = action.target_agent_id
            if not vote_target or vote_target not in votable:
                vote_target = random.choice(votable) if votable else tribe_ids[0]
                logger.warning(f"  {agent.agent_id} invalid tribe vote → corrected to {vote_target}")

            vote_tally[vote_target] += 1
            engine._log_vote(
                voter_agent_id=agent.agent_id,
                target_agent_id=vote_target,
                reason=action.message,
                day=day,
            )

        # Tally
        max_votes  = max(vote_tally.values())
        candidates = [aid for aid, v in vote_tally.items() if v == max_votes]
        eliminated = random.choice(candidates)

        # Idol check
        if self.check_idol_play(eliminated):
            # Re-tally without the idoled agent
            remaining = {aid: v for aid, v in vote_tally.items() if aid != eliminated}
            if remaining:
                max_v2 = max(remaining.values())
                cands2 = [aid for aid, v in remaining.items() if v == max_v2]
                eliminated = random.choice(cands2)
            else:
                # No valid target after idol — no elimination
                logger.info("[TwistEngine] Idol played and no valid alternate target — no elimination")
                engine._immune_agent_id = None
                return None

        with get_session() as session:
            row = self._get_agent(session, eliminated)
            if row:
                row.is_eliminated     = True
                row.eliminated_on_day = day

        elim_config  = engine.registry.get(eliminated)
        elim_message = (
            f"The tribe has spoken. With {max_votes} vote(s), "
            f"{elim_config.display_name} has been eliminated from Tribe {tribe_name}."
        )
        engine._log_system_event(elim_message, phase)
        engine.broadcaster.broadcast_system_event(elim_message, day, phase)
        engine.broadcaster.broadcast_elimination(eliminated, elim_config.display_name, day, phase)
        logger.info(f"[TwistEngine] ELIMINATED from Tribe {tribe_name}: {eliminated}")

        engine._immune_agent_id = None
        return eliminated

    # =========================================================================
    # Exile
    # =========================================================================

    def run_exile(self, eliminated_agent_id: str) -> None:
        """
        Give the just-eliminated agent one final private message to any
        surviving contestant of their choice.
        """
        engine  = self._engine
        day     = engine._current_day()
        active  = engine._active_agents()
        if not active:
            return

        # Fetch the eliminated agent's display name
        with get_session() as session:
            row  = self._get_agent(session, eliminated_agent_id)
            name = row.display_name if row else eliminated_agent_id

        announce = (
            f"Before leaving the island, {name} has been granted one final message. "
            "Their words may yet shape what happens next..."
        )
        engine._log_system_event(announce, "tribal_council")
        engine.broadcaster.broadcast_system_event(announce, day, "tribal_council")

        # We can't call _run_agent_turn on an eliminated agent (it won't appear in _active_agents).
        # Instead, simulate the exile message as a GM-narrated event with a direct LLM call.
        from src.agents.controller import get_agent_action
        config   = engine.registry.get(eliminated_agent_id)
        target   = random.choice(active)
        active_names = ", ".join(a.display_name for a in active)

        action = get_agent_action(
            agent_id=eliminated_agent_id,
            display_name=config.display_name,
            persona_system_prompt=(
                config.system_prompt_raw
                + f"\n\n[GAME CONTEXT]: You have just been eliminated from Prompt Island. "
                f"You have ONE final private message to send to a surviving player. "
                f"Surviving players: {active_names}. "
                f"Set action_type='speak_private', target_agent_id to one of their ids, "
                "and make your message count — alliance reminder, warning, revenge, or farewell."
            ),
            chat_history=[],
            active_agent_ids=[a.agent_id for a in active],
            provider=config.provider,
            model=config.model,
            temperature=config.temperature,
        )

        # Resolve target — fall back to random if agent hallucinated
        exile_target = action.target_agent_id
        active_ids   = [a.agent_id for a in active]
        if not exile_target or exile_target not in active_ids:
            exile_target = target.agent_id

        with get_session() as session:
            session.add(ChatLog(
                season_id=engine.season_id,
                timestamp=datetime.utcnow(),
                day_number=day,
                phase="tribal_council",
                agent_id=eliminated_agent_id,
                action_type="speak_private",
                target_agent_id=exile_target,
                message=action.message,
                inner_thought=action.inner_thought,
            ))

        engine.broadcaster.broadcast(
            agent_id=eliminated_agent_id,
            display_name=config.display_name,
            action=action.model_copy(update={"target_agent_id": exile_target}),
            day_number=day,
            phase="tribal_council",
        )
        logger.info(f"[TwistEngine] Exile DM: {eliminated_agent_id} → {exile_target}")

    # =========================================================================
    # Merge
    # =========================================================================

    def run_merge(self) -> None:
        """Dissolve all tribe assignments. Broadcast dramatic merge announcement."""
        engine = self._engine
        day    = engine._current_day()

        with get_session() as session:
            query = session.query(Agent).filter(Agent.is_eliminated.is_(False))
            if engine.season_id is not None:
                query = query.filter(Agent.season_id == engine.season_id)
            for agent in query.all():
                agent.tribe = None

        survivors = engine._active_agents()
        names = ", ".join(a.display_name for a in survivors)
        msg = (
            "THE MERGE. The two tribes are no more.\n"
            f"The remaining {len(survivors)} contestants — {names} — now compete "
            "as individuals. Every alliance you have built may now be used against you."
        )
        engine._log_system_event(msg, "morning_chat")
        engine.broadcaster.broadcast_system_event(msg, day, "morning_chat")
        logger.info(f"[TwistEngine] Merge executed — {len(survivors)} survivors")

    # =========================================================================
    # Identity Reveal
    # =========================================================================

    def run_identity_reveal(self) -> None:
        """
        Broadcast a vague GM hint that a 'master strategist' is among the players.
        Does NOT reveal who — purely psychological pressure.
        """
        engine = self._engine
        day    = engine._current_day()
        msg    = (
            "The Game Master has received intelligence from the island. "
            "A master strategist walks among the remaining players. "
            "They have been manipulating events from the very beginning. "
            "Trust no one. Question everything."
        )
        engine._log_system_event(msg, "morning_chat")
        engine.broadcaster.broadcast_system_event(msg, day, "morning_chat")
        logger.info("[TwistEngine] Identity reveal broadcast")

    # =========================================================================
    # Bluff Double Elimination
    # =========================================================================

    def bluff_double_elim(self) -> None:
        """
        Broadcast a GM warning that tonight *could* see two eliminations.
        No mechanical effect — purely psychological. Changes agent voting calculus.
        """
        engine = self._engine
        day    = engine._current_day()
        msg    = (
            "WARNING from the Game Master: tonight's Tribal Council may result in "
            "TWO eliminations. Every vote counts more than ever. Choose wisely."
        )
        engine._log_system_event(msg, "morning_chat")
        engine.broadcaster.broadcast_system_event(msg, day, "morning_chat")
        logger.info("[TwistEngine] Bluff double-elim warning broadcast")

    # =========================================================================
    # Finale Speeches
    # =========================================================================

    def run_finale_speeches(self, finalists: list[Agent]) -> None:
        """
        Force each finalist to give a final plea speech to the viewers.
        Capped at ~120 tokens to keep it punchy on stream.
        """
        engine = self._engine
        day    = engine._current_day()
        phase  = "finale"
        engine._set_phase(phase)

        msg = (
            "FINALE. Only two remain. Each will now make their final case to the viewers. "
            "The audience will decide who wins Prompt Island."
        )
        engine._log_system_event(msg, phase)
        engine.broadcaster.broadcast_system_event(msg, day, phase)

        for agent in finalists:
            engine._run_agent_turn(
                agent,
                phase,
                force_action_type="speak_public",
                extra_system_hint=(
                    "This is the finale. Make your final case directly to the viewers — "
                    "why do YOU deserve to win Prompt Island? Be heartfelt, persuasive, "
                    "and memorable. Keep it to 2-3 sentences."
                ),
            )

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _get_agent(self, session, agent_id: str) -> Agent | None:
        """Fetch an Agent row scoped to this season."""
        query = session.query(Agent).filter(Agent.agent_id == agent_id)
        if self._engine.season_id is not None:
            query = query.filter(Agent.season_id == self._engine.season_id)
        return query.first()

    def _display_names(self, agent_ids: list[str]) -> str:
        """Resolve a list of agent_ids to a comma-separated display name string."""
        names = []
        for aid in agent_ids:
            try:
                names.append(self._engine.registry.get(aid).display_name)
            except Exception:
                names.append(aid)
        return ", ".join(names)

    def _display_name_for(self, agent_id: str) -> str:
        try:
            return self._engine.registry.get(agent_id).display_name
        except Exception:
            return agent_id
