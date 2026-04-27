"""
ui/intro.py

Entry screen — first thing the user sees.

Buttons:
  New Game         → new game setup wizard (HTTP: POST /games)
  Load Game        → load an existing saved game
  Host Game        → host/admin view for a multiplayer game
  Create New Race  → design a brand-new race from scratch
  Edit Race        → open an existing race file for editing
  View Race        → open an existing race file read-only
  About            → credits and version info
  Exit             → quit

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

import json
import logging
import os

import requests
from PySide6.QtGui import QBrush, QPalette, QPixmap
from PySide6.QtWidgets import QBoxLayout, QDialog, QFileDialog, QMessageBox, QPushButton

from ..data.defaults import PlanetData, build_new_game_request
from ..data.loader import Language_Map
from ..data.r1_parser import load_race_file, save_race_json
from ..rendering.enumerations import ResourcePaths

log = logging.getLogger(__name__)


def _save_game_files(save_dir: str, safe_name: str, xy: dict, turn: dict) -> None:
    """Write the two canonical game files for a newly created game.

    {safe_name}.xy.json  — universe file fetched from GET /games/{id}
    {safe_name}.m1.json  — player turn file fetched from GET /games/{id}/turns/{year}/players/0
    """
    xy_path = os.path.join(save_dir, f"{safe_name}.xy.json")
    m1_path = os.path.join(save_dir, f"{safe_name}.m1.json")

    with open(xy_path, "w", encoding="utf-8") as f:
        json.dump(xy, f, indent=2)
    with open(m1_path, "w", encoding="utf-8") as f:
        json.dump(turn, f, indent=2)

    log.info("Saved %s and %s", xy_path, m1_path)


class IntroUI(QDialog):
    def __init__(self, engine_url: str = "http://localhost:8080"):
        super().__init__()
        self._engine_url = engine_url.rstrip("/")
        self._init_user_controls()
        self._init_ui()
        self._bind_user_controls()

    def _init_user_controls(self):
        ui = Language_Map.get("ui", {})
        gen = ui.get("general", {})

        self.new_game_button = QPushButton(gen.get("new-local-game", "New &Local Game"))
        self.load_game_button = QPushButton(gen.get("load-local-game", "Load &Local Game"))
        self.host_game_button = QPushButton(gen.get("host-game", "&Host Game"))
        self.create_race_button = QPushButton(gen.get("create-new-race", "&Create New Race"))
        self.edit_race_button = QPushButton(gen.get("edit-race", "&Edit Race"))
        self.view_race_button = QPushButton(gen.get("view-race", "&View Race"))
        self.about_button = QPushButton(gen.get("about", "&About"))
        self.exit_button = QPushButton(gen.get("exit", "E&xit"))

    def _bind_user_controls(self):
        self.new_game_button.clicked.connect(self._new_local_game_handler)
        self.load_game_button.clicked.connect(self._load_local_game_handler)
        self.host_game_button.clicked.connect(self._host_game_handler)
        self.create_race_button.clicked.connect(self._create_race_handler)
        self.edit_race_button.clicked.connect(self._edit_race_handler)
        self.view_race_button.clicked.connect(self._view_race_handler)
        self.about_button.clicked.connect(self._about_handler)
        self.exit_button.clicked.connect(self.close)

    def _init_ui(self):
        title = Language_Map.get("game-name", "Stars Reborn")
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 768, 768)
        self.setFixedSize(768, 768)

        logo_path = ResourcePaths.IntroLogo
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            palette = self.palette()
            palette.setBrush(QPalette.ColorRole.Window, QBrush(pixmap))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        button_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        button_layout.setContentsMargins(20, 0, 0, 20)
        button_layout.setSpacing(8)
        for btn in (
            self.new_game_button,
            self.load_game_button,
            self.host_game_button,
            self.create_race_button,
            self.edit_race_button,
            self.view_race_button,
            self.about_button,
            self.exit_button,
        ):
            btn.setFixedWidth(160)
            button_layout.addWidget(btn)

        background_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        background_layout.addLayout(button_layout)
        background_layout.addStretch(1)

        main_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        main_layout.addStretch(1)
        main_layout.addLayout(background_layout)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _new_local_game_handler(self):
        from .dialogs.new_game import NewGameDialog

        dlg = NewGameDialog(self)
        if dlg.exec() != NewGameDialog.DialogCode.Accepted:
            return

        settings = dlg.game_settings()

        payload = build_new_game_request(
            universe_size=settings["universe"]["size"],
            difficulty=settings["difficulty"],
            race_name=settings["race"],
        )

        try:
            resp = requests.post(
                f"{self._engine_url}/games",
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(
                self,
                "Engine Unavailable",
                f"Could not connect to the Stars Reborn engine at\n{self._engine_url}\n\n"
                "Make sure the engine is running before starting a new game.",
            )
            return
        except requests.exceptions.HTTPError as exc:
            log.error("Engine returned error: %s — %s", exc.response.status_code, exc.response.text)
            QMessageBox.critical(
                self,
                "New Game Failed",
                f"The engine rejected the new game request:\n\n{exc.response.text}",
            )
            return
        except requests.exceptions.RequestException as exc:
            log.error("New game request failed: %s", exc)
            QMessageBox.critical(self, "New Game Failed", str(exc))
            return

        body = resp.json()
        game_id = body["created-game"]["id"]
        log.info("Game created: id=%s", game_id)

        # Fetch both files the client needs: universe (.xy) and player turn (.m1)
        try:
            xy_resp = requests.get(
                f"{self._engine_url}/games/{game_id}",
                timeout=30,
            )
            xy_resp.raise_for_status()
            turn_resp = requests.get(
                f"{self._engine_url}/games/{game_id}/turns/2400/players/0",
                timeout=30,
            )
            turn_resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            log.error("Failed to fetch game files: %s", exc)
            QMessageBox.critical(self, "New Game Failed", f"Could not load game files:\n{exc}")
            return

        xy = xy_resp.json()
        turn = turn_resp.json()

        # --- Save game files ---
        game_name = xy["game-name"]
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in game_name)

        save_dir = QFileDialog.getExistingDirectory(
            self,
            f'Choose folder to save game files for "{game_name}"',
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if save_dir:
            try:
                _save_game_files(save_dir, safe_name, xy, turn)
            except Exception as exc:
                log.error("Failed to save game files: %s", exc)
                QMessageBox.warning(
                    self,
                    "Save Warning",
                    f"Game was created but files could not be saved:\n{exc}",
                )

        # Build planet list from the turn file (player's fog-of-war view).
        # Positions come from the turn file; the xy file is saved as-is for the engine to serve.
        planets = [PlanetData.from_turn_planet(p) for p in turn["planets"]]

        from .main_window import MainWindow

        self._main_window = MainWindow(
            planets=planets,
            universe_w=float(xy["universe-width"]),
            universe_h=float(xy["universe-height"]),
            player_id=turn["player-id"],
            game_year=turn["year"],
            game_name=game_name,
        )
        self._main_window.show()
        self.hide()

    def _load_local_game_handler(self):
        """Open a saved .m1.json turn file and launch the turn editor."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Local Game — Open Turn File",
            "",
            "Stars Reborn Turn Files (*.m1.json *.m*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                turn = json.load(f)
        except Exception as exc:
            log.error("Failed to read turn file %s: %s", path, exc)
            QMessageBox.critical(self, "Load Failed", f"Could not read turn file:\n{exc}")
            return

        # Look for the companion .xy.json in the same directory
        game_name = turn.get("game-name", "Game")
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in game_name)
        game_dir = os.path.dirname(path)
        xy_path = os.path.join(game_dir, f"{safe_name}.xy.json")

        universe_w, universe_h = 800.0, 800.0
        if os.path.exists(xy_path):
            try:
                with open(xy_path, encoding="utf-8") as f:
                    xy = json.load(f)
                universe_w = float(xy.get("universe-width", 800))
                universe_h = float(xy.get("universe-height", 800))
            except Exception as exc:
                log.warning("Could not read %s: %s", xy_path, exc)

        planets = [PlanetData.from_turn_planet(p) for p in turn.get("planets", [])]

        from .main_window import MainWindow

        self._main_window = MainWindow(
            planets=planets,
            universe_w=universe_w,
            universe_h=universe_h,
            player_id=turn.get("player-id", 0),
            game_year=turn.get("year", 2400),
            game_name=game_name,
        )
        self._main_window.show()
        self.hide()

    def _host_game_handler(self):
        # TODO: open host admin view (submission status, skip player, trigger generation).
        QMessageBox.information(self, "Host Game", "Host game admin view — coming soon.")

    def _create_race_handler(self):
        from .dialogs.race_wizard import RaceWizard

        dlg = RaceWizard(parent=self, engine_url=self._engine_url)
        if dlg.exec() != RaceWizard.DialogCode.Accepted:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Race File",
            "MyRace.r1.json",
            "Stars Reborn Race Files (*.r1.json)",
        )
        if not save_path:
            return

        try:
            save_race_json(save_path, dlg.race_dict())
        except Exception as exc:
            log.error("Failed to save race file: %s", exc)
            QMessageBox.critical(self, "Save Failed", str(exc))

    def _prompt_load_race(self, title: str) -> tuple[str, dict] | None:
        """Ask the user for a race file and load it. Returns (path, race) or None."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "Race Files (*.r1 *.r1.json *.race.json);;All Files (*)",
        )
        if not path:
            return None

        try:
            race = load_race_file(path)
        except Exception as exc:
            log.error("Failed to load race file %s: %s", path, exc)
            QMessageBox.critical(
                self,
                "Open Race Failed",
                f"Could not load race file:\n{path}\n\n{exc}",
            )
            return None

        return path, race

    def _suggest_save_path(self, source_path: str) -> str:
        """Turn any race source path into a reasonable .r1.json save target."""
        if source_path.endswith(".r1.json") or source_path.endswith(".race.json"):
            return source_path
        base, _ = os.path.splitext(source_path)
        if base.endswith(".r1"):
            base = base[:-3]
        return f"{base}.r1.json"

    def _edit_race_handler(self):
        loaded = self._prompt_load_race("Edit Race — Select Race File")
        if loaded is None:
            return
        source_path, race = loaded

        from .dialogs.race_wizard import RaceWizard

        dlg = RaceWizard(parent=self, race=race, engine_url=self._engine_url)
        if dlg.exec() != RaceWizard.DialogCode.Accepted:
            return

        suggested = self._suggest_save_path(source_path)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Race File",
            suggested,
            "Stars Reborn Race Files (*.r1.json)",
        )
        if not save_path:
            return

        try:
            save_race_json(save_path, dlg.race_dict())
        except Exception as exc:
            log.error("Failed to save race file: %s", exc)
            QMessageBox.critical(self, "Save Failed", str(exc))

    def _view_race_handler(self):
        loaded = self._prompt_load_race("View Race — Select Race File")
        if loaded is None:
            return
        _, race = loaded

        from .dialogs.race_wizard import RaceWizard

        dlg = RaceWizard(parent=self, race=race, engine_url=self._engine_url, read_only=True)
        dlg.exec()

    def _about_handler(self):
        try:
            from .dialogs import about

            dlg = about.AboutDialog()
            dlg.exec()
        except (ImportError, Exception):
            QMessageBox.about(
                self,
                "About Stars Reborn",
                "Stars Reborn — an open-source Stars! clone.\n\nSee docs/ for details.",
            )
