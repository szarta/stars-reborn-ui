"""
ui/dialogs/planet.py

Planet detail dialog — opened by double-clicking a planet on the space map.

Shows the iconic Stars! habitat bars (race range overlaid on the 0–100 axis),
population / growth rate, infrastructure counts, scanner coverage, and defenses.

Accepts duck-typed planet objects (populated from engine HTTP API response)
and an optional race object for hab-range rendering.
"""

from __future__ import annotations

import glob
import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QSizePolicy,
    QWidget,
)

from ...rendering.enumerations import NeverSeenPlanet, PrimaryRacialTrait, ResourcePaths
from ...rendering.space import normalize_gravity, normalize_temperature

# ── Colors ─────────────────────────────────────────────────────────────────

_BAR_BG = QColor(0x20, 0x20, 0x20)
_BAR_GOOD = QColor(0x00, 0xCC, 0x00)  # planet in race range
_BAR_MARGINAL = QColor(0x88, 0xCC, 0x00)  # near edge of range
_BAR_BAD = QColor(0xAA, 0x00, 0x00)  # outside range
_BAR_UNKNOWN = QColor(0x55, 0x55, 0x55)
_BAR_MARKER = QColor(0xFF, 0xFF, 0xFF)  # planet position tick
_BAR_RANGE = QColor(0x00, 0x99, 0x00, 180)  # race range band fill
_BAR_BORDER = QColor(0x80, 0x80, 0x80)
_LABEL_COLOR = QColor(0xDD, 0xDD, 0xDD)


# ── Hab bar widget ──────────────────────────────────────────────────────────


class _HabBar(QWidget):
    """
    Custom QPainter widget that draws one habitat axis as a horizontal bar.

    The bar represents the normalized 0–100 scale.  The race's preferred
    range is drawn as a green band; the planet's actual position is a
    white tick.  If the planet is unknown or the race is immune, the bar
    renders accordingly.
    """

    _BAR_H = 14
    _TICK_W = 3

    def __init__(
        self,
        axis_label: str,
        parent=None,
    ):
        super().__init__(parent)
        self._axis_label = axis_label
        self._planet_norm: int | None = None  # 0–100
        self._range_min: int | None = None  # 0–100
        self._range_max: int | None = None  # 0–100
        self._immune: bool = False
        self._unknown: bool = True
        self._value_text: str = "?"

        self.setMinimumHeight(self._BAR_H + 22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(
        self,
        planet_norm: int | None,
        range_min: int | None,
        range_max: int | None,
        immune: bool,
        unknown: bool,
        value_text: str,
    ):
        self._planet_norm = planet_norm
        self._range_min = range_min
        self._range_max = range_max
        self._immune = immune
        self._unknown = unknown
        self._value_text = value_text
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        label_w = 100
        val_w = 80
        bar_w = max(60, self.width() - label_w - val_w - 8)
        bar_x = label_w
        bar_y = (self.height() - self._BAR_H) // 2

        font = QFont("Arial", 9)
        p.setFont(font)
        p.setPen(_LABEL_COLOR)

        # Axis label (left)
        p.drawText(
            QRectF(0, 0, label_w - 4, self.height()),
            Qt.AlignRight | Qt.AlignVCenter,
            self._axis_label,
        )

        # Bar background
        bar_rect = QRectF(bar_x, bar_y, bar_w, self._BAR_H)
        p.fillRect(bar_rect, _BAR_BG)
        p.setPen(QPen(_BAR_BORDER, 1))
        p.drawRect(bar_rect)

        if self._unknown:
            # Just show a stippled unknown bar
            p.fillRect(bar_rect.adjusted(1, 1, -1, -1), _BAR_UNKNOWN)
        elif self._immune:
            # Full-width green — immune to this axis
            p.fillRect(bar_rect.adjusted(1, 1, -1, -1), _BAR_GOOD)
            p.setPen(_LABEL_COLOR)
            p.drawText(bar_rect, Qt.AlignCenter, "Immune")
        else:
            # Draw race range band
            if self._range_min is not None and self._range_max is not None:
                rx = bar_x + (self._range_min / 100.0) * bar_w
                rw = ((self._range_max - self._range_min) / 100.0) * bar_w
                range_rect = QRectF(rx, bar_y + 1, max(1.0, rw), self._BAR_H - 2)
                p.fillRect(range_rect, QBrush(_BAR_RANGE))

            # Planet tick
            if self._planet_norm is not None:
                in_range = (
                    self._range_min is not None
                    and self._range_max is not None
                    and self._range_min <= self._planet_norm <= self._range_max
                )
                tick_color = _BAR_GOOD if in_range else _BAR_BAD
                tx = bar_x + (self._planet_norm / 100.0) * bar_w
                tick_rect = QRectF(tx - self._TICK_W / 2, bar_y, self._TICK_W, self._BAR_H)
                p.fillRect(tick_rect, tick_color)

        # Value label (right)
        p.setPen(_LABEL_COLOR)
        p.drawText(
            QRectF(bar_x + bar_w + 4, 0, val_w, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._value_text,
        )


# ── Section frame ───────────────────────────────────────────────────────────


def _section(title: str) -> tuple[QFrame, QBoxLayout]:
    """Return a titled section frame + its inner layout."""
    outer = QFrame()
    outer.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)

    title_lbl = QLabel(f"<b>{title}</b>")
    title_lbl.setAlignment(Qt.AlignCenter)
    title_lbl.setStyleSheet("background: #404040; padding: 2px;")

    inner = QBoxLayout(QBoxLayout.Direction.TopToBottom)
    inner.setContentsMargins(6, 4, 6, 4)
    inner.setSpacing(3)

    wrapper = QBoxLayout(QBoxLayout.Direction.TopToBottom)
    wrapper.setContentsMargins(0, 0, 0, 0)
    wrapper.setSpacing(0)
    wrapper.addWidget(title_lbl)
    wrapper.addLayout(inner)
    outer.setLayout(wrapper)
    return outer, inner


def _kv_row(key: str, value: str) -> QBoxLayout:
    row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
    k = QLabel(f"<b>{key}:</b>")
    k.setFixedWidth(130)
    v = QLabel(value)
    row.addWidget(k)
    row.addWidget(v, 1)
    return row


# ── Main dialog ─────────────────────────────────────────────────────────────


class PlanetDialog(QDialog):
    """
    Full planet detail dialog.

    Parameters
    ----------
    planet:
        Duck-typed planet object (Python or Rust).
    player:
        Player object (optional).  If provided, its .race is used for hab
        range rendering and growth rate calculation.
    parent:
        Parent widget.
    """

    def __init__(self, planet, player=None, parent=None):
        super().__init__(parent)
        self._planet = planet
        self._player = player
        self._race = getattr(player, "race", None) if player else None

        self.setWindowTitle(f"Planet: {planet.name}")
        self.setMinimumWidth(560)
        self.setModal(True)

        root = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)
        self.setLayout(root)

        root.addLayout(self._build_header())
        root.addWidget(self._build_habitat_section())
        root.addWidget(self._build_population_section())
        root.addWidget(self._build_infrastructure_section())
        root.addWidget(self._build_scanner_section())

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── header ──────────────────────────────────────────────────────────────

    def _build_header(self) -> QBoxLayout:
        row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        row.setSpacing(12)

        # Planet image
        img_lbl = QLabel()
        img_lbl.setFixedSize(80, 80)
        img_lbl.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        img_lbl.setAlignment(Qt.AlignCenter)
        planet_files = sorted(glob.glob(f"{ResourcePaths.PlanetsPath}/*.png"))
        if planet_files:
            path = planet_files[self._planet.id % len(planet_files)]
            pix = QPixmap(path)
            if not pix.isNull():
                img_lbl.setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(img_lbl)

        # Name + owner
        info = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        name_lbl = QLabel(f"<h2>{self._planet.name}</h2>")
        info.addWidget(name_lbl)

        owner = getattr(self._planet, "owner", None)
        years_since = getattr(self._planet, "years_since", 0)
        if years_since == NeverSeenPlanet:
            info.addWidget(QLabel('<i style="color:gray">Never surveyed</i>'))
        elif owner is None:
            info.addWidget(QLabel('<i style="color:#aaa">Uninhabited</i>'))
        else:
            player_id = getattr(self._player, "id", None) if self._player else None
            if player_id is not None and owner == player_id:
                info.addWidget(QLabel('<b style="color:#00cc00">Your colony</b>'))
            else:
                info.addWidget(QLabel(f'<b style="color:#cc4444">Owner: Player {owner}</b>'))

        value = getattr(self._planet, "value", None)
        if value is not None and years_since != NeverSeenPlanet:
            color = "green" if value >= 0 else "red"
            info.addWidget(QLabel(f'Planet value: <b style="color:{color}">{value}%</b>'))

        info.addStretch(1)
        row.addLayout(info, 1)
        return row

    # ── habitat bars ────────────────────────────────────────────────────────

    def _build_habitat_section(self) -> QFrame:
        frame, layout = _section("Habitat")

        years_since = getattr(self._planet, "years_since", 0)
        unknown = years_since == NeverSeenPlanet

        grav_bar = _HabBar("Gravity")
        temp_bar = _HabBar("Temperature")
        rad_bar = _HabBar("Radiation")

        if unknown:
            for bar in (grav_bar, temp_bar, rad_bar):
                bar.set_data(None, None, None, False, True, "Unknown")
        else:
            # Gravity
            g_val = getattr(self._planet, "gravity", None)
            if g_val is not None:
                try:
                    g_norm = normalize_gravity(g_val)
                except (KeyError, Exception):
                    g_norm = None
                g_text = f"{g_val:.2f}g" if g_norm is not None else "?"
            else:
                g_norm, g_text = None, "?"

            g_immune = getattr(self._race, "gravity_immune", False) if self._race else False
            if g_immune:
                grav_bar.set_data(g_norm, None, None, True, False, g_text)
            elif self._race:
                try:
                    rg_min = normalize_gravity(self._race.gravity_min)
                    rg_max = normalize_gravity(self._race.gravity_max)
                except (KeyError, Exception):
                    rg_min, rg_max = None, None
                grav_bar.set_data(g_norm, rg_min, rg_max, False, False, g_text)
            else:
                grav_bar.set_data(g_norm, None, None, False, False, g_text)

            # Temperature
            t_val = getattr(self._planet, "temperature", None)
            t_norm = normalize_temperature(t_val) if t_val is not None else None
            t_text = f"{t_val}°C" if t_val is not None else "?"

            t_immune = getattr(self._race, "temperature_immune", False) if self._race else False
            if t_immune:
                temp_bar.set_data(t_norm, None, None, True, False, t_text)
            elif self._race:
                rt_min = normalize_temperature(self._race.temperature_min)
                rt_max = normalize_temperature(self._race.temperature_max)
                temp_bar.set_data(t_norm, rt_min, rt_max, False, False, t_text)
            else:
                temp_bar.set_data(t_norm, None, None, False, False, t_text)

            # Radiation
            r_val = getattr(self._planet, "radiation", None)
            r_norm = int(r_val) if r_val is not None else None
            r_text = f"{r_val} mR/yr" if r_val is not None else "?"

            r_immune = getattr(self._race, "radiation_immune", False) if self._race else False
            if r_immune:
                rad_bar.set_data(r_norm, None, None, True, False, r_text)
            elif self._race:
                rad_bar.set_data(
                    r_norm,
                    int(self._race.radiation_min),
                    int(self._race.radiation_max),
                    False,
                    False,
                    r_text,
                )
            else:
                rad_bar.set_data(r_norm, None, None, False, False, r_text)

        layout.addWidget(grav_bar)
        layout.addWidget(temp_bar)
        layout.addWidget(rad_bar)
        return frame

    # ── population ──────────────────────────────────────────────────────────

    def _build_population_section(self) -> QFrame:
        frame, layout = _section("Population")

        years_since = getattr(self._planet, "years_since", 0)
        pop = getattr(self._planet, "population", 0)

        if years_since == NeverSeenPlanet:
            layout.addLayout(_kv_row("Population", "Unknown"))
        elif pop == 0:
            layout.addLayout(_kv_row("Population", "Uninhabited"))
        else:
            layout.addLayout(_kv_row("Population", f"{pop:,}"))

            if self._race is not None:
                value = getattr(self._planet, "value", 0)
                gr = getattr(self._race, "growth_rate", 15)
                if value > 0:
                    annual = int(pop * (gr / 100.0) * (value / 100.0))
                    layout.addLayout(_kv_row("Annual growth", f"+{annual:,}  ({gr}% × {value}%)"))
                elif value < 0:
                    layout.addLayout(
                        _kv_row("Annual growth", f"<font color='red'>{value}% (dying)</font>")
                    )
                else:
                    layout.addLayout(_kv_row("Annual growth", "0 (0% value)"))

        return frame

    # ── infrastructure ──────────────────────────────────────────────────────

    def _build_infrastructure_section(self) -> QFrame:
        frame, layout = _section("Infrastructure")

        years_since = getattr(self._planet, "years_since", 0)

        if years_since == NeverSeenPlanet:
            layout.addLayout(_kv_row("Mines", "Unknown"))
            layout.addLayout(_kv_row("Factories", "Unknown"))
            layout.addLayout(_kv_row("Defenses", "Unknown"))
            return frame

        pop = getattr(self._planet, "population", 0)
        mines = getattr(self._planet, "mines", 0)
        factories = getattr(self._planet, "factories", 0)
        defenses = getattr(self._planet, "defenses", 0)
        pct_defense = getattr(self._planet, "planetary_defense", 0)

        prt = getattr(self._race, "primary_racial_trait", None) if self._race else None
        if prt == PrimaryRacialTrait.AlternateReality:
            mine_cap = int(math.sqrt(max(0, pop)) / 10)
            layout.addLayout(_kv_row("Mines", f"{mine_cap} (AR: √pop/10)"))
            layout.addLayout(_kv_row("Factories", "n/a (AR race)"))
        else:
            if self._race is not None:
                mine_cap = (pop // 10000) * getattr(self._race, "_colonists_operate_mines", 10)
                fact_cap = (pop // 10000) * getattr(self._race, "_colonists_operate_factories", 10)
                layout.addLayout(_kv_row("Mines", f"{mines} / {mine_cap} capacity"))
                layout.addLayout(_kv_row("Factories", f"{factories} / {fact_cap} capacity"))
            else:
                layout.addLayout(_kv_row("Mines", str(mines)))
                layout.addLayout(_kv_row("Factories", str(factories)))

        if pct_defense > 0:
            layout.addLayout(_kv_row("Defenses", f"{defenses} ({pct_defense}% kill rate)"))
        else:
            layout.addLayout(_kv_row("Defenses", str(defenses)))

        return frame

    # ── scanner ─────────────────────────────────────────────────────────────

    def _build_scanner_section(self) -> QFrame:
        frame, layout = _section("Scanner")

        years_since = getattr(self._planet, "years_since", 0)
        owner = getattr(self._planet, "owner", None)
        player_id = getattr(self._player, "id", None) if self._player else None
        is_mine = owner is not None and player_id is not None and owner == player_id

        if years_since == NeverSeenPlanet or not is_mine:
            layout.addLayout(_kv_row("Planetary scanner", "n/a"))
        else:
            # Tech-level scanner ranges not yet implemented (Phase 4 / 5)
            layout.addLayout(_kv_row("Planetary scanner", "Bat Scanner (basic)"))
            layout.addLayout(_kv_row("Basic range", "50 ly  (tech pending)"))
            layout.addLayout(_kv_row("Penetrating range", "0 ly"))

        return frame
