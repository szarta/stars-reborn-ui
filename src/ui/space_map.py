"""
ui/space_map.py

QPainter-based space map widget — replaces the old SVG/QWebView implementation.

Coordinate model
----------------
The map uses an absolute pixel-per-light-year scale that matches the original
Stars! game: at 100% zoom one ly = one pixel. World (0, 0) is anchored to
widget (0, 0); the widget grows with the universe and is intended to live
inside a QScrollArea, which provides panning via scrollbars.

Accepts any planet-like objects that expose:
  - .id   (int)
  - .name (str)
  - .x, .y  OR  .location() method  OR  .location tuple/list
  - .owner       (int | None, optional)
  - .value       (int 0-100, optional)
  - .years_since (int, -1 = never seen, optional)
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

# ── rendering constants ────────────────────────────────────────────────────

_PLANET_RADIUS_MIN = 3
_PLANET_RADIUS_OWNED = 4
_PLANET_RADIUS_BONUS_MAX = 2  # extra radius for high-value owned planets
_CLICK_RADIUS = 8  # px hit-test radius

_COLOR_OWNED = QColor(0x05, 0xFF, 0x00)  # Stars! green
_COLOR_ENEMY = QColor(0xFF, 0x40, 0x40)  # red
_COLOR_NEUTRAL = QColor(0xC0, 0xC0, 0xC0)  # light grey — colonisable but unowned
_COLOR_UNKNOWN = QColor(0x60, 0x60, 0x60)  # dark grey — never seen
_COLOR_TARGET = QColor(0xFF, 0xFF, 0x00)  # primary/secondary target arrow
_COLOR_BG = QColor(0x00, 0x00, 0x00)
_COLOR_TEXT = QColor(0xFF, 0xFF, 0xFF)

# Arrow marker geometry — primary is the larger arrow, secondary smaller.
_TARGET_PRIMARY_HEIGHT = 9.0
_TARGET_PRIMARY_HALF_WIDTH = 7.0
_TARGET_SECONDARY_HEIGHT = 6.0
_TARGET_SECONDARY_HALF_WIDTH = 5.0
_TARGET_GAP = 2.0  # px between planet edge and arrow tip

_MIN_SCALE = 0.05
_MAX_SCALE = 12.0

# 50 px of empty padding past the universe edge so dots / labels at the
# right/bottom edge aren't clipped (matches the JS reference renderer).
_EDGE_PAD = 50

# never-seen sentinel from enumerations.NeverSeenPlanet
_NEVER_SEEN = -1


# ── helpers ────────────────────────────────────────────────────────────────


def _planet_pos(planet) -> tuple[float, float]:
    """Return (x, y) world coords regardless of planet source (Python or Rust)."""
    loc = getattr(planet, "location", None)
    if callable(loc):
        return loc()
    if isinstance(loc, (tuple, list)):
        return float(loc[0]), float(loc[1])
    return float(planet.x), float(planet.y)


def _planet_known(planet) -> bool:
    """True if the player has ever seen this planet."""
    return getattr(planet, "years_since", 0) != _NEVER_SEEN


def _planet_owner(planet) -> int | None:
    return getattr(planet, "owner", None)


def _planet_value(planet) -> int:
    return getattr(planet, "value", 0)


# ── widget ─────────────────────────────────────────────────────────────────


class SpaceMap(QWidget):
    """QPainter-based interactive star map (absolute scale; scrollable host)."""

    planet_selected = Signal(int)  # emits planet id on left-click
    hover_world = Signal(int, int)  # emits (world_x, world_y) on mouse move
    zoom_step = Signal(int)  # +1 = zoom in one preset, -1 = zoom out

    def __init__(self, parent=None):
        super().__init__(parent)
        self._planets: list = []
        self._player_id: int | None = None
        self._universe_w: float = 400.0
        self._universe_h: float = 400.0
        self._scale: float = 1.0  # absolute px per ly

        # Two-slot target model (matches Stars! UI):
        #   primary   → drives left pane, marked with the larger arrow.
        #   secondary → drives bottom-right pane, marked with the smaller arrow.
        # When primary == secondary only the primary arrow is drawn.
        self._primary_id: int | None = None
        self._secondary_id: int | None = None
        self._show_names: bool = True
        self._view_mode: int = 0  # 0 = Normal (PlanetView.Normal)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._apply_size()

    # ── data API ───────────────────────────────────────────────────────────

    def set_universe(
        self,
        planets,
        universe_w: float,
        universe_h: float,
        player_id: int | None = None,
    ):
        """Load a new universe.  Keeps the current zoom scale."""
        self._planets = list(planets)
        self._universe_w = max(1.0, float(universe_w))
        self._universe_h = max(1.0, float(universe_h))
        self._player_id = player_id
        self._primary_id = None
        self._secondary_id = None
        self._apply_size()
        self.update()

    def set_show_names(self, enabled: bool):
        self._show_names = enabled
        self.update()

    def set_view_mode(self, mode: int):
        self._view_mode = mode
        self.update()

    def set_zoom(self, multiplier: float):
        """Set absolute scale in pixels per light-year (e.g., 1.25 ⇒ 125%)."""
        new_scale = max(_MIN_SCALE, min(_MAX_SCALE, float(multiplier)))
        if new_scale == self._scale:
            return
        self._scale = new_scale
        self._apply_size()
        self.update()

    @property
    def scale(self) -> float:
        return self._scale

    def set_primary_target(self, pid: int | None):
        if self._primary_id == pid:
            return
        self._primary_id = pid
        self.update()

    def set_secondary_target(self, pid: int | None):
        if self._secondary_id == pid:
            return
        self._secondary_id = pid
        self.update()

    def planet_screen_pos(self, pid: int) -> tuple[float, float] | None:
        """Widget-coord (x, y) for a planet id, or None if unknown."""
        planet = next((p for p in self._planets if p.id == pid), None)
        if planet is None:
            return None
        wx, wy = _planet_pos(planet)
        return wx * self._scale, wy * self._scale

    # ── coordinate transforms ──────────────────────────────────────────────

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return wx * self._scale, wy * self._scale

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return sx / self._scale, sy / self._scale

    # ── sizing ─────────────────────────────────────────────────────────────

    def _apply_size(self):
        w = int(math.ceil(self._universe_w * self._scale)) + _EDGE_PAD
        h = int(math.ceil(self._universe_h * self._scale)) + _EDGE_PAD
        self.setFixedSize(w, h)

    def sizeHint(self) -> QSize:
        return self.size()

    # ── hit testing ────────────────────────────────────────────────────────

    def _planet_at(self, sx: float, sy: float) -> int | None:
        best_id = None
        best_dist = float(_CLICK_RADIUS)
        for planet in self._planets:
            wx, wy = _planet_pos(planet)
            ex, ey = self._world_to_screen(wx, wy)
            d = math.hypot(sx - ex, sy - ey)
            if d < best_dist:
                best_dist = d
                best_id = planet.id
        return best_id

    # ── events ─────────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        # Plain wheel = scroll (handled by the enclosing QScrollArea).
        # Ctrl + wheel = zoom step.
        if not (event.modifiers() & Qt.ControlModifier):
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom_step.emit(1 if delta > 0 else -1)
        event.accept()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        wx, wy = self._screen_to_world(pos.x(), pos.y())
        self.hover_world.emit(int(wx), int(wy))
        pid = self._planet_at(pos.x(), pos.y())
        if pid is not None:
            planet = next((p for p in self._planets if p.id == pid), None)
            if planet:
                QToolTip.showText(event.globalPosition().toPoint(), planet.name, self)
                return
        QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            pid = self._planet_at(event.pos().x(), event.pos().y())
            if pid is not None:
                self.planet_selected.emit(pid)

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), _COLOR_BG)

        if not self._planets:
            return

        # Visible band — scroll area exposes only a viewport rect; cull the rest.
        visible = event.rect()
        margin = 20.0
        vx0, vy0 = visible.left() - margin, visible.top() - margin
        vx1, vy1 = visible.right() + margin, visible.bottom() + margin

        painter.setFont(QFont("Arial", 9))
        for planet in self._planets:
            wx, wy = _planet_pos(planet)
            sx, sy = wx * self._scale, wy * self._scale
            if sx < vx0 or sx > vx1 or sy < vy0 or sy > vy1:
                continue
            self._draw_planet(painter, planet, sx, sy)

        # Target arrows draw on top of all planet glyphs so they remain
        # visible when targets sit close together at low zoom levels.
        self._draw_target_arrows(painter)

    def _planet_color_radius(self, planet) -> tuple[QColor, float]:
        owner = _planet_owner(planet)
        known = _planet_known(planet)
        value = _planet_value(planet)
        is_mine = (owner is not None) and (owner == self._player_id)
        no_info = self._view_mode == 5  # PlanetView.NoInfo

        if no_info or not known:
            return _COLOR_UNKNOWN, float(_PLANET_RADIUS_MIN)
        if owner is None:
            return _COLOR_NEUTRAL, float(_PLANET_RADIUS_MIN)
        if is_mine:
            bonus = min(_PLANET_RADIUS_BONUS_MAX, max(0, value // 34))
            return _COLOR_OWNED, float(_PLANET_RADIUS_OWNED + bonus)
        return _COLOR_ENEMY, float(_PLANET_RADIUS_OWNED)

    def _draw_planet(self, painter: QPainter, planet, sx: float, sy: float):
        color, radius = self._planet_color_radius(planet)
        center = QPointF(sx, sy)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(center, radius, radius)

        # Names only when zoomed in to 75% or higher (matches the original game).
        if self._show_names and self._scale >= 0.75:
            painter.setPen(_COLOR_TEXT)
            painter.drawText(
                QRectF(sx - 40.0, sy + radius + 2.0, 80.0, 14.0),
                Qt.AlignHCenter | Qt.AlignTop,
                planet.name,
            )

    def _draw_target_arrows(self, painter: QPainter):
        # Secondary first so primary draws on top when both ids match the
        # same planet (paranoia — we also skip the secondary draw in that
        # case, but if both differ we still want the bigger arrow on top).
        if self._secondary_id is not None and self._secondary_id != self._primary_id:
            self._draw_target_arrow_for(painter, self._secondary_id, primary=False)
        if self._primary_id is not None:
            self._draw_target_arrow_for(painter, self._primary_id, primary=True)

    def _draw_target_arrow_for(self, painter: QPainter, pid: int, primary: bool):
        planet = next((p for p in self._planets if p.id == pid), None)
        if planet is None:
            return
        wx, wy = _planet_pos(planet)
        sx, sy = wx * self._scale, wy * self._scale
        _, radius = self._planet_color_radius(planet)

        if primary:
            h, w = _TARGET_PRIMARY_HEIGHT, _TARGET_PRIMARY_HALF_WIDTH
        else:
            h, w = _TARGET_SECONDARY_HEIGHT, _TARGET_SECONDARY_HALF_WIDTH

        # Upward-pointing chevron sitting just below the planet glyph,
        # tip aimed at the planet so it reads as a target indicator.
        tip_y = sy + radius + _TARGET_GAP
        poly = QPolygonF(
            [
                QPointF(sx - w, tip_y + h),
                QPointF(sx + w, tip_y + h),
                QPointF(sx, tip_y),
            ]
        )
        painter.setPen(QPen(_COLOR_TARGET, 1.0))
        painter.setBrush(QBrush(_COLOR_TARGET))
        painter.drawPolygon(poly)
