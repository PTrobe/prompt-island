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

---

## Frontend Architecture

### Phaser.js in Next.js

**`frontend/src/game/PhaserGame.tsx`** — React wrapper
- Instantiates `Phaser.Game` on mount, destroys on unmount
- Passes WebSocket event stream into the active scene via a shared event emitter
- `<canvas>` fills the viewport; CSS `image-rendering: pixelated`

**`frontend/src/game/scenes/IslandScene.ts`** — main Phaser scene
- Loads tilemap + tileset in `preload()`
- Creates all 6 `CharacterSprite` instances in `create()`
- Listens to game events and dispatches: moves, reactions, camera zooms
- Runs `LipSyncAnalyser` poll in `update()` at 60fps

**`frontend/src/game/sprites/CharacterSprite.ts`** — per-agent sprite class
- Owns the Phaser `Sprite` instance
- `AnimationStateMachine`: IDLE → WALK → TALK → REACT → ELIMINATED
- `moveTo(location)` — plays WALK animation, tweens position to target coords, returns to IDLE on arrival
- `setState(state)` — switches animation state
- `showSpeechBubble(text)` / `hideSpeechBubble()` — renders bubble above head in world space
- `setEliminated()` — applies grayscale pipeline, locks to ELIMINATED state

**`frontend/src/game/audio/LipSyncAnalyser.ts`**
- Wraps Web Audio `AnalyserNode` (FFT 256)
- `connectBuffer(buffer, ctx)` — attaches analyser to audio graph
- `getMouthState()` → `TALK_CLOSED | TALK_SLIGHT | TALK_OPEN | TALK_WIDE`
  - Amplitude 0–20 → CLOSED, 20–50 → SLIGHT, 50–80 → OPEN, 80+ → WIDE
- `disconnect()` — cleanup after audio ends

**`frontend/src/game/map/IslandMap.ts`** — location coordinate registry
```typescript
export const LOCATION_COORDS: Record<string, { x: number; y: number }> = {
  camp:             { x: 220, y: 240 },
  beach:            { x: 320, y: 80  },
  jungle:           { x: 120, y: 180 },
  tribal_fire:      { x: 320, y: 380 },
  confessional_hut: { x: 520, y: 200 },
  shelter:          { x: 200, y: 320 },
}
```

### Modified files

**`frontend/src/hooks/useGameStream.ts`** — add:
- `activeSpeaker: string | null`
- `pendingReaction: { agentId: string; state: string } | null`
- Emit `agent_move` and `camera_focus` events through to the Phaser scene via shared emitter

**`frontend/src/app/page.tsx`** — replace current layout with `<PhaserGame />` as primary view. Chat log panel becomes a slim overlay (bottom-right, semi-transparent) for viewers who want to follow text alongside the world.

---

## Script Pipeline (Asset Generation)

```
scripts/
  generate_sprites.py       → DALL-E 3, one frame per call, saves PNG per frame
  compose_sprite_sheets.py  → Pillow, assembles frames into 4×5 grid per character
  generate_tiles.py         → DALL-E 3, one tile per call, saves PNG per tile
  compose_tileset.py        → Pillow, assembles tiles into one tileset PNG
  validate_assets.py        → checks all sprites (64×120px) and tileset dimensions
```

**DALL-E character prompt template:**
```
Top-down pixel art character, 16x24 pixels, {description},
{state_description}, transparent background, crisp pixel art,
8-color palette per character, no anti-aliasing, viewed from slightly above,
Survivor reality show contestant, {archetype} personality visible.
```

**DALL-E tile prompt template:**
```
Top-down pixel art game tile, 16x16 pixels, {tile_description},
seamlessly tileable, tropical island aesthetic, crisp pixel art,
16-color palette, no anti-aliasing, no shadows, flat game tile style.
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
