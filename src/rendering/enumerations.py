"""
rendering/enumerations.py

Local constants and enumerations used by the UI.

NOTE: This module is NOT the Rust engine.  The real game engine is a separate
process reached over HTTP.  This module holds:

  - ResourcePaths: filesystem paths to UI assets
  - UI-side enumerations (view modes, zoom levels)
  - Game constants the UI needs for rendering (PrimaryRacialTrait, NeverSeenPlanet)

Full game data (tech trees, race definitions, etc.) is fetched from the engine
API at runtime.
"""

import os

# Paths are resolved relative to the project root:
#   src/engine/ → src/ → project root
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_MODULE_DIR))


def _asset(rel_path: str) -> str:
    return os.path.join(_PROJECT_ROOT, rel_path)


class ResourcePaths:
    IntroLogo = _asset("assets/png/entry.png")
    PlanetsPath = _asset("assets/png/planets")
    RaceIconsPath = _asset("assets/png/race_icons")
    HideArrowPath = _asset("assets/png/ui/hide_arrow.png")
    SaveGamePath = _asset("saved-games")
    EnglishLanguageMap = _asset("resources/strings/english_strings.json")
    TechnologyData = _asset("resources/data/technologies.dat")
    TutorialData = _asset("resources/data/tutorial.dat")
    # Toolbar icons (files will be added to assets/png/toolbar/ as they are created)
    NormalViewIcon = _asset("assets/png/toolbar/normal_view.png")
    SurfaceMineralsIcon = _asset("assets/png/toolbar/surface_minerals.png")
    MineralConcentrationsIcon = _asset("assets/png/toolbar/mineral_concentration.png")
    PercentIcon = _asset("assets/png/toolbar/percent.png")
    PopulationIcon = _asset("assets/png/toolbar/population_view.png")
    NoPlayerInfoIcon = _asset("assets/png/toolbar/no_player_info.png")
    AddWaypointIcon = _asset("assets/png/toolbar/add_waypoint.png")
    ShowRoutesIcon = _asset("assets/png/toolbar/show_routes.png")
    PlanetNamesIcon = _asset("assets/png/toolbar/planet_names.png")
    IdleFleetsIcon = _asset("assets/png/toolbar/idle_fleets.png")
    EnemyShipFilterIcon = _asset("assets/png/toolbar/enemy_ship_filter.png")
    ShipDesignFilterIcon = _asset("assets/png/toolbar/ship_design_filter.png")
    MagnifyingGlassIcon = _asset("assets/png/toolbar/magnifying_glass.png")


class PlanetView:
    Normal = 0
    SurfaceMinerals = 1
    MineralConcentration = 2
    PercentPopulation = 3
    PopulationView = 4
    NoInfo = 5
    Default = Normal


class ZoomLevel:
    Level25 = 0
    Level38 = 1
    Level50 = 2
    Level75 = 3
    Level100 = 4
    Level125 = 5
    Level150 = 6
    Level200 = 7
    Level400 = 8
    Lowest = Level25
    Highest = Level400
    Default = Level200

    @staticmethod
    def multipliers():
        return [0.25, 0.38, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0]

    @staticmethod
    def names():
        return ["25%", "38%", "50%", "75%", "100%", "125%", "150%", "200%", "400%"]


class PrimaryRacialTrait:
    """
    Primary Racial Traits from the original Stars! game.
    The UI uses these for conditional rendering (e.g. Alternate Reality mine display).
    Full trait data is fetched from the engine API.
    """

    ClaimAdjuster = 0
    JackOfAllTrades = 1
    InterstellarTraveler = 2
    InnerStrength = 3
    SpaceDemolition = 4
    WarMonger = 5
    PacketPhysics = 6
    SuperStealth = 7
    HyperExpansion = 8
    AlternateReality = 9


# Sentinel value: planet the player has never surveyed
NeverSeenPlanet = -1

TutorialGameSaveName = "Tutorial"
