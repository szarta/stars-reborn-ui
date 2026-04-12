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

import os

from PySide6.QtGui import QBrush, QPalette, QPixmap
from PySide6.QtWidgets import QBoxLayout, QDialog, QMessageBox, QPushButton

from ..data.loader import Language_Map
from ..rendering.enumerations import ResourcePaths


class IntroUI(QDialog):
    def __init__(self):
        super().__init__()
        self._init_user_controls()
        self._init_ui()
        self._bind_user_controls()

    def _init_user_controls(self):
        ui = Language_Map.get("ui", {})
        gen = ui.get("general", {})

        self.new_game_button = QPushButton(gen.get("new-game", "&New Game"))
        self.load_game_button = QPushButton(gen.get("load-game", "&Load Game"))
        self.host_game_button = QPushButton(gen.get("host-game", "&Host Game"))
        self.race_editor_button = QPushButton(gen.get("race-editor", "&Race Editor"))
        self.about_button = QPushButton(gen.get("about", "&About"))
        self.exit_button = QPushButton(gen.get("exit", "E&xit"))

    def _bind_user_controls(self):
        self.new_game_button.clicked.connect(self._new_game_handler)
        self.load_game_button.clicked.connect(self._load_game_handler)
        self.host_game_button.clicked.connect(self._host_game_handler)
        self.race_editor_button.clicked.connect(self._race_editor_handler)
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
        button_layout.setContentsMargins(20, 20, 0, 0)
        button_layout.setSpacing(8)
        for btn in (
            self.new_game_button,
            self.load_game_button,
            self.host_game_button,
            self.race_editor_button,
            self.about_button,
            self.exit_button,
        ):
            btn.setFixedWidth(160)
            button_layout.addWidget(btn)
        button_layout.addStretch(1)

        background_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        background_layout.addLayout(button_layout)
        background_layout.addStretch(1)

        main_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        main_layout.addLayout(background_layout)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _new_game_handler(self):
        # TODO: open new game setup wizard; on confirm POST /game/new to engine,
        # receive initial file assets, write to game folder, open turn editor.
        QMessageBox.information(self, "New Game", "New game wizard — coming soon.")

    def _load_game_handler(self):
        # TODO: open file picker for a game folder / remote host address.
        QMessageBox.information(self, "Load Game", "Load game — coming soon.")

    def _host_game_handler(self):
        # TODO: open host admin view (submission status, skip player, trigger generation).
        QMessageBox.information(self, "Host Game", "Host game admin view — coming soon.")

    def _race_editor_handler(self):
        # TODO: open standalone race editor.
        QMessageBox.information(self, "Race Editor", "Race editor — coming soon.")

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
