"""
ui/main_window.py

QMainWindow for the main game screen.
Contains: menu bar, toolbar, central space map, right-dock info panel, status bar.

Ported from src/ui/turn/editor.py (PySide → PySide6, SVG map → QPainter).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QDockWidget,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QWidget,
)

from ..rendering.enumerations import PlanetView, ResourcePaths, ZoomLevel
from .info_panel import InfoPanel
from .space_map import SpaceMap

_TOOLBAR_ICON_SIZE = QSize(24, 24)


# ── view-options container ──────────────────────────────────────────────────


class _ViewOptions:
    def __init__(self):
        self.zoom_level: int = ZoomLevel.Default
        self.planet_view: int = PlanetView.Default
        self.planet_names_overlay: bool = True

    def zoom_multiplier(self) -> float:
        return ZoomLevel.multipliers()[self.zoom_level]


# ── main window ─────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """
    Primary game window.

    Parameters
    ----------
    planets:
        Iterable of planet objects (duck-typed; populated from engine HTTP API response).
    universe_w, universe_h:
        Universe dimensions in light-years.
    player_id:
        Active player's id, used to color own planets green.
    game_year:
        Starting year shown in the status bar.
    game_name:
        Title bar suffix.
    player:
        Full player object (optional, passed to InfoPanel for race-aware display).
    """

    def __init__(
        self,
        planets=(),
        universe_w: float = 400.0,
        universe_h: float = 400.0,
        player_id: int | None = None,
        game_year: int = 2400,
        game_name: str = "New Game",
        player=None,
    ):
        super().__init__()
        self._planets = list(planets)
        self._universe_w = universe_w
        self._universe_h = universe_h
        self._player_id = player_id
        self._game_year = game_year
        self._game_name = game_name
        self._player = player
        self._view_opts = _ViewOptions()
        self._selected_planet = None

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_status_bar()
        self._load_universe()

    # ── setup ───────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle(f"Stars Reborn — {self._game_name}")
        self.setGeometry(100, 100, 1280, 800)

        # Central space map
        self._space_map = SpaceMap()
        self._space_map.planet_selected.connect(self._on_planet_selected)
        self._space_map.planet_activated.connect(self._on_planet_activated)
        self._space_map.hover_world.connect(self._on_hover_world)
        self.setCentralWidget(self._space_map)

        # Right dock — info panel
        self._info_panel = InfoPanel()
        dock = QDockWidget("Planet Info", self)
        dock.setWidget(self._info_panel)
        dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._info_dock = dock

    def _load_universe(self):
        self._space_map.set_universe(
            self._planets,
            self._universe_w,
            self._universe_h,
            self._player_id,
        )
        self._space_map.set_show_names(self._view_opts.planet_names_overlay)

    # ── menu bar ────────────────────────────────────────────────────────────

    def _init_menu(self):
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        file_menu.addAction(self._action("&New...", "Ctrl+N", self._handle_new))
        file_menu.addAction(self._action("&Open...", "Ctrl+O", self._handle_open))
        file_menu.addAction(self._action("&Save", "Ctrl+S", self._handle_save))
        file_menu.addSeparator()
        file_menu.addAction(self._action("&Close", None, self._handle_close))
        file_menu.addAction(self._action("E&xit", None, self.close))

        # View
        view_menu = mb.addMenu("&View")
        self._toolbar_action = self._action(
            "&Toolbar", None, self._handle_toggle_toolbar, checkable=True
        )
        self._toolbar_action.setChecked(True)
        view_menu.addAction(self._toolbar_action)
        view_menu.addSeparator()
        view_menu.addAction(self._action("&Find...", "Ctrl+F", self._handle_find))

        zoom_menu = view_menu.addMenu("&Zoom")
        zoom_group = QActionGroup(self)
        self._zoom_actions = []
        for i, name in enumerate(ZoomLevel.names()):
            a = self._action(
                name, None, lambda checked, idx=i: self._handle_zoom(idx), checkable=True
            )
            zoom_group.addAction(a)
            zoom_menu.addAction(a)
            self._zoom_actions.append(a)
        self._zoom_actions[self._view_opts.zoom_level].setChecked(True)

        view_menu.addSeparator()
        view_menu.addAction(self._action("&Race...", "F8", self._handle_race))
        view_menu.addAction(self._action("&Game Parameters...", None, self._handle_game_params))

        # Turn
        turn_menu = mb.addMenu("&Turn")
        turn_menu.addAction(self._action("&Generate", "F9", self._handle_generate))

        # Commands
        cmd_menu = mb.addMenu("&Commands")
        cmd_menu.addAction(self._action("&Ship Design...", "F4", self._handle_ship_design))
        cmd_menu.addAction(self._action("&Research...", "F5", self._handle_research))
        cmd_menu.addAction(self._action("&Battle Plans...", "F6", self._handle_battle_plans))

        # Report
        rep_menu = mb.addMenu("&Report")
        rep_menu.addAction(self._action("&Planets...", None, self._handle_planets_report))
        rep_menu.addAction(self._action("&Fleets...", None, self._handle_fleets_report))
        rep_menu.addSeparator()
        rep_menu.addAction(self._action("&Score...", "F10", self._handle_score))

        # Help
        help_menu = mb.addMenu("&Help")
        help_menu.addAction(self._action("Technology &Browser...", "F2", self._handle_tech_browser))
        help_menu.addSeparator()
        help_menu.addAction(self._action("&About...", None, self._handle_about))

    def _action(self, text, shortcut, slot, checkable=False) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        if checkable:
            a.setCheckable(True)
        return a

    # ── toolbar ─────────────────────────────────────────────────────────────

    def _init_toolbar(self):
        tb = QToolBar("Main Toolbar", self)
        tb.setIconSize(_TOOLBAR_ICON_SIZE)
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self._main_toolbar = tb

        view_buttons = []
        view_group = QButtonGroup(self)
        view_specs = [
            (
                "normal_view",
                ResourcePaths.NormalViewIcon,
                "Normal View",
                lambda: self._handle_view_mode(PlanetView.Normal),
            ),
            (
                "surface_minerals",
                ResourcePaths.SurfaceMineralsIcon,
                "Surface Mineral View",
                lambda: self._handle_view_mode(PlanetView.SurfaceMinerals),
            ),
            (
                "mineral_conc",
                ResourcePaths.MineralConcentrationsIcon,
                "Mineral Concentration View",
                lambda: self._handle_view_mode(PlanetView.MineralConcentration),
            ),
            (
                "value_view",
                ResourcePaths.PercentIcon,
                "Planet Value View",
                lambda: self._handle_view_mode(PlanetView.PercentPopulation),
            ),
            (
                "pop_view",
                ResourcePaths.PopulationIcon,
                "Population View",
                lambda: self._handle_view_mode(PlanetView.PopulationView),
            ),
            (
                "no_info",
                ResourcePaths.NoPlayerInfoIcon,
                "No Player Info View",
                lambda: self._handle_view_mode(PlanetView.NoInfo),
            ),
        ]
        for _name, icon_path, tip, handler in view_specs:
            btn = self._toolbar_btn(icon_path, tip, checkable=True)
            btn.clicked.connect(handler)
            tb.addWidget(btn)
            view_group.addButton(btn)
            view_buttons.append(btn)
        view_buttons[self._view_opts.planet_view].setChecked(True)
        self._view_buttons = view_buttons

        tb.addSeparator()

        self._waypoints_btn = self._toolbar_btn(ResourcePaths.AddWaypointIcon, "Add Waypoints Mode")
        self._waypoints_btn.clicked.connect(self._handle_add_waypoints)
        tb.addWidget(self._waypoints_btn)
        tb.addSeparator()

        self._routes_btn = self._toolbar_btn(
            ResourcePaths.ShowRoutesIcon, "Fleet Paths Overlay", checkable=True
        )
        self._routes_btn.clicked.connect(self._handle_fleet_paths)
        tb.addWidget(self._routes_btn)
        tb.addSeparator()

        self._names_btn = self._toolbar_btn(
            ResourcePaths.PlanetNamesIcon, "Toggle Planet Names", checkable=True
        )
        self._names_btn.setChecked(self._view_opts.planet_names_overlay)
        self._names_btn.clicked.connect(self._handle_names_toggle)
        tb.addWidget(self._names_btn)

        self._idle_fleets_btn = self._toolbar_btn(
            ResourcePaths.IdleFleetsIcon, "Idle Fleets Filter"
        )
        self._idle_fleets_btn.clicked.connect(self._handle_idle_fleets)
        tb.addWidget(self._idle_fleets_btn)

        tb.addSeparator()

        # Zoom in / out
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(24, 24)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(self._handle_zoom_in)
        tb.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(24, 24)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(self._handle_zoom_out)
        tb.addWidget(zoom_out_btn)

        zoom_fit_btn = QPushButton("⊡")
        zoom_fit_btn.setFixedSize(24, 24)
        zoom_fit_btn.setToolTip("Fit to View (Home)")
        zoom_fit_btn.clicked.connect(self._handle_zoom_fit)
        tb.addWidget(zoom_fit_btn)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Year display + Next Turn
        self._year_label = QLabel(f"Year {self._game_year}")
        self._year_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._year_label.setStyleSheet("font-weight: bold; padding: 0 8px;")
        tb.addWidget(self._year_label)

        self._next_turn_btn = QPushButton("Next Turn")
        self._next_turn_btn.setShortcut(QKeySequence("Space"))
        self._next_turn_btn.setToolTip("Generate next turn (Space)")
        self._next_turn_btn.clicked.connect(self._handle_generate)
        tb.addWidget(self._next_turn_btn)

    def _toolbar_btn(self, icon_path: str, tooltip: str, checkable: bool = False) -> QPushButton:
        btn = QPushButton()
        icon = QIcon(icon_path)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(_TOOLBAR_ICON_SIZE)
        else:
            btn.setText(tooltip[:3])
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.setFlat(True)
        if checkable:
            btn.setCheckable(True)
        return btn

    # ── status bar ───────────────────────────────────────────────────────────

    def _init_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._coords_label = QLabel("X: —  Y: —")
        self._coords_label.setFrameStyle(1)  # QFrame.Panel
        self._coords_label.setMinimumWidth(120)

        self._planet_label = QLabel("")
        self._planet_label.setFrameStyle(1)
        self._planet_label.setMinimumWidth(150)

        self._year_status_label = QLabel(f"Year {self._game_year}")
        self._year_status_label.setFrameStyle(1)

        sb.addWidget(self._coords_label)
        sb.addWidget(self._planet_label)
        sb.addPermanentWidget(self._year_status_label)

    # ── slots ───────────────────────────────────────────────────────────────

    def _on_planet_selected(self, pid: int):
        planet = next((p for p in self._planets if p.id == pid), None)
        if planet is None:
            return
        self._selected_planet = planet
        self._planet_label.setText(planet.name)
        self._info_panel.update_planet(planet, self._player)
        if self._info_dock.isHidden():
            self._info_dock.show()

    def _on_planet_activated(self, pid: int):
        """Double-click on a planet — open the full detail dialog."""
        planet = next((p for p in self._planets if p.id == pid), None)
        if planet is None:
            return
        self._selected_planet = planet
        self._planet_label.setText(planet.name)
        self._info_panel.update_planet(planet, self._player)
        try:
            from .dialogs.planet import PlanetDialog

            dlg = PlanetDialog(planet, self._player, self)
            dlg.exec()
        except Exception:
            pass

    def _on_hover_world(self, wx: int, wy: int):
        self._coords_label.setText(f"X: {wx}  Y: {wy}")

    # ── toolbar / menu handlers ─────────────────────────────────────────────

    def _handle_view_mode(self, mode: int):
        self._view_opts.planet_view = mode
        self._space_map.set_view_mode(mode)

    def _handle_names_toggle(self):
        enabled = self._names_btn.isChecked()
        self._view_opts.planet_names_overlay = enabled
        self._space_map.set_show_names(enabled)

    def _handle_zoom(self, level: int):
        self._view_opts.zoom_level = level
        self._space_map.set_zoom(ZoomLevel.multipliers()[level])

    def _handle_zoom_in(self):
        lvl = min(ZoomLevel.Highest, self._view_opts.zoom_level + 1)
        self._handle_zoom(lvl)
        self._zoom_actions[lvl].setChecked(True)

    def _handle_zoom_out(self):
        lvl = max(ZoomLevel.Lowest, self._view_opts.zoom_level - 1)
        self._handle_zoom(lvl)
        self._zoom_actions[lvl].setChecked(True)

    def _handle_zoom_fit(self):
        self._space_map._fit_to_view()
        self._space_map.update()

    def _handle_add_waypoints(self):
        self.statusBar().showMessage("Waypoint mode — not yet implemented.")

    def _handle_fleet_paths(self):
        self.statusBar().showMessage("Fleet paths overlay — not yet implemented.")

    def _handle_idle_fleets(self):
        self.statusBar().showMessage("Idle fleets filter — not yet implemented.")

    def _handle_toggle_toolbar(self):
        if self._main_toolbar.isVisible():
            self._main_toolbar.hide()
        else:
            self._main_toolbar.show()

    def _handle_new(self):
        self.statusBar().showMessage("New game — not yet implemented.")

    def _handle_open(self):
        self.statusBar().showMessage("Open game — not yet implemented.")

    def _handle_save(self):
        self.statusBar().showMessage("Save game — not yet implemented.")

    def _handle_close(self):
        self.close()

    def _handle_find(self):
        self.statusBar().showMessage("Find — not yet implemented.")

    def _handle_race(self):
        self.statusBar().showMessage("Race view — not yet implemented.")

    def _handle_game_params(self):
        self.statusBar().showMessage("Game parameters — not yet implemented.")

    def _handle_generate(self):
        self._game_year += 1
        self._year_label.setText(f"Year {self._game_year}")
        self._year_status_label.setText(f"Year {self._game_year}")
        self.statusBar().showMessage(f"Turn generated — Year {self._game_year}")

    def _handle_ship_design(self):
        self.statusBar().showMessage("Ship design — not yet implemented.")

    def _handle_research(self):
        if self._player is not None:
            try:
                from .dialogs.research import ResearchDialog

                dlg = ResearchDialog(self._player, False)
                dlg.exec()
                return
            except (ImportError, Exception):
                pass
        self.statusBar().showMessage("Research — not yet implemented.")

    def _handle_battle_plans(self):
        self.statusBar().showMessage("Battle plans — not yet implemented.")

    def _handle_planets_report(self):
        self.statusBar().showMessage("Planets report — not yet implemented.")

    def _handle_fleets_report(self):
        self.statusBar().showMessage("Fleets report — not yet implemented.")

    def _handle_score(self):
        self.statusBar().showMessage("Score — not yet implemented.")

    def _handle_tech_browser(self):
        if self._player is not None:
            try:
                from .dialogs.technology_browser import TechnologyBrowser

                dlg = TechnologyBrowser(self._player, False)
                dlg.exec()
                return
            except (ImportError, Exception):
                pass
        self.statusBar().showMessage("Technology browser — not yet implemented.")

    def _handle_about(self):
        try:
            from .dialogs import about

            dlg = about.AboutDialog()
            dlg.exec()
        except (ImportError, Exception):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.about(
                self, "About Stars Reborn", "Stars Reborn — an open-source Stars! clone."
            )
