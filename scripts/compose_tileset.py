#!/usr/bin/env python3
"""
compose_tileset.py — Scale the itch.io 16×16 RPG tileset to 32×32 for Phaser.

Source: Tileset_16x16.png (144×256px, 9 cols × 16 rows = 144 tiles at 16×16)
Output: island_tileset.png (288×512px, 9 cols × 16 rows = 144 tiles at 32×32)

Nearest-neighbour scaling preserves pixel art crispness.

Tile index reference (1-based Tiled indices, col×row from top-left):
  Grass (bright):   col 0, row 0  → tile  1
  Grass (flowers):  col 1, row 1  → tile 11
  Water (blue):     col 5, row 1  → tile 15
  Deep water:       col 2, row 6  → tile 57
  Sand/dirt:        col 0, row 4  → tile 37
  Dirt path:        col 5, row 0  → tile  6
  Dark grass:       col 7, row 2  → tile 26

Usage:
    python3 scripts/compose_tileset.py

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

SOURCE_PATH = Path("/Users/trobe/Downloads/graphics/16x16 RPG Pack by Yuri Santos Art/Tileset_16x16.png")
OUTPUT_PATH = Path("frontend/public/tiles/island_tileset.png")

SCALE = 2  # 16 → 32 px tiles


def main() -> None:
    if not SOURCE_PATH.exists():
        print(f"ERROR: Source tileset not found: {SOURCE_PATH}")
        print("Download the '16x16 RPG Pack' from itch.io and extract to ~/Downloads/graphics/")
        sys.exit(1)

    src = Image.open(SOURCE_PATH).convert("RGBA")
    cols = src.size[0] // 16
    rows_count = src.size[1] // 16
    print(f"Source: {SOURCE_PATH.name}  {src.size[0]}×{src.size[1]}px "
          f"({cols}×{rows_count} tiles @ 16px)")

    out = src.resize((src.width * SCALE, src.height * SCALE), Image.NEAREST)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUTPUT_PATH, "PNG")

    print(f"Output: {OUTPUT_PATH}  {out.size[0]}×{out.size[1]}px "
          f"({out.size[0]//32}×{out.size[1]//32} tiles @ 32px)")
    print(f"[OK] Tileset saved → {OUTPUT_PATH}")
    print(f"\nNext step: python3 scripts/generate_island_map.py")


if __name__ == "__main__":
    main()
