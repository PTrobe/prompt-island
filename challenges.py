"""
Default season challenge schedule for Prompt Island Season 1.

One challenge per game day. Pass this list to GameEngine.run_game() or
supply via the --challenges CLI flag.

Challenges are designed to escalate tension across the arc:
  Day 1 (tribe phase) — establish credibility within your tribe
  Day 2 (tribe phase) — skill/logic challenge; shows competence
  Day 3 (merge)       — social pitch; now competing as individuals
  Day 4 (final 4)     — survival persuasion; most desperate moment
  Day 5 (finale)      — no challenge; TwistEngine handles finale speeches
"""

SEASON_1_CHALLENGES: list[str | None] = [
    # Day 1 — Tribe phase
    (
        "Convince your tribemates why you are essential to this tribe's survival. "
        "What unique skill or quality do you bring that no one else does?"
    ),

    # Day 2 — Tribe phase (skill-based)
    (
        "Riddle challenge: 'I speak without a mouth and hear without ears. "
        "I have no body, but I come alive with the wind. What am I?' "
        "Give your answer AND explain your reasoning."
    ),

    # Day 3 — Merge day (social pitch to the whole group)
    (
        "The tribes have merged. Make your case to ALL remaining players: "
        "why do you uniquely deserve to reach the finale? "
        "Be specific — what have you done, and why should they trust you?"
    ),

    # Day 4 — Final 4 (pure survival)
    (
        "You are one vote away from the finale. Persuade the group that "
        "you are NOT the biggest threat in this game. Make them fear someone else more."
    ),

    # Day 5 — Finale (no challenge — speeches handled by TwistEngine)
    None,
]
