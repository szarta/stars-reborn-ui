"""
data/defaults.py

Default game parameters for the simple New Game path.

All confirmed values are from the original Stars! client.
The Advanced Game path lets the player override any of these.
See stars-reborn-research/docs/findings/new_game_defaults.rst.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlanetData:
    """Duck-typed planet object understood by SpaceMap and InfoPanel."""

    id: int
    name: str
    x: float
    y: float
    homeworld: bool = False
    owner: int | None = None
    population: int = 0
    years_since: int = 0  # 0 = seen this turn; -1 = never seen


# Default game name keyed on (difficulty, universe_size).
# This is a fixed lookup table in the original — NOT randomly generated.
# Confirmed: all Easy entries; Standard/Small.
# Remaining cells (Standard Tiny/Med/Large/Huge; all Harder; all Expert) are unknown.
# See stars-reborn-research/docs/findings/new_game_defaults.rst.
GAME_NAME_TABLE: dict[tuple[str, str], str] = {
    ("easy", "tiny"): "Shooting Fish in a Barrel",
    ("easy", "small"): "A Walk in the Park",
    ("easy", "medium"): "Sleepwalking in Paradise",
    ("easy", "large"): "The Big Easy",
    ("easy", "huge"): "Eternal Bliss",
    ("normal", "tiny"): "Duck Hunt",
    ("normal", "small"): "A Barefoot JayWalk",
    ("normal", "medium"): "A Rumble in the Jungle",
    ("normal", "large"): "Infected Root Canal",
    ("normal", "huge"): "Jungle Safari",
    ("tough", "tiny"): "Micro-Hardball",
    ("tough", "small"): "Roller Ball",
    ("tough", "medium"): "Wall Street",
    ("tough", "large"): "Big League",
    ("tough", "huge"): "Long Road to Morning",
    ("expert", "tiny"): "Tough Nuts",
    ("expert", "small"): "Blade Runner",
    ("expert", "medium"): "D-Day",
    ("expert", "large"): "World War III",
    ("expert", "huge"): "Eternity in Hell",
}

_GAME_NAME_FALLBACK = "New Game"


def default_game_name(difficulty: str, universe_size: str) -> str:
    """Return the original game's default name for this difficulty/size pair.
    Falls back to 'New Game' for combinations not yet confirmed."""
    return GAME_NAME_TABLE.get((difficulty, universe_size), _GAME_NAME_FALLBACK)


# Default game flags — all false for the Standard path.
DEFAULT_GAME_FLAGS: dict[str, bool] = {
    "maximum-minerals": False,
    "slow-tech-advances": False,
    "accelerated-play": False,
    "random-events": True,  # "No Random Events" defaults to false → events on
    "ai-alliances": False,
    "public-player-scores": False,
    "galaxy-clumping": False,
}

# Default victory conditions for Standard / Small.
DEFAULT_VICTORY_CONDITIONS: dict = {
    "number-of-conditions-met": 1,
    "minimum-years": 50,
    "percent-planets": 60,
    "tech-level-required": 22,
    "tech-fields": 4,
    "exceeds-second-place-by-percent": 100,
}

# Default AI player count keyed on universe size.
# Confirmed across all four difficulties — size is the sole determiner.
DEFAULT_AI_COUNT: dict[str, int] = {
    "tiny": 1,
    "small": 2,
    "medium": 6,
    "large": 11,
    "huge": 15,
}


def build_new_game_request(
    *,
    universe_size: str,
    difficulty: str,
    race_name: str,
) -> dict:
    """
    Assemble a request-create-new-game.json payload from the simple dialog
    selections plus confirmed defaults.  The game name is looked up from the
    confirmed difficulty × size table.
    """
    game_name = default_game_name(difficulty, universe_size)

    return {
        "game": {
            "name": game_name,
            "human-players": [
                {
                    "id": 0,
                    "race": race_name,
                }
            ],
            "ai-players": [
                {"difficulty": difficulty} for _ in range(DEFAULT_AI_COUNT[universe_size])
            ],
            "player-starting-distance": "moderate",
            "universe": {
                "size": universe_size,
                "density": "normal",
            },
            **DEFAULT_GAME_FLAGS,
            "victory-conditions": DEFAULT_VICTORY_CONDITIONS,
        }
    }
