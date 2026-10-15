"""Register portable symbols and choose readable desktop fonts before QML."""
from __future__ import annotations

import logging
from pathlib import Path
import sys

from PySide6.QtGui import QFont, QFontDatabase


SYMBOL_FAMILY = "CSPM Symbols"
SYMBOL_FONT_RELATIVE_PATH = Path("src/qml/assets/fonts/CSPMSymbols.ttf")
_logger = logging.getLogger(__name__)


def configure_application_typography(app, project_root: Path) -> dict[str, str]:
    """Keep Windows typography; resolve Linux text and symbols locally.

    Local font registration does not install fonts system-wide. QML uses the
    application text font on Linux, including windows created after startup.
    """
    font_path = Path(project_root) / SYMBOL_FONT_RELATIVE_PATH
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0 or SYMBOL_FAMILY not in QFontDatabase.applicationFontFamilies(font_id):
        raise RuntimeError(f"The bundled {SYMBOL_FAMILY} icon font could not be loaded")

    if sys.platform != "win32":
        families = set(QFontDatabase.families())
        # Noto matches Fedora Plasma's normal UI, is available in the Fedora
        # build dependencies and includes extended language/currency glyphs.
        # Keep the desktop general font when Noto is unavailable elsewhere.
        default_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        chosen_family = next((name for name in ("Noto Sans", "Adwaita Sans", "DejaVu Sans")
                              if name in families), default_font.family())
        font = QFont(app.font())
        font.setFamily(chosen_family)
        app.setFont(font)

    result = {"text": app.font().family(), "symbols": SYMBOL_FAMILY}
    _logger.info("Application typography: text=%s symbols=%s", result["text"], result["symbols"])
    return result
