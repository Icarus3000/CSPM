"""Immutable source-development capability for general layout/activation repairs.

Ordinary and frozen entrypoints are always disabled. This module contains no
motion selector, bridge, capture, native host, observer or animation dispatch.
"""
from pathlib import Path
import os
import sys

from PySide6.QtCore import QObject, Property


def _source_launcher_active() -> bool:
    if getattr(sys, "frozen", False):
        return False
    entry = getattr(sys.modules.get("__main__"), "__file__", None)
    if not entry:
        return False
    expected = Path(__file__).resolve().parents[3] / "scripts/launch_layout_repair_dev.py"
    return Path(entry).resolve() == expected and os.environ.get("CSPM_DEV_EXPERIMENTS") == "1"


class LayoutDevelopment(QObject):
    def __init__(self, parent=None, *, request_layout: bool = False, request_activation: bool = False):
        super().__init__(parent)
        authorized = _source_launcher_active()
        self._layout = authorized and request_layout and os.environ.get("CSPM_DEV_LAYOUT_REPAIRS") == "1"
        self._activation = authorized and request_activation and os.environ.get("CSPM_DEV_ACTIVATION_REPAIR") == "1"

    @Property(bool, constant=True)
    def layoutRepair(self) -> bool:
        return self._layout

    @Property(bool, constant=True)
    def activationRepair(self) -> bool:
        return self._activation


def resolve_development_capability(candidate=None) -> LayoutDevelopment:
    # Recheck at the normal application boundary; even a previously constructed
    # object cannot activate repairs through an ordinary/frozen entrypoint.
    if _source_launcher_active() and isinstance(candidate, LayoutDevelopment):
        return candidate
    return LayoutDevelopment()
