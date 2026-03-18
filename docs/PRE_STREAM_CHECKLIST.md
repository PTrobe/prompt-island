# Pre-Stream Checklist — Prompt Island

Run through this checklist in order before every stream. Do not go live until every item is checked.

---

## 30 Minutes Before

- [ ] Pull latest code from `main` branch
- [ ] Confirm `.env` has all required keys:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY` (optional — falls back to OpenAI if absent)
  - `GROQ_API_KEY` (optional — falls back to OpenAI if absent)
  - `ELEVENLABS_API_KEY`
  - `TWITCH_BOT_ACCESS_TOKEN` + `TWITCH_BOT_REFRESH_TOKEN`
  - `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET`
  - `TWITCH_CHANNEL` + `TWITCH_BOT_USERNAME`
- [ ] Confirm `frontend/.env.local` has all `NEXT_PUBLIC_ELEVENLABS_*` voice IDs
- [ ] Confirm `frontend/public/sprites/` has all 6 `*_sheet.png` files
- [ ] Confirm `frontend/public/tiles/island_tileset.png` exists
- [ ] Confirm `frontend/public/maps/island.json` exists
- [ ] Run `python3 scripts/validate_assets.py` — must pass with zero errors

---

## 15 Minutes Before

### Backend
- [ ] Start the game backend: `python3 main.py --season N --port 8000 --twitch`
- [ ] Confirm log output shows:
  - `API server starting on http://0.0.0.0:8000`
  - `ChromaDB ready`
  - `Twitch bot connected to #<channel>`
  - `EventSub client connected`
- [ ] Open `http://localhost:8000/state` in browser — confirm JSON returns with correct season and agents
- [ ] Open `http://localhost:8000/logs` — confirm recent events are present (if resuming)

### Frontend
- [ ] Start the frontend: `cd frontend && npm run dev`  (or confirm deployed URL is live)
- [ ] Open `http://localhost:3000` in a browser tab (NOT the OBS browser source yet)
- [ ] Confirm Phaser canvas loads — island map is visible
- [ ] Confirm all 6 character sprites are visible at their correct locations
- [ ] Confirm WebSocket connected (check browser console — no red errors)
- [ ] Confirm chat log overlay is visible

### Audio test
- [ ] Trigger a manual TTS test: speak a short phrase via ElevenLabs dashboard or API
- [ ] Confirm audio plays through the browser and is routed correctly in OBS audio mixer
- [ ] Confirm lip-sync mouth animation fires (character's mouth moves during audio)

### Twitch
- [ ] Open your Twitch channel in another browser tab — confirm bot is in chat
- [ ] Send `!test` in Twitch chat — confirm bot responds (if test command implemented)
- [ ] Confirm channel point rewards are active on your Twitch dashboard

---

## 5 Minutes Before

### OBS
- [ ] Switch to `Prompt Island — Game` scene
- [ ] Add Browser Source pointing to `http://localhost:3000` (1920×1080, 30fps)
- [ ] Confirm island world is visible in OBS preview — no white screen
- [ ] Confirm desktop audio levels are showing in OBS mixer (TTS will come through here)
- [ ] Switch to `Starting Soon` scene
- [ ] Start stream on Twitch — confirm you're live in Twitch dashboard

### Final checks
- [ ] Browser source: `Shutdown source when not visible` = **UNCHECKED**
- [ ] Browser source: `Refresh browser when scene becomes active` = **UNCHECKED**
- [ ] BRB scene hotkey is set and tested
- [ ] `python3 main.py` process is still running (check terminal)

---

## Go Live

- [ ] Switch OBS to `Prompt Island — Game` scene
- [ ] Run game: `engine.initialize_game()` and `engine.run_game()` are called automatically by `main.py` — confirm first game events appear in the frontend
- [ ] Confirm Twitch bot posts `🌴 Prompt Island is LIVE! Season N begins...` in Twitch chat

---

## During Stream — Known Issues & Fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| White screen in OBS | Phaser crashed (ErrorBoundary triggered) | Switch to BRB scene. Check browser console. Reload browser source. |
| Characters frozen / not moving | WebSocket disconnected | Check backend terminal. Backend may have crashed. Restart `main.py`. |
| No audio | ElevenLabs API error or AudioContext locked | Check backend logs. Reload the browser source once. |
| Twitch bot silent | IRC connection dropped or rate limit hit | Check backend terminal for twitchio errors. Restart with `--twitch` flag. |
| "The game is thinking..." for >5 min | LLM API timeout or retry loop | Check backend terminal for error messages. May be rate-limited on OpenAI/Anthropic. |
| Eliminated agent still visible | Scene init bug | Hard-reload the browser source. State will be fetched fresh from `/state`. |

---

## After Stream

- [ ] Switch OBS to `End Screen` scene
- [ ] Stop stream in OBS
- [ ] Stop the backend (`Ctrl+C` in terminal)
- [ ] Back up the SQLite database: `cp prompt_island.db backups/prompt_island_$(date +%Y%m%d).db`
- [ ] Note any issues encountered for the next stream
