"""
ui/space_map.py

QPainter-based space map widget — replaces the old SVG/QWebView implementation.

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

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
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
_COLOR_SELECTED = QColor(0xFF, 0xFF, 0x00)  # yellow selection ring
_COLOR_BG = QColor(0x00, 0x00, 0x00)
_COLOR_TEXT = QColor(0xFF, 0xFF, 0xFF)

_MIN_SCALE = 0.05
_MAX_SCALE = 12.0
_ZOOM_FACTOR = 1.15  # per scroll-wheel tick

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
    """QPainter-based interactive star map."""

    planet_selected = Signal(int)  # emits planet id on left-click
    planet_activated = Signal(int)  # emits planet id on double-click (open detail dialog)
    hover_world = Signal(int, int)  # emits (world_x, world_y) on mouse move

    def __init__(self, parent=None):
        super().__init__(parent)
        self._planets: list = []
        self._player_id: int | None = None
        self._universe_w: float = 400.0
        self._universe_h: float = 400.0
        self._scale: float = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._initialized = False

        self._selected_id: int | None = None
        self._show_names: bool = True
        self._view_mode: int = 0  # 0 = Normal (PlanetView.Normal)

        self._dragging = False
        self._drag_start = QPoint()
        self._drag_offset = QPointF()

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(300, 200)

    # ── data API ───────────────────────────────────────────────────────────

    def set_universe(
        self,
        planets,
        universe_w: float,
        universe_h: float,
        player_id: int | None = None,
    ):
        """Load a new universe.  Resets pan/zoom to fit-to-view."""
        self._planets = list(planets)
        self._universe_w = max(1.0, float(universe_w))
        self._universe_h = max(1.0, float(universe_h))
        self._player_id = player_id
        self._selected_id = None
        self._initialized = False  # trigger fit on next resize / paintEvent
        self._fit_to_view()
        self.update()

    def set_show_names(self, enabled: bool):
        self._show_names = enabled
        self.update()

    def set_view_mode(self, mode: int):
        self._view_mode = mode
        self.update()

    def set_zoom(self, multiplier: float):
        """Jump to a zoom level expressed as a fraction of the fit-to-view scale."""
        cx, cy = self.width() / 2.0, self.height() / 2.0
        new_scale = max(_MIN_SCALE, min(_MAX_SCALE, self._fit_scale() * multiplier))
        self._zoom_to(new_scale, cx, cy)

    def select_planet(self, pid: int):
        self._selected_id = pid
        self.update()

    def center_on_planet(self, pid: int):
        planet = next((p for p in self._planets if p.id == pid), None)
        if planet is None:
            return
        px, py = _planet_pos(planet)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        self._offset = QPointF(cx - px * self._scale, cy - py * self._scale)
        self.update()

    # ── coordinate transforms ──────────────────────────────────────────────

    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (
            self._offset.x() + wx * self._scale,
            self._offset.y() + wy * self._scale,
        )

    def _screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (
            (sx - self._offset.x()) / self._scale,
            (sy - self._offset.y()) / self._scale,
        )

    # ── fit / zoom ─────────────────────────────────────────────────────────

    def _fit_scale(self) -> float:
        w, h = max(1, self.width()), max(1, self.height())
        return min(w / self._universe_w, h / self._universe_h) * 0.90

    def _fit_to_view(self):
        w, h = max(1, self.width()), max(1, self.height())
        self._scale = self._fit_scale()
        self._offset = QPointF(
            (w - self._universe_w * self._scale) / 2.0,
            (h - self._universe_h * self._scale) / 2.0,
        )
        self._initialized = True

    def _zoom_to(self, new_scale: float, cx: float, cy: float):
        wx, wy = self._screen_to_world(cx, cy)
        self._scale = max(_MIN_SCALE, min(_MAX_SCALE, new_scale))
        self._offset = QPointF(cx - wx * self._scale, cy - wy * self._scale)
        self.update()

    # ── hit testing ────────────────────────────────────────────────────────

    def _planet_at(self, sx: float, sy: float) -> int | None:
        best_id = None
        best_dist = float(_CLICK_RADIUS)
        for planet in self._planets:
            px, py = _planet_pos(planet)
            ex, ey = self._world_to_screen(px, py)
            d = math.hypot(sx - ex, sy - ey)
            if d < best_dist:
                best_dist = d
                best_id = planet.id
        return best_id

    # ── events ─────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        if not self._initialized:
            self._fit_to_view()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = _ZOOM_FACTOR if delta > 0 else 1.0 / _ZOOM_FACTOR
        pos = event.position()
        self._zoom_to(self._scale * factor, pos.x(), pos.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = event.pos()
            self._drag_offset = QPointF(self._offset)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self._dragging:
            delta = pos - self._drag_start
            self._offset = self._drag_offset + QPointF(delta.x(), delta.y())
            self.update()
        else:
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
            dist = (event.pos() - self._drag_start).manhattanLength()
            self._dragging = False
            if dist < 4:
                pid = self._planet_at(event.pos().x(), event.pos().y())
                if pid is not None:
                    self._selected_id = pid
                    self.planet_selected.emit(pid)
                    self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            pid = self._planet_at(event.pos().x(), event.pos().y())
            if pid is not None:
                self._selected_id = pid
                self.planet_activated.emit(pid)
                self.update()

    def keyPressEvent(self, event):
        step = max(20.0, self._universe_w * 0.05)
        key = event.key()
        if key == Qt.Key_Left:
            self._offset += QPointF(step, 0)
        elif key == Qt.Key_Right:
            self._offset += QPointF(-step, 0)
        elif key == Qt.Key_Up:
            self._offset += QPointF(0, step)
        elif key == Qt.Key_Down:
            self._offset += QPointF(0, -step)
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._zoom_to(self._scale * _ZOOM_FACTOR, self.width() / 2, self.height() / 2)
            return
        elif key in (Qt.Key_Minus, Qt.Key_Underscore):
            self._zoom_to(self._scale / _ZOOM_FACTOR, self.width() / 2, self.height() / 2)
            return
        elif key == Qt.Key_Home:
            self._fit_to_view()
        else:
            super().keyPressEvent(event)
            return
        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, event):
        if not self._initialized:
            self._fit_to_view()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), _COLOR_BG)

        if not self._planets:
            return

        painter.setFont(QFont("Arial", 9))
        for planet in self._planets:
            self._draw_planet(painter, planet)

    def _draw_planet(self, painter: QPainter, planet):
        px, py = _planet_pos(planet)
        sx, sy = self._world_to_screen(px, py)

        # Cull off-screen planets
        margin = 20.0
        if (
            sx < -margin
            or sx > self.width() + margin
            or sy < -margin
            or sy > self.height() + margin
        ):
            return

        owner = _planet_owner(planet)
        known = _planet_known(planet)
        value = _planet_value(planet)
        is_mine = (owner is not None) and (owner == self._player_id)
        is_selected = planet.id == self._selected_id
        no_info = self._view_mode == 5  # PlanetView.NoInfo

        # Choose color and radius
        if no_info or not known:
            color = _COLOR_UNKNOWN
            radius = float(_PLANET_RADIUS_MIN)
        elif owner is None:
            color = _COLOR_NEUTRAL
            radius = float(_PLANET_RADIUS_MIN)
        elif is_mine:
            bonus = min(_PLANET_RADIUS_BONUS_MAX, max(0, value // 34))
            color = _COLOR_OWNED
            radius = float(_PLANET_RADIUS_OWNED + bonus)
        else:
            color = _COLOR_ENEMY
            radius = float(_PLANET_RADIUS_OWNED)

        center = QPointF(sx, sy)

        # Selection ring
        if is_selected:
            painter.setPen(QPen(_COLOR_SELECTED, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, radius + 4.0, radius + 4.0)

        # Planet dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(center, radius, radius)

        # Name label (only when zoomed in enough)
        if self._show_names and self._scale > 0.35:
            painter.setPen(_COLOR_TEXT)
            painter.drawText(
                QRectF(sx - 40.0, sy + radius + 2.0, 80.0, 14.0),
                Qt.AlignHCenter | Qt.AlignTop,
                planet.name,
            )
