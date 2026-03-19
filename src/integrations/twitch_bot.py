"""
Prompt Island — Twitch IRC viewer-vote bot.

Reads `!vote <name>` commands in a Twitch channel and forwards them to the
local `/vote` API endpoint.  The bot runs in a background daemon thread so
it never blocks the game loop.

Configuration (via environment variables):
    TWITCH_BOT_TOKEN   OAuth token for the bot account (starts with "oauth:")
    TWITCH_CHANNEL     Channel to monitor (without the # prefix, e.g. "promptisland")
    TWITCH_BOT_NICK    Bot account username (default: derived from token if omitted)
    API_BASE_URL       Base URL for the Prompt Island API (default: http://localhost:8000)

If TWITCH_BOT_TOKEN or TWITCH_CHANNEL are absent the bot silently skips startup.

Usage:
    from src.integrations.twitch_bot import start_twitch_bot
    start_twitch_bot()   # no-op if env vars missing

The bot uses the twitchio library (pip install twitchio).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise(name: str) -> str:
    """Lower-case, strip whitespace — used for fuzzy finalist matching."""
    return name.strip().lower()


def _post_vote(agent_id: str, viewer_id: str, api_base: str) -> None:
    """POST a vote to the local API.  Runs in the bot's async context."""
    import urllib.request
    import json

    payload = json.dumps({"agent_id": agent_id, "viewer_id": viewer_id}).encode()
    req = urllib.request.Request(
        f"{api_base}/vote",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.debug("Vote accepted: %s → %s (status %s)", viewer_id, agent_id, resp.status)
    except Exception as exc:
        logger.debug("Vote POST failed: %s", exc)


# ---------------------------------------------------------------------------
# TwitchVoteBot — thin twitchio wrapper
# ---------------------------------------------------------------------------


class TwitchVoteBot:
    """
    Minimal twitchio bot that:
      1. Joins a single channel.
      2. Listens for `!vote <name>` messages.
      3. Resolves <name> against the current finalist list (case-insensitive).
      4. POSTs to the local /vote endpoint with viewer_id="twitch:{username}".
    """

    def __init__(self, token: str, channel: str, nick: str, api_base: str) -> None:
        self._token    = token
        self._channel  = channel
        self._nick     = nick
        self._api_base = api_base

        # Finalist mapping: lower(display_name) → agent_id
        # Updated by set_finalists() when the vote window opens.
        self._finalists: dict[str, str] = {}

    def set_finalists(self, finalists: list[dict]) -> None:
        """
        Update the active finalist mapping.

        finalists: [{"agent_id": "...", "display_name": "..."}, ...]
        """
        self._finalists = {_normalise(f["display_name"]): f["agent_id"] for f in finalists}
        logger.info("Twitch bot: finalists set — %s", list(self._finalists.keys()))

    def clear_finalists(self) -> None:
        """Clear finalists when the vote window closes."""
        self._finalists = {}

    def run(self) -> None:
        """Blocking call — run inside a daemon thread."""
        try:
            import twitchio  # noqa: F401
            from twitchio.ext import commands as tio_commands
        except ImportError:
            logger.warning(
                "twitchio is not installed — Twitch bot disabled. "
                "Install it with: pip install twitchio"
            )
            return

        bot_instance = self
        api_base     = self._api_base
        finalists_ref = self

        class _Bot(tio_commands.Bot):
            def __init__(self):
                super().__init__(
                    token=bot_instance._token,
                    prefix="!",
                    initial_channels=[f"#{bot_instance._channel}"],
                )

            async def event_ready(self):
                logger.info(
                    "Twitch bot connected as %s — watching #%s",
                    self.nick,
                    bot_instance._channel,
                )

            async def event_message(self, message):
                # Ignore messages from the bot itself
                if message.echo:
                    return
                await self.handle_commands(message)

            @tio_commands.command(name="vote")
            async def vote_command(self, ctx):
                """!vote <contestant_name>"""
                content = ctx.message.content.strip()
                # Strip the command prefix + command name
                parts   = content.split(None, 1)
                if len(parts) < 2:
                    return
                name_arg = _normalise(parts[1])

                # Fuzzy match: exact, then prefix
                agent_id = finalists_ref._finalists.get(name_arg)
                if agent_id is None:
                    for key, aid in finalists_ref._finalists.items():
                        if key.startswith(name_arg) or name_arg in key:
                            agent_id = aid
                            break

                if agent_id is None:
                    logger.debug(
                        "Twitch vote from %s for unknown '%s' — ignoring",
                        ctx.author.name,
                        parts[1],
                    )
                    return

                viewer_id = f"twitch:{ctx.author.name}"
                threading.Thread(
                    target=_post_vote,
                    args=(agent_id, viewer_id, api_base),
                    daemon=True,
                ).start()

        _Bot().run()


# ---------------------------------------------------------------------------
# Module-level singleton + public API
# ---------------------------------------------------------------------------

_bot_instance: TwitchVoteBot | None = None


def start_twitch_bot() -> TwitchVoteBot | None:
    """
    Read env vars and start the Twitch bot in a daemon thread.

    Returns the TwitchVoteBot instance so callers can call set_finalists()
    when the vote window opens.  Returns None if env vars are missing.
    """
    global _bot_instance

    token    = os.getenv("TWITCH_BOT_TOKEN", "").strip()
    channel  = os.getenv("TWITCH_CHANNEL", "").strip()
    nick     = os.getenv("TWITCH_BOT_NICK", "promptisland_bot").strip()
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000").strip()

    if not token or not channel:
        logger.info(
            "Twitch bot disabled — set TWITCH_BOT_TOKEN and TWITCH_CHANNEL to enable"
        )
        return None

    _bot_instance = TwitchVoteBot(token=token, channel=channel, nick=nick, api_base=api_base)

    thread = threading.Thread(
        target=_bot_instance.run,
        daemon=True,
        name="twitch-bot",
    )
    thread.start()
    logger.info("Twitch bot thread started for channel #%s", channel)
    return _bot_instance


def get_bot() -> TwitchVoteBot | None:
    """Return the running bot instance, or None if not started."""
    return _bot_instance
