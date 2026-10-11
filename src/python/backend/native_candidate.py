"""Fail-closed startup and immutable data boundary for side-by-side acceptance."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

_profile: Path | None = None


def profile() -> Path | None:
    return _profile


def settings_override() -> dict:
    """Pin every candidate load path to the disposable, cloud-disabled profile."""
    if _profile is None:
        return {}
    return dict(localDataDir=str(_profile / "working" / "data"), masterDataDir="",
                runAtStartup=False, keepTrayAlive=False, autoBackupMinutes=0,
                autoBackupIntervalMins=0)


def validate_profile(root: Path, *, diagnostic_only: bool = False) -> Path:
    root = root.resolve()
    provenance = json.loads((root / "snapshot.private.json").read_text(encoding="utf-8"))
    if provenance.get("schemaVersion") != 1:
        raise ValueError("Unsupported snapshot provenance")
    if diagnostic_only and (provenance.get("purpose") != "diagnostic_only"
                            or provenance.get("productionEligible") is not False):
        raise ValueError("Diagnostic profile must be explicitly ineligible for production")
    if provenance.get("integrityPassed") is not True and not diagnostic_only:
        raise ValueError("The protected dataset has not passed canonical integrity")
    if provenance.get("cloudWritesEnabled") is not False:
        raise ValueError("Candidate must have cloud publishing disabled")
    source = Path(provenance["source"]).resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Acceptance profile must not overlap the authority")
    for name in ("CSPM.xlsm", "Dockets.xlsm"):
        baseline = root / "baseline" / name
        actual = hashlib.sha256(baseline.read_bytes()).hexdigest().upper()
        if actual != provenance["sourceHashes"][name] or actual != provenance["snapshotHashes"][name]:
            raise ValueError("Protected baseline hash mismatch")
        if not (root / "working" / "data" / name).is_file():
            raise ValueError("Acceptance working workbook is missing")
    return root


def configure() -> None:
    global _profile
    if not getattr(sys, "frozen", False):
        return
    marker = Path(getattr(sys, "_MEIPASS")) / "native-motion-candidate.json"
    if not marker.exists():
        return
    executable_root = Path(sys.executable).resolve().parent
    sidecar = executable_root / "candidate-profile.json"
    try:
        configuration = json.loads(sidecar.read_text(encoding="utf-8"))
        package = json.loads(marker.read_text(encoding="utf-8"))
        diagnostic_only = configuration.get("diagnosticOnly") is True
        if diagnostic_only and package.get("technicalQualificationComplete") is not False:
            raise ValueError("Qualified packages cannot bypass the production data gate")
        root = validate_profile(Path(configuration["profile"]), diagnostic_only=diagnostic_only)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # This path runs before Qt, the workspace, cloud sync or bridge loading.
        # A small native dialog gives a recovery action instead of blank startup.
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                "CSPM Native Motion Candidate cannot open: the protected latest-data snapshot is missing or failed validation. "
                "The production application and shared data have not been changed. "
                "See the candidate validation record before configuring a snapshot.",
                "CSPM Native Motion Candidate", 0x10)
        raise SystemExit(2) from exc
    _profile = root
    working = root / "working"
    # Read-only bootstrap also applies to startup worker processes. Folder
    # preferences are pinned in memory by AppController and AppPaths, avoiding
    # concurrent rewriting of settings during helper-process startup.
    os.environ.update(CSPM_RUNTIME_DIR=str(working), CSPM_DATA_DIR=str(working),
                      CSPM_EXECUTABLE_ROOT=str(working), CSPM_LOG_DIR=str(working / "logs"),
                      CSPM_EXPORT_DIR=str(working / "exports"),
                      CSPM_MACHINE_ID_FILE=str(working / "candidate-machine.json"))
