"""
ui/info_panel.py

Right-side context panel showing details for the selected planet or fleet.
Ported from src/ui/turn/statuspane.py and src/ui/turn/resourceinfo.py (PySide → PySide6).

Accepts the same duck-typed planet objects as SpaceMap (Python Planet or Rust Planet).
"""

from __future__ import annotations

import glob
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from ..rendering.enumerations import PrimaryRacialTrait, ResourcePaths


def _getattr_safe(obj, *attrs, default=None):
    """Return the first attribute that exists on obj, else default."""
    for attr in attrs:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    return default


# ── Section title bar with hide/show arrow ─────────────────────────────────


class _SectionPane(QWidget):
    """Collapsible titled section used in the info panel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._hidden = False

        title_bar = QFrame()
        title_bar.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignCenter)

        arrow_pix = QPixmap(ResourcePaths.HideArrowPath)
        self._toggle_btn = QPushButton()
        if not arrow_pix.isNull():
            from PySide6.QtGui import QIcon

            self._toggle_btn.setIcon(QIcon(arrow_pix))
            self._toggle_btn.setIconSize(arrow_pix.rect().size())
        else:
            self._toggle_btn.setText("▲")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.clicked.connect(self._toggle)

        bar_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        bar_layout.setContentsMargins(2, 0, 2, 0)
        bar_layout.addWidget(self._title_label, 1)
        bar_layout.addWidget(self._toggle_btn)
        title_bar.setLayout(bar_layout)

        self._content = QFrame()
        self._content.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(title_bar)
        main.addWidget(self._content)
        self.setLayout(main)

    def set_content_layout(self, layout):
        if self._content.layout():
            # Replace old layout
            old = self._content.layout()
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            old.deleteLater()
        self._content.setLayout(layout)

    def set_title(self, title: str):
        self._title_label.setText(title)

    def _toggle(self):
        if self._hidden:
            self._content.show()
            self._hidden = False
        else:
            self._content.hide()
            self._hidden = True


# ── Planet image section ────────────────────────────────────────────────────


class _PlanetImageSection(_SectionPane):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self._planet_files = sorted(glob.glob(f"{ResourcePaths.PlanetsPath}/*.png"))

        self._picture = QLabel()
        self._picture.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self._picture.setAlignment(Qt.AlignCenter)
        self._picture.setFixedSize(80, 80)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedWidth(24)
        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedWidth(24)

        btn_col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        btn_col.addWidget(self._prev_btn)
        btn_col.addWidget(self._next_btn)
        btn_col.addStretch(1)

        row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        row.setContentsMargins(4, 4, 4, 4)
        row.addStretch(1)
        row.addWidget(self._picture)
        row.addLayout(btn_col)
        row.addStretch(1)

        self.set_content_layout(row)

    def update_planet(self, planet):
        self.set_title(planet.name)
        if self._planet_files:
            path = self._planet_files[planet.id % len(self._planet_files)]
            pix = QPixmap(path)
            if not pix.isNull():
                self._picture.setPixmap(
                    pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self._picture.clear()


# ── Summary (value + population) ───────────────────────────────────────────


class _SummarySection(_SectionPane):
    def __init__(self, parent=None):
        super().__init__("Summary", parent)

        self._value_label = QLabel()
        self._report_label = QLabel()
        self._pop_label = QLabel()

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(2)
        col.addWidget(self._value_label)
        col.addWidget(self._report_label)
        col.addWidget(self._pop_label)
        self.set_content_layout(col)

    def update_planet(self, planet):
        from ..rendering.enumerations import NeverSeenPlanet

        years_since = getattr(planet, "years_since", 0)

        if years_since == NeverSeenPlanet:
            self._value_label.setText("Unknown")
            self._report_label.setText("")
            self._pop_label.setText("")
            return

        value = getattr(planet, "value", None)
        if value is not None:
            color = "green" if value >= 0 else "red"
            self._value_label.setText(f'Value: <font color="{color}"><b>{value}%</b></font>')
        else:
            self._value_label.setText("")

        if years_since == 0:
            self._report_label.setText('<font color="white">Report is current</font>')
        elif years_since > 0:
            self._report_label.setText(
                f'<font color="red">Report is {years_since} year(s) old</font>'
            )
        else:
            self._report_label.setText("")

        pop = getattr(planet, "population", 0)
        if pop == 0:
            self._pop_label.setText("Uninhabited")
        else:
            self._pop_label.setText(f"Population: {pop:,}")


# ── Minerals on hand ────────────────────────────────────────────────────────


class _MineralsSection(_SectionPane):
    def __init__(self, parent=None):
        super().__init__("Minerals on Hand", parent)

        self._iron_val = QLabel()
        self._bor_val = QLabel()
        self._ger_val = QLabel()
        self._mines_val = QLabel()
        self._factories_val = QLabel()

        iron_lbl = QLabel("<b>Ironium</b>")
        iron_lbl.setStyleSheet("color: #4488ff")
        bor_lbl = QLabel("<b>Boranium</b>")
        bor_lbl.setStyleSheet("color: #44cc44")
        ger_lbl = QLabel("<b>Germanium</b>")
        ger_lbl.setStyleSheet("color: #dddd00")

        def _row(label, value_label):
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(label)
            r.addStretch(1)
            r.addWidget(value_label)
            return r

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(2)
        col.addLayout(_row(iron_lbl, self._iron_val))
        col.addLayout(_row(bor_lbl, self._bor_val))
        col.addLayout(_row(ger_lbl, self._ger_val))

        divider = QFrame()
        divider.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        col.addWidget(divider)

        col.addLayout(_row(QLabel("<b>Mines</b>"), self._mines_val))
        col.addLayout(_row(QLabel("<b>Factories</b>"), self._factories_val))
        self.set_content_layout(col)

    def update_planet(self, planet, player=None):
        self._iron_val.setText(f"{getattr(planet, 'surface_ironium', 0)} kT")
        self._bor_val.setText(f"{getattr(planet, 'surface_boranium', 0)} kT")
        self._ger_val.setText(f"{getattr(planet, 'surface_germanium', 0)} kT")

        prt = None
        if player is not None:
            race = getattr(player, "race", None)
            if race is not None:
                prt = getattr(race, "primary_racial_trait", None)

        pop = getattr(planet, "population", 0)
        if prt == PrimaryRacialTrait.AlternateReality:
            self._mines_val.setText(f"{int(math.sqrt(max(0, pop)) / 10)}*")
            self._factories_val.setText("n/a")
        else:
            self._mines_val.setText(str(getattr(planet, "mines", 0)))
            self._factories_val.setText(str(getattr(planet, "factories", 0)))


# ── Mineral concentrations ──────────────────────────────────────────────────


class _ConcentrationSection(_SectionPane):
    def __init__(self, parent=None):
        super().__init__("Mineral Concentrations", parent)

        self._iron_val = QLabel()
        self._bor_val = QLabel()
        self._ger_val = QLabel()

        iron_lbl = QLabel("<b>Ironium</b>")
        iron_lbl.setStyleSheet("color: #4488ff")
        bor_lbl = QLabel("<b>Boranium</b>")
        bor_lbl.setStyleSheet("color: #44cc44")
        ger_lbl = QLabel("<b>Germanium</b>")
        ger_lbl.setStyleSheet("color: #dddd00")

        def _row(lbl, val):
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(lbl)
            r.addStretch(1)
            r.addWidget(val)
            return r

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(2)
        col.addLayout(_row(iron_lbl, self._iron_val))
        col.addLayout(_row(bor_lbl, self._bor_val))
        col.addLayout(_row(ger_lbl, self._ger_val))
        self.set_content_layout(col)

    def update_planet(self, planet):
        self._iron_val.setText(str(getattr(planet, "ironium_concentration", 0)))
        self._bor_val.setText(str(getattr(planet, "boranium_concentration", 0)))
        self._ger_val.setText(str(getattr(planet, "germanium_concentration", 0)))


# ── Hab display (gravity / temperature / radiation) ─────────────────────────


class _HabSection(_SectionPane):
    def __init__(self, parent=None):
        super().__init__("Habitat", parent)

        self._grav_val = QLabel()
        self._temp_val = QLabel()
        self._rad_val = QLabel()

        def _row(lbl_text, val_lbl):
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(QLabel(f"<b>{lbl_text}</b>"))
            r.addStretch(1)
            r.addWidget(val_lbl)
            return r

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(2)
        col.addLayout(_row("Gravity", self._grav_val))
        col.addLayout(_row("Temperature", self._temp_val))
        col.addLayout(_row("Radiation", self._rad_val))
        self.set_content_layout(col)

    def update_planet(self, planet):
        grav = getattr(planet, "gravity", None)
        self._grav_val.setText(f"{grav:.2f}g" if grav is not None else "?")
        temp = getattr(planet, "temperature", None)
        self._temp_val.setText(f"{temp}°C" if temp is not None else "?")
        rad = getattr(planet, "radiation", None)
        self._rad_val.setText(f"{rad} mR/yr" if rad is not None else "?")


# ── Top-level info panel ────────────────────────────────────────────────────


class InfoPanel(QWidget):
    """
    Right-side dockable panel.  Call update_planet(planet, player) whenever
    the selected planet changes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(180)
        self.setMaximumWidth(280)

        self._image_section = _PlanetImageSection()
        self._summary_section = _SummarySection()
        self._minerals_section = _MineralsSection()
        self._concentration_section = _ConcentrationSection()
        self._hab_section = _HabSection()

        self._nothing_label = QLabel("No selection")
        self._nothing_label.setAlignment(Qt.AlignCenter)
        self._nothing_label.setStyleSheet("color: gray; font-style: italic;")

        # Scrollable container for all sections
        scroll_content = QWidget()
        content_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        content_layout.addWidget(self._image_section)
        content_layout.addWidget(self._summary_section)
        content_layout.addWidget(self._minerals_section)
        content_layout.addWidget(self._concentration_section)
        content_layout.addWidget(self._hab_section)
        content_layout.addStretch(1)
        scroll_content.setLayout(content_layout)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(scroll_content)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self._nothing_label)
        main.addWidget(self._scroll)
        self.setLayout(main)

        self._scroll.hide()

    def update_planet(self, planet, player=None):
        self._nothing_label.hide()
        self._scroll.show()
        self._image_section.update_planet(planet)
        self._summary_section.update_planet(planet)
        self._minerals_section.update_planet(planet, player)
        self._concentration_section.update_planet(planet)
        self._hab_section.update_planet(planet)

    def clear(self):
        self._scroll.hide()
        self._nothing_label.show()
