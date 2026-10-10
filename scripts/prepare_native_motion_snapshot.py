"""Verify a governed cloud release and create an isolated acceptance snapshot.

Originals are read only. No lease is acquired and no publish method is called.
Provenance, records, and integrity details stay outside the repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
from services.paths import AppPaths
from services.workbook_integrity_service import WorkbookIntegrityService

FILES = ("CSPM.xlsm", "Dockets.xlsm")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest().upper()


def prepare(source: Path, destination: Path):
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise ValueError("Refusing to overwrite an existing acceptance profile")
    if destination == ROOT or ROOT in destination.parents or source in destination.parents:
        raise ValueError("Acceptance data must remain outside Git and outside the cloud authority")
    if (source / ".cspm_checkout.json").exists():
        raise ValueError("An active cloud checkout exists; verify the writer before taking an acceptance snapshot")
    releases = sorted((source / ".cspm_releases").glob("*/release.json"))
    if not releases:
        raise ValueError("No governed release manifest found")
    release_path = releases[-1]
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("schemaVersion") != 1 or set(release.get("files", {})) != set(FILES):
        raise ValueError("Invalid governed release manifest")
    before = {name: digest(source / name) for name in FILES}
    if before != release["files"]:
        raise ValueError("Canonical workbook pair differs from the latest governed release")
    for name in FILES:
        if digest(release_path.parent / name) != before[name]:
            raise ValueError("Governed release archive hash mismatch")
        with zipfile.ZipFile(source / name) as workbook:
            names = workbook.namelist()
            if workbook.testzip() is not None or not {"xl/workbook.xml", "[Content_Types].xml", "xl/_rels/workbook.xml.rels"}.issubset(names):
                raise ValueError("Workbook ZIP structure rejected")
            # Template-only VBA approval belongs to packaging, not to the
            # released live-data snapshot. Preserve every source ZIP member
            # byte-for-byte, including VBA; never execute workbook macros.
    report = WorkbookIntegrityService(AppPaths(ROOT)).check(source / "CSPM.xlsm")
    destination.mkdir(parents=True)
    (destination / "integrity.private.json").write_text(report.to_json(), encoding="utf-8")
    if not report.ok:
        raise ValueError(f"Canonical integrity rejected: {report.error_count} errors; private report retained")
    baseline, working = destination / "baseline", destination / "working" / "data"
    baseline.mkdir()
    working.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(source / name, baseline / name)
        shutil.copy2(baseline / name, working / name)
    after = {name: digest(source / name) for name in FILES}
    if before != after or any(digest(baseline / name) != before[name] or digest(working / name) != before[name] for name in FILES):
        raise ValueError("Source changed during snapshot or copy verification failed")
    if (source / ".cspm_checkout.json").exists():
        raise ValueError("A cloud writer acquired checkout during snapshot; reverify before acceptance")
    provenance = {"schemaVersion": 1, "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "release": release["releaseId"], "sourceHashes": before,
        "sourceModificationUtc": {name: datetime.fromtimestamp((source / name).stat().st_mtime, timezone.utc).isoformat() for name in FILES},
        "originalsUnchanged": True, "cloudWritesEnabled": False, "integrityPassed": True,
        "snapshotHashes": {name: digest(baseline / name) for name in FILES}}
    (destination / "snapshot.private.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    settings = {"appStyle": "Professional", "masterDataDir": "", "localDataDir": str(working),
                "keepTrayAlive": False, "runAtStartup": False, "autoBackupMinutes": 0}
    (destination / "working" / "user_settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    for name in FILES:
        (baseline / name).chmod(0o444)
    print(f"Snapshot verified: {report.tables_checked} tables; {report.rows_checked} rows; {report.warning_count} warnings")
    print("Authoritative pair unchanged; acceptance writes isolated; private provenance retained")
    return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    arguments = parser.parse_args()
    prepare(arguments.source, arguments.destination)
