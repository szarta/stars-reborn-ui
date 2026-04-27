"""
ui/info_panel.py

Left-side command panel: two columns of context-sensitive sections + messages pane.

Column 1: Planet header (name/icon/nav), Minerals On Hand, Status
Column 2: Fleets In Orbit, Production, Route To, Starbase
Bottom:   Messages pane
"""

from __future__ import annotations

import glob
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from ..rendering.enumerations import PrimaryRacialTrait, ResourcePaths


def _getattr_safe(obj, *attrs, default=None):
    for attr in attrs:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    return default


# ── Section title bar with collapse arrow ─────────────────────────────────


class _SectionPane(QWidget):
    """Collapsible titled section — common building block for both panel columns."""

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


# ── Column 1: Planet header ────────────────────────────────────────────────


class _PlanetHeaderSection(_SectionPane):
    """Planet name (title bar) + planet image + Prev/Next navigation."""

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._planet_files = sorted(glob.glob(f"{ResourcePaths.PlanetsPath}/*.png"))

        self._picture = QLabel()
        self._picture.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self._picture.setAlignment(Qt.AlignCenter)
        self._picture.setFixedSize(68, 68)
        self._picture.setAutoFillBackground(True)
        self._picture.setStyleSheet("background-color: black;")

        self._prev_btn = QPushButton("Prev")
        self._next_btn = QPushButton("Next")

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
                    pix.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self._picture.clear()


# ── Column 1: Minerals On Hand ─────────────────────────────────────────────


class _MineralsSection(_SectionPane):
    """Surface minerals (Ironium/Boranium/Germanium in kT) + mines and factories."""

    def __init__(self, parent=None):
        super().__init__("Minerals On Hand", parent)

        self._iron_val = QLabel("0 kT")
        self._bor_val = QLabel("0 kT")
        self._ger_val = QLabel("0 kT")
        self._mines_val = QLabel("0")
        self._factories_val = QLabel("0")

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


# ── Column 1: Status ───────────────────────────────────────────────────────


class _StatusSection(_SectionPane):
    """Population, resources/year, scanner, defenses."""

    def __init__(self, parent=None):
        super().__init__("Status", parent)

        self._pop_val = QLabel("n/a")
        self._res_val = QLabel("n/a")
        self._scanner_type_val = QLabel("n/a")
        self._scanner_range_val = QLabel("n/a")
        self._defenses_val = QLabel("n/a")
        self._defense_type_val = QLabel("n/a")
        self._def_coverage_val = QLabel("n/a")

        rows = [
            ("Population", self._pop_val),
            ("Resources/Year", self._res_val),
            ("Scanner Type", self._scanner_type_val),
            ("Scanner Range", self._scanner_range_val),
            ("Defenses", self._defenses_val),
            ("Defense Type", self._defense_type_val),
            ("Def Coverage", self._def_coverage_val),
        ]

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(1)
        for lbl_text, val_lbl in rows:
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(QLabel(lbl_text))
            r.addStretch(1)
            r.addWidget(val_lbl)
            col.addLayout(r)
        self.set_content_layout(col)

    def update_planet(self, planet, player=None):
        pop = getattr(planet, "population", 0)
        self._pop_val.setText(f"{pop:,}" if pop else "0")

        res = getattr(planet, "resources_per_year", None)
        cap = getattr(planet, "resource_capacity", None)
        if res is not None and cap is not None:
            self._res_val.setText(f"{res} of {cap}")
        elif res is not None:
            self._res_val.setText(str(res))
        else:
            self._res_val.setText("n/a")

        scanner = getattr(planet, "scanner_type", None)
        self._scanner_type_val.setText(scanner or "n/a")

        sr = getattr(planet, "scanner_range", None)
        self._scanner_range_val.setText(f"{sr} light years" if sr is not None else "n/a")

        defenses = getattr(planet, "defenses", None)
        self._defenses_val.setText(str(defenses) if defenses is not None else "n/a")

        def_type = getattr(planet, "defense_type", None)
        self._defense_type_val.setText(def_type or "n/a")

        coverage = getattr(planet, "defense_coverage", None)
        self._def_coverage_val.setText(str(coverage) if coverage is not None else "n/a")


# ── Column 2: Fleets In Orbit ─────────────────────────────────────────────


class _FleetsInOrbitSection(_SectionPane):
    """Fleet selector dropdown + fuel/cargo bars + Goto/Cargo buttons."""

    def __init__(self, parent=None):
        super().__init__("Fleets in Orbit", parent)

        self._fleet_combo = QComboBox()
        self._fleet_combo.addItem("(No fleets in orbit)")

        def _bar_row(label_text):
            lbl = QLabel(label_text)
            lbl.setFixedWidth(38)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(14)
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(lbl)
            r.addWidget(bar, 1)
            return r, bar

        fuel_row, self._fuel_bar = _bar_row("Fuel")
        cargo_row, self._cargo_bar = _bar_row("Cargo")

        btn_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        btn_row.addWidget(QPushButton("Goto"))
        btn_row.addStretch(1)
        btn_row.addWidget(QPushButton("Cargo"))

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(3)
        col.addWidget(self._fleet_combo)
        col.addLayout(fuel_row)
        col.addLayout(cargo_row)
        col.addLayout(btn_row)
        self.set_content_layout(col)


# ── Column 2: Production ───────────────────────────────────────────────────


class _ProductionSection(_SectionPane):
    """Production queue for the selected planet."""

    def __init__(self, parent=None):
        super().__init__("Production", parent)

        self._queue = QListWidget()
        self._queue.setMinimumHeight(70)
        self._queue.addItem("--- Queue is Empty ---")

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.addWidget(self._queue)
        self.set_content_layout(col)


# ── Column 2: Route To ────────────────────────────────────────────────────


class _RouteSection(_SectionPane):
    """Route destination + Change/Clear/Route buttons."""

    def __init__(self, parent=None):
        super().__init__("Route To", parent)

        dest_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        dest_row.addWidget(QLabel("Route to"))
        dest_row.addStretch(1)
        self._dest_label = QLabel("none")
        dest_row.addWidget(self._dest_label)

        btn_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        btn_row.addWidget(QPushButton("Change"))
        btn_row.addWidget(QPushButton("Clear"))
        btn_row.addStretch(1)
        btn_row.addWidget(QPushButton("Route"))

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(4)
        col.addLayout(dest_row)
        col.addLayout(btn_row)
        self.set_content_layout(col)


# ── Column 2: Starbase ────────────────────────────────────────────────────


class _StarbaseSection(_SectionPane):
    """Starbase stats for the selected planet."""

    def __init__(self, parent=None):
        super().__init__("Starbase", parent)

        self._dock_val = QLabel("n/a")
        self._armor_val = QLabel("n/a")
        self._shields_val = QLabel("n/a")
        self._damage_val = QLabel("n/a")
        self._mass_driver_val = QLabel("n/a")
        self._dest_val = QLabel("n/a")

        def _row(lbl_text, val_lbl):
            r = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            r.addWidget(QLabel(lbl_text))
            r.addStretch(1)
            r.addWidget(val_lbl)
            return r

        col = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        col.setContentsMargins(4, 4, 4, 4)
        col.setSpacing(1)
        col.addLayout(_row("Dock Capacity", self._dock_val))
        col.addLayout(_row("Armor", self._armor_val))
        col.addLayout(_row("Shields", self._shields_val))
        col.addLayout(_row("Damage", self._damage_val))
        col.addLayout(_row("Mass Driver", self._mass_driver_val))
        col.addLayout(_row("Destination", self._dest_val))
        set_dest = QPushButton("Set Dest")
        set_dest.setEnabled(False)
        col.addWidget(set_dest, 0, Qt.AlignLeft)
        self.set_content_layout(col)


# ── Messages pane ──────────────────────────────────────────────────────────


class _MessagesPane(QWidget):
    """Year/message counter bar + message text area at the bottom of the left panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)

        top_bar = QFrame()
        top_bar.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)

        self._filter_check = QCheckBox()
        self._filter_check.setChecked(True)
        self._filter_check.setFixedSize(18, 18)
        self._filter_check.setToolTip("Hide unimportant messages")

        self._year_count_label = QLabel("Year: 2400   Messages: 0 of 0")

        self._prev_btn = QPushButton("Prev")
        self._prev_btn.setFixedWidth(36)
        self._goto_btn = QPushButton("Goto")
        self._goto_btn.setFixedWidth(36)
        self._next_btn = QPushButton("Next")
        self._next_btn.setFixedWidth(36)

        bar_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        bar_layout.setContentsMargins(2, 2, 2, 2)
        bar_layout.setSpacing(2)
        bar_layout.addWidget(self._filter_check)
        bar_layout.addWidget(self._year_count_label, 1)
        bar_layout.addWidget(self._prev_btn)
        bar_layout.addWidget(self._goto_btn)
        bar_layout.addWidget(self._next_btn)
        top_bar.setLayout(bar_layout)

        self._msg_text = QLabel("(No messages)")
        self._msg_text.setWordWrap(True)
        self._msg_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._msg_text.setContentsMargins(4, 4, 4, 4)
        self._msg_text.setStyleSheet("background: black; color: white;")

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(top_bar)
        main.addWidget(self._msg_text, 1)
        self.setLayout(main)

    def set_year(self, year: int):
        self._year_count_label.setText(f"Year: {year}   Messages: 0 of 0")


# ── Left panel (top-level assembly) ───────────────────────────────────────


class LeftPanel(QWidget):
    """
    The left-side command panel.

    Two adjacent section columns fill the top area; a messages pane sits below.
    Call update_planet(planet, player) whenever selection changes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)

        # ── Column 1 ──────────────────────────────────────────────────────
        self._planet_header = _PlanetHeaderSection()
        self._minerals = _MineralsSection()
        self._status = _StatusSection()

        col1 = QWidget()
        c1 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        c1.setContentsMargins(0, 0, 0, 0)
        c1.setSpacing(0)
        c1.addWidget(self._planet_header)
        c1.addWidget(self._minerals)
        c1.addWidget(self._status)
        c1.addStretch(1)
        col1.setLayout(c1)

        # ── Column 2 ──────────────────────────────────────────────────────
        self._fleets = _FleetsInOrbitSection()
        self._production = _ProductionSection()
        self._route = _RouteSection()
        self._starbase = _StarbaseSection()

        col2 = QWidget()
        c2 = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        c2.setContentsMargins(0, 0, 0, 0)
        c2.setSpacing(0)
        c2.addWidget(self._fleets)
        c2.addWidget(self._production)
        c2.addWidget(self._route)
        c2.addWidget(self._starbase)
        c2.addStretch(1)
        col2.setLayout(c2)

        # ── Two-column row ─────────────────────────────────────────────────
        columns = QWidget()
        cols = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(0)
        cols.addWidget(col1)
        cols.addWidget(col2)
        columns.setLayout(cols)

        # ── Messages pane ──────────────────────────────────────────────────
        self._messages = _MessagesPane()

        # ── Vertical splitter: columns (top) / messages (bottom) ───────────
        # Original game anchors the messages pane to the bottom at a fixed
        # height; the section columns absorb vertical resize.
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(columns)
        self._splitter.addWidget(self._messages)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)

        main = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(self._splitter)
        self.setLayout(main)

    def update_planet(self, planet, player=None):
        self._planet_header.update_planet(planet)
        self._minerals.update_planet(planet, player)
        self._status.update_planet(planet, player)

    def set_year(self, year: int):
        self._messages.set_year(year)


# ── Back-compat alias ──────────────────────────────────────────────────────
InfoPanel = LeftPanel
