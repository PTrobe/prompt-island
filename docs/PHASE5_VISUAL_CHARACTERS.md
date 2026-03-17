# Phase 5 — Visual Characters (Pixel Art + Lip-Sync)

## Overview

Add animated pixel art characters to the frontend. Each agent has a sprite sheet with idle, talking, reaction, and eliminated states. Characters lip-sync to ElevenLabs audio in real time using the Web Audio API. The existing HubChat/Confessional layout stays; a `CharacterStage` component is overlaid at the bottom.

**Stack additions:**
- DALL-E 3 (OpenAI Images API) for sprite generation
- HTML Canvas 2D for rendering
- Web Audio API `AnalyserNode` for lip-sync amplitude detection

---

## Cast Design

Six diverse pixel art characters reflecting their archetype identity:

| Agent ID | Display Name | Archetype | Visual Identity |
|---|---|---|---|
| agent_01_machiavelli | Alex | Strategist | Black woman, 30s, power suit, calculating eyes, sharp posture |
| agent_02_chaos | Jordan | Wildcard | South Asian/mixed NB, 20s, punk/streetwear, wild hair, manic energy |
| agent_03_empath | Sam | Empath | Latina woman, 40s, warm earth tones, open body language, kind face |
| agent_04_pedant | Morgan | Know-it-all | East Asian man, 50s, glasses, neat collared shirt, slightly smug smirk |
| agent_05_paranoid | Casey | Paranoid | Middle Eastern man, 30s, hoodie, dark circles, eyes glancing sideways |
| agent_06_floater | Riley | People-pleaser | Mixed/Irish man, 20s, sporty neutral clothes, affable non-threatening smile |

**Diversity coverage:** 2F, 1NB, 3M — Black, South Asian, Latina, East Asian, Middle Eastern, mixed/white.

---

## Sprite Sheet Specification

Each character gets **one PNG sprite sheet** with all animation frames in a grid.

### Dimensions
- **Frame size:** 32×48px (portrait ratio)
- **Sheet layout:** 4 columns × 4 rows = 16 frames per sheet (not all used)
- **Display scale:** 3× = 96×144px on screen

### Frame Map (row, col — zero-indexed)

| Row | Col | State | Description |
|---|---|---|---|
| 0 | 0 | IDLE_0 | Neutral, standing |
| 0 | 1 | IDLE_1 | Subtle breath/blink frame |
| 0 | 2 | IDLE_2 | Return to neutral |
| 0 | 3 | IDLE_3 | Slight sway |
| 1 | 0 | TALK_CLOSED | Mouth fully closed |
| 1 | 1 | TALK_SLIGHT | Mouth slightly open |
| 1 | 2 | TALK_OPEN | Mouth open, mid-speech |
| 1 | 3 | TALK_WIDE | Mouth wide open, emphasis |
| 2 | 0 | REACT_HAPPY | Smile, eyebrows up |
| 2 | 1 | REACT_WORRIED | Furrowed brow, downturned mouth |
| 2 | 2 | REACT_SHOCKED | Wide eyes, open mouth (surprise/vote) |
| 2 | 3 | REACT_SUSPICIOUS | Narrowed eyes, side glance |
| 3 | 0 | ELIMINATED | Full body grayed-out, slumped |
| 3 | 1–3 | (reserved) | Future use |

---

## Phase 5a — Asset Generation

### Script: `scripts/generate_sprites.py`

Write a Python script using the OpenAI Images API (`dall-e-3`, size `1024×1024`, style `vivid`) that:

1. Iterates over each character definition
2. Builds a detailed prompt per character (see below)
3. Calls `openai.images.generate()` and downloads the result
4. Saves to `frontend/public/sprites/<agent_id>_sheet.png`
5. Prints a checklist of generated files

**Important:** DALL-E generates single images, not sprite sheets. The script generates **individual frames** per character, which are then composited into a sprite sheet using `Pillow`. A second script (`scripts/compose_sprite_sheet.py`) assembles frames into the final grid PNG.

### DALL-E Prompt Template

```
Pixel art character portrait, 32x48 pixels, {description},
{state_description}, transparent background, crisp pixel art style,
16-color palette, no anti-aliasing, facing forward slightly angled,
Survivor reality show contestant aesthetic, {archetype} personality visible in posture and expression.
```

**Per-character description strings (to embed in template):**

- **Alex:** `confident Black woman in her 30s wearing a fitted blazer and slacks, sharp calculating eyes, natural hair pulled back`
- **Jordan:** `non-binary South Asian person in their 20s with wild spiked dark hair, wearing oversized punk streetwear, energetic chaotic stance`
- **Sam:** `warm Latina woman in her 40s with curly dark hair, wearing comfortable earth-tone layers, open empathetic expression`
- **Morgan:** `East Asian man in his 50s with round glasses, neat short hair, wearing a collared shirt, slightly smug knowing smirk`
- **Casey:** `Middle Eastern man in his 30s wearing a dark hoodie, tired dark circles under eyes, nervous posture, eyes glancing sideways`
- **Riley:** `friendly mixed-heritage Irish man in his 20s with light wavy hair, wearing sporty casual clothes, easy approachable smile`

**Per-state description strings:**

- `IDLE_0`: `neutral standing pose, relaxed expression`
- `IDLE_1`: `eyes slightly squinted, very subtle exhale`
- `TALK_CLOSED`: `mouth closed, mid-thought expression`
- `TALK_SLIGHT`: `mouth slightly parted, beginning to speak`
- `TALK_OPEN`: `mouth open, actively speaking`
- `TALK_WIDE`: `mouth wide open, emphasizing a point`
- `REACT_HAPPY`: `eyebrows raised, wide smile, pleased expression`
- `REACT_WORRIED`: `furrowed brow, corners of mouth slightly down`
- `REACT_SHOCKED`: `wide eyes, mouth slightly open in surprise`
- `REACT_SUSPICIOUS`: `eyes narrowed, slight side glance, guarded expression`
- `ELIMINATED`: `entire sprite desaturated gray, slumped dejected posture, head down`

### Validation Script: `scripts/validate_sprites.py`

Checks that every sprite sheet PNG:
- Exists at `frontend/public/sprites/<agent_id>_sheet.png`
- Is exactly `128×192px` (4 cols × 32px, 4 rows × 48px)
- Has an alpha channel (RGBA)
- Raises a clear error per agent if any check fails

---

## Phase 5b — Canvas Animation Engine

### New files

**`frontend/src/lib/spriteRenderer.ts`**

```typescript
// SpriteState enum
export type SpriteState =
  | 'IDLE'
  | 'TALK_CLOSED' | 'TALK_SLIGHT' | 'TALK_OPEN' | 'TALK_WIDE'
  | 'REACT_HAPPY' | 'REACT_WORRIED' | 'REACT_SHOCKED' | 'REACT_SUSPICIOUS'
  | 'ELIMINATED'

// Frame map: state → [row, col] in the sprite sheet
const FRAME_MAP: Record<string, [number, number]> = {
  IDLE_0:           [0, 0],
  IDLE_1:           [0, 1],
  IDLE_2:           [0, 2],
  IDLE_3:           [0, 3],
  TALK_CLOSED:      [1, 0],
  TALK_SLIGHT:      [1, 1],
  TALK_OPEN:        [1, 2],
  TALK_WIDE:        [1, 3],
  REACT_HAPPY:      [2, 0],
  REACT_WORRIED:    [2, 1],
  REACT_SHOCKED:    [2, 2],
  REACT_SUSPICIOUS: [2, 3],
  ELIMINATED:       [3, 0],
}

// CharacterSprite class
// - Holds a loaded HTMLImageElement (sprite sheet)
// - Exposes drawFrame(ctx, state, x, y, scale)
// - Manages idle animation cycling at ~8fps
```

**`frontend/src/lib/lipSync.ts`**

```typescript
// LipSyncAnalyser class
// - Wraps Web Audio API AnalyserNode (FFT size 256)
// - connectBuffer(audioBuffer, audioContext) → attaches analyser to graph
// - getCurrentMouthState() → 'TALK_CLOSED' | 'TALK_SLIGHT' | 'TALK_OPEN' | 'TALK_WIDE'
//   Maps average frequency amplitude:
//     0–20   → TALK_CLOSED
//     20–50  → TALK_SLIGHT
//     50–80  → TALK_OPEN
//     80+    → TALK_WIDE
// - disconnect() → cleanup
```

**`frontend/src/lib/animationLoop.ts`**

```typescript
// AnimationLoop singleton
// - Runs a single requestAnimationFrame loop
// - Clears and redraws all active CharacterSprites each frame
// - Asks LipSyncAnalyser for current mouth state for the active speaker
// - Applies REACT_* state when a reaction event is queued (clears after 2s)
```

### Modify: `frontend/src/lib/elevenlabs.ts`

Wire `LipSyncAnalyser` into the existing `playAudioBuffer()` function:
- After `AudioContext.decodeAudioData()`, pass the buffer through `LipSyncAnalyser.connectBuffer()`
- On audio ended, call `LipSyncAnalyser.disconnect()` and reset speaker state

---

## Phase 5c — UI Integration

### New component: `frontend/src/components/CharacterStage.tsx`

- Renders a `<canvas>` element spanning the full width at bottom of screen (height ~180px)
- Draws all 6 characters spaced evenly
- Active speaker: scale 1.3×, bright border glow (CSS box-shadow on canvas wrapper)
- Eliminated: draws ELIMINATED frame with 50% opacity + skull emoji overlay
- Listens to `gameState` and `activeEvent` from `useGameStream` hook

### Modify: `frontend/src/hooks/useGameStream.ts`

Add two new pieces of state:
- `activeSpeaker: string | null` — agent_id of who is currently speaking (set from `speak_public` / `speak_private` events, cleared when TTS ends)
- `pendingReaction: { agentId: string; state: ReactionState } | null` — set from `vote` events and `eliminated` events, auto-clears after 2s

### Modify: `frontend/src/app/page.tsx`

- Import and render `<CharacterStage>` below the main panels
- Pass `activeSpeaker` and `pendingReaction` as props

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
  src/
    lib/
      spriteRenderer.ts      ← NEW
      lipSync.ts             ← NEW
      animationLoop.ts       ← NEW
      elevenlabs.ts          ← MODIFIED (wire LipSyncAnalyser)
    components/
      CharacterStage.tsx     ← NEW
    hooks/
      useGameStream.ts       ← MODIFIED (activeSpeaker, pendingReaction)
    app/
      page.tsx               ← MODIFIED (render CharacterStage)

scripts/
  generate_sprites.py        ← NEW
  compose_sprite_sheet.py    ← NEW
  validate_sprites.py        ← NEW
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| DALL-E pixel art quality is inconsistent | Generate 3 variants per frame, pick best manually. Use `style: "vivid"` and explicit `no anti-aliasing` instruction. |
| Sprite sheet composition misaligns frames | `validate_sprites.py` enforces exact pixel dimensions before any frontend code runs. |
| Lip-sync feels laggy or jittery | Smooth mouth state transitions with a 2-frame debounce (don't change state unless amplitude holds for 2 consecutive frames). |
| Canvas redraws cause layout jank | Use `will-change: transform` on the canvas wrapper. Keep CharacterStage in its own stacking context. |
| `AnalyserNode` not available in all browsers | Gate on `window.AudioContext` — if unavailable, show IDLE animation and skip lip-sync silently. |
