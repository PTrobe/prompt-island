#!/usr/bin/env python3
"""
generate_references.py — DALL-E 3 character reference images for Prompt Island.

Generates one full-body concept illustration per character using DALL-E 3.
These are NOT the game sprites — they are visual briefs for drawing sprites
in Aseprite. One image per character, saved to assets/references/.

Usage:
    python3 scripts/generate_references.py
    python3 scripts/generate_references.py --character agent_01_machiavelli

Requires:
    OPENAI_API_KEY in .env
    pip install openai pillow python-dotenv
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

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("assets/references")

# ---------------------------------------------------------------------------
# Character definitions
# ---------------------------------------------------------------------------

CHARACTERS: list[dict] = [
    {
        "agent_id": "agent_01_machiavelli",
        "display_name": "Alex",
        "archetype": "Strategist",
        "description": (
            "a confident Black woman in her early 30s wearing a fitted blazer "
            "and tailored slacks, natural hair pulled back neatly, sharp calculating eyes, "
            "upright posture that projects authority and control"
        ),
        "personality_note": (
            "She looks like she is always three moves ahead. Her expression is "
            "composed but calculating — never fully relaxed."
        ),
    },
    {
        "agent_id": "agent_02_chaos",
        "display_name": "Jordan",
        "archetype": "Wildcard",
        "description": (
            "a non-binary South Asian person in their mid-20s with wild spiked dark hair "
            "with colored tips, wearing oversized punk streetwear and mismatched accessories, "
            "an unpredictable energetic stance, expressive face mid-laugh or mid-shout"
        ),
        "personality_note": (
            "They look like they might do absolutely anything next. "
            "Chaotic energy, visible even in stillness."
        ),
    },
    {
        "agent_id": "agent_03_empath",
        "display_name": "Sam",
        "archetype": "Empath",
        "description": (
            "a warm Latina woman in her early 40s with curly dark brown hair, "
            "wearing comfortable earth-tone layers — terracotta, olive, cream — "
            "open and welcoming body language, soft kind eyes, a gentle smile"
        ),
        "personality_note": (
            "She looks like someone you would instinctively trust. "
            "Warm, approachable, the person everyone confides in."
        ),
    },
    {
        "agent_id": "agent_04_pedant",
        "display_name": "Morgan",
        "archetype": "Know-it-all",
        "description": (
            "an East Asian man in his early 50s with short neat grey-streaked hair "
            "and round wire-frame glasses, wearing a crisp button-up collared shirt "
            "tucked in with a slight over-formal quality, a faintly smug knowing smirk"
        ),
        "personality_note": (
            "He looks like he is about to gently correct something you just said. "
            "Precise, composed, slightly insufferable."
        ),
    },
    {
        "agent_id": "agent_05_paranoid",
        "display_name": "Casey",
        "archetype": "Paranoid",
        "description": (
            "a Middle Eastern man in his early 30s wearing a dark hoodie pulled up "
            "with the hood slightly raised, tired dark circles under his eyes, "
            "a tense guarded posture, eyes glancing sideways as if checking for someone"
        ),
        "personality_note": (
            "He looks like he has not slept in two days and is convinced "
            "someone is watching him. Nervous energy, never fully still."
        ),
    },
    {
        "agent_id": "agent_06_floater",
        "display_name": "Riley",
        "archetype": "People-pleaser / Floater",
        "description": (
            "a mixed-heritage Irish man in his mid-20s with light wavy brown hair, "
            "wearing casual sporty clothes — joggers, a plain tee, clean sneakers — "
            "an easy affable smile, relaxed open posture, no strong visual identity "
            "(intentionally forgettable, blends in)"
        ),
        "personality_note": (
            "He looks friendly and harmless — someone you would forget was in the room. "
            "That is exactly the point."
        ),
    },
]

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(char: dict) -> str:
    return (
        f"Full-body character concept art for a Survivor-style reality show contestant. "
        f"The character is {char['description']}. "
        f"{char['personality_note']} "
        f"Pose: standing upright, facing forward with a slight natural angle, full body visible "
        f"from head to toe including feet. "
        f"Background: plain white, no props, no shadows on background. "
        f"Style: clean digital illustration with strong outlines, flat colours with minimal shading, "
        f"suitable as a pixel art reference guide. "
        f"This image will be used by a pixel artist to draw a 16x24 pixel sprite — "
        f"so clothing details, colour palette, and silhouette must be very clear and distinct. "
        f"Label the character archetype '{char['archetype']}' in small text at the bottom of the image."
    )

# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_reference(client: OpenAI, char: dict, output_dir: Path) -> Path:
    out_path = output_dir / f"{char['agent_id']}_reference.png"

    if out_path.exists():
        print(f"  [SKIP] {out_path.name} already exists — delete to regenerate")
        return out_path

    print(f"  Generating reference for {char['display_name']} ({char['archetype']})...")
    prompt = build_prompt(char)

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        response_format="b64_json",
        n=1,
    )

    img_data = base64.b64decode(response.data[0].b64_json)
    out_path.write_bytes(img_data)
    print(f"  [OK] Saved → {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DALL-E 3 character reference images")
    parser.add_argument(
        "--character",
        type=str,
        default=None,
        help="Generate only this agent_id (default: generate all 6)",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in environment or .env file")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = CHARACTERS
    if args.character:
        targets = [c for c in CHARACTERS if c["agent_id"] == args.character]
        if not targets:
            known = [c["agent_id"] for c in CHARACTERS]
            print(f"ERROR: Unknown character '{args.character}'. Known IDs: {known}")
            sys.exit(1)

    print(f"\nGenerating {len(targets)} reference image(s) → {OUTPUT_DIR}/\n")

    failed: list[str] = []
    for i, char in enumerate(targets):
        try:
            generate_reference(client, char, OUTPUT_DIR)
            # Respect DALL-E rate limits — 5 req/min on tier 1
            if i < len(targets) - 1:
                time.sleep(13)
        except Exception as exc:
            print(f"  [FAIL] {char['agent_id']}: {exc}")
            failed.append(char["agent_id"])

    print(f"\n{'─' * 50}")
    print(f"Done. {len(targets) - len(failed)}/{len(targets)} generated successfully.")
    if failed:
        print(f"Failed: {failed}")
        print("Re-run with --character <agent_id> to retry individual characters.")
    else:
        print(f"\nNext step: open each image in assets/references/ and use it")
        print("as a visual guide to draw the sprite sheet in Aseprite.")
        print("See docs/PHASE5_VISUAL_CHARACTERS.md for the sprite sheet spec.")


if __name__ == "__main__":
    main()
