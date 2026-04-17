"""
ui/intro.py

Entry screen — first thing the user sees.

Buttons:
  New Game     → new game setup wizard (HTTP: POST /game/new)
  Load Game    → load an existing saved game
  Host Game    → host/admin view for a multiplayer game
  Race Editor  → standalone race design tool
  About        → credits and version info
  Exit         → quit

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

import logging
import os

import requests
from PySide6.QtGui import QBrush, QPalette, QPixmap
from PySide6.QtWidgets import QBoxLayout, QDialog, QFileDialog, QMessageBox, QPushButton

from ..data.defaults import build_new_game_request
from ..data.loader import Language_Map
from ..data.r1_parser import load_race_file, save_race_json
from ..rendering.enumerations import ResourcePaths

log = logging.getLogger(__name__)


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

        self.new_game_button = QPushButton(gen.get("new-game", "&New Game"))
        self.load_game_button = QPushButton(gen.get("load-game", "&Load Game"))
        self.host_game_button = QPushButton(gen.get("host-game", "&Host Game"))
        self.create_race_button = QPushButton(gen.get("create-race", "&Create Race"))
        self.open_race_button = QPushButton(gen.get("open-race", "&Open Race"))
        self.about_button = QPushButton(gen.get("about", "&About"))
        self.exit_button = QPushButton(gen.get("exit", "E&xit"))

    def _bind_user_controls(self):
        self.new_game_button.clicked.connect(self._new_game_handler)
        self.load_game_button.clicked.connect(self._load_game_handler)
        self.host_game_button.clicked.connect(self._host_game_handler)
        self.create_race_button.clicked.connect(self._create_race_handler)
        self.open_race_button.clicked.connect(self._open_race_handler)
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
            self.open_race_button,
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

    def _new_game_handler(self):
        from .dialogs.new_game import NewGameDialog

        dlg = NewGameDialog(self)
        if dlg.exec() != NewGameDialog.DialogCode.Accepted:
            return

        settings = dlg.game_settings()

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "New Game",
            "Game.xy.json",
            "Stars! Game Files (*.xy.json)",
        )
        if not save_path:
            return

        save_dir = os.path.dirname(save_path)

        payload = build_new_game_request(
            universe_size=settings["universe"]["size"],
            difficulty=settings["difficulty"],
            race_name=settings["race"],
        )

        try:
            resp = requests.post(
                f"{self._engine_url}/game/new",
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

        # TODO: write returned game files to save_dir, then open turn editor.
        log.info("New game created at %s, save dir: %s", self._engine_url, save_dir)
        QMessageBox.information(
            self,
            "New Game",
            f"Game created.\n\nFiles will be written to:\n{save_dir}",
        )

    def _load_game_handler(self):
        # TODO: open file picker for a game folder / remote host address.
        QMessageBox.information(self, "Load Game", "Load game — coming soon.")

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

    def _open_race_handler(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Race File",
            "",
            "Race Files (*.r1 *.r1.json *.race.json);;All Files (*)",
        )
        if not path:
            return

        try:
            race = load_race_file(path)
        except Exception as exc:
            log.error("Failed to load race file %s: %s", path, exc)
            QMessageBox.critical(
                self,
                "Open Race Failed",
                f"Could not load race file:\n{path}\n\n{exc}",
            )
            return

        from .dialogs.race_wizard import RaceWizard

        dlg = RaceWizard(parent=self, race=race, engine_url=self._engine_url)
        if dlg.exec() != RaceWizard.DialogCode.Accepted:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Race File",
            "",
            "Stars Reborn Race Files (*.r1.json)",
        )
        if not save_path:
            return

        try:
            save_race_json(save_path, dlg.race_dict())
        except Exception as exc:
            log.error("Failed to save race file: %s", exc)
            QMessageBox.critical(self, "Save Failed", str(exc))

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
