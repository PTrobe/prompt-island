# Phase 5 — Interactive Island World (Pixel Art + Phaser.js)

## Overview

Build a fully interactive top-down pixel art island world rendered in the browser via Phaser.js. All six agents exist as animated sprites on the island map, moving between named locations as the game phases change. The camera stays fixed on the full island but zooms smoothly into the active location during key moments (speech, confessionals, votes). Speech bubbles appear above characters in world space, synced to ElevenLabs audio. Audience watches passively via stream (OBS browser capture).

**Stack additions:**
- `phaser` — 2D game framework (tilemap, sprites, camera, tweens)
- `openai` images API — DALL-E 3 for pixel art asset generation
- `pillow` (Python) — sprite sheet composition
- Phaser embedded in Next.js via a React wrapper component

---

## Island Map Layout

Top-down pixel art island. One screen — no scrolling. Camera zooms in on active location, pulls back between events.

### Locations

| ID | Name | Description | Phases active |
|---|---|---|---|
| `camp` | Base Camp | Central area, main hub | Morning Chat |
| `beach` | Beach | Open sand area, challenge zone | Challenge |
| `jungle` | Jungle Paths | Dense trees, private meetings | Scramble (private DMs) |
| `tribal_fire` | Tribal Fire Pit | Stone circle with fire | Tribal Council |
| `confessional_hut` | Confessional Hut | Small hut, right side of island | Confessionals (any phase) |
| `shelter` | Shelter | Covered sleeping area | Night / idle |

### Map Dimensions
- **Tilemap:** 40×30 tiles at 16×16px = 640×480px world
- **Display:** Scaled to fill browser window (CSS `image-rendering: pixelated`)
- **Tile size:** 16×16px — fine enough for detail, fast to generate

### Camera Zoom Levels
| Trigger | Zoom | Duration |
|---|---|---|
| Default (between events) | 1.0× | — |
| Agent speaking (public) | 1.8× centered on speaker | 400ms ease-out |
| Confessional | 2.5× centered on hut | 600ms ease-out |
| Vote reveal | 2.0× centered on tribal fire | 500ms ease-out |
| Elimination | 2.2× centered on eliminated agent | 700ms ease-out |
| Phase transition | Pull back to 1.0× | 400ms ease-in |

---

## Cast Design

Six diverse pixel art characters reflecting their archetype identity. Top-down perspective — sprites show characters from slightly above.

| Agent ID | Display Name | Archetype | Visual Identity |
|---|---|---|---|
| agent_01_machiavelli | Alex | Strategist | Black woman, 30s, blazer, sharp posture, calculating expression |
| agent_02_chaos | Jordan | Wildcard | South Asian/mixed NB, 20s, punk streetwear, wild spiked hair |
| agent_03_empath | Sam | Empath | Latina woman, 40s, earth tones, warm open posture |
| agent_04_pedant | Morgan | Know-it-all | East Asian man, 50s, glasses, collared shirt, slightly smug |
| agent_05_paranoid | Casey | Paranoid | Middle Eastern man, 30s, hoodie, nervous posture, eyes sideways |
| agent_06_floater | Riley | People-pleaser | Mixed/Irish man, 20s, sporty casual, easy approachable smile |

**Diversity:** 2F, 1NB, 3M — Black, South Asian, Latina, East Asian, Middle Eastern, mixed/white.

---

## Sprite Sheet Specification

Each character: one PNG sprite sheet, all states in a grid.

### Frame size
- **Frame:** 16×24px (top-down portrait, slightly taller than wide)
- **Sheet:** 4 columns × 5 rows = 20 frames
- **Display scale:** 3× = 48×72px on screen

### Frame Map

| Row | Col | State | Description |
|---|---|---|---|
| 0 | 0 | IDLE_0 | Neutral stand, top-down view |
| 0 | 1 | IDLE_1 | Subtle breath/weight shift |
| 0 | 2 | IDLE_2 | Return neutral |
| 0 | 3 | IDLE_3 | Slight sway |
| 1 | 0 | WALK_0 | Walk cycle frame 1 |
| 1 | 1 | WALK_1 | Walk cycle frame 2 |
| 1 | 2 | WALK_2 | Walk cycle frame 3 |
| 1 | 3 | WALK_3 | Walk cycle frame 4 |
| 2 | 0 | TALK_CLOSED | Mouth closed |
| 2 | 1 | TALK_SLIGHT | Mouth slightly open |
| 2 | 2 | TALK_OPEN | Mouth open |
| 2 | 3 | TALK_WIDE | Mouth wide open |
| 3 | 0 | REACT_HAPPY | Smile, eyebrows raised |
| 3 | 1 | REACT_WORRIED | Furrowed brow |
| 3 | 2 | REACT_SHOCKED | Wide eyes, surprise |
| 3 | 3 | REACT_SUSPICIOUS | Narrowed eyes, side glance |
| 4 | 0 | ELIMINATED | Full desaturated, slumped |
| 4 | 1–3 | (reserved) | Future use |

---

## Tile Sheet Specification

Island tileset: one PNG containing all terrain and prop tiles.

### Tile categories

| Category | Tiles needed | Notes |
|---|---|---|
| Terrain | grass, sand, dirt path, water edge, deep water | Base layer |
| Vegetation | palm tree, bush, jungle foliage (dense/light) | Decoration layer |
| Structures | hut wall, hut roof, shelter roof, fire pit (lit/unlit) | Object layer |
| Props | stone, log, torch, vote urn | Detail layer |

### Generation approach
- Generate each tile individually with DALL-E 3 at 256×256 (minimum DALL-E size), then downsample to 16×16 with nearest-neighbor (preserves pixel art look)
- `scripts/generate_tiles.py` — generates all tile variants
- `scripts/compose_tileset.py` — assembles into one tileset PNG

---

## Backend Changes (Game Engine)

### New event types (emitted by GameEngine → WebSocket)

**`agent_move`** — emitted when a phase transition moves agents to a new location:
```json
{
  "type": "agent_move",
  "agent_id": "agent_01_machiavelli",
  "from_location": "camp",
  "to_location": "beach",
  "timestamp": "..."
}
```

**`camera_focus`** — explicit camera instruction (optional, frontend can also derive from existing events):
```json
{
  "type": "camera_focus",
  "location": "confessional_hut",
  "zoom": 2.5,
  "duration_ms": 600
}
```

### Phase → location mapping (in `game_loop.py`)

| Phase | Agent assignment |
|---|---|
| Morning Chat | All → `camp` |
| Challenge | All → `beach` |
| Scramble | Agents in DM → `jungle`; others → `camp` |
| Tribal Council | All → `tribal_fire` |
| Confessional (any phase) | Speaking agent → `confessional_hut` temporarily |
| Night | All → `shelter` |

### DB change
Add `current_location` column to `Agent` model:
```sql
ALTER TABLE agents ADD COLUMN current_location VARCHAR(32) DEFAULT 'shelter';
```
Add to `migrate_add_season_columns()` in `database.py`.

### `/state` API update (`src/api/server.py`)

Add `current_location` to the agent dict returned by `_state_for_season()`:

```python
{
    "agent_id":          a.agent_id,
    "display_name":      a.display_name,
    "is_eliminated":     a.is_eliminated,
    "eliminated_on_day": a.eliminated_on_day,
    "current_location":  a.current_location or "shelter",   # ← ADD THIS
}
```

### Scene initialisation sequence (`IslandScene.ts`)

The Phaser scene must fetch `/state` before connecting to the WebSocket. If OBS crashes and the browser source reloads, the WebSocket event replay (last 20 events) may not include the `agent_move` events needed to reconstruct agent positions. Fetching `/state` on `create()` guarantees correct initial positions regardless of reconnect timing.

```typescript
async create() {
  // 1. Load tilemap and create sprites at default positions (shelter)
  this.buildMap()
  this.createCharacters()

  // 2. Fetch current server state and snap characters to correct locations
  const state = await fetch('/api/state').then(r => r.json())
  for (const contestant of state.contestants) {
    const sprite = this.characters.get(contestant.agent_id)
    sprite?.snapToLocation(contestant.current_location)  // no walk animation, instant
    if (contestant.is_eliminated) sprite?.setEliminated()
  }

  // 3. Only now connect the WebSocket event stream
  this.connectEventStream()
}
```

---

## Frontend Architecture

### Phaser.js in Next.js

**`frontend/src/game/PhaserGame.tsx`** — React wrapper
- Instantiates `Phaser.Game` on mount, destroys on unmount
- Passes WebSocket event stream into the active scene via a shared event emitter
- `<canvas>` fills the viewport; CSS `image-rendering: pixelated`
- **Must never be imported directly in a Server Component.** Phaser uses `window` and `document` — server-side rendering will crash immediately.

Import it in `page.tsx` using Next.js dynamic import with SSR disabled:
```typescript
// page.tsx
import dynamic from 'next/dynamic'

const PhaserGame = dynamic(
  () => import('@/game/PhaserGame'),
  { ssr: false, loading: () => <LoadingScreen /> }
)
```
This ensures Phaser is only ever evaluated in the browser. The `loading` prop renders a static loading screen while the JS bundle downloads — important for stream startup.

**`frontend/src/game/scenes/IslandScene.ts`** — main Phaser scene
- Loads tilemap + tileset in `preload()`
- Creates all 6 `CharacterSprite` instances in `create()`
- Listens to game events and dispatches: moves, reactions, camera zooms
- Runs `LipSyncAnalyser` poll in `update()` at 60fps

**Scene visual states** — the island is never a static dead screen:

| State | Trigger | Visual |
|---|---|---|
| `ACTIVE` | Events arriving normally | Normal lighting, characters animated |
| `NIGHT_IDLE` | `phase_start: night` event received | Dark blue overlay (alpha 0.55), star particle effect, ambient text "Night falls on the island..." fades in. Characters at shelter in IDLE. This phase can last minutes during LLM summarisation — this state makes it watchable. |
| `WAITING` | No game events for 90 seconds | Subtle pulsing "⏳ The game is thinking..." text overlay at bottom of screen. Clears automatically when the next event arrives. Never shows a frozen scene with no explanation. |

Both `NIGHT_IDLE` and `WAITING` are implemented as Phaser overlay graphics + text objects toggled in `update()`. They do not affect character state or camera.

**`frontend/src/game/sprites/CharacterSprite.ts`** — per-agent sprite class
- Owns the Phaser `Sprite` instance
- `AnimationStateMachine`: IDLE → WALK → TALK → REACT → ELIMINATED
- `moveTo(location, delayMs?)` — plays WALK animation, tweens position to target formation spot, returns to IDLE on arrival
  - Accepts an optional `delayMs` to stagger departure. Phase transitions call `moveTo` for all 6 agents with 150ms increments (random order) so they leave one by one rather than all simultaneously. Six agents walking in a rugby scrum looks broken; a staggered departure looks natural.
- `setState(state)` — switches animation state
- `showSpeechBubble(text)` / `hideSpeechBubble()` — renders bubble above head in world space
  - **Truncation rule:** show first 15 words + "..." — agents speak in full paragraphs which are physically impossible to read on a 48×72px sprite at stream resolution. Full text goes to the chat log overlay panel. The bubble teases the speech; the panel shows everything.
  - Bubble width: clamped to 120px max, word-wrapped, clamped to map bounds horizontally so it never renders off-screen
- `setEliminated()` — plays the full elimination exit sequence:
  1. Switch to `REACT_SHOCKED` for 1.5s (the moment they learn)
  2. Switch to `ELIMINATED` sprite frame (desaturated, slumped)
  3. Camera zooms to 2.2× centered on this agent for 2s (dramatic beat)
  4. Agent walks toward the nearest map edge (WALK animation, tween off-screen over 2s)
  5. Sprite is hidden (`setVisible(false)`) once off-screen — they do not appear again this season
  6. Camera pulls back to 1.0× after exit completes
  - On reconnect / scene init, eliminated agents are initialised as hidden (`setVisible(false)`) — they never reappear

**`frontend/src/game/ui/PixelFont.ts`** — bitmap font loader

Phaser's default canvas text uses a proportional system font which looks wrong alongside pixel art characters. All in-world text (speech bubbles, name labels, overlays) must use a pixel font.

```typescript
// Uses Press Start 2P — free Google Font, classic pixel aesthetic.
// Load as a Phaser BitmapFont in preload():
//   this.load.bitmapFont('pixel', '/fonts/pressstart2p.png', '/fonts/pressstart2p.xml')
// Use everywhere:
//   this.add.bitmapText(x, y, 'pixel', text, 8)  // 8px base size, scale up as needed
```

Add to `frontend/public/fonts/`:
- `pressstart2p.png` — font texture atlas (export from Phaser's font tool or use a prebuilt asset)
- `pressstart2p.xml` — font descriptor

**Rule:** No `this.add.text()` calls anywhere in the codebase. All text is `this.add.bitmapText()` with the `pixel` key.

**`frontend/src/game/audio/LipSyncAnalyser.ts`**
- Wraps Web Audio `AnalyserNode` (FFT 256)
- `connectBuffer(buffer, ctx)` — attaches analyser to audio graph
- `getMouthState()` → `TALK_CLOSED | TALK_SLIGHT | TALK_OPEN | TALK_WIDE`
  - Amplitude 0–20 → CLOSED, 20–50 → SLIGHT, 50–80 → OPEN, 80+ → WIDE
- `disconnect()` — cleanup after audio ends

**`frontend/src/game/map/IslandMap.ts`** — location coordinate registry

Each location defines 6 individual formation spots — one per agent. Agents are assigned to spots by index (agent_01 → spot[0], etc.) so positions are stable and never overlap. Spots are arranged in natural groupings appropriate to the location.

```typescript
// One world-space coordinate per agent slot, per location.
// 6 spots per location — agents never share a position.
export const LOCATION_FORMATIONS: Record<string, Array<{ x: number; y: number }>> = {
  camp: [             // Loose cluster around campfire table, centre-left
    { x: 200, y: 230 }, { x: 220, y: 250 }, { x: 240, y: 230 },
    { x: 200, y: 260 }, { x: 240, y: 260 }, { x: 220, y: 240 },
  ],
  beach: [            // Spread out along shoreline, top of map
    { x: 260, y: 75 }, { x: 290, y: 70 }, { x: 320, y: 75 },
    { x: 350, y: 70 }, { x: 380, y: 75 }, { x: 340, y: 85 },
  ],
  jungle: [           // Pairs scattered along jungle paths — simulates private meetings
    { x: 100, y: 160 }, { x: 115, y: 175 },  // pair 1
    { x: 140, y: 190 }, { x: 155, y: 205 },  // pair 2
    { x: 120, y: 210 }, { x: 135, y: 225 },  // pair 3
  ],
  tribal_fire: [      // Semicircle around fire pit, bottom-centre
    { x: 295, y: 390 }, { x: 315, y: 400 }, { x: 335, y: 390 },
    { x: 295, y: 375 }, { x: 335, y: 375 }, { x: 315, y: 385 },
  ],
  confessional_hut: [ // All agents wait outside; active speaker goes to hut entrance
    { x: 490, y: 225 }, { x: 505, y: 235 }, { x: 520, y: 225 },
    { x: 490, y: 240 }, { x: 520, y: 240 }, { x: 505, y: 215 },
  ],
  shelter: [          // Two rows under shelter roof, night/idle positions
    { x: 185, y: 315 }, { x: 200, y: 315 }, { x: 215, y: 315 },
    { x: 185, y: 330 }, { x: 200, y: 330 }, { x: 215, y: 330 },
  ],
}

// Helper: get the world position for a specific agent at a location.
// agentIndex is the agent's position in the sorted agent list (0–5).
export function getFormationSpot(location: string, agentIndex: number): { x: number; y: number } {
  const spots = LOCATION_FORMATIONS[location] ?? LOCATION_FORMATIONS.shelter
  return spots[agentIndex % spots.length]
}
```

**`frontend/src/game/PhaserErrorBoundary.tsx`** — React ErrorBoundary wrapping the Phaser canvas

Critical for live stream stability. If Phaser throws at any point (corrupted sprite sheet, WebGL context lost, malformed tilemap), the ErrorBoundary catches it and renders the text-only fallback UI instead of a white screen. The stream never dies.

```typescript
// Class component (ErrorBoundary must be a class component in React)
// - Catches errors from <PhaserGame /> and any child
// - Fallback: renders <TextOnlyFallback /> — the original HubChat + Confessional layout
// - Logs error to console with full stack for debugging
// - Shows a small "visual mode unavailable" banner in the fallback so the streamer knows
```

Usage in `page.tsx`:
```tsx
<PhaserErrorBoundary>
  <PhaserGame ... />
</PhaserErrorBoundary>
```

### Modified files

**`frontend/src/hooks/useGameStream.ts`** — add:
- `activeSpeaker: string | null`
- `pendingReaction: { agentId: string; state: string } | null`
- Emit `agent_move` and `camera_focus` events through to the Phaser scene via shared emitter

**`frontend/src/app/page.tsx`** — replace current layout with `<PhaserGame />` as primary view. Chat log panel becomes a slim overlay (bottom-right, semi-transparent) for viewers who want to follow text alongside the world.

---

## Asset Generation Pipeline

### Why not DALL-E for sprites

DALL-E 3 generates each image independently. A character generated for IDLE_0 will look noticeably different from the same character in WALK_2 or REACT_SHOCKED — different face shape, different clothing details, different lighting. Animated across 13 frames this produces a flickering mess. This is a design flaw, not a quality risk.

**The correct pipeline is two-stage:**

**Stage 1 — DALL-E 3 for character reference images only**

One call per character. Output is a full-body concept illustration used as a visual brief for the sprite artist (you, in Aseprite).

```
scripts/
  generate_references.py    → DALL-E 3, one reference image per character, saves to assets/references/
```

**DALL-E reference prompt template:**
```
Full-body concept art of a Survivor reality show contestant, {description},
standing facing forward, plain white background, detailed character design,
showing clothing, face, and posture clearly. This is a reference image for
a pixel art artist. No background, no props, clean lines.
```

**Stage 2 — Aseprite for actual sprite sheets**

[Aseprite](https://www.aseprite.org/) is the industry-standard pixel art tool (one-time ~$20 purchase, or free if compiled from source). Using the DALL-E reference as a visual guide, draw each character's sprite sheet manually. At 16×24px this is 1–2 hours per character.

**Why this is faster than fighting DALL-E:**
- DALL-E at 1024px → downsample to 16px = 64× reduction. Output looks like noise.
- One Aseprite session at 16×24px gives you full control over every pixel, consistent style across all frames, and clean transparency.
- Aseprite has built-in animation preview so you can verify the walk/talk cycles look correct before exporting.

**Export from Aseprite:**
- File → Export Sprite Sheet → output `{agent_id}_sheet.png`, layout: grid 4 columns × 5 rows
- Ensure "Trim" is OFF and "Layers" exports the merged result

### Tile generation (DALL-E 2 is acceptable here)

Tiles are static, non-animated, and don't need cross-frame consistency. DALL-E 2 at 256×256 (the actual minimum for dall-e-2, not dall-e-3 which requires 1024×1024) is acceptable, then downsample.

```
scripts/
  generate_tiles.py         → openai.images.generate(model="dall-e-2", size="256x256"), saves per tile
  compose_tileset.py        → Pillow nearest-neighbor downsample to 16×16, assembles tileset PNG
  validate_assets.py        → checks all sprite sheets (64×120px) and tileset dimensions
```

**DALL-E 2 tile prompt template:**
```
Top-down pixel art game tile, tropical island, {tile_description},
seamlessly tileable, flat colors, no shadows, no gradients,
16 colors maximum, clean pixel art style, square tile.
```

---

## File Structure After Phase 5

```
frontend/
  public/
    sprites/
      agent_01_machiavelli_sheet.png
      agent_02_chaos_sheet.png
      agent_03_empath_sheet.png
      agent_04_pedant_sheet.png
      agent_05_paranoid_sheet.png
      agent_06_floater_sheet.png
    tiles/
      island_tileset.png
    maps/
      island.json              ← Phaser tilemap definition (generated by script)
  src/
    game/
      PhaserGame.tsx
      scenes/
        IslandScene.ts
      sprites/
        CharacterSprite.ts
      audio/
        LipSyncAnalyser.ts
      map/
        IslandMap.ts
    hooks/
      useGameStream.ts         ← modified
    app/
      page.tsx                 ← modified (PhaserGame as primary view)

scripts/
  generate_sprites.py
  compose_sprite_sheets.py
  generate_tiles.py
  compose_tileset.py
  validate_assets.py
```

---

## Ambient Audio

The island world should never be completely silent. Simple looping ambient audio significantly improves stream quality and makes idle phases (night, waiting) watchable rather than eerie.

### Required audio files (royalty-free — see sources below)

| File | Description | Used in |
|---|---|---|
| `ambient_day.mp3` | Gentle ocean waves + tropical birds | All active daytime phases |
| `ambient_night.mp3` | Crickets + soft wind | `NIGHT_IDLE` state |
| `tribal_drums.mp3` | Low rhythmic percussion | Tribal Council phase |
| `tension_sting.mp3` | Short 2s dramatic sound | Vote reveal, elimination moment |

### Implementation

Load all ambient tracks in Phaser's `preload()` using `this.load.audio()`. Play/fade using Phaser's `Sound` manager:

```typescript
// Crossfade between ambient states — 1s fade so transitions aren't jarring
this.ambientDay = this.sound.add('ambient_day', { loop: true, volume: 0 })
this.ambientNight = this.sound.add('ambient_night', { loop: true, volume: 0 })
this.tribalDrums = this.sound.add('tribal_drums', { loop: true, volume: 0 })

// Phase-driven transitions:
// morning_chat  → fade in ambientDay (vol 0.4), fade out others
// tribal_council → fade in tribalDrums (vol 0.5), reduce ambientDay to 0.15
// night         → fade out ambientDay, fade in ambientNight (vol 0.3)
```

**TTS audio ducking:** When ElevenLabs TTS fires, reduce ambient volume to 0.1 for the duration and restore after. Prevents ambient audio from competing with speech.

### Royalty-free sources

- [freesound.org](https://freesound.org) — filter by CC0 license
- [pixabay.com/music](https://pixabay.com/music) — royalty-free, no attribution required
- [opengameart.org](https://opengameart.org) — game-specific audio, CC0/CC-BY

Download files and place in `frontend/public/audio/`. Add to `validate_assets.py` checks.

## Sub-phases

| Sub-phase | Deliverable |
|---|---|
| **5a** | Asset generation scripts + all PNG assets validated |
| **5b** | Phaser scaffolding in Next.js, tilemap renders, 6 characters placed on map |
| **5c** | Character walk animations, phase → location movement from WebSocket events |
| **5d** | Camera zoom system wired to game events |
| **5e** | Lip-sync (AnalyserNode → mouth frames), speech bubbles in world space |
| **5f** | Confessional sequence (zoom in, bubble + voice, zoom out), elimination animation |
| **5g** | Chat log overlay panel, final layout polish for OBS capture |
| **5h** | Dry run — full end-to-end test before first public stream |

### 5h — Dry Run Protocol

Do not stream publicly until a complete private dry run passes. This is not optional.

**Dry run requirements:**
- Run a full game from Day 1 to game-over with `--days 3` (accelerated)
- Verify every phase visually: characters move to correct location, camera zooms correctly, speech bubbles appear and truncate, TTS plays with lip-sync
- Trigger a confessional — verify zoom in, bubble, audio, zoom out
- Reach Tribal Council — verify tribal drums fade in, camera focuses on fire, vote reactions fire on each character, elimination sequence plays (shock → slump → walk off)
- Verify the NIGHT_IDLE state activates and deactivates correctly
- Artificially trigger WAITING state by pausing the backend — verify "thinking" indicator appears after 90s
- Test browser source reload mid-game — verify agent positions restore correctly from `/state`
- Run the full pre-stream checklist ([PRE_STREAM_CHECKLIST.md](PRE_STREAM_CHECKLIST.md)) with OBS active
- Record the dry run locally (OBS local recording, not stream) and watch the recording — issues visible in recording are issues your audience will see

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| DALL-E pixel art quality is inconsistent at small sizes | Generate at 256×256, downsample with nearest-neighbor (not bilinear). Manual touch-up pass if needed. |
| Walk animation looks wrong top-down | Use a simple 4-frame bob cycle (feet alternate) rather than directional walk. Flip sprite horizontally when moving left. |
| Phaser + Next.js SSR conflict | Instantiate `Phaser.Game` inside `useEffect` only. Never import Phaser at module level in a Server Component. |
| Speech bubble text overflows map edge | Clamp bubble X position to map bounds before rendering. |
| Camera zoom + lip-sync cause frame drops | Profile with Chrome DevTools. LipSyncAnalyser polls in Phaser `update()` — if needed, throttle to every 3 frames. |
| DALL-E tile seams visible | Add a `tileable` instruction to prompt. Post-process: blur edges of each tile by 1px before nearest-neighbor downsample. |
