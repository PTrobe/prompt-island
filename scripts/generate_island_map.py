#!/usr/bin/env python3
"""
generate_island_map.py — Generate the Phaser tilemap JSON for the Prompt Island world.

Map: 80×60 tiles × 32px = 2560×1920px world space.
Tileset: island_tileset.png (288×512px, 9 cols × 16 rows = 144 tiles at 32×32).

Tile layout reference (1-based Tiled index, formula = row*9 + col + 1):

  FLAT GRASS FILL (rows 11-12 — truly seamless, no directional arcs, safe for interior):
    100-108  row 11: plain flat bright grass variants
    109-117  row 12: more flat grass variants

  GRASS EDGE tiles (rows 0-3 — bumpy canopy edges, used at terrain boundaries):
    1-5    row 0: top-row grass (bumpy top + right + left)
    10-14  row 1: second row (bumpy sides only)
    19-23  row 2: third row
    28-36  row 3: fourth row

  CLIFF / GRASS-TO-DIRT edges (rows 9-10 — grass over brown dirt):
    82-90  row 9:  grass-top + dirt face (directional cliff)
    91-99  row 10: lower cliff face

  WATER (shallow):  15-17  row 1 cols 5-7
  WATER (deep):     57     row 6 col 2
  WATER transitions: 49-53, 60-62  rows 5-6

  SAND/BEACH:  37-40  row 4 cols 0-3
  DIRT/PATH:    6- 8  row 0 cols 5-7

  DARK GRASS (jungle interior): 26, 29-30
  FLOWERS (sparse decoration):  11, 2

Usage:
    python3 scripts/generate_island_map.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Map dimensions
# ---------------------------------------------------------------------------

MAP_W   = 80
MAP_H   = 60
TILE_W  = 32
TILE_H  = 32

TILESET_COLS        = 9
TILESET_IMAGE_W     = 288
TILESET_IMAGE_H     = 512
TILESET_TILE_COUNT  = 144

# ---------------------------------------------------------------------------
# Tile indices (1-based Tiled format)
# ---------------------------------------------------------------------------

# ── Flat grass (rows 11-12 — seamless flat green, no directional arcs)
T_GRASS       = 100  # flat bright green (row 11 col 0)
T_GRASS_2     = 101
T_GRASS_3     = 102
T_GRASS_4     = 103
T_GRASS_5     = 104

# ── Flat grass with decorations (sparse — ~5% of grass tiles)
T_FLOWERS     = 11   # purple flower on grass (row 1 col 1)
T_SPARKLE     = 2    # white sparkle on grass (row 0 col 1)
# Extra flat grass variants from row 12
T_GRASS_6     = 109
T_GRASS_7     = 110

# ── Cliff/edge grass (rows 9-10 — grass with brown dirt face below)
#    col mapping (same for both rows): 0=topleft, 1=top, 2=topright,
#    3=left, 4=solid, 5=right, 6=botleft, 7=bottom, 8=botright
T_CLIFF_ROW9  = 82   # row 9 base  (grass-top + dirt face)
T_CLIFF_TL    = 82   # top-left cliff corner
T_CLIFF_T     = 83   # top edge
T_CLIFF_TR    = 84   # top-right corner
T_CLIFF_L     = 85   # left edge
T_CLIFF_MID   = 86   # solid interior
T_CLIFF_R     = 87   # right edge
T_CLIFF_BL    = 88   # bottom-left corner
T_CLIFF_B     = 89   # bottom edge
T_CLIFF_BR    = 90   # bottom-right corner

# ── Dark grass / jungle (verified pure-green tiles, no water content)
T_DARK_A      = 29   # dark green (row 3 col 1) — verified no water
T_DARK_B      = 30   # dark green (row 3 col 2)
T_DARK_C      = 42   # dark green (row 4 col 5)

# ── Water
T_WATER       = 15   # shallow light-blue (row 1 col 5)
T_WATER_2     = 16
T_WATER_3     = 17
T_DEEP_WATER  = 57   # deep blue ocean (row 6 col 2)

# ── Sand / beach
T_SAND        = 37   # tan sand (row 4 col 0)
T_SAND_2      = 38
T_SAND_3      = 39

# ── Paths (dirt brown)
T_DIRT        = 6    # brown path (row 0 col 5)
T_DIRT_2      = 7
T_DIRT_3      = 8

T_EMPTY       = 0    # no object on cell


# ---------------------------------------------------------------------------
# Deterministic pseudo-random (no external deps, seed by position)
# ---------------------------------------------------------------------------

def phash(r: int, c: int, salt: int = 0) -> int:
    """Cheap non-seeded hash of a grid position. Returns 0-999."""
    h = (r * 2654435761 ^ c * 2246822519 ^ salt * 1234567891) & 0xFFFF_FFFF
    h = ((h >> 16) ^ h) * 0x45D9F3B & 0xFFFF_FFFF
    return h % 1000


def grass_tile(r: int, c: int) -> int:
    """Return a flat grass tile, with occasional decorative variants."""
    h = phash(r, c)
    if h < 20:   return T_FLOWERS   # 2% purple flowers
    if h < 40:   return T_SPARKLE   # 2% sparkle
    if h < 180:  return T_GRASS_2
    if h < 330:  return T_GRASS_3
    if h < 480:  return T_GRASS_4
    if h < 600:  return T_GRASS_5
    if h < 750:  return T_GRASS_6
    if h < 870:  return T_GRASS_7
    return T_GRASS


def dark_grass_tile(r: int, c: int) -> int:
    """Return a dark grass tile (jungle) with variation."""
    h = phash(r, c, salt=7)
    if h < 300: return T_DARK_A
    if h < 600: return T_DARK_B
    return T_DARK_C


def sand_tile(r: int, c: int) -> int:
    h = phash(r, c, salt=3)
    if h < 333: return T_SAND
    if h < 666: return T_SAND_2
    return T_SAND_3


def water_tile(r: int, c: int) -> int:
    h = phash(r, c, salt=5)
    if h < 400: return T_WATER
    if h < 700: return T_WATER_2
    return T_WATER_3


def dirt_tile(r: int, c: int) -> int:
    h = phash(r, c, salt=11)
    if h < 400: return T_DIRT
    if h < 700: return T_DIRT_2
    return T_DIRT_3


# ---------------------------------------------------------------------------
# Island shape helpers
# ---------------------------------------------------------------------------

# Island centre and radii (in tile units)
CX      = 40.0   # col centre
CY      = 30.0   # row centre
RX      = 32.0   # col semi-axis
RY      = 24.0   # row semi-axis

# Slightly bumpy coast using low-frequency sine variation
def coast_distance(r: int, c: int) -> float:
    """
    Returns a normalised distance from the island centre.
    Values < 1.0 are inside the island.
    The coastline is made irregular by adding sine bumps.
    """
    dr = (r - CY) / RY
    dc = (c - CX) / RX
    base = math.sqrt(dr * dr + dc * dc)

    # Two overlapping sine waves make the coast slightly irregular
    angle = math.atan2(dr, dc)
    bump  = (
        0.06 * math.sin(angle * 3 + 0.4) +
        0.04 * math.sin(angle * 7 + 1.1) +
        0.03 * math.sin(angle * 11 + 2.3)
    )
    return base + bump


def in_zone(r: int, c: int, threshold: float) -> bool:
    return coast_distance(r, c) < threshold


# Jungle blob: compact cluster in the west-interior of the island
def in_jungle(r: int, c: int) -> bool:
    if not in_zone(r, c, 0.62): return False
    dr = (r - CY) / RY
    dc = (c - CX) / RX
    # Cols ~18-27, rows ~25-36 (left interior only, away from coast)
    return dc < -0.40 and dr > -0.25 and dr < 0.25


# Small internal pond (top-right interior)
POND_CR, POND_CC = 22, 52
POND_RR, POND_RC = 5, 7
def in_pond(r: int, c: int) -> bool:
    dr = (r - POND_CR) / POND_RR
    dc = (c - POND_CC) / POND_RC
    return dr * dr + dc * dc < 1.0


# Path system — simple horizontal/vertical lines connecting locations
def on_path(r: int, c: int) -> bool:
    paths = [
        # Beach ↔ tribal fire (vertical spine, 2 tiles wide)
        lambda r, c: 15 <= r <= 45 and 39 <= c <= 41,
        # Camp ↔ confessional (east spur, 2 tiles tall)
        lambda r, c: 28 <= r <= 30 and 41 <= c <= 58,
        # Camp ↔ jungle (west spur, 2 tiles tall)
        lambda r, c: 28 <= r <= 30 and 22 <= c <= 41,
        # Shelter path (south branch, 2 tiles wide)
        lambda r, c: 30 <= r <= 41 and 27 <= c <= 29,
    ]
    return any(fn(r, c) for fn in paths)


# ---------------------------------------------------------------------------
# Terrain layer
# ---------------------------------------------------------------------------

def build_terrain_layer() -> list[list[int]]:
    g = [[T_DEEP_WATER] * MAP_W for _ in range(MAP_H)]

    for r in range(MAP_H):
        for c in range(MAP_W):
            d = coast_distance(r, c)

            if d < 0.70:
                # Solid island interior
                if in_pond(r, c):
                    g[r][c] = water_tile(r, c)
                elif on_path(r, c):
                    g[r][c] = dirt_tile(r, c)
                elif in_jungle(r, c):
                    g[r][c] = dark_grass_tile(r, c)
                else:
                    g[r][c] = grass_tile(r, c)

            elif d < 0.78:
                # Beach ring around the island
                g[r][c] = sand_tile(r, c)

            elif d < 0.88:
                # Shallow water / lagoon around beach
                g[r][c] = water_tile(r, c)

            else:
                # Deep ocean
                g[r][c] = T_DEEP_WATER

    return g


# ---------------------------------------------------------------------------
# Objects layer — sparse decorations placed on top of terrain
# ---------------------------------------------------------------------------

def build_objects_layer() -> list[list[int]]:
    """
    Sparse decorations on top of terrain: extra flowers and grass detail.
    Intentionally very light — terrain variation carries most of the visual
    interest; objects just add occasional accent spots.
    """
    terrain = build_terrain_layer()
    g = [[T_EMPTY] * MAP_W for _ in range(MAP_H)]

    for r in range(1, MAP_H - 1):
        for c in range(1, MAP_W - 1):
            tile = terrain[r][c]
            h = phash(r, c, salt=42)

            # Extra flowers/sparkles over flat grass (4% chance)
            if tile in (T_GRASS, T_GRASS_2, T_GRASS_3, T_GRASS_4, T_GRASS_5, T_GRASS_6, T_GRASS_7):
                if h < 25:
                    g[r][c] = T_FLOWERS
                elif h < 45:
                    g[r][c] = T_SPARKLE

    return g


# ---------------------------------------------------------------------------
# Tiled JSON serialisation
# ---------------------------------------------------------------------------

def grid_to_tiled_data(grid: list[list[int]]) -> list[int]:
    return [tile for row in grid for tile in row]


def build_tiled_json(terrain: list[list[int]], objects: list[list[int]]) -> dict:
    return {
        "compressionlevel": -1,
        "height": MAP_H,
        "infinite": False,
        "layers": [
            {
                "data": grid_to_tiled_data(terrain),
                "height": MAP_H, "id": 1, "name": "terrain",
                "opacity": 1, "type": "tilelayer", "visible": True,
                "width": MAP_W, "x": 0, "y": 0,
            },
            {
                "data": grid_to_tiled_data(objects),
                "height": MAP_H, "id": 2, "name": "objects",
                "opacity": 1, "type": "tilelayer", "visible": True,
                "width": MAP_W, "x": 0, "y": 0,
            },
        ],
        "nextlayerid": 3,
        "nextobjectid": 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.10.0",
        "tileheight": TILE_H,
        "tilesets": [{
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
        }],
        "tilewidth": TILE_W,
        "type": "map",
        "version": "1.10",
        "width": MAP_W,
        "properties": [
            {"name": "location_beach_x",            "type": "int", "value": 1312},
            {"name": "location_beach_y",            "type": "int", "value": 448},
            {"name": "location_jungle_x",           "type": "int", "value": 736},
            {"name": "location_jungle_y",           "type": "int", "value": 800},
            {"name": "location_tribal_fire_x",      "type": "int", "value": 1280},
            {"name": "location_tribal_fire_y",      "type": "int", "value": 1408},
            {"name": "location_confessional_hut_x", "type": "int", "value": 1792},
            {"name": "location_confessional_hut_y", "type": "int", "value": 704},
            {"name": "location_shelter_x",          "type": "int", "value": 896},
            {"name": "location_shelter_y",          "type": "int", "value": 1248},
            {"name": "location_camp_x",             "type": "int", "value": 896},
            {"name": "location_camp_y",             "type": "int", "value": 960},
        ],
    }


def main() -> None:
    output_path = Path("frontend/public/maps/island.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Building terrain layer (organic island shape + flat grass fill)...")
    terrain = build_terrain_layer()

    print("Building objects layer (jungle canopy clusters)...")
    objects = build_objects_layer()

    # Quick stats
    from collections import Counter
    flat = [t for row in terrain for t in row]
    counts = Counter(flat)
    print(f"  Deep water: {counts[T_DEEP_WATER]}, Shallow: {counts.get(T_WATER,0)+counts.get(T_WATER_2,0)+counts.get(T_WATER_3,0)}")
    print(f"  Sand: {counts.get(T_SAND,0)+counts.get(T_SAND_2,0)+counts.get(T_SAND_3,0)}")
    print(f"  Grass (flat): {sum(counts.get(t,0) for t in [T_GRASS,T_GRASS_2,T_GRASS_3,T_GRASS_4,T_GRASS_5,T_GRASS_6,T_GRASS_7,T_FLOWERS,T_SPARKLE])}")
    print(f"  Jungle (dark): {sum(counts.get(t,0) for t in [T_DARK_A,T_DARK_B,T_DARK_C])}")
    print(f"  Paths: {sum(counts.get(t,0) for t in [T_DIRT,T_DIRT_2,T_DIRT_3])}")

    map_json = build_tiled_json(terrain, objects)
    output_path.write_text(json.dumps(map_json, indent=2), encoding="utf-8")

    print(f"\n[OK] Island map saved → {output_path}")
    print(f"     {MAP_W}×{MAP_H} tiles @ {TILE_W}px = {MAP_W*TILE_W}×{MAP_H*TILE_H}px world")


if __name__ == "__main__":
    main()
