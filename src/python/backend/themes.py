"""
Default theme palette data and loading helpers.

Extracted from app_controller.py to reduce monolith size and allow
independent testing of theme definitions.
"""
import json
import logging
import os
from typing import Any, Dict

from services.theme_contrast import sanitize_theme_map

THEMES_FILE = os.path.join(os.path.dirname(__file__), "../../qml/themes/themes.json")

DEFAULT_THEME_PALETTE: Dict[str, Dict[str, str]] = {
    "Light": {
        "mode": "Light",
        "bg": "#FFFFFF",
        "panel": "#F9FAFB",
        "panel2": "#F1F3F5",
        "accent": "#0E1116",
        "hover": "#E1E5EA",
        "text": "#0B0D10",
        "muted": "#5A626F",
        "btn_text": "#FFFFFF",
        "glow": "#1D2128",
    },
    "Dark": {
        "mode": "Dark",
        "bg": "#040405",
        "panel": "#0E0F11",
        "panel2": "#181A1E",
        "accent": "#F8FAFC",
        "hover": "#2A2D33",
        "text": "#F5F7FA",
        "muted": "#A4AAB4",
        "btn_text": "#050506",
        "glow": "#FFFFFF",
    }
}


def load_default_themes() -> Dict[str, Dict[str, Any]]:
    """Return sanitized default palette without reading the themes file."""
    return sanitize_theme_map(DEFAULT_THEME_PALETTE)


def load_themes_from_file(themes_file: str = THEMES_FILE) -> Dict[str, Dict[str, Any]]:
    """Load themes from the JSON file, falling back to defaults on failure.

    Returns:
        Tuple of (themes_dict, error_or_none).
    """
    if not os.path.exists(themes_file):
        return load_default_themes()
    try:
        with open(themes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_themes = data.get("themes", {})
        result = sanitize_theme_map(raw_themes if isinstance(raw_themes, dict) else {})
        if not result:
            return load_default_themes()
        return result
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger("theme.reload").warning(
            "Theme file load failed, falling back to defaults: %s", exc
        )
        return load_default_themes()
