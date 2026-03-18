# OBS Studio Setup — Prompt Island Stream

## Overview

The Prompt Island frontend runs in a browser. OBS captures it via a Browser Source and streams it to Twitch. This document covers the exact OBS configuration needed for a clean, stable stream.

---

## Requirements

- OBS Studio 30+ (free, [obsproject.com](https://obsproject.com))
- The Next.js frontend running locally (`cd frontend && npm run dev` → `http://localhost:3000`)
- Or deployed URL if hosting remotely

---

## Scene Setup

### 1. Create a new Scene

Name it `Prompt Island — Game`.

### 2. Add a Browser Source

`Sources → + → Browser`

| Setting | Value |
|---|---|
| URL | `http://localhost:3000` (dev) or your deployed URL |
| Width | `1920` |
| Height | `1080` |
| FPS | `30` |
| CSS | *(leave blank — styling is handled by the app)* |
| **Shutdown source when not visible** | ☐ **UNCHECKED** — if checked, Phaser pauses when you switch scenes |
| **Refresh browser when scene becomes active** | ☐ **UNCHECKED** — causes Phaser to reload and lose state mid-game |

### 3. Audio from Browser Source

By default, OBS browser sources route audio through the Desktop Audio channel. Verify:

`Edit → Settings → Audio → Desktop Audio Device` — set to your system default output.

To monitor the TTS audio on your headphones while streaming:
`Audio Mixer → Desktop Audio → ⚙ → Advanced Audio Properties → Monitor Only (mute output)` — then switch to `Monitor and Output` for the stream.

Alternatively: right-click the Browser Source → `Properties` → check **"Use custom audio device"** and select your preferred output.

---

## Recommended Stream Settings (Twitch)

`Settings → Stream`:
- Service: `Twitch`
- Server: Auto (or manually select closest)
- Stream Key: *(from your Twitch dashboard)*

`Settings → Output → Encoding`:

| Setting | Value |
|---|---|
| Encoder | NVENC (NVIDIA) or x264 (CPU) |
| Rate Control | CBR |
| Bitrate | `6000 Kbps` (Twitch max for partners) or `3500 Kbps` (standard) |
| Keyframe Interval | `2` seconds |
| Preset | Quality (NVENC) or `veryfast` (x264) |

`Settings → Video`:

| Setting | Value |
|---|---|
| Base (Canvas) Resolution | `1920×1080` |
| Output (Scaled) Resolution | `1920×1080` |
| Downscale Filter | Lanczos |
| FPS | `30` |

---

## Additional Scenes

### `Starting Soon` scene
A static image or looping video shown before the game starts. Add a text overlay: "Prompt Island Season N — starting soon".

### `BRB / Technical Difficulties` scene
A fallback scene if something goes wrong. Simple image with text. Switch to this manually if:
- The backend crashes and the browser source shows an error
- ElevenLabs TTS stops working and you need to restart
- The game loop freezes

**Hotkey:** Assign a keyboard shortcut to this scene (`Settings → Hotkeys → Switch to scene: BRB`). Practice switching to it so it's muscle memory.

### `End Screen` scene
Shown after the game ends. Displays the winner, season stats, "thanks for watching" message.

---

## Browser Source — Pixel Art Rendering

The Phaser canvas uses `image-rendering: pixelated` CSS to keep pixel art crisp. OBS browser sources support this natively. No additional OBS filter is needed.

If sprites appear blurry:
1. Confirm the browser source is exactly `1920×1080`
2. Confirm the Phaser game config uses integer scale only (`zoom: 3` not `zoom: 2.5`)
3. In OBS, right-click the source → `Scale Filtering → Point` (nearest-neighbor)

---

## Audio Routing Summary

| Source | Destination |
|---|---|
| ElevenLabs TTS (browser) | Desktop Audio → stream |
| Ambient island sounds (browser) | Desktop Audio → stream |
| Your microphone (optional commentary) | Mic/Aux → stream |
| Twitch chat bot messages | Not audio — text only in Twitch chat |

---

## Pre-Stream Check

See [PRE_STREAM_CHECKLIST.md](PRE_STREAM_CHECKLIST.md) for the full go-live verification sequence.
