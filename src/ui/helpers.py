"""
ui/helpers.py

Methods commonly used across multiple UI screens.

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QPushButton,
    QRadioButton,
)


def build_radio_group(array):
    radio_group = QButtonGroup()
    for button_id, label in enumerate(array):
        rb = QRadioButton(label)
        radio_group.addButton(rb, button_id)
    return radio_group


def build_checkbox_group(array):
    check_group = QButtonGroup()
    for button_id, label in enumerate(array):
        cb = QCheckBox(label)
        check_group.addButton(cb, button_id)
    return check_group


def build_push_button_group(array):
    button_group = QButtonGroup()
    for button_id, label in enumerate(array):
        pb = QPushButton(label)
        button_group.addButton(pb, button_id)
    return button_group


def build_button_group_box(button_group, title, columns=1):
    horizontal_box = QBoxLayout(QBoxLayout.Direction.LeftToRight)

    column_layouts = []
    for _ in range(columns):
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        column_layouts.append(layout)
        horizontal_box.addLayout(layout)

    for i, button in enumerate(button_group.buttons(), start=1):
        column_layouts[i % columns].addWidget(button)

    group_box = QGroupBox(title)
    group_box.setLayout(horizontal_box)
    return group_box
