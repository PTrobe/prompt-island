#!/usr/bin/env python3
"""
assemble_sprite_sheets.py — Assemble individual 32×32 character frames into
Phaser-compatible sprite sheets.

Source: Downloaded itch.io packs (FrontWalk/BackWalk/SideWalk frames, 32×32 each).
Output: One 128×160px sprite sheet per agent, saved to frontend/public/sprites/.

Sprite sheet layout (4 cols × 5 rows, 32×32 px per frame):
  Row 0 (idle,     frames  0-3):  FrontWalk 1-4
  Row 1 (walk,     frames  4-7):  SideWalk  1-4
  Row 2 (talk,     frames  8-11): FrontWalk 1-4   (lip-sync overrides frames directly)
  Row 3 (react,    frames 12-15): BackWalk  1-4
  Row 4 (eliminated, frames 16-19): FrontWalk1 × 4 (static — code applies grey tint)

Usage:
    python3 scripts/assemble_sprite_sheets.py

Requires:
    pip install pillow
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PACK1 = Path("/Users/trobe/Downloads/graphics/RPGCharactersPortraits+SpritesPack1Demo")
PACK2 = Path("/Users/trobe/Downloads/graphics/RPGCharactersPortraits+SpritesPack2Demo")
OUTPUT_DIR = Path("frontend/public/sprites")

FRAME_SIZE = 32  # source frame dimensions (px)

# ---------------------------------------------------------------------------
# Agent → source frame mapping
# ---------------------------------------------------------------------------

def pack1_frames(char_dir: str, front_prefix: str, back_prefix: str, side_prefix: str) -> dict:
    base = PACK1 / char_dir
    return {
        "front": [base / "FrontWalk" / f"{front_prefix}{i}.png" for i in range(1, 5)],
        "back":  [base / "BackWalk"  / f"{back_prefix}{i}.png"  for i in range(1, 5)],
        "side":  [base / "SideWalk"  / f"{side_prefix}{i}.png"  for i in range(1, 5)],
    }


def pack2_frames(char_dir: str, front_prefix: str, back_prefix: str, side_prefix: str) -> dict:
    base = PACK2 / char_dir
    return {
        "front": [base / "FrontWalk" / f"{front_prefix}{i}.png" for i in range(1, 5)],
        "back":  [base / "BackWalk"  / f"{back_prefix}{i}.png"  for i in range(1, 5)],
        "side":  [base / "SideWalk"  / f"{side_prefix}{i}.png"  for i in range(1, 5)],
    }


AGENTS: list[tuple[str, dict]] = [
    ("agent_01_machiavelli", pack1_frames(
        "MenHuman1",
        front_prefix="HumanManFrontWalk",
        back_prefix="HumanManBackWalk",
        side_prefix="HumanManSideWalk",
    )),
    ("agent_02_chaos", pack1_frames(
        "MenHuman1(Recolor)",
        front_prefix="FrontWalk",
        back_prefix="BackWalk",
        side_prefix="SideWalk",
    )),
    ("agent_03_empath", pack1_frames(
        "WomanHuman1",
        front_prefix="FrontWalk",
        back_prefix="BackWalk",
        side_prefix="SideWalk",
    )),
    ("agent_04_pedant", pack1_frames(
        "WomanHuman1(Recolor)",
        front_prefix="FrontWalk",
        back_prefix="BackWalk",
        side_prefix="SideWalk",
    )),
    ("agent_05_paranoid", pack2_frames(
        "NobleMan/Original",
        front_prefix="NobleManFrontWalk",
        back_prefix="NobleManBackWalk",
        side_prefix="NobleManSideWalk",
    )),
    ("agent_06_floater", pack2_frames(
        "NobleGirl/Original",
        front_prefix="NobleGirlFoward",  # note: typo in source ("Foward")
        back_prefix="NobleGirlBack",
        side_prefix="NobleGirlSide",
    )),
]


# ---------------------------------------------------------------------------
# Sheet builder
# ---------------------------------------------------------------------------

def build_sheet(agent_id: str, frames: dict) -> Image.Image:
    """
    Assemble a 128×160px sprite sheet (4 cols × 5 rows @ 32×32).

    Row layout:
      0 = idle      → FrontWalk 1-4
      1 = walk      → SideWalk  1-4
      2 = talk      → FrontWalk 1-4
      3 = react     → BackWalk  1-4
      4 = eliminated → FrontWalk1 × 4 (static)
    """
    cols, rows = 4, 5
    sheet = Image.new("RGBA", (cols * FRAME_SIZE, rows * FRAME_SIZE), (0, 0, 0, 0))

    row_sources = [
        frames["front"],          # row 0: idle
        frames["side"],           # row 1: walk
        frames["front"],          # row 2: talk
        frames["back"],           # row 3: react
        [frames["front"][0]] * 4, # row 4: eliminated (static first frame)
    ]

    for row_idx, source_list in enumerate(row_sources):
        for col_idx, src_path in enumerate(source_list):
            frame = Image.open(src_path).convert("RGBA")
            if frame.size != (FRAME_SIZE, FRAME_SIZE):
                frame = frame.resize((FRAME_SIZE, FRAME_SIZE), Image.NEAREST)
            sheet.paste(frame, (col_idx * FRAME_SIZE, row_idx * FRAME_SIZE))

    return sheet


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    errors: list[str] = []

    for agent_id, frames in AGENTS:
        # Verify all source files exist
        missing = []
        for direction, paths in frames.items():
            for p in paths:
                if not p.exists():
                    missing.append(str(p))
        if missing:
            errors.append(f"{agent_id}: missing files:\n" + "\n".join(f"  {m}" for m in missing))
            continue

        sheet = build_sheet(agent_id, frames)
        out_path = OUTPUT_DIR / f"{agent_id}_sheet.png"
        sheet.save(out_path, "PNG")
        print(f"  [OK] {agent_id}_sheet.png  ({sheet.size[0]}×{sheet.size[1]}px)")
        ok += 1

    print(f"\n{'='*50}")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(e)
    print(f"Generated {ok}/{len(AGENTS)} sprite sheets → {OUTPUT_DIR}/")
    if ok == len(AGENTS):
        print("\nNext step: python3 scripts/compose_tileset.py")


if __name__ == "__main__":
    main()
