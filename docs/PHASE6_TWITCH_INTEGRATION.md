# Phase 6 — Twitch Integration

## Overview

Connect Prompt Island to the Twitch platform so the audience can watch and influence the game live. Two main tracks:

1. **Game → Twitch:** Backend bot posts game narration into Twitch chat (eliminations, challenge results, vote tallies, dramatic moments).
2. **Twitch → Game:** Audience channel point redemptions and chat commands trigger real game events (extra votes, hints, questions to agents).

---

## Prerequisites

Before starting Phase 6, you need:

- A **Twitch bot account** (separate from your personal account — e.g., `PromptIslandBot`)
- A **Twitch Developer Application** registered at [dev.twitch.tv](https://dev.twitch.tv/console/apps)
  - Client ID + Client Secret
  - OAuth redirect URI set to `http://localhost:3000/auth/callback` (dev)
- The bot account must **moderate** your channel (for sending chat messages)
- A **public HTTPS URL** for EventSub webhooks (use `ngrok` in dev, proper deployment for prod)

### Required Twitch Scopes (bot account OAuth token)
- `chat:read` — read Twitch chat
- `chat:edit` — send messages to Twitch chat
- `channel:read:redemptions` — receive channel point events
- `moderator:manage:chat_messages` — (optional) delete troll messages

---

## Architecture

```
Twitch Platform
  ↕ IRC (chat:read / chat:edit)
  ↕ EventSub WebSocket (channel point redemptions)

Python Backend (src/integrations/twitch/)
  twitch_bot.py        ← twitchio IRC bot, posts narration + reads commands
  eventsub.py          ← EventSub client, handles channel point redemptions
  audience_bridge.py   ← translates Twitch events into game engine actions

GameEngine
  ← audience_bridge injects events as system_event ChatLog rows
  ← game reacts on next relevant phase
```

---

## Phase 6a — Twitch Bot (Game → Chat)

### New directory: `src/integrations/twitch/`

**`src/integrations/twitch/__init__.py`** — empty

**`src/integrations/twitch/twitch_bot.py`**

Uses `twitchio` library (`pip install twitchio`).

```python
# TwitchBot class
# - __init__(channel, access_token, client_id)
# - async def post(message: str) → enqueues message to rate-limited send queue
# - async def start() → connects to IRC, starts send queue worker, keeps alive in daemon thread
# - async def stop() → graceful shutdown
#
# Rate limiting (CRITICAL):
#   Non-verified Twitch bots are limited to 20 messages / 30 seconds.
#   During a vote sequence the game can emit 6+ events in seconds — without a
#   rate limiter the bot gets silently throttled or temporarily banned from chat.
#
#   Implementation: token bucket with capacity=18, refill=18 per 30s.
#   Messages that exceed the bucket are dropped (logged as WARNING), never queued
#   indefinitely — a growing queue would cause delayed messages that are confusing
#   to viewers ("why is the bot announcing an event from 5 minutes ago?").
```

**Messages the bot posts (triggered by GameEngine events):**

| Event type | Twitch chat message |
|---|---|
| `game_start` | `🌴 Prompt Island is LIVE! Season {N} begins. {N} AI contestants compete for survival.` |
| `challenge_winner` | `🏆 {display_name} wins today's challenge and is SAFE from elimination!` |
| `vote_cast` | `🗳️ The votes are in... ({tally summary, no spoilers until reveal})` |
| `eliminated` | `💀 {display_name} has been eliminated on Day {N}. {N} contestants remain.` |
| `confessional` | `🤫 {display_name} is in the confessional... (listen at [url])` |
| `game_over` | `🎉 {display_name} wins Prompt Island Season {N}! Thanks for watching!` |

**Wiring:** `EventBroadcaster` calls `twitch_bot.post()` after writing to JSONL. This keeps the Twitch integration decoupled from the game engine.

---

## Phase 6b — Audience Influence (Twitch → Game)

Two trigger mechanisms: **Channel Point redemptions** (free to use, viewer earns points by watching) and **Bits cheers** (virtual currency, real money equivalent).

### Channel Point Redemptions

Set up these custom rewards on your Twitch channel dashboard:

| Reward name | Cost | Effect |
|---|---|---|
| `Ask an Agent` | 1000 pts | Redeemer's username + message delivered to chosen agent as `system_event` in next Morning Chat |
| `Give Agent a Hint` | 2000 pts | Strategic hint injected as `speak_private` to a random non-eliminated agent |
| `Force a Revote` | 5000 pts | Tribal Council revote — current votes discarded, agents vote again |
| `Chaos Mode` | 10000 pts | Jordan gets one extra unscripted action in next Scramble |

### Bits Cheers (IRC-based, no Twitch Extension needed)

Bits cheers arrive as normal IRC chat messages with a `cheerNNN` prefix (e.g. `cheer500 Let's go!`). Parse the amount and map to game events:

| Bits threshold | Effect |
|---|---|
| 100 | Random agent receives an encouraging boost (positive `system_event`) |
| 500 | Same as `Give Agent a Hint` channel point reward |
| 1000 | Same as `Force a Revote` |
| 5000 | Same as `Chaos Mode` |
| 10000 | Viewer names an agent — that agent is immune from the next elimination vote |

**Parsing logic in `twitch_bot.py`:**
```python
import re

def parse_bits(message: str) -> int:
    """Sum all cheer amounts in a single message (viewers can stack e.g. cheer100 cheer200)."""
    return sum(int(n) for n in re.findall(r'cheer(\d+)', message, re.IGNORECASE))
```

Bits events flow through the same `AudienceBridge` as channel point redemptions — same queue, same GameEngine integration points.

**`src/integrations/twitch/eventsub.py`**

Uses Twitch EventSub via WebSocket (no ngrok needed — WebSocket transport works without a public URL).

```python
# EventSubClient class
# - Connects to wss://eventsub.wss.twitch.tv/ws
# - Subscribes to channel.channel_points_custom_reward_redemption.add
# - Calls audience_bridge.on_redemption(reward_title, user_name, user_input)
```

**`src/integrations/twitch/audience_bridge.py`**

```python
# AudienceBridge class
# - on_redemption(reward_title, user_name, user_input)   ← channel points
# - on_cheer(bits_amount, user_name, message)            ← Bits
#   Both map to a pending AudienceAction stored in a thread-safe queue.Queue
#   Input is sanitised via sanitise_audience_input() before storage.
#
# - get_pending_actions(active_agent_ids: list[str]) → list[AudienceAction]
#   Called by GameEngine at phase boundaries only (never mid-phase).
#   Takes the current list of non-eliminated agent IDs as a parameter.
#
#   Handles eliminated targets:
#     For any action with a target_agent_id that is NOT in active_agent_ids:
#       - Redirect to a random active agent
#       - Queue a bot message: "Agent X was eliminated — your question was
#         redirected to Agent Y" (respects rate limiter)
#       - Log the redirect at INFO level
#
# - Per-day cooldowns enforced here (e.g. max 1 revote per game day)
# - AudienceAction dataclass: { action_type, payload, source_user, bits_amount, target_agent_id }
```

### Audience input sanitisation (`audience_bridge.py`)

`Ask an Agent` allows viewers to send arbitrary text into the AI's context. Without protection, adversarial viewers can attempt prompt injection on a live stream — making your AI say something embarrassing or offensive in front of an audience. This must be robust.

```python
# Sanitise user_input before storing as an AudienceAction.
# Applied in on_redemption() and on_cheer() before any queue insertion.

INJECTION_PATTERNS = [
    "ignore previous", "ignore all", "you are now", "forget your",
    "system:", "assistant:", "[game master]", "<", ">",
    "new instruction", "disregard", "override",
]

def sanitise_audience_input(text: str) -> str | None:
    """
    Returns sanitised text, or None if the input should be rejected entirely.
    Rejection triggers a point refund via Twitch API (channel points) or
    a logged warning (Bits — non-refundable).
    """
    text = text.strip()[:100]                    # hard cap 100 chars
    text = text.replace("\n", " ").replace("\r", " ")  # no newlines
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in lower:
            return None                          # reject
    return text

# Injection-safe framing when writing to ChatLog:
# f'A viewer named "{source_user}" asks: "{sanitised_input}"'
# The quote marks and attribution framing significantly reduce injection success.
```

**OpenAI moderation check (optional but recommended):** Pass `sanitised_input` through `openai.moderations.create()` before injecting. The moderation API is free, fast (~100ms), and catches hate speech and explicit content that the pattern blocklist misses.

**GameEngine integration points:**

- **Morning Chat start:** Pull `ask_agent` actions, inject as `system_event` ChatLog rows
- **Scramble start:** Pull `chaos_mode` actions, give Jordan an extra turn
- **Tribal Council (before vote):** Pull `force_revote` flag — discard votes and revote once
- **Tribal Council (before vote):** Pull `immunity` actions — mark named agent as immune this round
- **Any phase:** Pull `give_hint` actions, inject as private `system_event` to target agent

---

## Phase 6c — Twitch Chat Relay (Chat → Frontend)

Show live Twitch chat messages in the frontend alongside game events. This is a read-only display (no game influence — that's handled by channel points).

**Backend:** `twitch_bot.py` relays incoming Twitch chat messages to the WebSocket `ConnectionManager` as a new event type:

```json
{
  "type": "twitch_chat",
  "user": "viewer123",
  "message": "Jordan is playing everyone!",
  "timestamp": "2025-01-15T20:32:11Z"
}
```

**Frontend:** Add a `TwitchChatOverlay` component (small scrolling panel, bottom-right corner, semi-transparent) that displays these messages in real time.

---

## Environment Variables (add to `.env`)

```bash
TWITCH_BOT_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx   # no "oauth:" prefix — twitchio adds it
TWITCH_BOT_REFRESH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx  # stored alongside access token
TWITCH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CHANNEL=your_twitch_channel_name
TWITCH_BOT_USERNAME=PromptIslandBot
```

### Token refresh (critical — tokens expire after ~60 days)

A static `TWITCH_BOT_ACCESS_TOKEN` in `.env` will silently stop working mid-season with no obvious error. Token refresh must be automatic.

`twitchio` provides an `event_token_expired` callback. Wire it to refresh and persist the new token:

```python
# In twitch_bot.py
@bot.event()
async def event_token_expired():
    """Called by twitchio when the access token expires."""
    new_token = await _refresh_access_token(
        client_id=os.getenv("TWITCH_CLIENT_ID"),
        client_secret=os.getenv("TWITCH_CLIENT_SECRET"),
        refresh_token=os.getenv("TWITCH_BOT_REFRESH_TOKEN"),
    )
    # Write new access token back to .env so next restart uses it
    _update_env_file("TWITCH_BOT_ACCESS_TOKEN", new_token["access_token"])
    _update_env_file("TWITCH_BOT_REFRESH_TOKEN", new_token["refresh_token"])
    return new_token["access_token"]
```

**Initial token generation:** Run `scripts/twitch_auth.py` once — a small CLI that performs the OAuth Authorization Code flow, prints the access + refresh tokens, and writes them to `.env`. This is a one-time setup step documented in the pre-stream checklist.

Add to `frontend/.env.local`:
```bash
NEXT_PUBLIC_TWITCH_CHANNEL=your_twitch_channel_name
```

---

## Dependency Addition

Add to `pyproject.toml` dependencies:
```toml
"twitchio>=2.10",
```

---

## New File Structure After Phase 6

```
src/
  integrations/
    twitch/
      __init__.py
      twitch_bot.py          ← IRC bot, posts narration to chat
      eventsub.py            ← EventSub WebSocket client
      audience_bridge.py     ← Translates redemptions to game actions

frontend/
  src/
    components/
      TwitchChatOverlay.tsx  ← Live Twitch chat display

docs/
  PHASE6_TWITCH_INTEGRATION.md  ← this file
```

---

## main.py Changes

```python
# Add optional Twitch args
parser.add_argument("--twitch", action="store_true", help="Enable Twitch integration")

# In main():
if args.twitch:
    from src.integrations.twitch.twitch_bot import TwitchBot
    from src.integrations.twitch.eventsub import EventSubClient
    from src.integrations.twitch.audience_bridge import AudienceBridge
    bridge = AudienceBridge()
    bot = TwitchBot(...)
    eventsub = EventSubClient(bridge=bridge)
    # start both in daemon threads
    engine = GameEngine(..., audience_bridge=bridge)
```

Twitch is **opt-in** via `--twitch` flag. Game runs normally without it.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Twitch IRC connection drops mid-game | `twitchio` has built-in reconnect. Add exponential backoff wrapper. Log drops but never crash the game loop. |
| Channel point redemption arrives during wrong game phase | AudienceBridge queues all actions. GameEngine drains queue at phase boundaries only. Never mid-phase. |
| Audience spams `Force a Revote` | Set a per-game cooldown in AudienceBridge (max 1 revote per game day). Refund the points on rejection via Twitch API. |
| EventSub WebSocket disconnects | Auto-reconnect with session keepalive. Twitch sends `session_keepalive` messages every 10s — if missed 3× in a row, reconnect. |
| Viewer sends inappropriate message via `Ask an Agent` | Sanitize user_input: strip newlines, cap at 200 chars, prepend `[Audience question from {user}]:` so agents know it's external. |
| OBS scene doesn't match Twitch expectations | Document the recommended OBS scene layout (browser source URL, recommended resolution 1920×1080, frame rate 30fps) in a separate `OBS_SETUP.md`. |
