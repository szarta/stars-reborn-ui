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

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from ..rendering.enumerations import NeverSeenPlanet

# ── Hab panel ──────────────────────────────────────────────────────────────


class _HabPanel(QWidget):
    """
    Three stacked hab bars (Gravity / Temperature / Radiation).

    Each bar background spans the full universal axis range; the race's
    tolerance window is rendered as a saturated coloured band over the
    matching span (blue / red / green); the planet's actual value is shown
    as a diamond + crosshair marker on top of the bar.  The numeric value
    (e.g. ``1.00g``, ``0°C``, ``50mR``) is drawn just outside the right
    edge of the bar.  The axis name sits at the left.
    """

    KEYS = ("gravity", "temperature", "radiation")
    LABELS = ("Gravity", "Temperature", "Radiation")
    BAND_COLORS = (
        QColor(0x10, 0x20, 0xC0),  # gravity   — saturated blue
        QColor(0xB0, 0x10, 0x10),  # temp      — saturated red
        QColor(0x10, 0xA0, 0x10),  # radiation — saturated green
    )

    _BAR_H = 14
    _BAR_GAP = 0
    _LEFT_W = 78
    _RIGHT_W = 46
    _DIAMOND = 9

    _BG = QColor(0x00, 0x00, 0x00)
    _BORDER = QColor(0x60, 0x60, 0x60)
    _UNKNOWN_FILL = QColor(0x40, 0x40, 0x40)
    _LABEL = QColor(0x00, 0x00, 0x00)
    _VALUE = QColor(0x00, 0x00, 0x00)
    _DIAMOND_BORDER = QColor(0x00, 0x00, 0x00)
    _IMMUNE_TEXT = QColor(0xFF, 0xFF, 0xFF)

    bar_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = [
            {"norm": None, "min": None, "max": None, "immune": False, "unknown": True, "text": "?"}
            for _ in range(3)
        ]
        h = 3 * self._BAR_H + 2 * self._BAR_GAP + 2
        self.setMinimumHeight(h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_axis(
        self,
        i: int,
        planet_norm: int | None,
        range_min: int | None,
        range_max: int | None,
        immune: bool,
        unknown: bool,
        value_text: str,
    ):
        self._state[i] = {
            "norm": planet_norm,
            "min": range_min,
            "max": range_max,
            "immune": immune,
            "unknown": unknown,
            "text": value_text,
        }
        self.update()

    def _bar_y(self, i: int) -> int:
        return i * (self._BAR_H + self._BAR_GAP)

    def _chart_geometry(self):
        chart_x = self._LEFT_W
        chart_w = max(40, self.width() - chart_x - self._RIGHT_W)
        return chart_x, chart_w

    def _hit_test(self, x: float, y: float) -> int | None:
        chart_x, chart_w = self._chart_geometry()
        if x < chart_x or x > chart_x + chart_w:
            return None
        for i in range(3):
            y0 = self._bar_y(i)
            if y0 <= y <= y0 + self._BAR_H:
                return i
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            i = self._hit_test(event.position().x(), event.position().y())
            if i is not None:
                self.bar_clicked.emit(self.KEYS[i])
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        chart_x, chart_w = self._chart_geometry()

        p.setFont(QFont("Arial", 8))
        for i in range(3):
            st = self._state[i]
            y = self._bar_y(i)

            # Axis label at left
            p.setPen(self._LABEL)
            p.drawText(
                QRectF(0, y, self._LEFT_W - 4, self._BAR_H),
                Qt.AlignRight | Qt.AlignVCenter,
                self.LABELS[i],
            )

            # Bar background
            bar_rect = QRectF(chart_x, y, chart_w, self._BAR_H)
            p.fillRect(bar_rect, self._BG)
            p.setPen(QPen(self._BORDER, 1))
            p.drawRect(bar_rect)

            inner = bar_rect.adjusted(1, 1, -1, -1)

            if st["unknown"]:
                p.fillRect(inner, self._UNKNOWN_FILL)
            elif st["immune"]:
                p.fillRect(inner, self.BAND_COLORS[i])
                p.setPen(self._IMMUNE_TEXT)
                p.drawText(bar_rect, Qt.AlignCenter, "Immune")
            else:
                if st["min"] is not None and st["max"] is not None:
                    lo = max(0, min(100, int(st["min"])))
                    hi = max(0, min(100, int(st["max"])))
                    rx = chart_x + (chart_w - 1) * lo / 100.0
                    rw = max(1.0, (chart_w - 1) * (hi - lo) / 100.0)
                    p.fillRect(
                        QRectF(rx, y + 1, rw, self._BAR_H - 2),
                        QBrush(self.BAND_COLORS[i]),
                    )

            # Value text on right of bar
            p.setPen(self._VALUE)
            p.drawText(
                QRectF(chart_x + chart_w + 4, y, self._RIGHT_W - 4, self._BAR_H),
                Qt.AlignLeft | Qt.AlignVCenter,
                st["text"],
            )

        # Diamond + crosshair markers on top
        for i in range(3):
            st = self._state[i]
            if st["unknown"] or st["immune"] or st["norm"] is None:
                continue
            n = max(0, min(100, int(st["norm"])))
            cx = chart_x + (chart_w - 1) * n / 100.0
            cy = self._bar_y(i) + self._BAR_H / 2
            d = self._DIAMOND / 2

            p.setRenderHint(QPainter.Antialiasing, False)
            p.setPen(QPen(self._DIAMOND_BORDER, 1))
            p.drawLine(
                QPointF(cx - d - 2, cy),
                QPointF(cx + d + 2, cy),
            )
            p.drawLine(
                QPointF(cx, cy - d - 2),
                QPointF(cx, cy + d + 2),
            )

            p.setRenderHint(QPainter.Antialiasing, True)
            poly = QPolygonF(
                [
                    QPointF(cx, cy - d),
                    QPointF(cx + d, cy),
                    QPointF(cx, cy + d),
                    QPointF(cx - d, cy),
                ]
            )
            p.setBrush(QBrush(self.BAND_COLORS[i]))
            p.setPen(QPen(self._DIAMOND_BORDER, 1))
            p.drawPolygon(poly)
        p.setRenderHint(QPainter.Antialiasing, False)


# ── Mineral panel ──────────────────────────────────────────────────────────


class _MineralPanel(QWidget):
    """
    Three stacked mineral bars (Ironium / Boranium / Germanium) sharing a
    single horizontal kT axis spanning 0–20000 kT.

    Each bar shows surface kT as a filled bar from the left.  A coloured
    diamond marker on the same axis sits at concentration × 200 (0–100
    concentration → 0–20000 kT).  A single labelled ruler is painted once
    below the three bars with a tick every 1000 kT.
    """

    KEYS = ("ironium", "boranium", "germanium")
    LABELS = ("Ironium", "Boranium", "Germanium")
    FILLS = (
        QColor(0x44, 0x88, 0xFF),
        QColor(0x44, 0xCC, 0x44),
        QColor(0xDD, 0xDD, 0x00),
    )

    _MAX_KT = 20000
    _BAR_H = 12
    _BAR_GAP = 1
    _RULER_H = 16
    _LEFT_PAD = 78  # room for the mineral name label and the "kT" ruler tag
    _RIGHT_PAD = 46  # matches _HabPanel._RIGHT_W so bar right edges align
    _DIAMOND = 9

    _BG = QColor(0x00, 0x00, 0x00)
    _BORDER = QColor(0x60, 0x60, 0x60)
    _AXIS = QColor(0x00, 0x00, 0x00)
    _DIAMOND_BORDER = QColor(0x00, 0x00, 0x00)

    bar_clicked = Signal(str)  # "ironium" | "boranium" | "germanium"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._surface = [0, 0, 0]
        self._concentration: list[int | None] = [None, None, None]
        h = 3 * self._BAR_H + 2 * self._BAR_GAP + self._RULER_H + 2
        self.setMinimumHeight(h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(
        self,
        surface: tuple[int, int, int],
        concentration: tuple[int | None, int | None, int | None],
    ):
        self._surface = [int(s or 0) for s in surface]
        self._concentration = [None if c is None else int(c) for c in concentration]
        self.update()

    def _chart_geometry(self):
        chart_x = self._LEFT_PAD
        chart_w = max(40, self.width() - chart_x - self._RIGHT_PAD)
        return chart_x, chart_w

    def _bar_y(self, i: int) -> int:
        return i * (self._BAR_H + self._BAR_GAP)

    def _hit_test(self, x: float, y: float) -> int | None:
        chart_x, chart_w = self._chart_geometry()
        if x < chart_x or x > chart_x + chart_w:
            return None
        for i in range(3):
            y0 = self._bar_y(i)
            if y0 <= y <= y0 + self._BAR_H:
                return i
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            i = self._hit_test(event.position().x(), event.position().y())
            if i is not None:
                self.bar_clicked.emit(self.KEYS[i])
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        chart_x, chart_w = self._chart_geometry()

        p.setFont(QFont("Arial", 8))
        for i in range(3):
            y = self._bar_y(i)
            bar_rect = QRectF(chart_x, y, chart_w, self._BAR_H)
            p.fillRect(bar_rect, self._BG)
            p.setPen(QPen(self._BORDER, 1))
            p.drawRect(bar_rect)

            kt = max(0, min(self._MAX_KT, self._surface[i]))
            if kt > 0:
                fw = (chart_w - 2) * kt / self._MAX_KT
                p.fillRect(
                    QRectF(chart_x + 1, y + 1, fw, self._BAR_H - 2),
                    self.FILLS[i],
                )

            # Mineral name sits to the LEFT of the bar (in the panel
            # background), matching the original game's layout.
            p.setPen(self.FILLS[i])
            p.drawText(
                QRectF(0, y, chart_x - 4, self._BAR_H),
                Qt.AlignVCenter | Qt.AlignRight,
                self.LABELS[i],
            )

        p.setRenderHint(QPainter.Antialiasing, True)
        for i in range(3):
            c = self._concentration[i]
            if c is None:
                continue
            cx = chart_x + (chart_w - 1) * max(0, min(100, c)) / 100.0
            cy = self._bar_y(i) + self._BAR_H / 2
            d = self._DIAMOND / 2
            poly = QPolygonF(
                [
                    QPointF(cx, cy - d),
                    QPointF(cx + d, cy),
                    QPointF(cx, cy + d),
                    QPointF(cx - d, cy),
                ]
            )
            p.setBrush(QBrush(self.FILLS[i]))
            p.setPen(QPen(self._DIAMOND_BORDER, 1))
            p.drawPolygon(poly)
        p.setRenderHint(QPainter.Antialiasing, False)

        ruler_y = 3 * self._BAR_H + 2 * self._BAR_GAP + 1
        p.setPen(self._AXIS)
        p.drawText(
            QRectF(0, ruler_y, chart_x - 2, self._RULER_H),
            Qt.AlignRight | Qt.AlignTop,
            "kT",
        )
        for n in range(0, self._MAX_KT + 1, 1000):
            x = chart_x + (chart_w - 1) * n / self._MAX_KT
            p.drawLine(QPointF(x, ruler_y), QPointF(x, ruler_y + 3))
            p.drawText(
                QRectF(x - 30, ruler_y + 3, 60, self._RULER_H - 3),
                Qt.AlignTop | Qt.AlignHCenter,
                str(n),
            )


# ── Click-overlay popup framework ─────────────────────────────────────────


class _ClickPopup(QFrame):
    """
    Transient cream-coloured tooltip-style popup, dismissed by clicking
    elsewhere (Qt.Popup window flag).  Displays a single rich-text block.
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(1)
        self.setStyleSheet(
            "QFrame { background-color: #ffffcc; border: 1px solid black; }"
            "QLabel { background: transparent; padding: 0px; }"
        )
        self._label = QLabel(self)
        self._label.setTextFormat(Qt.RichText)
        lay = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(0)
        lay.addWidget(self._label)

    def show_html(self, html: str, pos):
        self._label.setText(html)
        self.adjustSize()
        self.move(pos)
        self.show()
        self.raise_()


class _ClickableLabel(QLabel):
    """QLabel that emits ``clicked`` on a left-mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


# ── Population helpers ────────────────────────────────────────────────────


def _population_factor(race) -> float:
    """Combined PRT/LRT multiplier on max-pop (PopulationFactor in design)."""
    if race is None:
        return 1.0
    factor = 1.0
    prt = (getattr(race, "prt", "") or "").upper()
    lrts = [s.upper() for s in (getattr(race, "lrts", []) or [])]
    if prt == "HE":
        factor *= 0.5
    elif prt == "JOAT":
        factor *= 1.2
    if "OBRM" in lrts:
        factor *= 1.1
    return factor


def _max_pop(value_pct: int | None, race) -> int:
    """``MaxPlanetPop × hab/100 × PopulationFactor`` (design/mechanics)."""
    if value_pct is None or value_pct <= 0:
        return 0
    v = max(5, int(value_pct))
    return int(1_000_000 * v / 100 * _population_factor(race))


def _capacity_factor(pop: int, max_pop: int) -> float:
    if max_pop <= 0:
        return 0.0
    cap = pop / max_pop
    if cap <= 0.25:
        return 1.0
    return (16.0 / 9.0) * (1.0 - cap) ** 2


def _annual_growth(pop: int, race, value_pct: int | None, max_pop: int) -> int:
    """
    Single-turn growth using the documented formula.  Returns 0 when the
    planet has zero/negative value (dying populations are handled
    separately and not surfaced through this helper).
    """
    if pop <= 0 or value_pct is None or value_pct <= 0 or max_pop <= 0:
        return 0
    rate = float(getattr(race, "growth_rate", 15) or 15) / 100.0
    if (getattr(race, "prt", "") or "").upper() == "HE":
        rate *= 2.0
    v = max(5, int(value_pct)) / 100.0
    return int(round(pop * rate * v * _capacity_factor(pop, max_pop)))


def _mining_rate(mines: int, mine_setting: int, concentration: int | None) -> int:
    """``mines × mine_setting × concentration / 1000`` (kT/year, floored).

    The ``mine_setting`` race stat is calibrated against 10 mines at
    concentration 100 (Stars! in-game help, *Mines* section), so the
    combined formula divides by 1000 rather than 100.
    """
    if concentration is None or mines <= 0 or mine_setting <= 0:
        return 0
    return int(mines * mine_setting * max(0, int(concentration)) // 1000)


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

        # Distance line — "<n> light years from <primary name>" when a
        # secondary target distinct from the primary is selected.
        self._distance_label = QLabel("")
        self._distance_label.setStyleSheet(
            "color: #00ccee; background: black; padding: 2px 4px; font-family: monospace;"
        )

        # Planet name header
        self._name_label = QLabel()
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet("font-weight: bold; font-size: 11pt;")

        # Value + population row.  The value text is indented to align with
        # the start of the hab/mineral bars below; the population label
        # remains right-aligned.
        self._value_label = QLabel()
        self._value_label.setContentsMargins(_HabPanel._LEFT_W, 0, 0, 0)
        self._pop_label = _ClickableLabel()
        self._pop_label.setCursor(Qt.PointingHandCursor)
        val_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        val_row.addWidget(self._value_label)
        val_row.addStretch(1)
        val_row.addWidget(self._pop_label)

        # Report age (aligned with the start of the hab/mineral bars).
        self._report_label = QLabel()
        self._report_label.setContentsMargins(_HabPanel._LEFT_W, 0, 0, 0)

        # Hab panel (3 stacked axis bars with saturated tolerance bands)
        self._hab_panel = _HabPanel()

        # Mineral panel (3 bars + shared 0–20000 kT ruler)
        self._mineral_panel = _MineralPanel()

        # Click-overlay popup + selection state
        self._popup = _ClickPopup(self)
        self._current_planet = None  # secondary target driving this pane
        self._current_player = None
        self._current_primary = None  # primary target — only used for the distance line

        self._hab_panel.bar_clicked.connect(self._show_hab_overlay)
        self._mineral_panel.bar_clicked.connect(self._show_mineral_overlay)
        self._pop_label.clicked.connect(self._show_population_overlay)

        # Content area uses the default window-color background to match the
        # original Stars! UI (light grey, like the rest of the app chrome).
        content = QWidget()
        cl = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        cl.setContentsMargins(4, 4, 4, 2)
        cl.setSpacing(1)
        cl.addWidget(self._name_label)
        cl.addLayout(val_row)
        cl.addWidget(self._report_label)
        cl.addWidget(self._hab_panel)
        cl.addWidget(self._mineral_panel)
        cl.addStretch(1)
        content.setLayout(cl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._coords_label)
        main.addWidget(self._distance_label)
        main.addWidget(scroll, 1)
        self.setLayout(main)

    # ── Public API ─────────────────────────────────────────────────────────

    def update_hover_coords(self, x: float, y: float):
        """Called while the mouse hovers over the space map (no planet selected)."""
        self._coords_label.setText(f"X: {int(x)}  Y: {int(y)}")

    def _refresh_distance_label(self):
        """Set the distance line to "<n> light years from <primary>" when
        a secondary target distinct from the primary is selected."""
        secondary = self._current_planet
        primary = self._current_primary
        if secondary is None or primary is None or primary is secondary:
            self._distance_label.setText("")
            return
        try:
            dx = float(getattr(secondary, "x", 0)) - float(getattr(primary, "x", 0))
            dy = float(getattr(secondary, "y", 0)) - float(getattr(primary, "y", 0))
        except (TypeError, ValueError):
            self._distance_label.setText("")
            return
        ly = (dx * dx + dy * dy) ** 0.5
        self._distance_label.setText(f"{ly:.2f} light years from {primary.name}")

    def set_primary_target(self, planet):
        """Track the primary target for the "X light years from Y" line."""
        self._current_primary = planet
        self._refresh_distance_label()

    def update_planet(self, planet, player=None):
        """Called when a planet is selected on the space map."""
        self._current_planet = planet
        self._current_player = player
        if self._popup.isVisible():
            self._popup.hide()

        x = getattr(planet, "x", 0)
        y = getattr(planet, "y", 0)
        self._coords_label.setText(f"ID #{planet.id}  X: {int(x)}  Y: {int(y)}  {planet.name}")
        self._refresh_distance_label()

        years_since = getattr(planet, "years_since", 0)
        self._name_label.setText(f"{planet.name} Summary")

        if years_since == NeverSeenPlanet:
            self._value_label.setText("Unknown")
            self._pop_label.setText("")
            self._report_label.setText("")
            for i in range(3):
                self._hab_panel.set_axis(i, None, None, None, False, True, "?")
            self._mineral_panel.set_data((0, 0, 0), (None, None, None))
            return

        value = getattr(planet, "value", None)
        if value is not None:
            color = "#298e12" if value >= 0 else "#cc0000"
            self._value_label.setText(f'Value: <font color="{color}"><b>{value}%</b></font>')
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

        from ..rendering.space import normalize_gravity, normalize_temperature

        # Gravity
        g_val = getattr(planet, "gravity", None)
        g_norm, g_text = None, "?"
        if g_val is not None:
            try:
                g_norm = normalize_gravity(g_val)
                g_text = f"{g_val:.2f}g"
            except Exception:
                pass
        g_immune = getattr(race, "gravity_immune", False) if race else False
        g_min = g_max = None
        if not g_immune and race:
            try:
                g_min = normalize_gravity(race.gravity_min)
                g_max = normalize_gravity(race.gravity_max)
            except Exception:
                pass
        self._hab_panel.set_axis(0, g_norm, g_min, g_max, g_immune, g_norm is None, g_text)

        # Temperature
        t_val = getattr(planet, "temperature", None)
        t_norm, t_text = None, "?"
        if t_val is not None:
            try:
                t_norm = normalize_temperature(t_val)
                t_text = f"{t_val}°C"
            except Exception:
                pass
        t_immune = getattr(race, "temperature_immune", False) if race else False
        t_min = t_max = None
        if not t_immune and race:
            try:
                t_min = normalize_temperature(race.temperature_min)
                t_max = normalize_temperature(race.temperature_max)
            except Exception:
                pass
        self._hab_panel.set_axis(1, t_norm, t_min, t_max, t_immune, t_norm is None, t_text)

        # Radiation (mR; native 0–100 scale, no normalization needed)
        r_val = getattr(planet, "radiation", None)
        r_norm = int(r_val) if r_val is not None else None
        r_text = f"{r_val}mR" if r_val is not None else "?"
        r_immune = getattr(race, "radiation_immune", False) if race else False
        r_min = r_max = None
        if not r_immune and race:
            try:
                r_min = int(race.radiation_min)
                r_max = int(race.radiation_max)
            except Exception:
                pass
        self._hab_panel.set_axis(2, r_norm, r_min, r_max, r_immune, r_norm is None, r_text)

    def _update_mineral_bars(self, planet):
        surface = (
            getattr(planet, "surface_ironium", 0) or 0,
            getattr(planet, "surface_boranium", 0) or 0,
            getattr(planet, "surface_germanium", 0) or 0,
        )
        concentration = (
            getattr(planet, "ironium_concentration", None),
            getattr(planet, "boranium_concentration", None),
            getattr(planet, "germanium_concentration", None),
        )
        self._mineral_panel.set_data(surface, concentration)

    # ── Click overlays ─────────────────────────────────────────────────────

    _HAB_TEXT_COLORS = {
        "gravity": "#1820c0",
        "temperature": "#b01010",
        "radiation": "#10a010",
    }

    _MINERAL_TEXT_COLORS = {
        "ironium": "#3478e0",
        "boranium": "#10a010",
        "germanium": "#b8b800",
    }

    @staticmethod
    def _format_gravity(g: float) -> str:
        return f"{g:.2f}g"

    @staticmethod
    def _format_temperature(t: int) -> str:
        return f"{int(t)}°C"

    @staticmethod
    def _format_radiation(r: int) -> str:
        return f"{int(r)}mR"

    _HAB_AXIS_LABELS = {
        "gravity": "Gravity",
        "temperature": "Temperature",
        "radiation": "Radiation",
    }

    def _hab_axis_formatter(self, axis: str):
        return {
            "gravity": self._format_gravity,
            "temperature": self._format_temperature,
            "radiation": self._format_radiation,
        }[axis]

    def _show_hab_overlay(self, axis: str):
        planet = self._current_planet
        if planet is None:
            return
        race = getattr(self._current_player, "race", None) if self._current_player else None
        color = self._HAB_TEXT_COLORS.get(axis, "#000000")
        label = self._HAB_AXIS_LABELS[axis]
        fmt = self._hab_axis_formatter(axis)

        cur_val = getattr(planet, axis, None)
        cur = fmt(cur_val) if cur_val is not None else "?"
        mn = getattr(race, f"{axis}_min", None) if race else None
        mx = getattr(race, f"{axis}_max", None) if race else None
        immune = bool(getattr(race, f"{axis}_immune", False)) if race else False
        rng = f"{fmt(mn)} and {fmt(mx)}" if (mn is not None and mx is not None) else None

        line1 = f"{label} currently is {cur}."
        if immune:
            body = f"{line1}<br>Your colonists are immune to {label.lower()}."
        elif rng is not None:
            body = (
                f"{line1}<br>Your colonists prefer planets where the<br>{label} is between {rng}."
            )
        else:
            body = line1

        html = f'<font color="{color}">{body}</font>'
        self._popup.show_html(html, QCursor.pos())

    def _show_mineral_overlay(self, mineral: str):
        planet = self._current_planet
        if planet is None:
            return
        race = getattr(self._current_player, "race", None) if self._current_player else None

        label = mineral.capitalize()
        color = self._MINERAL_TEXT_COLORS.get(mineral, "#000000")

        surface = getattr(planet, f"surface_{mineral}", 0) or 0
        concentration = getattr(planet, f"{mineral}_concentration", None)
        homeworld = bool(getattr(planet, "homeworld", False))
        mines = int(getattr(planet, "mines", 0) or 0)
        mine_setting = int(getattr(race, "mine_production", 10) if race else 10)

        rate = _mining_rate(mines, mine_setting, concentration)

        conc_text = (
            f"{int(concentration)}{' (HW)' if homeworld else ''}"
            if concentration is not None
            else "?"
        )
        body = (
            f"<b>{label}</b><br>"
            f"On Surface: {int(surface)}kT<br>"
            f"Mineral Concentration: {conc_text}<br>"
            f"Mining Rate: {rate}kT/yr"
        )
        html = f'<font color="{color}">{body}</font>'
        self._popup.show_html(html, QCursor.pos())

    def _show_population_overlay(self):
        planet = self._current_planet
        if planet is None:
            return
        race = getattr(self._current_player, "race", None) if self._current_player else None

        name = getattr(planet, "name", "this planet")
        pop = int(getattr(planet, "population", 0) or 0)
        if pop <= 0:
            # Uninhabited planets do not show the population popup in the
            # original — bail out silently.
            return

        value = getattr(planet, "value", None)
        cap = _max_pop(value, race)
        growth = _annual_growth(pop, race, value, cap)

        # The original game shows a (min, max) range.  The exact min/max
        # formula has not yet been confirmed via oracle; until it is, show
        # the documented annual-growth value for both bounds so the popup
        # matches the wording of the screencap.  Tracked as research.
        body = (
            f"Your population on {name} is {pop:,}.<br>"
            f"{name} will support a population of up to {cap:,} of your colonists.<br>"
            f"Your population on {name} will grow by {growth:,} to {growth:,} next year."
        )
        html = f'<font color="#cc7a00">{body}</font>'
        self._popup.show_html(html, QCursor.pos())
