"""
ui/dialogs/race_wizard.py

Six-page race design wizard — create or edit a race file.

Pages:
  0 · General Details     — name, plural name, icon, predefined templates, leftover spend
  1 · Primary Racial Trait
  2 · Lesser Racial Traits
  3 · Environmental Habitat — gravity, temperature, radiation, growth rate
  4 · Economy               — resource/factory/mine settings
  5 · Research Costs        — per-field cost multipliers

Accepts an optional race dict (conformant to the engine's Race struct / race_file_format.rst)
for editing.  Outputs via race_dict() on accept.

Calls POST /race/validate for live advantage-point feedback (500 ms debounce).
Fails gracefully when the engine is unreachable.

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

import copy
import logging
import os
import random as _random

import requests
from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedLayout,
    QTextEdit,
    QToolButton,
    QWidget,
)

from ...data.r1_parser import (
    LRT_BIT_ORDER,
    c_to_temp_idx,
    g_to_grav_idx,
    grav_idx_to_g,
    temp_idx_to_c,
)
from ...rendering.enumerations import ResourcePaths

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Display constants
# ---------------------------------------------------------------------------

PRT_DISPLAY: list[str] = [
    "Hyper-Expansion",
    "Super Stealth",
    "War Monger",
    "Claim Adjuster",
    "Inner-Strength",
    "Space Demolition",
    "Packet Physics",
    "Interstellar Traveler",
    "Alternate Reality",
    "Jack of All Trades",
]

# Same order as PRT_BYTE: HE=0 … JOAT=9
PRT_CODE: list[str] = ["HE", "SS", "WM", "CA", "IS", "SD", "PP", "IT", "AR", "JOAT"]

PRT_DESC: list[str] = [
    "Creates extra colony ships at game start and grows rapidly, but cannot reach planet "
    "capacity. Colonises new worlds faster than any other race.",
    "Master of stealth technology. Can cloak ships and scan enemy cloaked fleets. "
    "Excellent at intelligence gathering and surprise attacks.",
    "Battle-hardened warriors. Earns bonus advantage points for weapons research and "
    "starts the game with additional combat vessels.",
    "Terraforming specialists. Can adjust gravity, temperature, and radiation to suit "
    "their needs more efficiently than other races.",
    "Superior crew skill and resilience. Fleets repair faster and suffer reduced losses "
    "in combat. Excellent defensive PRT.",
    "Mine-field experts. Builds faster, denser mine fields and is better at detonating "
    "enemy mines.",
    "Mass driver specialists. Launches mineral packets that double as weapons. Can "
    "colonise distant worlds without ships.",
    "Built for long-range travel. Stargate use costs fewer resources and the race starts "
    "with a head-start in propulsion technology.",
    "Lives in orbiting starbases rather than on planets. Has a unique economy and "
    "growth model. Starbases serve as population centres.",
    "No single speciality, but broadly competent. Gets one free tech level in every "
    "field at game start and benefits from a slight fleet bonus.",
]

LRT_DISPLAY: list[str] = [
    "Improved Fuel Efficiency",
    "Total Terraforming",
    "Advanced Remote Mining",
    "Improved Starbases",
    "Generalized Research",
    "Ultimate Recycling",
    "Mineral Alchemy",
    "No Ramscoop Engines",
    "Cheap Engines",
    "Only Basic Remote Mining",
    "No Advanced Scanners",
    "Low Starting Population",
    "Bleeding Edge Technology",
    "Regenerating Shields",
]

LRT_DESC: list[str] = [
    "Ships are equipped with fuel mizers. Burn less fuel on long voyages.",
    "Terraforms up to 30% per field per year instead of 15%. Total terraforming capability.",
    "Remote mining fleets have larger hulls and higher mineral output.",
    "Space stations and orbital forts are cheaper to build and have extra component slots.",
    "Research advances in all fields simultaneously rather than one at a time.",
    "Scrapping ships returns substantially more minerals than normal.",
    "Can convert kT of germanium/ironium into boranium each year via mineral alchemy.",
    "No ramscoop engines are available. All ships must carry fuel or use mizers.",
    "All engines cost 75% less resources to build.",
    "Only basic robominer class remote-mining ships can be constructed.",
    "No advanced penetrating scanners available. Intelligence gathering is limited.",
    "Colony ships start with 17.5% fewer colonists.",
    "All research fields cost 75% more, but start at tech level 4.",
    "Shields partially regenerate between battle rounds.",
]

LEFTOVER_DISPLAY: list[str] = [
    "Surface Minerals",
    "Mineral Concentrations",
    "Mines",
    "Factories",
    "Defenses",
]

LEFTOVER_CODE: list[str] = [
    "surface_minerals",
    "mineral_concentrations",
    "mines",
    "factories",
    "defenses",
]

# Labels exactly as shown in the original game's research page
TECH_COST_DISPLAY: list[str] = ["Costs 75% extra", "Costs standard amount", "Costs 50% less"]
TECH_COST_CODE: list[str] = ["expensive", "normal", "cheap"]

# Template names in display order.
# 2-column grid: even index → left column, odd index → right column.
#   Col 0: Humanoid, Rabbitoid, Insectoid, Nucleotid
#   Col 1: Silicanoid, Antetheral, Random, Custom
TEMPLATE_NAMES: list[str] = [
    "Humanoid",  # 0  col 0 row 0
    "Silicanoid",  # 1  col 1 row 0
    "Rabbitoid",  # 2  col 0 row 1
    "Antetheral",  # 3  col 1 row 1
    "Insectoid",  # 4  col 0 row 2
    "Random",  # 5  col 1 row 2
    "Nucleotid",  # 6  col 0 row 3
    "Custom",  # 7  col 1 row 3
]

# ---------------------------------------------------------------------------
# Race icons — map icon_index (0..31) → asset path
# ---------------------------------------------------------------------------

RACE_ICON_COUNT = 32


def _build_race_icon_map() -> dict[int, str]:
    """Scan the race_icons asset folder once and map index → path.

    Files are named 'race_NN_<label>.png' where NN is 1-based. icon_index is
    0-based, so icon_index = NN - 1.
    """
    result: dict[int, str] = {}
    folder = ResourcePaths.RaceIconsPath
    if not os.path.isdir(folder):
        return result
    for fname in os.listdir(folder):
        if not fname.startswith("race_") or not fname.endswith(".png"):
            continue
        try:
            nn = int(fname.split("_", 2)[1])
        except (IndexError, ValueError):
            continue
        result[nn - 1] = os.path.join(folder, fname)
    return result


_RACE_ICON_PATHS: dict[int, str] = _build_race_icon_map()


def race_icon_path(icon_index: int) -> str | None:
    return _RACE_ICON_PATHS.get(icon_index % RACE_ICON_COUNT)


# ---------------------------------------------------------------------------
# Default / predefined races
# ---------------------------------------------------------------------------


def _default_race() -> dict:
    """Humanoid default — the standard baseline race."""
    return {
        "format_version": 1,
        "name": "Humanoid",
        "plural_name": "Humanoids",
        "prt": "JOAT",
        "lrts": [],
        "hab": {
            "gravity": {"immune": False, "min": grav_idx_to_g(15), "max": grav_idx_to_g(85)},
            "temperature": {"immune": False, "min": temp_idx_to_c(15), "max": temp_idx_to_c(85)},
            "radiation": {"immune": False, "min": 15.0, "max": 85.0},
        },
        "economy": {
            "resource_production": 1000,
            "factory_production": 10,
            "factory_cost": 10,
            "factory_cheap_germanium": False,
            "colonists_operate_factories": 10,
            "mine_production": 10,
            "mine_cost": 5,
            "colonists_operate_mines": 10,
            "growth_rate": 15,
        },
        "research_costs": {
            "energy": "normal",
            "weapons": "normal",
            "propulsion": "normal",
            "construction": "normal",
            "electronics": "normal",
            "biotechnology": "normal",
            "expensive_tech_boost": False,
        },
        "leftover_spend": "surface_minerals",
        "icon_index": 0,
    }


# Predefined race templates verified against actual .r1 binary files.
PREDEFINED_RACES: dict[str, dict] = {
    "Humanoid": _default_race(),
    "Antetheral": {
        **_default_race(),
        "name": "Antetheral",
        "plural_name": "Antheherals",
        "prt": "SD",
        "lrts": ["ARM", "MA", "NRE", "CE", "NAS"],
        "hab": {
            "gravity": {"immune": False, "min": grav_idx_to_g(0), "max": grav_idx_to_g(30)},
            "temperature": {"immune": False, "min": temp_idx_to_c(0), "max": temp_idx_to_c(100)},
            "radiation": {"immune": False, "min": 70.0, "max": 100.0},
        },
        "economy": {
            **_default_race()["economy"],
            "growth_rate": 7,
            "resource_production": 700,
            "factory_production": 11,
            "colonists_operate_factories": 18,
            "mine_cost": 10,
        },
        "research_costs": {
            "energy": "cheap",
            "weapons": "expensive",
            "propulsion": "cheap",
            "construction": "cheap",
            "electronics": "cheap",
            "biotechnology": "cheap",
            "expensive_tech_boost": False,
        },
        "icon_index": 17,
    },
    "Insectoid": {
        **_default_race(),
        "name": "Insectoid",
        "plural_name": "Insectoids",
        "prt": "WM",
        "lrts": ["ISB", "CE", "RS"],
        "hab": {
            "gravity": {"immune": True},
            "temperature": {"immune": False, "min": temp_idx_to_c(0), "max": temp_idx_to_c(100)},
            "radiation": {"immune": False, "min": 70.0, "max": 100.0},
        },
        "economy": {
            **_default_race()["economy"],
            "mine_production": 9,
            "mine_cost": 10,
            "colonists_operate_mines": 6,
            "growth_rate": 10,
        },
        "research_costs": {
            "energy": "cheap",
            "weapons": "cheap",
            "propulsion": "cheap",
            "construction": "cheap",
            "electronics": "normal",
            "biotechnology": "expensive",
            "expensive_tech_boost": False,
        },
        "leftover_spend": "mineral_concentrations",
        "icon_index": 3,
    },
    "Nucleotid": {
        **_default_race(),
        "name": "Nucleotid",
        "plural_name": "Nucleotids",
        "prt": "SS",
        "lrts": ["ARM", "ISB"],
        "hab": {
            "gravity": {"immune": True},
            "temperature": {"immune": False, "min": temp_idx_to_c(12), "max": temp_idx_to_c(88)},
            "radiation": {"immune": False, "min": 0.0, "max": 100.0},
        },
        "economy": {
            **_default_race()["economy"],
            "resource_production": 900,
            "mine_cost": 15,
            "colonists_operate_mines": 5,
            "growth_rate": 10,
        },
        "research_costs": {
            "energy": "expensive",
            "weapons": "expensive",
            "propulsion": "expensive",
            "construction": "expensive",
            "electronics": "expensive",
            "biotechnology": "expensive",
            "expensive_tech_boost": True,
        },
        "leftover_spend": "factories",
        "icon_index": 24,
    },
    "Rabbitoid": {
        **_default_race(),
        "name": "Rabbitoid",
        "plural_name": "Rabbitoids",
        "prt": "IT",
        "lrts": ["IFE", "TT", "CE", "NAS"],
        "hab": {
            "gravity": {
                "immune": False,
                "min": grav_idx_to_g(10),
                "max": grav_idx_to_g(56),
                "min_idx": 10,
                "max_idx": 56,
            },
            "temperature": {"immune": False, "min": temp_idx_to_c(35), "max": temp_idx_to_c(81)},
            "radiation": {"immune": False, "min": 13.0, "max": 53.0},
        },
        "economy": {
            "resource_production": 1000,
            "factory_production": 10,
            "factory_cost": 9,
            "factory_cheap_germanium": True,
            "colonists_operate_factories": 17,
            "mine_production": 10,
            "mine_cost": 9,
            "colonists_operate_mines": 10,
            "growth_rate": 20,
        },
        "research_costs": {
            "energy": "expensive",
            "weapons": "expensive",
            "propulsion": "cheap",
            "construction": "normal",
            "electronics": "normal",
            "biotechnology": "cheap",
            "expensive_tech_boost": False,
        },
        "leftover_spend": "defenses",
        "icon_index": 11,
    },
    "Silicanoid": {
        **_default_race(),
        "name": "Silicanoid",
        "plural_name": "Silicanoids",
        "prt": "HE",
        "lrts": ["IFE", "UR", "OBRM", "BET"],
        "hab": {
            "gravity": {"immune": True},
            "temperature": {"immune": True},
            "radiation": {"immune": True},
        },
        "economy": {
            "resource_production": 800,
            "factory_production": 12,
            "factory_cost": 12,
            "factory_cheap_germanium": False,
            "colonists_operate_factories": 15,
            "mine_production": 10,
            "mine_cost": 9,
            "colonists_operate_mines": 10,
            "growth_rate": 6,
        },
        "research_costs": {
            "energy": "normal",
            "weapons": "normal",
            "propulsion": "cheap",
            "construction": "cheap",
            "electronics": "normal",
            "biotechnology": "expensive",
            "expensive_tech_boost": False,
        },
        "leftover_spend": "factories",
        "icon_index": 4,
    },
}

# ---------------------------------------------------------------------------
# Helper: convert race hab dict ↔ index representation
# ---------------------------------------------------------------------------


def _race_hab_to_idx(hab: dict) -> dict:
    """Convert a race hab dict (physical units) to index-based representation.

    Prefers axis.min_idx/max_idx when present (authoritative .r1 raw indices)
    over physical→index conversion — gravity has collisions (e.g. 0.17 g maps
    to either index 9 or 10) that would otherwise be lost on round-trip.
    """

    def axis_to_idx(axis, to_idx_fn):
        if axis.get("immune"):
            return {"immune": True, "min_idx": 50, "max_idx": 50}
        if "min_idx" in axis and "max_idx" in axis:
            return {
                "immune": False,
                "min_idx": int(axis["min_idx"]),
                "max_idx": int(axis["max_idx"]),
            }
        return {
            "immune": False,
            "min_idx": to_idx_fn(axis.get("min", 0)),
            "max_idx": to_idx_fn(axis.get("max", 100)),
        }

    return {
        "gravity": axis_to_idx(hab.get("gravity", {}), g_to_grav_idx),
        "temperature": axis_to_idx(hab.get("temperature", {}), c_to_temp_idx),
        "radiation": axis_to_idx(
            hab.get("radiation", {}), lambda r: min(max(int(round(r)), 0), 100)
        ),
    }


def _idx_hab_to_race(idx_hab: dict) -> dict:
    """Convert index-based hab representation back to a race hab dict (physical units).

    Emits min_idx/max_idx alongside min/max so the engine bypasses the lossy
    physical→index round-trip (e.g. gravity index 9 and 10 both decode to 0.17 g).
    """

    def idx_to_axis(axis, to_phys_fn):
        if axis.get("immune"):
            return {"immune": True}
        return {
            "immune": False,
            "min": to_phys_fn(axis["min_idx"]),
            "max": to_phys_fn(axis["max_idx"]),
            "min_idx": axis["min_idx"],
            "max_idx": axis["max_idx"],
        }

    return {
        "gravity": idx_to_axis(idx_hab["gravity"], grav_idx_to_g),
        "temperature": idx_to_axis(idx_hab["temperature"], temp_idx_to_c),
        "radiation": idx_to_axis(idx_hab["radiation"], float),
    }


def _habitable_fraction(hab_idx: dict) -> float:
    """Approximate fraction of planets habitable (product of non-immune axis range widths / 100)."""
    frac = 1.0
    for axis_name in ("gravity", "temperature", "radiation"):
        ax = hab_idx[axis_name]
        if not ax["immune"]:
            width = ax["max_idx"] - ax["min_idx"]
            frac *= width / 100.0
    return frac


def _habitable_text(hab_idx: dict) -> str:
    """Return the 'You can expect that 1 in N planets...' string."""
    frac = _habitable_fraction(hab_idx)
    if frac <= 0.001:
        return "No planets will be habitable to your race."
    if frac >= 0.995:
        return "Every planet will be habitable to your race."
    n = max(2, round(1.0 / frac))
    return f"You can expect that 1 in {n} planets will be habitable to your race."


# ---------------------------------------------------------------------------
# ColorSlider widget
# ---------------------------------------------------------------------------


class ColorSlider(QWidget):
    """Horizontal bar (250 × 30) showing a coloured hab range over a black background."""

    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self._low = 0
        self._high = 100
        self._immune = False
        self.setFixedSize(250, 30)

    def update_range(self, low: int, high: int, immune: bool = False):
        self._low = max(0, min(low, 100))
        self._high = max(0, min(high, 100))
        self._immune = immune
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        if not self._immune:
            x0 = int(250 * self._low / 100)
            x1 = int(250 * self._high / 100)
            if x1 > x0:
                painter.fillRect(QRect(x0, 0, x1 - x0, 30), self._color)


# ---------------------------------------------------------------------------
# HabAxisControl widget
# ---------------------------------------------------------------------------


class HabAxisControl(QWidget):
    """
    One habitat axis control row.

    Layout (matches original game):
      Row 1:  [Title]  [←]  [======SLIDER======]  [→]     min_val
      Row 2:           [<<] [>>]  [Immune to X]  [>>] [<<]    to
                                                             max_val
    """

    changed = Signal()

    _MIN_RANGE: dict[str, int] = {
        "gravity": 1,
        "temperature": 20,  # 80 °C / 4 = 20 index units
        "radiation": 1,
    }

    _IMMUNE_LABELS: dict[str, str] = {
        "gravity": "Immune to Gravity",
        "temperature": "Immune to Temperature",
        "radiation": "Immune to Radiation",
    }

    def __init__(self, axis: str, color: QColor, parent=None):
        super().__init__(parent)
        self._axis = axis
        self._min_idx = 15
        self._max_idx = 85
        self._immune = False
        self._updating = False

        self._slider = ColorSlider(color, self)

        self._btn_left = QToolButton()
        self._btn_left.setArrowType(Qt.ArrowType.LeftArrow)
        self._btn_right = QToolButton()
        self._btn_right.setArrowType(Qt.ArrowType.RightArrow)

        self._btn_expand = QPushButton("<< >>")
        self._btn_contract = QPushButton(">> <<")
        self._btn_expand.setFixedWidth(55)
        self._btn_contract.setFixedWidth(55)

        self._immune_cb = QCheckBox(self._IMMUNE_LABELS[axis])

        title_map = {"gravity": "Gravity", "temperature": "Temperature", "radiation": "Radiation"}
        self._title_lbl = QLabel(f"<b>{title_map[axis]}</b>")
        self._title_lbl.setFixedWidth(80)

        self._min_lbl = QLabel()
        self._max_lbl = QLabel()
        self._to_lbl = QLabel("to")
        self._min_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._max_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._min_lbl.setFixedWidth(70)
        self._max_lbl.setFixedWidth(70)

        # Row 1: title | ← | slider | → | min_val
        top_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top_row.addWidget(self._title_lbl)
        top_row.addWidget(self._btn_left)
        top_row.addWidget(self._slider)
        top_row.addWidget(self._btn_right)
        top_row.addWidget(self._min_lbl)

        # Row 2: (indent) << >> | Immune checkbox | >> << | "to"
        bot_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        bot_row.addSpacing(80)  # align under slider
        bot_row.addWidget(self._btn_expand)
        bot_row.addWidget(self._btn_contract)
        bot_row.addWidget(self._immune_cb)
        bot_row.addStretch(1)
        bot_row.addWidget(self._to_lbl)

        # Row 3: max_val right-aligned
        max_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        max_row.addStretch(1)
        max_row.addWidget(self._max_lbl)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        layout.setSpacing(2)
        layout.addLayout(top_row)
        layout.addLayout(bot_row)
        layout.addLayout(max_row)

        self._btn_left.clicked.connect(self._on_shift_left)
        self._btn_right.clicked.connect(self._on_shift_right)
        self._btn_expand.clicked.connect(self._on_expand)
        self._btn_contract.clicked.connect(self._on_contract)
        self._immune_cb.toggled.connect(self._on_immune_toggled)

        self._refresh_display()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, min_idx: int, max_idx: int, immune: bool):
        self._updating = True
        self._immune = immune
        self._min_idx = min(min_idx, max_idx)
        self._max_idx = max(min_idx, max_idx)
        self._immune_cb.setChecked(immune)
        self._updating = False
        self._refresh_display()

    def min_idx(self) -> int:
        return self._min_idx

    def max_idx(self) -> int:
        return self._max_idx

    def immune(self) -> bool:
        return self._immune

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_val(self, idx: int) -> str:
        if self._axis == "gravity":
            return f"{grav_idx_to_g(idx):.2f}g"
        if self._axis == "temperature":
            return f"{int(temp_idx_to_c(idx))}°C"
        return f"{idx}mR"

    def _min_range(self) -> int:
        return self._MIN_RANGE[self._axis]

    def _refresh_display(self):
        immune = self._immune
        self._slider.update_range(self._min_idx, self._max_idx, immune)
        self._btn_left.setEnabled(not immune)
        self._btn_right.setEnabled(not immune)
        self._btn_expand.setEnabled(not immune)
        self._btn_contract.setEnabled(not immune)
        if immune:
            self._min_lbl.setText("Immune")
            self._max_lbl.setText("")
            self._to_lbl.setText("")
        else:
            self._min_lbl.setText(self._format_val(self._min_idx))
            self._max_lbl.setText(self._format_val(self._max_idx))
            self._to_lbl.setText("to")

    def _on_immune_toggled(self, checked: bool):
        if self._updating:
            return
        self._immune = checked
        self._refresh_display()
        self.changed.emit()

    def _on_shift_left(self):
        if self._min_idx > 0:
            self._min_idx -= 1
            self._max_idx -= 1
            self._refresh_display()
            self.changed.emit()

    def _on_shift_right(self):
        if self._max_idx < 100:
            self._min_idx += 1
            self._max_idx += 1
            self._refresh_display()
            self.changed.emit()

    def _on_expand(self):
        changed = False
        if self._min_idx > 0:
            self._min_idx -= 1
            changed = True
        if self._max_idx < 100:
            self._max_idx += 1
            changed = True
        if changed:
            self._refresh_display()
            self.changed.emit()

    def _on_contract(self):
        if self._max_idx - self._min_idx > self._min_range():
            self._min_idx += 1
            self._max_idx -= 1
            self._refresh_display()
            self.changed.emit()


# ---------------------------------------------------------------------------
# ArrowControl widget — numeric parameter with up/down arrows
# ---------------------------------------------------------------------------


class ArrowControl(QWidget):
    """Displays a numeric parameter with prefix text, value, up/down arrows, and suffix text."""

    changed = Signal(int)

    def __init__(
        self, prefix: str, suffix: str, minimum: int, maximum: int, step: int = 1, parent=None
    ):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._step = step
        self._value = minimum

        self._up_btn = QToolButton()
        self._up_btn.setArrowType(Qt.ArrowType.UpArrow)
        self._up_btn.setMaximumHeight(12)

        self._dn_btn = QToolButton()
        self._dn_btn.setArrowType(Qt.ArrowType.DownArrow)
        self._dn_btn.setMaximumHeight(12)

        self._val_lbl = QLabel()

        arrow_box = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        arrow_box.setSpacing(0)
        arrow_box.addWidget(self._up_btn)
        arrow_box.addWidget(self._dn_btn)

        row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        if prefix:
            row.addWidget(QLabel(prefix))
        row.addWidget(self._val_lbl)
        row.addLayout(arrow_box)
        if suffix:
            row.addWidget(QLabel(suffix))
        row.addStretch()

        self._up_btn.clicked.connect(self._increment)
        self._dn_btn.clicked.connect(self._decrement)
        self._refresh()

    def set_value(self, v: int):
        self._value = max(self._min, min(v, self._max))
        self._refresh()

    def value(self) -> int:
        return self._value

    def _refresh(self):
        self._val_lbl.setText(str(self._value))
        self._up_btn.setEnabled(self._value < self._max)
        self._dn_btn.setEnabled(self._value > self._min)

    def _increment(self):
        self.set_value(self._value + self._step)
        self.changed.emit(self._value)

    def _decrement(self):
        self.set_value(self._value - self._step)
        self.changed.emit(self._value)


# ---------------------------------------------------------------------------
# Main wizard dialog
# ---------------------------------------------------------------------------


class RaceWizard(QDialog):
    """
    Six-page race design wizard.

    Pass race=None for a new race (starts with Humanoid defaults).
    Pass race=<dict> to edit an existing race loaded from a .r1 or .r1.json file.
    Pass read_only=True to show the race without the ability to modify it.
    """

    _HELP_BTN = 0
    _CANCEL_BTN = 1
    _PREV_BTN = 2
    _NEXT_BTN = 3
    _FINISH_BTN = 4

    def __init__(
        self,
        parent=None,
        race: dict | None = None,
        engine_url: str = "http://localhost:2001",
        read_only: bool = False,
    ):
        super().__init__(parent)
        self._engine_url = engine_url.rstrip("/")
        self._race = copy.deepcopy(race) if race else _default_race()
        self._hab_idx = _race_hab_to_idx(self._race["hab"])
        self._loading = False
        self._read_only = read_only

        self._val_timer = QTimer(self)
        self._val_timer.setSingleShot(True)
        self._val_timer.setInterval(500)
        self._val_timer.timeout.connect(self._do_validate)

        self._init_controls()
        self._init_ui()
        self._load_race_into_controls()
        self._schedule_validation()
        if self._read_only:
            self._apply_read_only()

    # ------------------------------------------------------------------
    # Control creation
    # ------------------------------------------------------------------

    def _init_controls(self):
        # ── Advantage points frame (top-right corner) ─────────────────
        self._ap_frame = QFrame()
        self._ap_frame.setFrameShape(QFrame.Shape.Box)
        self._ap_frame.setLineWidth(1)
        _ap_title = QLabel("Advantage\nPoints Left")
        _ap_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ap_val_lbl = QLabel("---")
        self._ap_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _val_font = self._ap_val_lbl.font()
        _val_font.setPointSize(_val_font.pointSize() + 8)
        _val_font.setBold(True)
        self._ap_val_lbl.setFont(_val_font)
        _ap_fl = QBoxLayout(QBoxLayout.Direction.TopToBottom, self._ap_frame)
        _ap_fl.setContentsMargins(8, 4, 8, 4)
        _ap_fl.addWidget(_ap_title)
        _ap_fl.addWidget(self._ap_val_lbl)
        self._ap_frame.setFixedSize(120, 72)

        # ── General page ──────────────────────────────────────────────
        self._name_edit = QLineEdit()
        self._plural_name_edit = QLineEdit()
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self._template_group = QButtonGroup(self)
        self._template_group.setExclusive(True)
        for i, name in enumerate(TEMPLATE_NAMES):
            rb = QRadioButton(name)
            self._template_group.addButton(rb, i)

        self._icon_prev_btn = QToolButton()
        self._icon_prev_btn.setArrowType(Qt.ArrowType.LeftArrow)
        self._icon_next_btn = QToolButton()
        self._icon_next_btn.setArrowType(Qt.ArrowType.RightArrow)
        self._icon_idx_lbl = QLabel()
        self._icon_idx_lbl.setFixedSize(64, 64)
        self._icon_idx_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_idx_lbl.setFrameShape(QFrame.Shape.Box)

        self._leftover_combo = QComboBox()
        for lbl in LEFTOVER_DISPLAY:
            self._leftover_combo.addItem(lbl)

        # ── PRT page ──────────────────────────────────────────────────
        self._prt_group = QButtonGroup(self)
        self._prt_group.setExclusive(True)
        for i, lbl in enumerate(PRT_DISPLAY):
            rb = QRadioButton(lbl)
            self._prt_group.addButton(rb, i)
        self._prt_desc = QTextEdit()
        self._prt_desc.setReadOnly(True)
        self._prt_desc.setFixedHeight(90)
        self._prt_desc.setStyleSheet("QTextEdit { background-color: #001800; color: #00cc00; }")

        # ── LRT page ──────────────────────────────────────────────────
        self._lrt_group = QButtonGroup(self)
        self._lrt_group.setExclusive(False)
        for i, lbl in enumerate(LRT_DISPLAY):
            cb = QCheckBox(lbl)
            self._lrt_group.addButton(cb, i)
        self._lrt_desc = QTextEdit()
        self._lrt_desc.setReadOnly(True)
        self._lrt_desc.setFixedHeight(70)
        self._lrt_desc.setStyleSheet("QTextEdit { background-color: #001800; color: #00cc00; }")

        # ── Habitat page ──────────────────────────────────────────────
        self._grav_ctrl = HabAxisControl("gravity", QColor(0, 128, 0))
        self._temp_ctrl = HabAxisControl("temperature", QColor(160, 0, 0))
        self._rad_ctrl = HabAxisControl("radiation", QColor(0, 100, 180))
        self._growth = ArrowControl(
            "Maximum colonist growth rate per year: ", "%", minimum=1, maximum=20
        )
        self._hab_text_lbl = QLabel()
        self._hab_text_lbl.setWordWrap(True)
        self._hab_text_lbl.setStyleSheet("color: #00aa00;")

        # ── Economy page ─────────────────────────────────────────────
        self._rp = ArrowControl(
            "One resource is generated each year for every ",
            " colonists.",
            minimum=700,
            maximum=2500,
            step=100,
        )
        self._fp = ArrowControl(
            "Every 10 factories produce ", " resources each year.", minimum=5, maximum=15
        )
        self._fc = ArrowControl("Factories require ", " resources to build.", minimum=5, maximum=25)
        self._cof = ArrowControl(
            "Every 10,000 colonists may operate up to ", " factories.", minimum=5, maximum=25
        )
        self._germ = QCheckBox("Factories cost 1kT less of Germanium to build")
        self._mp = ArrowControl(
            "Every 10 mines produce up to ", "kT of each mineral every year.", minimum=5, maximum=25
        )
        self._mc = ArrowControl("Mines require ", " resources to build.", minimum=2, maximum=15)
        self._com = ArrowControl(
            "Every 10,000 colonists may operate up to ", " mines.", minimum=5, maximum=25
        )

        # ── Research page ─────────────────────────────────────────────
        self._tech_groups: dict[str, QButtonGroup] = {}
        self._tech_fields = [
            "Energy",
            "Weapons",
            "Propulsion",
            "Construction",
            "Electronics",
            "Biotechnology",
        ]
        for field in self._tech_fields:
            bg = QButtonGroup(self)
            bg.setExclusive(True)
            for j, label in enumerate(TECH_COST_DISPLAY):
                rb = QRadioButton(label)
                bg.addButton(rb, j)
            self._tech_groups[field.lower()] = bg
        self._exp_tech = QCheckBox()  # label set by _update_exp_tech_label() based on PRT

        # ── Nav buttons ───────────────────────────────────────────────
        self._nav = QButtonGroup(self)
        for i, lbl in enumerate(["&Help", "&Cancel", "< &Back", "&Next >", "&Finish"]):
            pb = QPushButton(lbl)
            self._nav.addButton(pb, i)

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------

    def _init_ui(self):
        self.setWindowTitle("View Race" if self._read_only else "Edit Race")
        self.setMinimumSize(600, 540)

        self._stack = QStackedLayout()
        self._stack.addWidget(self._page_general())
        self._stack.addWidget(self._page_prt())
        self._stack.addWidget(self._page_lrt())
        self._stack.addWidget(self._page_habitat())
        self._stack.addWidget(self._page_economy())
        self._stack.addWidget(self._page_research())

        # AP box floats top-right
        ap_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        ap_row.addStretch(1)
        ap_row.addWidget(self._ap_frame)

        btn_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        for btn_id in (
            self._HELP_BTN,
            self._CANCEL_BTN,
            self._PREV_BTN,
            self._NEXT_BTN,
            self._FINISH_BTN,
        ):
            btn_row.addWidget(self._nav.button(btn_id))

        root = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addLayout(ap_row)
        root.addLayout(self._stack, 1)
        root.addLayout(btn_row)

        self._nav.idClicked.connect(self._on_nav)
        self._set_page(0)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def _page_general(self) -> QWidget:
        page = QFrame()

        # Name fields
        name_form = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        name_form.addWidget(QLabel("Race Name:"))
        name_form.addWidget(self._name_edit)
        name_form.addWidget(QLabel("Plural Race Name:"))
        name_form.addWidget(self._plural_name_edit)
        name_form.addWidget(QLabel("Password:"))
        name_form.addWidget(self._password_edit)

        # Template radio buttons (2 columns)
        col0 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col1 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        for i in range(len(TEMPLATE_NAMES)):
            btn = self._template_group.button(i)
            (col0 if i % 2 == 0 else col1).addWidget(btn)
        tmpl_cols = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        tmpl_cols.addLayout(col0)
        tmpl_cols.addLayout(col1)
        tmpl_box = QGroupBox("Predefined Races")
        tmpl_box.setLayout(tmpl_cols)

        # Leftover combo
        lo_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        lo_row.addWidget(QLabel("Spend up to 50 leftover advantage points on:"))
        lo_row.addWidget(self._leftover_combo)
        lo_row.addStretch()

        # Icon selector (bottom-right)
        icon_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        icon_row.addWidget(self._icon_prev_btn)
        icon_row.addWidget(self._icon_idx_lbl)
        icon_row.addWidget(self._icon_next_btn)

        bottom_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        bottom_row.addLayout(lo_row)
        bottom_row.addStretch(1)
        bottom_row.addLayout(icon_row)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addLayout(name_form)
        layout.addWidget(tmpl_box)
        layout.addLayout(bottom_row)
        layout.addStretch()
        page.setLayout(layout)

        self._icon_prev_btn.clicked.connect(self._on_icon_prev)
        self._icon_next_btn.clicked.connect(self._on_icon_next)
        self._name_edit.textChanged.connect(self._on_name_changed)
        self._plural_name_edit.textChanged.connect(self._on_plural_changed)
        self._template_group.idClicked.connect(self._on_template_selected)
        self._leftover_combo.currentIndexChanged.connect(self._on_leftover_changed)
        return page

    def _page_prt(self) -> QWidget:
        page = QFrame()

        col0 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col1 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        for i, btn in enumerate(self._prt_group.buttons()):
            (col0 if i % 2 == 0 else col1).addWidget(btn)
        prt_cols = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        prt_cols.addLayout(col0)
        prt_cols.addLayout(col1)
        prt_box = QGroupBox("Primary Racial Trait")
        prt_box.setLayout(prt_cols)

        desc_box = QGroupBox("Description of Trait")
        dl = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        dl.addWidget(self._prt_desc)
        desc_box.setLayout(dl)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addWidget(prt_box)
        layout.addStretch()
        layout.addWidget(desc_box)
        page.setLayout(layout)

        self._prt_group.idClicked.connect(self._on_prt_changed)
        return page

    def _page_lrt(self) -> QWidget:
        page = QFrame()

        col0 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col1 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        for i, btn in enumerate(self._lrt_group.buttons()):
            (col0 if i % 2 == 0 else col1).addWidget(btn)
        lrt_cols = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        lrt_cols.addLayout(col0)
        lrt_cols.addLayout(col1)
        lrt_box = QGroupBox("Lesser Racial Traits")
        lrt_box.setLayout(lrt_cols)

        desc_box = QGroupBox("Description of Trait")
        dl = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        dl.addWidget(self._lrt_desc)
        desc_box.setLayout(dl)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addWidget(lrt_box)
        layout.addStretch()
        layout.addWidget(desc_box)
        page.setLayout(layout)

        self._lrt_group.idClicked.connect(self._on_lrt_changed)
        return page

    def _page_habitat(self) -> QWidget:
        page = QFrame()
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addWidget(self._grav_ctrl)
        layout.addWidget(self._temp_ctrl)
        layout.addWidget(self._rad_ctrl)
        layout.addSpacing(8)
        layout.addWidget(self._growth)
        layout.addWidget(self._hab_text_lbl)
        layout.addStretch()
        page.setLayout(layout)

        for ctrl in (self._grav_ctrl, self._temp_ctrl, self._rad_ctrl):
            ctrl.changed.connect(self._on_hab_changed)
        self._growth.changed.connect(self._on_growth_changed)
        return page

    def _page_economy(self) -> QWidget:
        page = QFrame()
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        for w in (
            self._rp,
            self._fp,
            self._fc,
            self._cof,
            self._germ,
            self._mp,
            self._mc,
            self._com,
        ):
            layout.addWidget(w)
        layout.addStretch()
        page.setLayout(layout)

        for ctrl, key in (
            (self._rp, "resource_production"),
            (self._fp, "factory_production"),
            (self._fc, "factory_cost"),
            (self._cof, "colonists_operate_factories"),
            (self._mp, "mine_production"),
            (self._mc, "mine_cost"),
            (self._com, "colonists_operate_mines"),
        ):
            ctrl.changed.connect(lambda v, k=key: self._on_economy_changed(k, v))

        self._germ.toggled.connect(lambda v: self._on_economy_changed("factory_cheap_germanium", v))
        return page

    def _page_research(self) -> QWidget:
        page = QFrame()

        left_fields = self._tech_fields[:3]
        right_fields = self._tech_fields[3:]

        left_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        right_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        for field_set, col_layout in ((left_fields, left_layout), (right_fields, right_layout)):
            for field in field_set:
                bg = self._tech_groups[field.lower()]
                col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
                for btn in bg.buttons():
                    col.addWidget(btn)
                box = QGroupBox(f"{field} Research")
                box.setLayout(col)
                col_layout.addWidget(box)

        cols = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        cols.addLayout(left_layout)
        cols.addLayout(right_layout)

        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        layout.addLayout(cols)
        layout.addWidget(self._exp_tech)
        layout.addStretch()
        page.setLayout(layout)

        for field, bg in self._tech_groups.items():
            bg.idClicked.connect(lambda idx, f=field: self._on_tech_changed(f, TECH_COST_CODE[idx]))
        self._exp_tech.toggled.connect(
            lambda v: self._on_research_flag_changed("expensive_tech_boost", v)
        )
        return page

    # ------------------------------------------------------------------
    # Load race into controls
    # ------------------------------------------------------------------

    def _load_race_into_controls(self):
        self._loading = True
        try:
            r = self._race
            self._name_edit.setText(r.get("name", ""))
            self._plural_name_edit.setText(r.get("plural_name", ""))
            self._refresh_icon_display()

            # Template selection — highlight the button whose name matches this race
            race_name = r.get("name", "")
            tmpl_idx = next(
                (i for i, n in enumerate(TEMPLATE_NAMES) if n == race_name),
                -1,
            )
            if tmpl_idx >= 0:
                self._template_group.button(tmpl_idx).setChecked(True)
            else:
                # Custom race — deselect any currently checked template button
                checked = self._template_group.checkedButton()
                if checked:
                    self._template_group.setExclusive(False)
                    checked.setChecked(False)
                    self._template_group.setExclusive(True)

            # Leftover
            lo_code = r.get("leftover_spend", "surface_minerals")
            lo_idx = LEFTOVER_CODE.index(lo_code) if lo_code in LEFTOVER_CODE else 0
            self._leftover_combo.setCurrentIndex(lo_idx)

            # PRT
            prt_code = r.get("prt", "JOAT")
            prt_idx = PRT_CODE.index(prt_code) if prt_code in PRT_CODE else 9
            self._prt_group.button(prt_idx).setChecked(True)
            self._prt_desc.setText(PRT_DESC[prt_idx])

            # LRT
            active_lrts = set(r.get("lrts", []))
            for i, lrt_code in enumerate(LRT_BIT_ORDER):
                self._lrt_group.button(i).setChecked(lrt_code in active_lrts)

            # Habitat
            hab = self._hab_idx
            self._grav_ctrl.set_state(
                hab["gravity"]["min_idx"], hab["gravity"]["max_idx"], hab["gravity"]["immune"]
            )
            self._temp_ctrl.set_state(
                hab["temperature"]["min_idx"],
                hab["temperature"]["max_idx"],
                hab["temperature"]["immune"],
            )
            self._rad_ctrl.set_state(
                hab["radiation"]["min_idx"], hab["radiation"]["max_idx"], hab["radiation"]["immune"]
            )

            eco = r.get("economy", {})
            self._growth.set_value(eco.get("growth_rate", 15))
            self._rp.set_value(eco.get("resource_production", 1000))
            self._fp.set_value(eco.get("factory_production", 10))
            self._fc.set_value(eco.get("factory_cost", 10))
            self._cof.set_value(eco.get("colonists_operate_factories", 10))
            self._germ.setChecked(eco.get("factory_cheap_germanium", False))
            self._mp.set_value(eco.get("mine_production", 10))
            self._mc.set_value(eco.get("mine_cost", 5))
            self._com.set_value(eco.get("colonists_operate_mines", 10))

            rc = r.get("research_costs", {})
            for field in self._tech_fields:
                key = field.lower()
                code = rc.get(key, "normal")
                idx = TECH_COST_CODE.index(code) if code in TECH_COST_CODE else 1
                self._tech_groups[key].button(idx).setChecked(True)
            self._exp_tech.setChecked(rc.get("expensive_tech_boost", False))
        finally:
            self._loading = False

        self._update_exp_tech_label()
        self._update_hab_text()

    # ------------------------------------------------------------------
    # Change handlers → update self._race
    # ------------------------------------------------------------------

    def _on_name_changed(self, text: str):
        if self._loading:
            return
        self._race["name"] = text
        self._schedule_validation()

    def _on_plural_changed(self, text: str):
        if self._loading:
            return
        self._race["plural_name"] = text

    def _on_icon_prev(self):
        idx = (self._race.get("icon_index", 0) - 1) % RACE_ICON_COUNT
        self._race["icon_index"] = idx
        self._refresh_icon_display()

    def _on_icon_next(self):
        idx = (self._race.get("icon_index", 0) + 1) % RACE_ICON_COUNT
        self._race["icon_index"] = idx
        self._refresh_icon_display()

    def _refresh_icon_display(self):
        idx = self._race.get("icon_index", 0) % RACE_ICON_COUNT
        path = race_icon_path(idx)
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                size = self._icon_idx_lbl.size()
                self._icon_idx_lbl.setPixmap(
                    pm.scaled(
                        size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self._icon_idx_lbl.setToolTip(f"Icon {idx}")
                return
        # Fallback: show the index as text if the asset is missing
        self._icon_idx_lbl.setPixmap(QPixmap())
        self._icon_idx_lbl.setText(str(idx))
        self._icon_idx_lbl.setToolTip("")

    def _on_template_selected(self, btn_id: int):
        if self._loading:
            return
        name = TEMPLATE_NAMES[btn_id]
        if name == "Custom":
            return  # Keep current settings unchanged
        if name == "Random":
            name = _random.choice(list(PREDEFINED_RACES.keys()))
        template = copy.deepcopy(PREDEFINED_RACES[name])
        self._race = template
        self._hab_idx = _race_hab_to_idx(self._race["hab"])
        self._load_race_into_controls()
        self._schedule_validation()

    def _on_leftover_changed(self, idx: int):
        if self._loading:
            return
        self._race["leftover_spend"] = LEFTOVER_CODE[idx]

    def _on_prt_changed(self, btn_id: int):
        if self._loading:
            return
        self._race["prt"] = PRT_CODE[btn_id]
        self._prt_desc.setText(PRT_DESC[btn_id])
        self._update_exp_tech_label()
        self._schedule_validation()

    def _update_exp_tech_label(self):
        """Expensive Tech Boost starts fields at tech 4 for JOAT, tech 3 for all others."""
        level = 4 if self._race.get("prt") == "JOAT" else 3
        self._exp_tech.setText(f"All 'Costs 75% extra' research fields start at Tech {level}")

    def _on_lrt_changed(self, btn_id: int):
        if self._loading:
            return
        # OBRM and ARM are mutually exclusive
        obrm_idx = LRT_BIT_ORDER.index("OBRM")
        arm_idx = LRT_BIT_ORDER.index("ARM")
        if btn_id == obrm_idx and self._lrt_group.button(obrm_idx).isChecked():
            self._lrt_group.button(arm_idx).setChecked(False)
        elif btn_id == arm_idx and self._lrt_group.button(arm_idx).isChecked():
            self._lrt_group.button(obrm_idx).setChecked(False)

        self._lrt_desc.setText(LRT_DESC[btn_id])
        self._race["lrts"] = [
            LRT_BIT_ORDER[i] for i, btn in enumerate(self._lrt_group.buttons()) if btn.isChecked()
        ]
        self._schedule_validation()

    def _on_hab_changed(self):
        self._hab_idx = {
            "gravity": {
                "immune": self._grav_ctrl.immune(),
                "min_idx": self._grav_ctrl.min_idx(),
                "max_idx": self._grav_ctrl.max_idx(),
            },
            "temperature": {
                "immune": self._temp_ctrl.immune(),
                "min_idx": self._temp_ctrl.min_idx(),
                "max_idx": self._temp_ctrl.max_idx(),
            },
            "radiation": {
                "immune": self._rad_ctrl.immune(),
                "min_idx": self._rad_ctrl.min_idx(),
                "max_idx": self._rad_ctrl.max_idx(),
            },
        }
        self._race["hab"] = _idx_hab_to_race(self._hab_idx)
        self._update_hab_text()
        self._schedule_validation()

    def _on_growth_changed(self, value: int):
        self._race.setdefault("economy", {})["growth_rate"] = value
        self._schedule_validation()

    def _on_economy_changed(self, key: str, value):
        if self._loading:
            return
        self._race.setdefault("economy", {})[key] = value
        self._schedule_validation()

    def _on_tech_changed(self, field: str, cost_code: str):
        if self._loading:
            return
        self._race.setdefault("research_costs", {})[field] = cost_code
        self._schedule_validation()

    def _on_research_flag_changed(self, key: str, value: bool):
        if self._loading:
            return
        self._race.setdefault("research_costs", {})[key] = value
        self._schedule_validation()

    # ------------------------------------------------------------------
    # Habitable planets estimate
    # ------------------------------------------------------------------

    def _update_hab_text(self):
        self._hab_text_lbl.setText(_habitable_text(self._hab_idx))

    # ------------------------------------------------------------------
    # Advantage-point validation
    # ------------------------------------------------------------------

    def _schedule_validation(self):
        self._val_timer.start()

    def _do_validate(self):
        race = self.race_dict()
        try:
            resp = requests.post(
                f"{self._engine_url}/race/validate",
                json=race,
                timeout=2,
            )
            resp.raise_for_status()
            data = resp.json()
            pts = data.get("advantage_points", "?")
            valid = data.get("valid", False)
            self._ap_val_lbl.setText(str(pts))
            self._ap_val_lbl.setStyleSheet("color: green;" if valid else "color: red;")
        except Exception as exc:
            log.debug("race/validate failed: %s", exc)
            self._ap_val_lbl.setText("---")
            self._ap_val_lbl.setStyleSheet("")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _set_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._nav.button(self._PREV_BTN).setEnabled(idx > 0)
        self._nav.button(self._NEXT_BTN).setEnabled(idx < 5)
        # Finish is always available (matches original game)

    def _apply_read_only(self):
        """Disable every editable page and convert the dialog into a viewer."""
        for i in range(self._stack.count()):
            self._stack.widget(i).setEnabled(False)
        self._nav.button(self._FINISH_BTN).setVisible(False)
        self._nav.button(self._CANCEL_BTN).setText("&Close")

    def _on_nav(self, btn_id: int):
        cur = self._stack.currentIndex()
        if btn_id == self._CANCEL_BTN:
            self.reject()
        elif btn_id == self._NEXT_BTN and cur < 5:
            self._set_page(cur + 1)
        elif btn_id == self._PREV_BTN and cur > 0:
            self._set_page(cur - 1)
        elif btn_id == self._FINISH_BTN:
            self.accept()
        elif btn_id == self._HELP_BTN:
            pass  # TODO: context-sensitive help

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def race_dict(self) -> dict:
        """Return a copy of the current race state as a race dict."""
        r = copy.deepcopy(self._race)
        r["hab"] = _idx_hab_to_race(self._hab_idx)
        return r
