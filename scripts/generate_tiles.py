#!/usr/bin/env python3
"""
generate_tiles.py — DALL-E 2 tile reference images for the Prompt Island map.

Generates one 256×256 image per tile type using DALL-E 2, saved to assets/tiles_raw/.
These are then downsampled and composited into the final tileset by compose_tileset.py.

DALL-E 2 is used (not DALL-E 3) because:
  - Minimum size is 256×256 (DALL-E 3 minimum is 1024×1024)
  - Tiles are static, non-animated — cross-frame consistency is not a concern
  - Cost is $0.016/image vs $0.040 for DALL-E 3

Usage:
    python3 scripts/generate_tiles.py
    python3 scripts/generate_tiles.py --tile grass

Requires:
    OPENAI_API_KEY in .env
    pip install openai python-dotenv
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OUTPUT_DIR = Path("assets/tiles_raw")

# ---------------------------------------------------------------------------
# Tile manifest
#
# index: position in the final tileset grid (left-to-right, top-to-bottom)
# name:  filename key and Phaser tile reference
# prompt: DALL-E 2 prompt fragment (inserted into the template)
# ---------------------------------------------------------------------------

TILE_MANIFEST: list[dict] = [
    # Row 0 — Terrain
    {
        "index": 0,
        "name": "deep_water",
        "prompt": "deep tropical ocean water, dark navy blue, gentle wave ripples, seamless tile",
    },
    {
        "index": 1,
        "name": "water_edge",
        "prompt": "shallow tropical ocean water meeting sandy beach, light turquoise blue fading to sand, seamless tile",
    },
    {
        "index": 2,
        "name": "sand",
        "prompt": "tropical beach sand, warm light tan colour, fine sand texture, seamless tile",
    },
    {
        "index": 3,
        "name": "grass",
        "prompt": "tropical island grass, medium green, flat short grass texture, seamless tile",
    },
    {
        "index": 4,
        "name": "dirt_path",
        "prompt": "dirt path on tropical island, earthy brown, worn footpath texture, seamless tile",
    },
    {
        "index": 5,
        "name": "grass_dark",
        "prompt": "dark tropical grass, deep forest green, dense short grass, seamless tile",
    },
    # Row 1 — Vegetation
    {
        "index": 6,
        "name": "palm_tree",
        "prompt": "top-down view of a palm tree, dark green palm frond crown with brown trunk center visible, tropical island",
    },
    {
        "index": 7,
        "name": "bush",
        "prompt": "top-down view of a tropical bush, rounded dark green shrub, lush foliage",
    },
    {
        "index": 8,
        "name": "jungle_dense",
        "prompt": "top-down view of dense jungle canopy, very dark green overlapping leaves, impenetrable forest",
    },
    {
        "index": 9,
        "name": "jungle_light",
        "prompt": "top-down view of light jungle foliage, medium green dappled leaves, partial canopy",
    },
    {
        "index": 10,
        "name": "flowers",
        "prompt": "top-down view of tropical flowers on grass, small bright coloured blooms, decorative",
    },
    {
        "index": 11,
        "name": "rocks",
        "prompt": "top-down view of scattered grey rocks and stones on dirt ground, natural arrangement",
    },
    # Row 2 — Structures and props
    {
        "index": 12,
        "name": "hut_roof",
        "prompt": "top-down view of a thatched grass roof on a small hut, golden yellow dried grass, bamboo frame visible",
    },
    {
        "index": 13,
        "name": "shelter_roof",
        "prompt": "top-down view of an open-sided shelter with palm leaf roof, brown and green, rustic tribal camp",
    },
    {
        "index": 14,
        "name": "fire_pit_lit",
        "prompt": "top-down view of a campfire in a stone ring, bright orange and yellow flames, glowing embers, grey stones",
    },
    {
        "index": 15,
        "name": "fire_pit_unlit",
        "prompt": "top-down view of an unlit stone fire pit, grey stones in a circle, dark ash in center, no flames",
    },
    {
        "index": 16,
        "name": "vote_urn",
        "prompt": "top-down view of a decorative ceramic voting urn, painted tribal patterns, dark clay, lid on top",
    },
    {
        "index": 17,
        "name": "log_seat",
        "prompt": "top-down view of a wooden log used as a seat, brown rough bark, cut cross-section at ends",
    },
]

TILE_PROMPT_TEMPLATE = (
    "Top-down pixel art game tile, 256x256 pixels. {prompt}. "
    "Flat colours, minimal shading, no cast shadows, no perspective distortion. "
    "Tropical island aesthetic. Clean pixel art style. Square tile format."
)


def generate_tile(client: OpenAI, tile: dict, output_dir: Path) -> Path:
    out_path = output_dir / f"{tile['name']}.png"

    if out_path.exists():
        print(f"  [SKIP] {out_path.name} already exists — delete to regenerate")
        return out_path

    print(f"  Generating tile: {tile['name']}...")
    prompt = TILE_PROMPT_TEMPLATE.format(prompt=tile["prompt"])

    response = client.images.generate(
        model="dall-e-2",
        prompt=prompt,
        size="256x256",
        response_format="b64_json",
        n=1,
    )

    img_data = base64.b64decode(response.data[0].b64_json)
    out_path.write_bytes(img_data)
    print(f"  [OK] Saved → {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DALL-E 2 tile images")
    parser.add_argument(
        "--tile",
        type=str,
        default=None,
        help="Generate only this tile name (default: generate all)",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in environment or .env file")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = TILE_MANIFEST
    if args.tile:
        targets = [t for t in TILE_MANIFEST if t["name"] == args.tile]
        if not targets:
            known = [t["name"] for t in TILE_MANIFEST]
            print(f"ERROR: Unknown tile '{args.tile}'. Known names: {known}")
            sys.exit(1)

    print(f"\nGenerating {len(targets)} tile image(s) → {OUTPUT_DIR}/\n")

    failed: list[str] = []
    for i, tile in enumerate(targets):
        try:
            generate_tile(client, tile, OUTPUT_DIR)
            # DALL-E 2 rate limit: 5 req/min on tier 1 — pace conservatively
            if i < len(targets) - 1:
                time.sleep(13)
        except Exception as exc:
            print(f"  [FAIL] {tile['name']}: {exc}")
            failed.append(tile["name"])

    print(f"\n{'─' * 50}")
    print(f"Done. {len(targets) - len(failed)}/{len(targets)} generated successfully.")
    if failed:
        print(f"Failed: {failed}")
        print("Re-run with --tile <name> to retry individual tiles.")
    else:
        print("\nNext step: run python3 scripts/compose_tileset.py")


if __name__ == "__main__":
    main()
