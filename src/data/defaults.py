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
    """Duck-typed planet object understood by SpaceMap and InfoPanel.

    Field shape mirrors the engine's per-player turn file (PlayerView):
    identity (id, name, x, y) is always present; contents fields are
    populated only for planets the player has observed (penetrating-scan
    range or owned). For never-observed planets contents stay at their
    None / 0 defaults and ``years_since`` is -1.

    See stars-reborn-design/docs/architecture.rst (Per-Player Visibility).
    """

    id: int
    name: str
    x: float
    y: float

    # Identity-adjacent (always present in current engine output).
    homeworld: bool = False
    owner: int | None = None
    population: int = 0
    years_since: int = 0  # 0 = scanned this turn; -1 = never observed.

    # Hab — None for never-observed; concrete value for observed.
    gravity: float | None = None
    temperature: int | None = None
    radiation: int | None = None

    # Mineral concentrations (1..100) — None for never-observed.
    ironium_concentration: int | None = None
    boranium_concentration: int | None = None
    germanium_concentration: int | None = None

    # Surface minerals in kT — 0 default is fine (panels render "0 kT").
    surface_ironium: int = 0
    surface_boranium: int = 0
    surface_germanium: int = 0

    # Installations — 0 default for never-observed and unowned planets.
    factories: int = 0
    mines: int = 0

    # Planet value (0..100 habitable, negative red, capped at -45) computed
    # against the viewing player's race. None for never-observed planets.
    value: int | None = None

    @classmethod
    def from_turn_planet(cls, p: dict) -> PlanetData:
        """Build a ``PlanetData`` from one entry in the engine's PlayerView.

        The engine emits either an Observed planet (full contents) or an
        Unobserved planet (only id/name/x/y). Wire field names are
        kebab-case per the project schema convention
        (stars-reborn-schemas/response-turn-file.json). Fields absent
        from the JSON — the never-observed case — fall back to the
        dataclass defaults (``None`` for hab/concentrations/value, ``0``
        for surface and installations, ``-1`` for ``years_since``).
        """
        return cls(
            id=p["id"],
            name=p["name"],
            x=float(p["x"]),
            y=float(p["y"]),
            homeworld=p.get("homeworld", False),
            owner=p.get("owner"),
            population=p.get("population", 0),
            years_since=p.get("years-since-last-scan", -1),
            gravity=p.get("gravity"),
            temperature=p.get("temperature"),
            radiation=p.get("radiation"),
            ironium_concentration=p.get("ironium-concentration"),
            boranium_concentration=p.get("boranium-concentration"),
            germanium_concentration=p.get("germanium-concentration"),
            surface_ironium=p.get("surface-ironium", 0),
            surface_boranium=p.get("surface-boranium", 0),
            surface_germanium=p.get("surface-germanium", 0),
            factories=p.get("factories", 0),
            mines=p.get("mines", 0),
            value=p.get("value"),
        )


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
