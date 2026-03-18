#!/usr/bin/env python3
"""
generate_island_map.py — Generate the Phaser tilemap JSON for the Prompt Island world.

Produces a Tiled-compatible JSON file at frontend/public/maps/island.json.
The map is 40×30 tiles at 16×16px = 640×480px world space.

Tile index reference (0-indexed, must match compose_tileset.py TILE_ORDER):
    0  = deep_water      6  = palm_tree      12 = hut_roof
    1  = water_edge      7  = bush           13 = shelter_roof
    2  = sand            8  = jungle_dense   14 = fire_pit_lit
    3  = grass           9  = jungle_light   15 = fire_pit_unlit
    4  = dirt_path      10  = flowers        16 = vote_urn
    5  = grass_dark     11  = rocks          17 = log_seat

In Tiled JSON format, tile indices are 1-based (0 = empty cell).
So tile index 0 (deep_water) → value 1 in the data array.

Map locations (tile coordinates, 0-indexed):
    camp:             centre ~(14, 15)
    beach:            top    ~(20, 5)
    jungle:           left   ~(8,  12)
    tribal_fire:      bottom ~(20, 23)
    confessional_hut: right  ~(32, 12)
    shelter:          mid    ~(13, 20)

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

MAP_W    = 40
MAP_H    = 30
TILE_W   = 32
TILE_H   = 32

# ---------------------------------------------------------------------------
# Tile indices (0-based, +1 in Tiled JSON data)
# ---------------------------------------------------------------------------

T_DEEP_WATER    = 0
T_WATER_EDGE    = 1
T_SAND          = 2
T_GRASS         = 3
T_DIRT_PATH     = 4
T_GRASS_DARK    = 5
T_PALM          = 6
T_BUSH          = 7
T_JUNGLE_DENSE  = 8
T_JUNGLE_LIGHT  = 9
T_FLOWERS       = 10
T_ROCKS         = 11
T_HUT_ROOF      = 12
T_SHELTER_ROOF  = 13
T_FIRE_LIT      = 14
T_FIRE_UNLIT    = 15
T_VOTE_URN      = 16
T_LOG_SEAT      = 17


def empty_grid() -> list[list[int]]:
    return [[T_DEEP_WATER] * MAP_W for _ in range(MAP_H)]


def fill_rect(grid: list[list[int]], r1: int, c1: int, r2: int, c2: int, tile: int) -> None:
    """Fill a rectangle [r1..r2, c1..c2] inclusive with a tile."""
    for r in range(max(0, r1), min(MAP_H, r2 + 1)):
        for c in range(max(0, c1), min(MAP_W, c2 + 1)):
            grid[r][c] = tile


def set_tile(grid: list[list[int]], row: int, col: int, tile: int) -> None:
    if 0 <= row < MAP_H and 0 <= col < MAP_W:
        grid[row][col] = tile


def build_terrain_layer() -> list[list[int]]:
    """
    Base terrain: water, beach, grass island interior.

    Layout:
      rows 0-1       : deep water border
      rows 2-3       : water edge (shallow)
      rows 4-8       : beach (sand) across cols 8-32
      rows 4-27      : main island (grass) across cols 4-36
      rows 27-28     : water edge (bottom)
      row  29        : deep water border
    """
    g = empty_grid()

    # Main island — grass interior
    fill_rect(g, 4, 4, 27, 36, T_GRASS)

    # Beach strip across the top of the island
    fill_rect(g, 4, 8, 8, 32, T_SAND)

    # Water edge around island perimeter
    # Top
    fill_rect(g, 2, 4, 3, 36, T_WATER_EDGE)
    # Bottom
    fill_rect(g, 28, 4, 28, 36, T_WATER_EDGE)
    # Left
    fill_rect(g, 4, 2, 27, 3, T_WATER_EDGE)
    # Right
    fill_rect(g, 4, 37, 27, 38, T_WATER_EDGE)

    # Jungle area — darker grass on left side
    fill_rect(g, 8, 4, 22, 12, T_GRASS_DARK)

    # Dirt paths connecting all locations
    # Horizontal: camp ↔ beach (col 14-22, row 9-14)
    fill_rect(g, 9, 14, 14, 22, T_DIRT_PATH)
    # Horizontal: camp ↔ tribal fire (col 14-22, row 15-23)
    fill_rect(g, 15, 14, 23, 22, T_DIRT_PATH)
    # Horizontal: camp ↔ confessional (row 14-15, col 22-32)
    fill_rect(g, 13, 22, 15, 32, T_DIRT_PATH)
    # Vertical: jungle ↔ camp (col 12-14, row 11-15)
    fill_rect(g, 11, 12, 15, 14, T_DIRT_PATH)
    # Shelter path (col 12-14, row 20-21)
    fill_rect(g, 19, 12, 21, 14, T_DIRT_PATH)

    return g


def build_objects_layer() -> list[list[int]]:
    """
    Objects: trees, structures, fire pit, props.
    0 = empty (no object on this cell).
    """
    g = empty_grid()  # all empty

    # --- Jungle foliage (left area) ---
    jungle_dense_spots = [
        (8, 4), (8, 6), (9, 5), (10, 4), (10, 7), (11, 5), (11, 8),
        (12, 4), (12, 6), (13, 5), (14, 4), (14, 7), (15, 5), (15, 8),
        (16, 4), (16, 6), (17, 5), (18, 4), (18, 7), (19, 5),
        (20, 4), (20, 6), (21, 5), (22, 4),
    ]
    for r, c in jungle_dense_spots:
        set_tile(g, r, c, T_JUNGLE_DENSE)

    jungle_light_spots = [
        (8, 8), (9, 7), (9, 9), (10, 8), (10, 10), (11, 7), (11, 9),
        (12, 8), (13, 7), (13, 9), (14, 8), (15, 7), (16, 8), (17, 7),
    ]
    for r, c in jungle_light_spots:
        set_tile(g, r, c, T_JUNGLE_LIGHT)

    # --- Palm trees along the beach ---
    palm_spots = [
        (5, 9), (5, 13), (5, 18), (5, 23), (5, 27), (5, 31),
        (6, 11), (6, 16), (6, 21), (6, 25), (6, 29),
    ]
    for r, c in palm_spots:
        set_tile(g, r, c, T_PALM)

    # --- Bushes scattered on island ---
    bush_spots = [
        (10, 15), (11, 18), (12, 25), (13, 30), (14, 33),
        (17, 28), (18, 32), (20, 27), (21, 30), (22, 34),
        (24, 16), (25, 20), (26, 24),
    ]
    for r, c in bush_spots:
        set_tile(g, r, c, T_BUSH)

    # --- Rocks ---
    rock_spots = [(9, 19), (16, 13), (23, 18), (25, 30)]
    for r, c in rock_spots:
        set_tile(g, r, c, T_ROCKS)

    # --- Confessional hut (right side, ~col 32, row 12) ---
    # Hut roof tiles (2x2)
    set_tile(g, 11, 31, T_HUT_ROOF)
    set_tile(g, 11, 32, T_HUT_ROOF)
    set_tile(g, 12, 31, T_HUT_ROOF)
    set_tile(g, 12, 32, T_HUT_ROOF)

    # --- Shelter (mid-left, ~col 13, row 20) ---
    # Shelter roof tiles (2x2)
    set_tile(g, 20, 12, T_SHELTER_ROOF)
    set_tile(g, 20, 13, T_SHELTER_ROOF)
    set_tile(g, 21, 12, T_SHELTER_ROOF)
    set_tile(g, 21, 13, T_SHELTER_ROOF)

    # --- Tribal fire pit (bottom-centre, ~col 20, row 23) ---
    set_tile(g, 23, 19, T_LOG_SEAT)
    set_tile(g, 23, 21, T_LOG_SEAT)
    set_tile(g, 24, 20, T_FIRE_LIT)    # active fire
    set_tile(g, 24, 22, T_VOTE_URN)
    set_tile(g, 25, 19, T_LOG_SEAT)
    set_tile(g, 25, 21, T_LOG_SEAT)

    # --- Flowers (decorative, scattered) ---
    flower_spots = [(10, 22), (12, 28), (15, 35), (18, 25), (22, 19)]
    for r, c in flower_spots:
        set_tile(g, r, c, T_FLOWERS)

    return g


def grid_to_tiled_data(grid: list[list[int]]) -> list[int]:
    """
    Flatten 2D grid to a 1D list in Tiled format.
    Tiled uses 1-based indices (0 = empty). Our 0-based indices become +1.
    deep_water (T=0) → 1; empty object cells (T=0) → 0 (treated as: 0 stays 0 for objects).
    """
    flat = []
    for row in grid:
        for tile in row:
            flat.append(tile + 1)  # convert 0-based to 1-based
    return flat


def grid_to_tiled_data_objects(grid: list[list[int]]) -> list[int]:
    """
    Object layer: 0 in our grid means 'no object' → keep as 0 in Tiled (empty).
    Non-zero values → +1 for 1-based Tiled indexing.
    """
    flat = []
    for row in grid:
        for tile in row:
            flat.append(tile + 1 if tile != 0 else 0)
    return flat


def build_tiled_json(terrain: list[list[int]], objects: list[list[int]]) -> dict:
    """Build a Tiled-compatible JSON map definition."""
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
                "data": grid_to_tiled_data_objects(objects),
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
                "columns":     6,
                "firstgid":    1,
                "image":       "../tiles/island_tileset.png",
                "imageheight": 96,
                "imagewidth":  192,
                "margin":      0,
                "name":        "island_tileset",
                "spacing":     0,
                "tilecount":   18,
                "tileheight":  32,
                "tilewidth":   32,
            }
        ],
        "tilewidth": TILE_W,
        "type": "map",
        "version": "1.10",
        "width": MAP_W,
        # Custom properties — location coordinates for IslandMap.ts reference
        "properties": [
            {"name": "location_camp_x",             "type": "int", "value": 448},
            {"name": "location_camp_y",             "type": "int", "value": 480},
            {"name": "location_beach_x",            "type": "int", "value": 640},
            {"name": "location_beach_y",            "type": "int", "value": 160},
            {"name": "location_jungle_x",           "type": "int", "value": 256},
            {"name": "location_jungle_y",           "type": "int", "value": 384},
            {"name": "location_tribal_fire_x",      "type": "int", "value": 640},
            {"name": "location_tribal_fire_y",      "type": "int", "value": 736},
            {"name": "location_confessional_hut_x", "type": "int", "value": 1024},
            {"name": "location_confessional_hut_y", "type": "int", "value": 384},
            {"name": "location_shelter_x",          "type": "int", "value": 416},
            {"name": "location_shelter_y",          "type": "int", "value": 640},
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

    total_tiles = MAP_W * MAP_H
    print(f"\n[OK] Island map saved → {output_path}")
    print(f"     Dimensions: {MAP_W}×{MAP_H} tiles = {MAP_W * TILE_W}×{MAP_H * TILE_H}px world space")
    print(f"     Total cells: {total_tiles} ({total_tiles * 2} across 2 layers)")
    print(f"\nNext step: run python3 scripts/validate_assets.py")


if __name__ == "__main__":
    main()
