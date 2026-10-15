"""Open exported documents using the current desktop's file associations."""
from __future__ import annotations

import os
from pathlib import Path
import sys


def system_process_environment() -> dict[str, str]:
    """Keep bundled Qt/glibc plugin paths out of external desktop programs."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        original = env.pop("LD_LIBRARY_PATH_ORIG", "")
        if original:
            env["LD_LIBRARY_PATH"] = original
        else:
            env.pop("LD_LIBRARY_PATH", None)
        for name in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
            env.pop(name, None)
    return env


def open_local_file(path: str | Path) -> None:
    target = Path(path).expanduser().resolve()
    if os.name == "nt":
        os.startfile(str(target))
        return
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
        raise OSError(f"The desktop could not open {target.name}.")


def configure_linux_autostart(enabled: bool) -> None:
    folder = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart"
    target = folder / "cspm.desktop"
    if not enabled:
        target.unlink(missing_ok=True)
        return
    folder.mkdir(parents=True, exist_ok=True)
    command = ["/usr/bin/env", "QT_QPA_PLATFORM=xcb",
               "CSPM_LOW_PERF=" + os.environ.get("CSPM_LOW_PERF", "0"), sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve().parents[1] / "main.py"))
    command.append("--tray-only")
    def quote(value: str) -> str:
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    target.write_text(
        "[Desktop Entry]\nType=Application\nName=CSPM\n"
        "Exec=" + " ".join(map(quote, command)) + "\n"
        "Terminal=false\nStartupNotify=false\nX-KDE-autostart-after=panel\n",
        encoding="utf-8",
    )
