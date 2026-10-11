"""Process-wide, inherited write boundary for an explicit data verification run."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ENVIRONMENT_KEY = "CSPM_VERIFY_DATA_READ_ONLY"


def enabled() -> bool:
    return os.environ.get(ENVIRONMENT_KEY, "").strip().lower() in {"1", "true", "yes", "on"}


def configure(argv: list[str] | None = None, settings: dict[str, Any] | None = None) -> bool:
    """Latch verification before repositories exist and inherit it in helpers.

    A false setting cannot weaken an explicit CLI/environment request within
    the same process. The next normal launch may use its saved policy.
    """
    requested = argv is not None and "--verify-data-read-only" in argv
    saved = settings is not None and settings.get("readOnlyVerification") is True
    if requested or saved:
        os.environ[ENVIRONMENT_KEY] = "1"
    return enabled()


def assert_writes_allowed() -> None:
    if enabled():
        raise PermissionError(
            "CSPM data verification is read-only. Workbook changes, schema migration, "
            "writer checkout and cloud publishing are disabled for this launch."
        )


def assert_separate_replica(local: str | Path, master: str | Path | None) -> None:
    """Verification uses a dedicated replica so runtime metadata cannot hit authority."""
    if enabled() and master and Path(local).resolve() == Path(master).resolve():
        raise PermissionError("Read-only verification requires a separate local replica; the governed source cannot be the runtime data folder.")
