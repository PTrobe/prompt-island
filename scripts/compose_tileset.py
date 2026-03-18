#!/usr/bin/env python3
"""
compose_tileset.py — Assemble raw tile PNGs into the final Phaser tileset.

Takes the 256×256 images from assets/tiles_raw/, downsamples each to 16×16
using nearest-neighbour resampling (preserves pixel art crispness), then
arranges them in a grid and saves to frontend/public/tiles/island_tileset.png.

Tile grid layout: 6 columns × 3 rows = 18 tiles
Final tileset size: 96×48 pixels

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

# ---------------------------------------------------------------------------
# Configuration — must match generate_tiles.py TILE_MANIFEST indices
# ---------------------------------------------------------------------------

TILE_SIZE    = 64           # final pixel size of each tile in the tileset
GRID_COLS    = 6            # tiles per row
RAW_DIR      = Path("assets/tiles_raw")
OUTPUT_PATH  = Path("frontend/public/tiles/island_tileset.png")

# Ordered list of tile names — index in this list = tile index in Phaser
# Must match the 'index' field ordering in generate_tiles.py TILE_MANIFEST
TILE_ORDER = [
    # Row 0 — terrain
    "deep_water", "water_edge", "sand", "grass", "dirt_path", "grass_dark",
    # Row 1 — vegetation
    "palm_tree", "bush", "jungle_dense", "jungle_light", "flowers", "rocks",
    # Row 2 — structures and props
    "hut_roof", "shelter_roof", "fire_pit_lit", "fire_pit_unlit", "vote_urn", "log_seat",
]


def main() -> None:
    # Verify all source tiles exist
    missing = []
    for name in TILE_ORDER:
        src = RAW_DIR / f"{name}.png"
        if not src.exists():
            missing.append(str(src))

    if missing:
        print("ERROR: Missing tile source files:")
        for m in missing:
            print(f"  {m}")
        print("\nRun python3 scripts/generate_tiles.py to generate missing tiles.")
        sys.exit(1)

    grid_rows = (len(TILE_ORDER) + GRID_COLS - 1) // GRID_COLS
    tileset_w = GRID_COLS * TILE_SIZE
    tileset_h = grid_rows * TILE_SIZE

    tileset = Image.new("RGBA", (tileset_w, tileset_h), (0, 0, 0, 0))

    print(f"Composing {len(TILE_ORDER)} tiles into {GRID_COLS}×{grid_rows} grid "
          f"({tileset_w}×{tileset_h}px)...\n")

    for idx, name in enumerate(TILE_ORDER):
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        x   = col * TILE_SIZE
        y   = row * TILE_SIZE

        src_path = RAW_DIR / f"{name}.png"
        tile_img  = Image.open(src_path).convert("RGBA")

        # Nearest-neighbour downsample — critical for pixel art crispness.
        # Bilinear or lanczos would produce blurry anti-aliased edges.
        tile_small = tile_img.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)

        tileset.paste(tile_small, (x, y))
        print(f"  [{idx:02d}] {name:20s} → grid ({col}, {row})  paste at ({x}px, {y}px)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tileset.save(OUTPUT_PATH, "PNG")

    print(f"\n[OK] Tileset saved → {OUTPUT_PATH}")
    print(f"     Size: {tileset_w}×{tileset_h}px, {len(TILE_ORDER)} tiles")
    print(f"\nNext step: run python3 scripts/generate_island_map.py")


if __name__ == "__main__":
    main()
