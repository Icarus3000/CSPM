"""
utils/log.py — Shared logging configuration for CSPM.

Call ``configure_logging()`` early in main.py (or any entry point) to set
up the root logger with a consistent format.  All modules should use the
standard ``logging.getLogger(__name__)`` pattern — never call this module's
``configure_logging()`` more than once per process.
"""
from __future__ import annotations

import logging
import sys


def configure_logging(
    *,
    level: int = logging.INFO,
    verbose: bool = False,
) -> None:
    """
    Install a StreamHandler on the root logger with the CSPM house format.

    Args:
        level: Base log level (default INFO).  Overridden to DEBUG when
               ``verbose=True``.
        verbose: If True, sets the effective level to DEBUG.
    """
    effective_level = logging.DEBUG if verbose else level

    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g., called twice in the same process).
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(effective_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.addHandler(handler)
    root.setLevel(effective_level)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — returns ``logging.getLogger(name)``."""
    return logging.getLogger(name)
