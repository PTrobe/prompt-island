#!/usr/bin/env python3
"""
validate_assets.py — Verify all Phase 5 assets before touching any frontend code.

Checks:
  1. Character sprite sheets (frontend/public/sprites/) — all 6 present, correct size
  2. Island tileset (frontend/public/tiles/island_tileset.png) — correct size
  3. Island map (frontend/public/maps/island.json) — valid Tiled JSON structure
  4. Reference images (assets/references/) — all 6 present (informational)
  5. Raw tiles (assets/tiles_raw/) — all 18 present (informational)

Sprite sheet spec (from PHASE5_VISUAL_CHARACTERS.md):
  Frame size: 16×24px
  Grid:       4 columns × 5 rows
  Sheet size: 64×120px   (4×16 = 64px wide, 5×24 = 120px tall)

Tileset spec:
  Tile size:  16×16px
  Grid:       6 columns × 3 rows = 18 tiles
  Sheet size: 96×48px

Exit code 0 if all checks pass, 1 if any critical check fails.

Usage:
    python3 scripts/validate_assets.py
    python3 scripts/validate_assets.py --strict   # also fails on missing references/raw tiles

Requires:
    pip install pillow
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Expected asset specs
# ---------------------------------------------------------------------------

AGENT_IDS = [
    "agent_01_machiavelli",
    "agent_02_chaos",
    "agent_03_empath",
    "agent_04_pedant",
    "agent_05_paranoid",
    "agent_06_floater",
]

SPRITE_SHEET_SIZE = (128, 240)  # 4 cols × 32px = 128, 5 rows × 48px = 240
TILESET_SIZE      = (192, 96)   # 6 cols × 32px = 192, 3 rows × 32px = 96

TILE_NAMES = [
    "deep_water", "water_edge", "sand", "grass", "dirt_path", "grass_dark",
    "palm_tree", "bush", "jungle_dense", "jungle_light", "flowers", "rocks",
    "hut_roof", "shelter_roof", "fire_pit_lit", "fire_pit_unlit", "vote_urn", "log_seat",
]

SPRITE_DIR    = Path("frontend/public/sprites")
TILESET_PATH  = Path("frontend/public/tiles/island_tileset.png")
MAP_PATH      = Path("frontend/public/maps/island.json")
REFS_DIR      = Path("assets/references")
TILES_RAW_DIR = Path("assets/tiles_raw")

# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

PASS  = "✓"
FAIL  = "✗"
WARN  = "⚠"
SKIP  = "–"


def check_image(path: Path, expected_size: tuple[int, int]) -> tuple[bool, str]:
    """Return (ok, message)."""
    if not path.exists():
        return False, f"{FAIL} MISSING  {path}"
    try:
        img = Image.open(path)
        w, h = img.size
        if (w, h) != expected_size:
            return False, (
                f"{FAIL} WRONG SIZE  {path}\n"
                f"     Expected {expected_size[0]}×{expected_size[1]}px, "
                f"got {w}×{h}px"
            )
        mode = img.mode
        if "A" not in mode:
            return False, (
                f"{FAIL} NO ALPHA  {path}\n"
                f"     Mode is '{mode}' — sprites must be RGBA (transparent background)"
            )
        return True, f"{PASS} OK  {path}  ({w}×{h}px, {mode})"
    except Exception as exc:
        return False, f"{FAIL} UNREADABLE  {path}  ({exc})"


def check_exists(path: Path, label: str) -> tuple[bool, str]:
    if path.exists():
        return True, f"{PASS} OK  {path}"
    return False, f"{FAIL} MISSING  {path}  ({label})"


def check_map_json(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{FAIL} MISSING  {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"{FAIL} INVALID JSON  {path}  ({exc})"

    errors = []
    if data.get("width") != 40:
        errors.append(f"expected width=40, got {data.get('width')}")
    if data.get("height") != 30:
        errors.append(f"expected height=30, got {data.get('height')}")
    if data.get("tilewidth") != 32:
        errors.append(f"expected tilewidth=32, got {data.get('tilewidth')}")
    if data.get("tileheight") != 32:
        errors.append(f"expected tileheight=32, got {data.get('tileheight')}")
    layers = data.get("layers", [])
    if len(layers) < 2:
        errors.append(f"expected 2 layers, got {len(layers)}")
    else:
        expected_len = 40 * 30
        for layer in layers:
            if layer.get("type") == "tilelayer":
                data_len = len(layer.get("data", []))
                if data_len != expected_len:
                    errors.append(
                        f"layer '{layer.get('name')}' has {data_len} cells, "
                        f"expected {expected_len}"
                    )

    if errors:
        return False, f"{FAIL} MAP JSON ERRORS  {path}\n     " + "\n     ".join(errors)
    return True, f"{PASS} OK  {path}  (40×30 tiles, {len(layers)} layers)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Phase 5 game assets")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on missing reference images and raw tiles (not just sprite sheets)",
    )
    args = parser.parse_args()

    failures: list[str] = []
    warnings: list[str] = []

    # ── 1. Sprite sheets (CRITICAL) ──────────────────────────────────────────
    print("\n── Sprite Sheets ──────────────────────────────────────────────────")
    print(f"   Expected: {SPRITE_SHEET_SIZE[0]}×{SPRITE_SHEET_SIZE[1]}px, RGBA, "
          f"4 cols × 5 rows of 32×48px frames\n")
    for agent_id in AGENT_IDS:
        path = SPRITE_DIR / f"{agent_id}_sheet.png"
        ok, msg = check_image(path, SPRITE_SHEET_SIZE)
        print(f"   {msg}")
        if not ok:
            failures.append(msg)

    # ── 2. Tileset (CRITICAL) ────────────────────────────────────────────────
    print("\n── Tileset ─────────────────────────────────────────────────────────")
    print(f"   Expected: {TILESET_SIZE[0]}×{TILESET_SIZE[1]}px, RGBA, "
          f"6 cols × 3 rows of 32×32px tiles\n")
    ok, msg = check_image(TILESET_PATH, TILESET_SIZE)
    print(f"   {msg}")
    if not ok:
        failures.append(msg)

    # ── 3. Map JSON (CRITICAL) ───────────────────────────────────────────────
    print("\n── Island Map JSON ─────────────────────────────────────────────────\n")
    ok, msg = check_map_json(MAP_PATH)
    print(f"   {msg}")
    if not ok:
        failures.append(msg)

    # ── 4. Reference images (informational / strict) ─────────────────────────
    print("\n── Character References (assets/references/) ───────────────────────\n")
    for agent_id in AGENT_IDS:
        path = REFS_DIR / f"{agent_id}_reference.png"
        ok, msg = check_exists(path, "run generate_references.py")
        status = f"   {msg}"
        if not ok:
            if args.strict:
                failures.append(msg)
                print(f"   {FAIL} MISSING  {path}")
            else:
                warnings.append(msg)
                print(f"   {WARN} MISSING  {path}  (not critical — generate_references.py)")
        else:
            print(status)

    # ── 5. Raw tile images (informational / strict) ───────────────────────────
    print("\n── Raw Tiles (assets/tiles_raw/) ────────────────────────────────────\n")
    for name in TILE_NAMES:
        path = TILES_RAW_DIR / f"{name}.png"
        ok, msg = check_exists(path, "run generate_tiles.py")
        if not ok:
            if args.strict:
                failures.append(msg)
                print(f"   {FAIL} MISSING  {path}")
            else:
                warnings.append(msg)
                print(f"   {WARN} MISSING  {path}  (run generate_tiles.py)")
        else:
            print(f"   {PASS} OK  {path}")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    if failures:
        print(f"\n  {FAIL} VALIDATION FAILED — {len(failures)} critical error(s)\n")
        for f in failures:
            print(f"  {f}")
        print()
        sys.exit(1)
    else:
        if warnings:
            print(f"\n  {PASS} All critical assets valid")
            print(f"  {WARN} {len(warnings)} non-critical file(s) missing — see above\n")
        else:
            print(f"\n  {PASS} All assets valid — ready to proceed to Phase 5b\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
