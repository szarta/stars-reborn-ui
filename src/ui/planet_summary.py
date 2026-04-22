"""
ui/planet_summary.py

Bottom-right panel shown below the space map.

Layout (top to bottom):
  • Coords bar  — "ID #N  X: XXXX  Y: XXXX  PlanetName" (updates on hover + select)
  • Goto line   — text input stub (originally a search/goto field)
  • Summary     — planet name, value %, population, report age,
                  hab bars (gravity / temperature / radiation),
                  mineral bars (ironium / boranium / germanium)
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from ..rendering.enumerations import NeverSeenPlanet

# ── Hab bar ────────────────────────────────────────────────────────────────


class _HabBar(QWidget):
    """
    Horizontal hab-axis bar.

    Shows the race's preferred range as a green band and the planet's actual
    position as a tick.  Renders "Immune" when the race ignores this axis.
    """

    _H = 14
    _TICK_W = 3

    _BG = QColor(0x20, 0x20, 0x20)
    _BORDER = QColor(0x80, 0x80, 0x80)
    _UNKNOWN_FILL = QColor(0x55, 0x55, 0x55)
    _RANGE_FILL = QColor(0x00, 0x99, 0x00, 180)
    _TICK_GOOD = QColor(0x00, 0xCC, 0x00)
    _TICK_BAD = QColor(0xAA, 0x00, 0x00)
    _IMMUNE_FILL = QColor(0x00, 0xCC, 0x00)
    _TEXT = QColor(0xDD, 0xDD, 0xDD)

    def __init__(self, axis_label: str, parent=None):
        super().__init__(parent)
        self._label = axis_label
        self._planet_norm: int | None = None
        self._range_min: int | None = None
        self._range_max: int | None = None
        self._immune = False
        self._unknown = True
        self._value_text = "?"
        self.setMinimumHeight(self._H + 20)
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

        lbl_w = 85
        val_w = 65
        bar_w = max(40, self.width() - lbl_w - val_w - 6)
        bar_x = lbl_w
        bar_y = (self.height() - self._H) // 2

        p.setFont(QFont("Arial", 8))
        p.setPen(self._TEXT)
        p.drawText(
            QRectF(0, 0, lbl_w - 2, self.height()),
            Qt.AlignRight | Qt.AlignVCenter,
            self._label,
        )

        bar_rect = QRectF(bar_x, bar_y, bar_w, self._H)
        p.fillRect(bar_rect, self._BG)
        p.setPen(QPen(self._BORDER, 1))
        p.drawRect(bar_rect)

        if self._unknown:
            p.fillRect(bar_rect.adjusted(1, 1, -1, -1), self._UNKNOWN_FILL)
        elif self._immune:
            p.fillRect(bar_rect.adjusted(1, 1, -1, -1), self._IMMUNE_FILL)
            p.setPen(self._TEXT)
            p.drawText(bar_rect, Qt.AlignCenter, "Immune")
        else:
            if self._range_min is not None and self._range_max is not None:
                rx = bar_x + (self._range_min / 100.0) * bar_w
                rw = ((self._range_max - self._range_min) / 100.0) * bar_w
                p.fillRect(
                    QRectF(rx, bar_y + 1, max(1.0, rw), self._H - 2),
                    QBrush(self._RANGE_FILL),
                )
            if self._planet_norm is not None:
                in_range = (
                    self._range_min is not None
                    and self._range_max is not None
                    and self._range_min <= self._planet_norm <= self._range_max
                )
                tick_color = self._TICK_GOOD if in_range else self._TICK_BAD
                tx = bar_x + (self._planet_norm / 100.0) * bar_w
                p.fillRect(
                    QRectF(tx - self._TICK_W / 2, bar_y, self._TICK_W, self._H),
                    tick_color,
                )

        p.setPen(self._TEXT)
        p.drawText(
            QRectF(bar_x + bar_w + 4, 0, val_w, self.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            self._value_text,
        )


# ── Mineral bar ────────────────────────────────────────────────────────────


class _MineralBar(QWidget):
    """
    Horizontal mineral-amount bar.

    Shows a filled bar proportional to surface kT (scale 0–5000 kT).
    """

    _H = 12
    _MAX_KT = 5000

    _BG = QColor(0x20, 0x20, 0x20)
    _BORDER = QColor(0x60, 0x60, 0x60)
    _TEXT = QColor(0xDD, 0xDD, 0xDD)

    def __init__(self, label: str, fill_color: QColor, parent=None):
        super().__init__(parent)
        self._label = label
        self._fill = fill_color
        self._amount = 0
        self.setMinimumHeight(self._H + 18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_amount(self, kt: int):
        self._amount = max(0, kt)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        lbl_w = 70
        bar_w = max(40, self.width() - lbl_w - 4)
        bar_x = lbl_w
        bar_y = (self.height() - self._H) // 2

        p.setFont(QFont("Arial", 8))
        p.setPen(self._TEXT)
        p.drawText(
            QRectF(0, 0, lbl_w - 2, self.height()),
            Qt.AlignRight | Qt.AlignVCenter,
            self._label,
        )

        bar_rect = QRectF(bar_x, bar_y, bar_w, self._H)
        p.fillRect(bar_rect, self._BG)
        p.setPen(QPen(self._BORDER, 1))
        p.drawRect(bar_rect)

        if self._amount > 0:
            fill_w = min(bar_w - 2, (self._amount / self._MAX_KT) * bar_w)
            p.fillRect(QRectF(bar_x + 1, bar_y + 1, fill_w, self._H - 2), self._fill)


# ── Planet summary widget ──────────────────────────────────────────────────


class PlanetSummaryWidget(QWidget):
    """
    Bottom-right panel: coords bar + planet summary + hab/mineral bars.

    Call update_planet(planet, player) on planet selection.
    Call update_hover_coords(x, y) while hovering over empty space.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(120)

        # Coords bar
        self._coords_label = QLabel("Select a planet")
        self._coords_label.setStyleSheet(
            "color: #00ccee; background: black; padding: 2px 4px; font-family: monospace;"
        )

        # Goto / search field (stub)
        self._goto_line = QLineEdit()
        self._goto_line.setFixedHeight(18)
        self._goto_line.setStyleSheet("background: black; color: white; border: 1px solid #444;")

        # Planet name header
        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet("font-weight: bold; font-size: 11pt;")

        # Value + population row
        self._value_label = QLabel()
        self._pop_label = QLabel()
        val_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        val_row.addWidget(self._value_label)
        val_row.addStretch(1)
        val_row.addWidget(self._pop_label)

        # Report age
        self._report_label = QLabel()

        # Hab bars
        self._grav_bar = _HabBar("Gravity")
        self._temp_bar = _HabBar("Temperature")
        self._rad_bar = _HabBar("Radiation")

        # Mineral bars
        self._iron_bar = _MineralBar("Ironium", QColor(0x44, 0x88, 0xFF))
        self._bor_bar = _MineralBar("Boranium", QColor(0x44, 0xCC, 0x44))
        self._ger_bar = _MineralBar("Germanium", QColor(0xDD, 0xDD, 0x00))

        # Dark-background content area
        content = QWidget()
        content.setStyleSheet("background: black; color: #dddddd;")
        cl = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        cl.setContentsMargins(4, 4, 4, 2)
        cl.setSpacing(1)
        cl.addWidget(self._name_label)
        cl.addLayout(val_row)
        cl.addWidget(self._report_label)
        cl.addWidget(self._grav_bar)
        cl.addWidget(self._temp_bar)
        cl.addWidget(self._rad_bar)
        cl.addWidget(self._iron_bar)
        cl.addWidget(self._bor_bar)
        cl.addWidget(self._ger_bar)
        cl.addStretch(1)
        content.setLayout(cl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: black; border: none;")

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._coords_label)
        main.addWidget(self._goto_line)
        main.addWidget(scroll, 1)
        self.setLayout(main)

    # ── Public API ─────────────────────────────────────────────────────────

    def update_hover_coords(self, x: float, y: float):
        """Called while the mouse hovers over the space map (no planet selected)."""
        self._coords_label.setText(f"X: {int(x)}  Y: {int(y)}")

    def update_planet(self, planet, player=None):
        """Called when a planet is selected on the space map."""
        x = getattr(planet, "x", 0)
        y = getattr(planet, "y", 0)
        self._coords_label.setText(f"ID #{planet.id}  X: {int(x)}  Y: {int(y)}  {planet.name}")

        years_since = getattr(planet, "years_since", 0)
        self._name_label.setText(f"{planet.name} Summary")

        if years_since == NeverSeenPlanet:
            self._value_label.setText("Unknown")
            self._pop_label.setText("")
            self._report_label.setText("")
            for bar in (self._grav_bar, self._temp_bar, self._rad_bar):
                bar.set_data(None, None, None, False, True, "?")
            self._iron_bar.set_amount(0)
            self._bor_bar.set_amount(0)
            self._ger_bar.set_amount(0)
            return

        value = getattr(planet, "value", None)
        if value is not None:
            color = "#00cc00" if value >= 0 else "#cc0000"
            self._value_label.setText(f'<font color="{color}">Value: <b>{value}%</b></font>')
        else:
            self._value_label.setText("")

        pop = getattr(planet, "population", 0)
        self._pop_label.setText(f"Population: {pop:,}" if pop else "Uninhabited")

        if years_since == 0:
            self._report_label.setText("Report is current")
        elif years_since > 0:
            self._report_label.setText(
                f"<font color='red'>Report is {years_since} year(s) old</font>"
            )
        else:
            self._report_label.setText("")

        self._update_hab_bars(planet, player)
        self._update_mineral_bars(planet)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _update_hab_bars(self, planet, player):
        race = getattr(player, "race", None) if player else None

        # Gravity
        g_val = getattr(planet, "gravity", None)
        g_norm, g_text = None, "?"
        if g_val is not None:
            try:
                from ..rendering.space import normalize_gravity

                g_norm = normalize_gravity(g_val)
                g_text = f"{g_val:.2f}g"
            except Exception:
                pass
        g_immune = getattr(race, "gravity_immune", False) if race else False
        if g_immune:
            self._grav_bar.set_data(g_norm, None, None, True, False, g_text)
        elif race:
            try:
                from ..rendering.space import normalize_gravity

                self._grav_bar.set_data(
                    g_norm,
                    normalize_gravity(race.gravity_min),
                    normalize_gravity(race.gravity_max),
                    False,
                    False,
                    g_text,
                )
            except Exception:
                self._grav_bar.set_data(g_norm, None, None, False, g_norm is None, g_text)
        else:
            self._grav_bar.set_data(g_norm, None, None, False, g_norm is None, g_text)

        # Temperature
        t_val = getattr(planet, "temperature", None)
        t_norm, t_text = None, "?"
        if t_val is not None:
            try:
                from ..rendering.space import normalize_temperature

                t_norm = normalize_temperature(t_val)
                t_text = f"{t_val}°C"
            except Exception:
                pass
        t_immune = getattr(race, "temperature_immune", False) if race else False
        if t_immune:
            self._temp_bar.set_data(t_norm, None, None, True, False, t_text)
        elif race:
            try:
                from ..rendering.space import normalize_temperature

                self._temp_bar.set_data(
                    t_norm,
                    normalize_temperature(race.temperature_min),
                    normalize_temperature(race.temperature_max),
                    False,
                    False,
                    t_text,
                )
            except Exception:
                self._temp_bar.set_data(t_norm, None, None, False, t_norm is None, t_text)
        else:
            self._temp_bar.set_data(t_norm, None, None, False, t_norm is None, t_text)

        # Radiation
        r_val = getattr(planet, "radiation", None)
        r_norm = int(r_val) if r_val is not None else None
        r_text = f"{r_val} mR/yr" if r_val is not None else "?"
        r_immune = getattr(race, "radiation_immune", False) if race else False
        if r_immune:
            self._rad_bar.set_data(r_norm, None, None, True, False, r_text)
        elif race:
            self._rad_bar.set_data(
                r_norm,
                int(race.radiation_min),
                int(race.radiation_max),
                False,
                False,
                r_text,
            )
        else:
            self._rad_bar.set_data(r_norm, None, None, False, r_norm is None, r_text)

    def _update_mineral_bars(self, planet):
        self._iron_bar.set_amount(getattr(planet, "surface_ironium", 0) or 0)
        self._bor_bar.set_amount(getattr(planet, "surface_boranium", 0) or 0)
        self._ger_bar.set_amount(getattr(planet, "surface_germanium", 0) or 0)
