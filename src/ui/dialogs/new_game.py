"""
ui/dialogs/new_game.py

New Game dialog — faithful reproduction of the original Stars! new-game popup.

Simple path (Ok): single-player game with selected difficulty, universe size,
and predefined race.

Advanced path (Advanced Game...): opens the advanced setup dialog for
multiplayer configuration, custom victory conditions, and game flags.

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ── Predefined races (from race.json schema) ──────────────────────────────────

_PREDEFINED_RACES = [
    "Humanoid",
    "Rabbitoid",
    "Insectoid",
    "Nucleotid",
    "Silcanoid",
    "Antetheral",
]

_RANDOM_RACE = "Random"

# ── Difficulty options ────────────────────────────────────────────────────────

_DIFFICULTY = [
    ("Easy", "easy"),
    ("Standard", "normal"),
    ("Harder", "tough"),
    ("Expert", "expert"),
]

# ── Universe sizes ────────────────────────────────────────────────────────────

_UNIVERSE_SIZES = [
    ("Tiny", "tiny"),
    ("Small", "small"),
    ("Medium", "medium"),
    ("Large", "large"),
    ("Huge", "huge"),
]


class NewGameDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        self.setWindowTitle("New Game")

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        columns = QHBoxLayout()
        columns.setSpacing(10)
        columns.addLayout(self._build_left_column())
        columns.addLayout(self._build_right_column())
        root.addLayout(columns)
        root.addLayout(self._build_bottom_buttons())

        self.setFixedSize(self.sizeHint())

    def _build_left_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        # ── Difficulty Level ──
        diff_group = QGroupBox("Difficulty Level")
        diff_layout = QVBoxLayout(diff_group)
        diff_layout.setSpacing(2)

        self._difficulty_group = QButtonGroup(self)
        for label, value in _DIFFICULTY:
            btn = QRadioButton(label)
            btn.setProperty("value", value)
            self._difficulty_group.addButton(btn)
            diff_layout.addWidget(btn)
            if value == "normal":
                btn.setChecked(True)

        col.addWidget(diff_group)

        # ── Universe Size ──
        size_group = QGroupBox("Universe Size")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(2)

        self._size_group = QButtonGroup(self)
        for label, value in _UNIVERSE_SIZES:
            btn = QRadioButton(label)
            btn.setProperty("value", value)
            self._size_group.addButton(btn)
            size_layout.addWidget(btn)
            if value == "small":
                btn.setChecked(True)  # confirmed default: Standard/Small

        col.addWidget(size_group)

        return col

    def _build_bottom_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._tutorial_btn = QPushButton("Begin Tutorial")
        self._tutorial_btn.clicked.connect(self._on_tutorial)
        row.addWidget(self._tutorial_btn)

        row.addStretch()

        self._ok_btn = QPushButton("Ok")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self.accept)
        row.addWidget(self._ok_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        row.addWidget(self._cancel_btn)

        return row

    def _build_right_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        # ── Player Race ──
        race_group = QGroupBox("Player Race")
        race_layout = QVBoxLayout(race_group)
        race_layout.setSpacing(6)

        self._race_combo = QComboBox()
        self._race_combo.addItem(_RANDOM_RACE)
        for name in _PREDEFINED_RACES:
            self._race_combo.addItem(name)
        race_layout.addWidget(self._race_combo)

        self._customize_btn = QPushButton("Customize Race...")
        self._customize_btn.clicked.connect(self._on_customize_race)
        race_layout.addWidget(self._customize_btn)

        race_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        col.addWidget(race_group)

        # ── Advanced Game ──
        adv_group = QGroupBox("Advanced Game")
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(8)

        adv_text = QLabel(
            "This button allows you to configure "
            "multi-player games and custom tailor "
            "advanced game options. You do not need "
            "to press this button for standard single "
            "player games."
        )
        adv_text.setWordWrap(True)
        adv_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        adv_text.setStyleSheet("color: #cc8800;")
        adv_layout.addWidget(adv_text)

        self._advanced_btn = QPushButton("Advanced Game...")
        self._advanced_btn.clicked.connect(self._on_advanced_game)
        adv_layout.addWidget(self._advanced_btn)

        col.addWidget(adv_group)

        return col

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _selected_difficulty(self) -> str:
        btn = self._difficulty_group.checkedButton()
        return btn.property("value") if btn else "normal"

    def _selected_size(self) -> str:
        btn = self._size_group.checkedButton()
        return btn.property("value") if btn else "small"

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_tutorial(self) -> None:
        QMessageBox.information(self, "Tutorial", "Tutorial — coming soon.")

    def _on_customize_race(self) -> None:
        QMessageBox.information(self, "Customize Race", "Race editor — coming soon.")

    def _on_advanced_game(self) -> None:
        QMessageBox.information(self, "Advanced Game", "Advanced game setup — coming soon.")

    # ── Public API ────────────────────────────────────────────────────────────

    def game_settings(self) -> dict:
        """Return selected settings; call only after the dialog is accepted.

        If the player chose Random, a race is picked here so the engine always
        receives a concrete race name.
        """
        race = self._race_combo.currentText()
        if race == _RANDOM_RACE:
            race = random.choice(_PREDEFINED_RACES)
        return {
            "difficulty": self._selected_difficulty(),
            "universe": {
                "size": self._selected_size(),
                "density": "normal",
            },
            "race": race,
        }
