#!/usr/bin/env python3
"""
generate_sprite_sheets.py — Auto-generate pixel art sprite sheets from DALL-E reference images.

Takes the 6 reference images from assets/references/, processes each into a
16×24px pixel art sprite, generates all 20 animation frames programmatically,
and saves the final 64×120px sprite sheet to frontend/public/sprites/.

Pipeline per character:
  1. Load reference image (1024×1024 DALL-E output)
  2. Remove white background → transparent
  3. Crop to character bounding box
  4. Resize to 16×24px (LANCZOS → NEAREST for clean pixel art)
  5. Quantize to 8-color palette (gives crisp pixel art look)
  6. Generate 20 animation frames with programmatic variations
  7. Assemble 4×5 grid → 64×120px RGBA PNG

Frame layout (matches PHASE5_VISUAL_CHARACTERS.md):
  Row 0: IDLE_0  IDLE_1  IDLE_2  IDLE_3
  Row 1: WALK_0  WALK_1  WALK_2  WALK_3
  Row 2: TALK_CLOSED  TALK_SLIGHT  TALK_OPEN  TALK_WIDE
  Row 3: REACT_HAPPY  REACT_WORRIED  REACT_SHOCKED  REACT_SUSPICIOUS
  Row 4: ELIMINATED   (blank)         (blank)         (blank)

Usage:
    python3 scripts/generate_sprite_sheets.py
    python3 scripts/generate_sprite_sheets.py --character agent_01_machiavelli

Requires:
    pip install pillow
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SPRITE_W    = 16
SPRITE_H    = 24
SHEET_COLS  = 4
SHEET_ROWS  = 5
PALETTE_COLORS = 8

REF_DIR    = Path("assets/references")
OUTPUT_DIR = Path("frontend/public/sprites")

AGENT_IDS = [
    "agent_01_machiavelli",
    "agent_02_chaos",
    "agent_03_empath",
    "agent_04_pedant",
    "agent_05_paranoid",
    "agent_06_floater",
]

# ---------------------------------------------------------------------------
# Image processing helpers
# ---------------------------------------------------------------------------

def remove_white_background(img: Image.Image, threshold: int = 230) -> Image.Image:
    """
    Make near-white pixels transparent.
    DALL-E generates images on a white background — this strips it cleanly.
    """
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r > threshold and g > threshold and b > threshold:
                pixels[x, y] = (r, g, b, 0)
    return img


def crop_to_content(img: Image.Image, padding: int = 20) -> Image.Image:
    """Crop image to non-transparent bounding box with padding."""
    bbox = img.getbbox()
    if not bbox:
        return img
    w, h = img.size
    left   = max(0, bbox[0] - padding)
    top    = max(0, bbox[1] - padding)
    right  = min(w, bbox[2] + padding)
    bottom = min(h, bbox[3] + padding)
    return img.crop((left, top, right, bottom))


def resize_to_sprite(img: Image.Image) -> Image.Image:
    """
    Resize to SPRITE_W × SPRITE_H maintaining aspect ratio, centred on
    a transparent canvas.

    Uses LANCZOS for the initial downsample (smooth, preserves colours),
    then a nearest-neighbour pass to lock to pixel boundaries.
    """
    # Fit within SPRITE_W × SPRITE_H while preserving aspect ratio
    img_ratio    = img.width / img.height
    target_ratio = SPRITE_W / SPRITE_H

    if img_ratio > target_ratio:
        new_w = SPRITE_W
        new_h = max(1, int(SPRITE_W / img_ratio))
    else:
        new_h = SPRITE_H
        new_w = max(1, int(SPRITE_H * img_ratio))

    # Two-pass resize: smooth → pixelate
    mid_scale = 4  # intermediate scale before final pixel snap
    mid = img.resize((new_w * mid_scale, new_h * mid_scale), Image.LANCZOS)
    small = mid.resize((new_w, new_h), Image.NEAREST)

    # Centre on transparent SPRITE_W × SPRITE_H canvas
    canvas = Image.new("RGBA", (SPRITE_W, SPRITE_H), (0, 0, 0, 0))
    x_off  = (SPRITE_W - new_w) // 2
    y_off  = (SPRITE_H - new_h) // 2
    canvas.paste(small, (x_off, y_off), small)
    return canvas


def quantize_to_palette(img: Image.Image, colors: int = PALETTE_COLORS) -> Image.Image:
    """
    Reduce to a limited colour palette for the pixel art look.
    Re-applies transparency from the original after quantisation.
    """
    original = img.copy()
    rgb      = img.convert("RGB")
    quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    result   = quantized.convert("RGBA")

    # Restore transparent pixels lost during quantisation
    orig_px   = original.load()
    result_px = result.load()
    for y in range(SPRITE_H):
        for x in range(SPRITE_W):
            if orig_px[x, y][3] < 128:
                result_px[x, y] = (0, 0, 0, 0)

    return result

# ---------------------------------------------------------------------------
# Animation frame generators
# ---------------------------------------------------------------------------

def _shift_rows(base: Image.Image, row_start: int, row_end: int,
                dy: int = 0, dx: int = 0) -> Image.Image:
    """Shift a horizontal band of pixels by (dx, dy) — used for idle/walk."""
    result = base.copy()
    src    = base.load()
    dst    = result.load()

    # Clear target band first
    for y in range(row_start, row_end + 1):
        for x in range(SPRITE_W):
            dst[x, y] = (0, 0, 0, 0)

    # Write shifted pixels
    for y in range(row_start, row_end + 1):
        src_y = y - dy
        for x in range(SPRITE_W):
            src_x = x - dx
            if 0 <= src_y < SPRITE_H and 0 <= src_x < SPRITE_W:
                dst[x, y] = src[src_x, src_y]

    return result


def make_idle_frames(base: Image.Image) -> list[Image.Image]:
    """
    4 idle frames — very subtle 1-pixel breathing shift on the upper body.
    At 16×24px this creates a gentle alive-looking animation.
    """
    f0 = base.copy()
    f1 = _shift_rows(base, 0, 10, dy=1)   # upper body shifts up 1px (inhale)
    f2 = base.copy()                        # back to neutral
    f3 = _shift_rows(base, 0, 10, dy=-1)  # upper body shifts down 1px (exhale)
    return [f0, f1, f2, f3]


def make_walk_frames(base: Image.Image) -> list[Image.Image]:
    """
    4 walk-cycle frames — bottom half (legs) alternates left/right offset.
    Simple but reads correctly as walking from top-down.
    """
    frames = []
    leg_top  = 14
    leg_offsets = [(0, -1), (0, 1), (0, 0), (0, 0)]  # (left_dy, right_dy) per frame

    for l_dy, r_dy in leg_offsets:
        frame = base.copy()
        src   = base.load()
        dst   = frame.load()

        # Clear leg rows
        for y in range(leg_top, SPRITE_H):
            for x in range(SPRITE_W):
                dst[x, y] = (0, 0, 0, 0)

        mid = SPRITE_W // 2
        for y in range(leg_top, SPRITE_H):
            # Left leg
            for x in range(0, mid):
                src_y = y - l_dy
                if leg_top <= src_y < SPRITE_H:
                    dst[x, y] = src[x, src_y]
            # Right leg
            for x in range(mid, SPRITE_W):
                src_y = y - r_dy
                if leg_top <= src_y < SPRITE_H:
                    dst[x, y] = src[x, src_y]

        frames.append(frame)

    return frames


def make_talk_frames(base: Image.Image) -> list[Image.Image]:
    """
    4 talk frames — modify the mouth area (rows 4-6, centre columns).
    Mouth rows are approximate for a top-down character at 16×24px.
    """
    frames = []
    mouth_row   = 5
    mouth_cols  = range(6, 10)   # cols 6-9
    mouth_dark  = (30, 15, 10, 255)   # dark mouth interior
    mouth_bg    = _sample_dominant_colour(base, mouth_cols, [mouth_row])

    # Frame 0: TALK_CLOSED — no change
    frames.append(base.copy())

    # Frame 1: TALK_SLIGHT — 1-pixel slot
    f1 = base.copy()
    d1 = ImageDraw.Draw(f1)
    for x in mouth_cols:
        d1.point((x, mouth_row), fill=mouth_dark)
    frames.append(f1)

    # Frame 2: TALK_OPEN — 2 rows
    f2 = base.copy()
    d2 = ImageDraw.Draw(f2)
    for x in mouth_cols:
        d2.point((x, mouth_row),     fill=mouth_dark)
        d2.point((x, mouth_row + 1), fill=mouth_dark)
    frames.append(f2)

    # Frame 3: TALK_WIDE — 2 rows, 1 px wider each side
    f3 = base.copy()
    d3 = ImageDraw.Draw(f3)
    wide_cols = range(max(0, mouth_cols.start - 1), min(SPRITE_W, mouth_cols.stop + 1))
    for x in wide_cols:
        d3.point((x, mouth_row),     fill=mouth_dark)
        d3.point((x, mouth_row + 1), fill=mouth_dark)
    frames.append(f3)

    return frames


def make_react_frames(base: Image.Image) -> list[Image.Image]:
    """
    4 reaction frames.
    At 16×24px the changes are necessarily very subtle — the main
    read comes from context (camera zoom, speech bubble) rather than
    the sprite expression. These are functionally distinct states
    that the animation engine can trigger.
    """
    # REACT_HAPPY: brighten top half slightly
    happy = _brighten_region(base, 0, 8, factor=1.2)

    # REACT_WORRIED: darken top half slightly
    worried = _darken_region(base, 0, 8, factor=0.8)

    # REACT_SHOCKED: add 2 bright pixels at eye level (wide eyes)
    shocked = base.copy()
    d = ImageDraw.Draw(shocked)
    d.point((5, 3),  fill=(255, 255, 255, 255))
    d.point((10, 3), fill=(255, 255, 255, 255))

    # REACT_SUSPICIOUS: shift one eye area 1px (squint effect)
    suspicious = base.copy()
    d2 = ImageDraw.Draw(suspicious)
    d2.point((10, 3), fill=(20, 20, 20, 255))

    return [happy, worried, shocked, suspicious]


def make_eliminated_frame(base: Image.Image) -> Image.Image:
    """
    Desaturated, darkened sprite for the eliminated state.
    50% darker and fully greyscale — reads immediately as 'out of the game'.
    """
    gray    = ImageOps.grayscale(base.convert("RGB"))
    darkened = gray.point(lambda p: int(p * 0.6))
    result  = darkened.convert("RGBA")

    # Restore transparency
    base_px = base.load()
    res_px  = result.load()
    for y in range(SPRITE_H):
        for x in range(SPRITE_W):
            if base_px[x, y][3] < 128:
                res_px[x, y] = (0, 0, 0, 0)

    # Slump: shift lower body down 1px
    result = _shift_rows(result, 12, SPRITE_H - 1, dy=-1)
    return result

# ---------------------------------------------------------------------------
# Colour utilities
# ---------------------------------------------------------------------------

def _sample_dominant_colour(
    img: Image.Image,
    cols: range,
    rows: list[int],
) -> tuple[int, int, int, int]:
    """Sample the most common non-transparent colour in a region."""
    px = img.load()
    counts: dict[tuple, int] = {}
    for y in rows:
        for x in cols:
            c = px[x, y]
            if c[3] > 128:
                counts[c] = counts.get(c, 0) + 1
    if not counts:
        return (200, 180, 160, 255)
    return max(counts, key=counts.get)


def _brighten_region(img: Image.Image, row_start: int, row_end: int,
                     factor: float = 1.2) -> Image.Image:
    result = img.copy()
    px = result.load()
    for y in range(row_start, min(row_end + 1, SPRITE_H)):
        for x in range(SPRITE_W):
            r, g, b, a = px[x, y]
            if a > 0:
                px[x, y] = (
                    min(255, int(r * factor)),
                    min(255, int(g * factor)),
                    min(255, int(b * factor)),
                    a,
                )
    return result


def _darken_region(img: Image.Image, row_start: int, row_end: int,
                   factor: float = 0.8) -> Image.Image:
    result = img.copy()
    px = result.load()
    for y in range(row_start, min(row_end + 1, SPRITE_H)):
        for x in range(SPRITE_W):
            r, g, b, a = px[x, y]
            if a > 0:
                px[x, y] = (
                    max(0, int(r * factor)),
                    max(0, int(g * factor)),
                    max(0, int(b * factor)),
                    a,
                )
    return result

# ---------------------------------------------------------------------------
# Sprite sheet assembly
# ---------------------------------------------------------------------------

def assemble_sheet(frames: list[Image.Image]) -> Image.Image:
    """Arrange 20 frames into a 4×5 grid (64×120px)."""
    sheet_w = SHEET_COLS * SPRITE_W   # 64
    sheet_h = SHEET_ROWS * SPRITE_H   # 120
    sheet   = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    for i, frame in enumerate(frames[: SHEET_COLS * SHEET_ROWS]):
        col = i % SHEET_COLS
        row = i // SHEET_COLS
        sheet.paste(frame, (col * SPRITE_W, row * SPRITE_H))

    return sheet

# ---------------------------------------------------------------------------
# Per-character pipeline
# ---------------------------------------------------------------------------

def process_character(agent_id: str) -> bool:
    ref_path = REF_DIR    / f"{agent_id}_reference.png"
    out_path = OUTPUT_DIR / f"{agent_id}_sheet.png"

    if not ref_path.exists():
        print(f"  [FAIL] Reference not found: {ref_path}")
        print(f"         Run: python3 scripts/generate_references.py --character {agent_id}")
        return False

    print(f"  Loading {ref_path.name}...")
    raw = Image.open(ref_path).convert("RGBA")

    print("  Removing white background...")
    nobg = remove_white_background(raw)

    print("  Cropping to character...")
    cropped = crop_to_content(nobg)

    print("  Resizing to 16×24px...")
    sprite = resize_to_sprite(cropped)

    print("  Quantizing to 8-colour palette...")
    base = quantize_to_palette(sprite)

    print("  Generating frames:")
    print("    Row 0 — IDLE (4 frames)...")
    idle  = make_idle_frames(base)

    print("    Row 1 — WALK (4 frames)...")
    walk  = make_walk_frames(base)

    print("    Row 2 — TALK (4 frames)...")
    talk  = make_talk_frames(base)

    print("    Row 3 — REACT (4 frames)...")
    react = make_react_frames(base)

    print("    Row 4 — ELIMINATED + blanks...")
    blank = Image.new("RGBA", (SPRITE_W, SPRITE_H), (0, 0, 0, 0))
    elim  = [make_eliminated_frame(base), blank.copy(), blank.copy(), blank.copy()]

    frames = idle + walk + talk + react + elim  # 20 frames total

    print("  Assembling 64×120px sprite sheet...")
    sheet = assemble_sheet(frames)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "PNG")

    w, h = sheet.size
    print(f"  [OK] Saved → {out_path}  ({w}×{h}px, {len(frames)} frames)")
    return True

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-generate pixel art sprite sheets from reference images"
    )
    parser.add_argument(
        "--character",
        type=str,
        default=None,
        help="Generate only this agent_id (default: all 6)",
    )
    args = parser.parse_args()

    targets = AGENT_IDS
    if args.character:
        if args.character not in AGENT_IDS:
            print(f"ERROR: Unknown agent_id '{args.character}'")
            print(f"Known IDs: {AGENT_IDS}")
            sys.exit(1)
        targets = [args.character]

    print(f"\nGenerating sprite sheets for {len(targets)} character(s)...\n")

    failed: list[str] = []
    for agent_id in targets:
        print(f"── {agent_id} ──")
        ok = process_character(agent_id)
        if not ok:
            failed.append(agent_id)
        print()

    print("─" * 50)
    print(f"Done. {len(targets) - len(failed)}/{len(targets)} generated successfully.")

    if failed:
        print(f"Failed: {failed}")
        sys.exit(1)
    else:
        print("\nNext step: python3 scripts/validate_assets.py")


if __name__ == "__main__":
    main()
