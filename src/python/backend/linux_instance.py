"""Per-user desktop instance ownership, independent of source/bundle location."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QLockFile


def acquire_instance_lock(candidate: bool = False) -> QLockFile | None:
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    name = "native-candidate" if candidate else "main"
    lock = QLockFile(str(root / f"cspm-{os.getuid()}-{name}.lock"))
    # A desktop app can run for days. Qt still detects crashed owners by PID;
    # elapsed time must never let another launch replace a live owner.
    lock.setStaleLockTime(0)
    return lock if lock.tryLock(0) else None
