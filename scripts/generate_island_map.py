#!/usr/bin/env python3
"""
generate_island_map.py — Generate the Phaser tilemap JSON for the Prompt Island world.

Map: 80×60 tiles × 32px = 2560×1920px world space.
Tileset: island_tileset.png (288×512px, 9 cols × 16 rows = 144 tiles at 32×32).

Tile index reference (1-based Tiled indices; col index within 9-wide tileset):
  T_GRASS      = 1   col 0, row 0  — bright green grass
  T_WATER      = 15  col 5, row 1  — blue water
  T_DEEP_WATER = 57  col 2, row 6  — deep/dark blue water
  T_SAND       = 37  col 0, row 4  — sandy tan
  T_DIRT_PATH  = 6   col 5, row 0  — brown dirt
  T_GRASS_DARK = 26  col 7, row 2  — dark green grass
  T_FLOWERS    = 11  col 1, row 1  — grass with purple flowers

Map locations (tile coordinates → pixel coords at 32px/tile):
  beach:            ~ col 40, row 10   → px (1280, 320)
  jungle:           ~ col 16, row 24   → px (512,  768)
  tribal_fire:      ~ col 40, row 46   → px (1280, 1472)
  confessional_hut: ~ col 64, row 24   → px (2048, 768)
  shelter:          ~ col 26, row 40   → px (832,  1280)
  camp:             ~ col 28, row 30   → px (896,  960)

Usage:
    python3 scripts/generate_island_map.py

No external dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Map dimensions
# ---------------------------------------------------------------------------

MAP_W   = 80   # tiles wide
MAP_H   = 60   # tiles tall
TILE_W  = 32   # px per tile (32×32)
TILE_H  = 32

# Tileset dimensions (288×512 = 9 cols × 16 rows)
TILESET_COLS        = 9
TILESET_IMAGE_W     = 288
TILESET_IMAGE_H     = 512
TILESET_TILE_COUNT  = TILESET_COLS * 16  # = 144

# ---------------------------------------------------------------------------
# Tile indices (1-based Tiled format)
# Formula: idx = row * TILESET_COLS + col + 1
# ---------------------------------------------------------------------------

T_GRASS         = 1    # (col=0, row=0)  bright green
T_FLOWERS       = 11   # (col=1, row=1)  grass + purple flowers
T_WATER         = 15   # (col=5, row=1)  blue water
T_GRASS_DARK    = 26   # (col=7, row=2)  dark green (jungle)
T_SAND          = 37   # (col=0, row=4)  sandy tan (beach)
T_DIRT_PATH     = 6    # (col=5, row=0)  brown dirt path
T_DEEP_WATER    = 57   # (col=2, row=6)  deep blue water

# Empty tile (no object on cell)
T_EMPTY         = 0


def empty_grid(fill: int = T_DEEP_WATER) -> list[list[int]]:
    return [[fill] * MAP_W for _ in range(MAP_H)]


def fill_rect(grid: list[list[int]], r1: int, c1: int, r2: int, c2: int, tile: int) -> None:
    for r in range(max(0, r1), min(MAP_H, r2 + 1)):
        for c in range(max(0, c1), min(MAP_W, c2 + 1)):
            grid[r][c] = tile


def set_tile(grid: list[list[int]], row: int, col: int, tile: int) -> None:
    if 0 <= row < MAP_H and 0 <= col < MAP_W:
        grid[row][col] = tile


# ---------------------------------------------------------------------------
# Layer builders
# ---------------------------------------------------------------------------

def build_terrain_layer() -> list[list[int]]:
    """
    Base terrain layout (in tiles):
      - Deep water borders
      - Shallow water ring
      - Sandy beach
      - Grass interior island
      - Dark jungle zone (left)
      - Dirt paths connecting locations
    """
    g = empty_grid(T_DEEP_WATER)

    # Main island — grass interior
    fill_rect(g, 8,  8,  55, 72, T_GRASS)

    # Beach strip across the top of the island
    fill_rect(g, 8,  16, 16, 64, T_SAND)

    # Shallow water ring around island perimeter
    fill_rect(g, 4,   8,  7, 72, T_WATER)   # top
    fill_rect(g, 56,  8, 57, 72, T_WATER)   # bottom
    fill_rect(g, 8,   4, 55,  7, T_WATER)   # left
    fill_rect(g, 8,  73, 55, 76, T_WATER)   # right

    # Jungle zone — dark grass on left portion
    fill_rect(g, 16,  8, 44, 24, T_GRASS_DARK)

    # Paths (dirt) — connect all 6 locations
    # Horizontal main path: beach ↔ tribal fire (cols 28-44, rows 18-28)
    fill_rect(g, 18, 28, 28, 44, T_DIRT_PATH)
    # Vertical: camp ↔ tribal fire (cols 28-32, rows 28-46)
    fill_rect(g, 28, 28, 46, 32, T_DIRT_PATH)
    # Horizontal: camp ↔ confessional (rows 28-32, cols 40-64)
    fill_rect(g, 26, 40, 32, 64, T_DIRT_PATH)
    # Vertical: jungle ↔ camp (cols 22-28, rows 22-30)
    fill_rect(g, 22, 22, 30, 28, T_DIRT_PATH)
    # Shelter path (cols 24-28, rows 38-42)
    fill_rect(g, 38, 24, 42, 28, T_DIRT_PATH)

    # Decorative grass patches near paths
    for r, c in [(20, 30), (22, 38), (25, 34), (30, 42), (35, 28), (40, 44)]:
        set_tile(g, r, c, T_FLOWERS)

    return g


def build_objects_layer() -> list[list[int]]:
    """
    Objects layer — sparse props. 0 = empty.

    The real tileset is terrain-focused; we keep this sparse.
    Flowers tile (T_FLOWERS) is used for decorative spots.
    """
    g = empty_grid(T_EMPTY)

    # Flower/grass decorations scattered across interior
    decoration_spots = [
        (10, 20), (12, 35), (14, 50), (16, 60),
        (20, 44), (22, 52), (25, 64), (28, 68),
        (32, 48), (35, 54), (38, 60), (42, 70),
        (44, 20), (46, 28), (48, 36), (50, 44),
    ]
    for r, c in decoration_spots:
        set_tile(g, r, c, T_FLOWERS)

    return g


# ---------------------------------------------------------------------------
# Tiled JSON serialisation
# ---------------------------------------------------------------------------

def grid_to_tiled_data(grid: list[list[int]]) -> list[int]:
    """Flatten 2D grid → 1D Tiled data (values are already 1-based or 0 for empty)."""
    return [tile for row in grid for tile in row]


def build_tiled_json(terrain: list[list[int]], objects: list[list[int]]) -> dict:
    return {
        "compressionlevel": -1,
        "height": MAP_H,
        "infinite": False,
        "layers": [
            {
                "data": grid_to_tiled_data(terrain),
                "height": MAP_H,
                "id": 1,
                "name": "terrain",
                "opacity": 1,
                "type": "tilelayer",
                "visible": True,
                "width": MAP_W,
                "x": 0,
                "y": 0,
            },
            {
                "data": grid_to_tiled_data(objects),
                "height": MAP_H,
                "id": 2,
                "name": "objects",
                "opacity": 1,
                "type": "tilelayer",
                "visible": True,
                "width": MAP_W,
                "x": 0,
                "y": 0,
            },
        ],
        "nextlayerid": 3,
        "nextobjectid": 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.10.0",
        "tileheight": TILE_H,
        "tilesets": [
            {
                "columns":      TILESET_COLS,
                "firstgid":     1,
                "image":        "../tiles/island_tileset.png",
                "imageheight":  TILESET_IMAGE_H,
                "imagewidth":   TILESET_IMAGE_W,
                "margin":       0,
                "name":         "island_tileset",
                "spacing":      0,
                "tilecount":    TILESET_TILE_COUNT,
                "tileheight":   TILE_H,
                "tilewidth":    TILE_W,
            }
        ],
        "tilewidth": TILE_W,
        "type": "map",
        "version": "1.10",
        "width": MAP_W,
        # Pixel coordinates of each location (for IslandMap.ts reference)
        "properties": [
            {"name": "location_beach_x",            "type": "int", "value": 1280},
            {"name": "location_beach_y",            "type": "int", "value": 320},
            {"name": "location_jungle_x",           "type": "int", "value": 512},
            {"name": "location_jungle_y",           "type": "int", "value": 768},
            {"name": "location_tribal_fire_x",      "type": "int", "value": 1280},
            {"name": "location_tribal_fire_y",      "type": "int", "value": 1472},
            {"name": "location_confessional_hut_x", "type": "int", "value": 2048},
            {"name": "location_confessional_hut_y", "type": "int", "value": 768},
            {"name": "location_shelter_x",          "type": "int", "value": 832},
            {"name": "location_shelter_y",          "type": "int", "value": 1280},
            {"name": "location_camp_x",             "type": "int", "value": 896},
            {"name": "location_camp_y",             "type": "int", "value": 960},
        ],
    }


def main() -> None:
    output_path = Path("frontend/public/maps/island.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Building terrain layer...")
    terrain = build_terrain_layer()

    print("Building objects layer...")
    objects = build_objects_layer()

    print("Composing Tiled JSON...")
    map_json = build_tiled_json(terrain, objects)

    output_path.write_text(json.dumps(map_json, indent=2), encoding="utf-8")

    world_w = MAP_W * TILE_W
    world_h = MAP_H * TILE_H
    print(f"\n[OK] Island map saved → {output_path}")
    print(f"     {MAP_W}×{MAP_H} tiles @ {TILE_W}px = {world_w}×{world_h}px world space")
    print(f"\nNext step: python3 scripts/validate_assets.py")


if __name__ == "__main__":
    main()
