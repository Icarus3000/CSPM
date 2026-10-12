"""Path-safe application identity from governed packaging metadata."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication


UNAVAILABLE = "Unavailable"


def _read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _safe_token(value, pattern: str) -> str:
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else UNAVAILABLE


def version_information(metadata: dict, version: dict, *, executable: Path | None,
                        motion: str, local_timezone=None) -> dict:
    """Whitelist display/copy fields; never pass through raw metadata or paths."""
    result = {
        "product": "CSPM",
        "version": _safe_token(metadata.get("version", version.get("version")), r"\d+\.\d+\.\d+(?:[.-][A-Za-z0-9]+)*"),
        "codename": _safe_token(metadata.get("codename", version.get("codename")), r"Phase \d+"),
        "versionBuild": _safe_token(metadata.get("versionBuild", version.get("build")), r"\d+"),
        "sourceSha": _safe_token(metadata.get("sourceSha"), r"[0-9a-fA-F]{40}"),
        "sourceStatus": _safe_token(metadata.get("sourceStatus"), r"clean|modified"),
        "buildUtc": UNAVAILABLE,
        "buildLocal": UNAVAILABLE,
        "executableSha256": UNAVAILABLE if executable is not None else "Not packaged (source run)",
        "motionPreference": motion if motion in {"native", "legacy", "reduced"} else UNAVAILABLE,
    }
    try:
        stamp = datetime.fromisoformat(metadata["buildTimestampUtc"].replace("Z", "+00:00"))
        if stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0:
            result["buildUtc"] = stamp.astimezone(timezone.utc).isoformat(timespec="microseconds") + " (UTC)"
            result["buildLocal"] = stamp.astimezone(local_timezone).isoformat(timespec="microseconds")
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        pass
    if executable is not None:
        try:
            digest = hashlib.sha256()
            with executable.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result["executableSha256"] = digest.hexdigest().upper()
        except OSError:
            pass
    return result


def copy_text(information: dict) -> str:
    # Constructed only from the sanitized snapshot, never filenames/settings.
    return "\n".join((
        "Product: CSPM",
        f"Version: {information['version']} ({information['codename']}, build {information['versionBuild']})",
        f"Source Git SHA: {information['sourceSha']}",
        f"Source status: {information['sourceStatus']}",
        f"Build UTC: {information['buildUtc']}",
        f"Build local: {information['buildLocal']}",
        f"Executable SHA-256: {information['executableSha256']}",
        f"Motion preference: {information['motionPreference']}",
    ))


class AboutInformation(QObject):
    def __init__(self, motion, parent=None, *, root: Path | None = None,
                 executable: Path | None = None, frozen: bool | None = None):
        super().__init__(parent)
        self._motion = motion
        self._frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        self._root = root or (Path(sys._MEIPASS) if self._frozen else Path(__file__).resolve().parents[3])
        self._executable = executable or (Path(sys.executable) if self._frozen else None)
        self._version = _read_object(self._root / "version.json")
        self._metadata = _read_object(self._root / "release-provenance.json") if self._frozen else {}
        self._snapshot = None

    def _source_identity(self) -> None:
        if self._frozen or self._metadata:
            return
        try:
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self._root, text=True,
                                          stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).strip()
            status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"],
                                             cwd=self._root, text=True, stderr=subprocess.DEVNULL,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._metadata = {"sourceSha": sha, "sourceStatus": "modified" if status.strip() else "clean"}
        except (OSError, subprocess.SubprocessError):
            pass

    @Slot(bool, result="QVariantMap")
    def information(self, reduced: bool = False) -> dict:
        self._source_identity()
        motion = "reduced" if reduced or self._motion.reducedMotion else self._motion.engine
        if self._snapshot is None:
            self._snapshot = version_information(self._metadata, self._version,
                                                 executable=self._executable, motion=motion)
        self._snapshot["motionPreference"] = motion if motion in {"native", "legacy", "reduced"} else UNAVAILABLE
        return dict(self._snapshot)

    @Slot(bool, result=bool)
    def copyVersionInformation(self, reduced: bool = False) -> bool:
        if not isinstance(QGuiApplication.instance(), QGuiApplication):
            return False
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(copy_text(self.information(reduced)))
        return True
