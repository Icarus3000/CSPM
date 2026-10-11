"""Local motion recovery preference, usable without Qt, data, or the bridge."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

MODES = ("native", "legacy", "reduced")


def preference_path() -> Path:
    # Deliberately independent of workbook preferences and checkout state.
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CSPM-Motion" / "motion.json"


def read_mode(path: Path | None = None) -> str:
    try:
        mode = json.loads((path or preference_path()).read_text(encoding="utf-8"))["engine"]
        return mode if mode in MODES else "native"
    except (OSError, ValueError, KeyError, TypeError):
        return "native"


def write_mode(mode: str, path: Path | None = None) -> None:
    if mode not in MODES:
        raise ValueError("Motion engine must be native, legacy, or reduced")
    path = path or preference_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="motion-", suffix=".json.tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schemaVersion": 1, "engine": mode}, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def handle_motion_arguments(argv: list[str]) -> None:
    """Run recovery before logging, QApplication, instance locks, or data I/O."""
    if "--motion-settings" in argv:
        from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout
        application = QApplication(argv)
        dialog = QDialog()
        dialog.setWindowTitle("CSPM Motion Settings")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose the motion engine for the next CSPM launch."))
        choices = QComboBox()
        for label, mode in (("Native Motion - Default", "native"), ("Legacy Motion - Fallback", "legacy"),
                            ("Reduced Motion - Immediate", "reduced")):
            choices.addItem(label, mode)
        choices.setCurrentIndex(MODES.index(read_mode()))
        layout.addWidget(choices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            write_mode(choices.currentData())
        application.quit()
        raise SystemExit(0)
    if "--set-motion-engine" not in argv:
        return
    parser = argparse.ArgumentParser(description="Set CSPM's local motion recovery preference")
    parser.add_argument("--set-motion-engine", choices=MODES, required=True)
    args = parser.parse_args(argv[1:])
    write_mode(args.set_motion_engine)
    raise SystemExit(0)


def system_reduced_motion() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    enabled = ctypes.c_int(1)
    # SPI_GETCLIENTAREAANIMATION: read only; never alters Windows preferences.
    accepted = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
    return bool(accepted and not enabled.value)
