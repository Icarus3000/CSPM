"""
startup_config.py — Splash timeline constants and environment helpers.

Extracted from main.py to keep the entry-point focused on wiring.
Import these values/functions in main.py to use them.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project-level paths
# ---------------------------------------------------------------------------

# Two levels up from src/python/ → project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

SPLASH_LOGO_CLEAN_PATH: Path = PROJECT_ROOT / "assets" / "CS.svg"
SPLASH_LOGO_ANIMATED_PATH: Path = PROJECT_ROOT / "assets" / "splash_logo.svg"
SPLASH_AUDIO_PATHS: list[Path] = [
    PROJECT_ROOT / "assets" / "splash_sound.wav",
    PROJECT_ROOT / "assets" / "splash_sound.mp3",
]

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def env_flag(name: str, default: bool = False) -> bool:
    """Return True if the named env var is set to a truthy string."""
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    """Parse a float env var, clamped to [min_value, max_value]."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except (ValueError, TypeError):
        return default
    return max(min_value, min(max_value, value))


def env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    """Parse an int env var, clamped to [min_value, max_value]."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return default
    return max(min_value, min(max_value, value))


# ---------------------------------------------------------------------------
# Splash logo path selector
# ---------------------------------------------------------------------------


def splash_logo_paths() -> list[Path]:
    """Return logo paths in preference order based on CSPM_SPLASH_LOGO_VARIANT."""
    variant = os.environ.get("CSPM_SPLASH_LOGO_VARIANT", "animated").strip().lower()
    if variant in ("clean", "static"):
        return [SPLASH_LOGO_CLEAN_PATH, SPLASH_LOGO_ANIMATED_PATH]
    return [SPLASH_LOGO_ANIMATED_PATH, SPLASH_LOGO_CLEAN_PATH]


# ---------------------------------------------------------------------------
# Feature flags (read once at import time for convenience)
# ---------------------------------------------------------------------------

VERBOSE_TERMINAL_LOGGING: bool = env_flag("CSPM_VERBOSE_LOGGING", False)
SPLASH_TIMELINE_LOGGING: bool = env_flag("CSPM_SPLASH_TIMELINE_LOGGING", False)
DEBUG_FRAMES_ENABLED: bool = env_flag("CSPM_DEBUG_FRAMES", False)
