"""
ui/app.py

QApplication setup with a Windows 95 / Win3.x visual style.

:author: Brandon Arrendondo
:license: MIT, see LICENSE.txt for more details.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Win95 system-color palette (approximated from the original RGB values)
_WIN95_COLORS = {
    QPalette.ColorRole.Window: QColor(0xC0, 0xC0, 0xC0),
    QPalette.ColorRole.WindowText: QColor(0x00, 0x00, 0x00),
    QPalette.ColorRole.Base: QColor(0xFF, 0xFF, 0xFF),
    QPalette.ColorRole.AlternateBase: QColor(0xC0, 0xC0, 0xC0),
    QPalette.ColorRole.Text: QColor(0x00, 0x00, 0x00),
    QPalette.ColorRole.Button: QColor(0xC0, 0xC0, 0xC0),
    QPalette.ColorRole.ButtonText: QColor(0x00, 0x00, 0x00),
    QPalette.ColorRole.Highlight: QColor(0x00, 0x00, 0x80),
    QPalette.ColorRole.HighlightedText: QColor(0xFF, 0xFF, 0xFF),
    QPalette.ColorRole.Light: QColor(0xFF, 0xFF, 0xFF),
    QPalette.ColorRole.Midlight: QColor(0xDF, 0xDF, 0xDF),
    QPalette.ColorRole.Mid: QColor(0x80, 0x80, 0x80),
    QPalette.ColorRole.Dark: QColor(0x40, 0x40, 0x40),
    QPalette.ColorRole.Shadow: QColor(0x00, 0x00, 0x00),
}


def build_win95_palette():
    palette = QPalette()
    for role, color in _WIN95_COLORS.items():
        palette.setColor(QPalette.ColorGroup.All, role, color)
    return palette


def create_app(argv):
    """Create and configure the QApplication with Win95 style."""
    app = QApplication(argv)
    app.setStyle("Fusion")  # consistent base; palette overrides give Win95 look
    app.setPalette(build_win95_palette())
    app.setApplicationName("Stars Reborn")
    app.setOrganizationName("Stars Reborn Project")
    return app
