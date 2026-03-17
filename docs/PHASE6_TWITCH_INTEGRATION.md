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
# - __init__(channel, token, client_id)
# - async def post(message: str) → sends message to Twitch chat
# - async def start() → connects to IRC, keeps alive in background thread
# - async def stop() → graceful shutdown
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

### Channel Point Redemptions → Game Events

Set up these custom channel point rewards on your Twitch channel:

| Reward name | Cost | Effect |
|---|---|---|
| `Force a Revote` | 5000 pts | Tribal Council revote — current votes are discarded and agents vote again |
| `Give Agent a Hint` | 2000 pts | Delivers a strategic hint to a random non-eliminated agent as a `speak_private` system message |
| `Ask an Agent` | 1000 pts | Redeemer's Twitch username + message is delivered to the agent of their choice as a `system_event` in the next Morning Chat |
| `Chaos Mode` | 10000 pts | Activates chaos_agent (Jordan) for one extra unscripted action during the next Scramble |

**`src/integrations/twitch/eventsub.py`**

Uses Twitch EventSub via WebSocket (preferred over webhook for dev — no ngrok needed).

```python
# EventSubClient class
# - Connects to wss://eventsub.wss.twitch.tv/ws
# - Subscribes to channel.channel_points_custom_reward_redemption.add
# - Calls audience_bridge.on_redemption(reward_title, user_name, user_input)
```

**`src/integrations/twitch/audience_bridge.py`**

```python
# AudienceBridge class
# - on_redemption(reward_title, user_name, user_input)
#   → maps reward_title to a pending game action
#   → stores in a thread-safe queue (queue.Queue)
# - get_pending_actions() → list[AudienceAction]
#   → called by GameEngine at the start of each phase
# - AudienceAction dataclass: { action_type, payload, source_user }
```

**GameEngine integration points:**

- **Morning Chat start:** Pull `ask_agent` actions from bridge, inject as `system_event` ChatLog rows
- **Scramble start:** Pull `chaos_mode` actions, give Jordan an extra turn
- **Tribal Council (before vote):** Pull `force_revote` flag — if set, after first vote tally, discard and revote once
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
TWITCH_BOT_TOKEN=oauth:xxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CHANNEL=your_twitch_channel_name
TWITCH_BOT_USERNAME=PromptIslandBot
```

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
