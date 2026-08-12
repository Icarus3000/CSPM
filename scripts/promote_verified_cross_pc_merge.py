"""Atomically promote a verified two-workbook merge package with rollback.

The command accepts a previously validated candidate and two explicit live data
directories.  It snapshots the current local and canonical shared packages to
two dated recovery locations before staging either replacement.  Each file is
replaced atomically; any replacement or verification failure restores both
destinations from their snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_FILES = ("CSPM.xlsm", "Dockets.xlsm")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Cannot read required JSON artifact {path}: {exc}") from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def _candidate_hashes(candidate_dir: Path) -> dict[str, str]:
    return {name: _sha256(candidate_dir / name) for name in PACKAGE_FILES}


def _verify_candidate(candidate_dir: Path) -> dict[str, str]:
    candidate_dir = candidate_dir.resolve()
    if candidate_dir.name.startswith("CSPM_MergeCandidate_") is False:
        raise ValueError("Candidate directory name must start with CSPM_MergeCandidate_.")
    for name in PACKAGE_FILES:
        if not (candidate_dir / name).is_file():
            raise ValueError(f"Candidate package file is missing: {candidate_dir / name}")
    validation = _read_json(candidate_dir / "merge_validation.json")
    integrity = _read_json(candidate_dir / "cspm_integrity.json")
    repair = _read_json(candidate_dir / "legacy_reconciliation_repair.json")
    if not validation.get("ok"):
        raise ValueError("Candidate validation report is not successful.")
    if integrity.get("ok") is not True or integrity.get("issues"):
        raise ValueError("Candidate integrity report contains errors or warnings.")
    if repair.get("status") != "candidate-repaired-awaiting-validation":
        raise ValueError("Candidate repair artifact is absent or has an unexpected status.")
    hashes = _candidate_hashes(candidate_dir)
    declared = validation.get("hashes", {}).get("candidate", {})
    if hashes != {name: str(declared.get(name, "")).upper() for name in PACKAGE_FILES}:
        raise ValueError("Candidate workbook hashes no longer match merge_validation.json.")
    integrity_hash = str(integrity.get("workbookSha256", "")).upper()
    if integrity_hash != hashes["CSPM.xlsm"]:
        raise ValueError("Candidate CSPM hash no longer matches cspm_integrity.json.")
    return hashes


def _all_backup_sources(data_dir: Path) -> list[Path]:
    sources: list[Path] = []
    for name in PACKAGE_FILES:
        source = data_dir / name
        if not source.is_file():
            raise ValueError(f"Live package file is missing: {source}")
        sources.append(source)
    for source in sorted(data_dir.rglob("*.bak")):
        if source.is_file():
            sources.append(source)
    return sources


def _snapshot(data_dir: Path, archive_dir: Path) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for source in _all_backup_sources(data_dir):
        relative = source.relative_to(data_dir)
        destination = archive_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        source_hash = _sha256(source)
        backup_hash = _sha256(destination)
        if source_hash != backup_hash:
            raise RuntimeError(f"Backup hash mismatch for {source}.")
        entries[str(relative)] = {"sourceSha256": source_hash, "backupSha256": backup_hash}
    return entries


def _replace_from(source: Path, target: Path) -> None:
    temporary = target.parent / f".{target.name}.cspm-promotion-{uuid.uuid4().hex}.tmp"
    try:
        shutil.copy2(source, temporary)
        if _sha256(temporary) != _sha256(source):
            raise RuntimeError(f"Staged hash mismatch for {target}.")
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _assert_live_hashes_unchanged(data_dir: Path, expected: dict[str, dict[str, str]]) -> None:
    for name in PACKAGE_FILES:
        expected_hash = expected[name]["sourceSha256"]
        actual_hash = _sha256(data_dir / name)
        if actual_hash != expected_hash:
            raise RuntimeError(f"Live {data_dir / name} changed after its backup was captured.")


def _protect_recovery_archive(archive_dir: Path) -> None:
    for path in archive_dir.rglob("*"):
        if path.is_file():
            try:
                os.chmod(path, path.stat().st_mode | stat.S_IREAD)
            except OSError:
                pass


def _destination_hashes(data_dir: Path) -> dict[str, str]:
    return {name: _sha256(data_dir / name) for name in PACKAGE_FILES}


def promote(
    candidate_dir: Path,
    local_dir: Path,
    shared_dir: Path,
    local_archive: Path,
    exchange_archive: Path,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    candidate_dir = candidate_dir.resolve()
    local_dir = local_dir.resolve()
    shared_dir = shared_dir.resolve()
    local_archive = local_archive.resolve()
    exchange_archive = exchange_archive.resolve()
    if local_dir == shared_dir:
        raise ValueError("Local and canonical shared data directories must be distinct.")
    if local_archive.exists() or exchange_archive.exists():
        raise ValueError("Promotion archive destination already exists.")
    candidate_hashes = _verify_candidate(candidate_dir)
    targets = {"currentComputerLocal": local_dir, "canonicalOneDriveShared": shared_dir}
    preflight = {
        name: {"path": str(path), "hashes": _destination_hashes(path)}
        for name, path in targets.items()
    }
    if dry_run:
        return {
            "ok": True,
            "dryRun": True,
            "candidate": str(candidate_dir),
            "candidateHashes": candidate_hashes,
            "preflight": preflight,
        }

    local_archive.mkdir(parents=True, exist_ok=False)
    exchange_archive.mkdir(parents=True, exist_ok=False)
    archives = {"localRecovery": local_archive, "oneDriveExchangeRecovery": exchange_archive}
    manifest: dict[str, Any] = {
        "operation": "verified cross-PC workbook package promotion",
        "preparedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "prepared-before-promotion",
        "candidate": str(candidate_dir),
        "candidateHashes": candidate_hashes,
        "destinations": preflight,
        "archives": {name: str(path) for name, path in archives.items()},
        "backups": {},
    }
    manifest_paths = [path / "promotion_manifest.json" for path in archives.values()]
    try:
        for archive_name, archive_root in archives.items():
            archive_backup: dict[str, dict[str, dict[str, str]]] = {}
            for target_name, target_dir in targets.items():
                archive_backup[target_name] = _snapshot(target_dir, archive_root / f"{target_name}_before")
            manifest["backups"][archive_name] = archive_backup
        for manifest_path in manifest_paths:
            _write_json(manifest_path, manifest)

        for target_name, target_dir in targets.items():
            _assert_live_hashes_unchanged(target_dir, manifest["backups"]["localRecovery"][target_name])

        replaced: dict[str, list[str]] = {name: [] for name in targets}
        try:
            for target_name, target_dir in targets.items():
                for package_name in PACKAGE_FILES:
                    _replace_from(candidate_dir / package_name, target_dir / package_name)
                    replaced[target_name].append(package_name)
            post_hashes = {name: _destination_hashes(path) for name, path in targets.items()}
            for target_name, hashes in post_hashes.items():
                if hashes != candidate_hashes:
                    raise RuntimeError(f"Post-promotion hash mismatch in {target_name}.")
        except Exception:
            rollback_errors: list[str] = []
            for target_name, target_dir in targets.items():
                backup_dir = local_archive / f"{target_name}_before"
                for package_name in replaced[target_name]:
                    try:
                        _replace_from(backup_dir / package_name, target_dir / package_name)
                    except Exception as rollback_exc:
                        rollback_errors.append(f"{target_name}/{package_name}: {rollback_exc}")
            if rollback_errors:
                raise RuntimeError(f"Promotion failed and rollback was incomplete: {rollback_errors}")
            raise

        manifest.update(
            {
                "status": "promoted-and-hash-verified",
                "promotedAtUtc": datetime.now(timezone.utc).isoformat(),
                "postPromotionHashes": post_hashes,
                "destinationHashesMatchCandidate": True,
            }
        )
        for manifest_path in manifest_paths:
            _write_json(manifest_path, manifest)
        for archive_root in archives.values():
            _protect_recovery_archive(archive_root)
        return {"ok": True, "dryRun": False, "manifest": manifest}
    except Exception as exc:
        manifest.update(
            {
                "status": "promotion-failed-live-files-rolled-back-or-untouched",
                "failedAtUtc": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
        )
        for manifest_path in manifest_paths:
            _write_json(manifest_path, manifest)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--local-dir", type=Path, required=True)
    parser.add_argument("--shared-dir", type=Path, required=True)
    parser.add_argument("--local-archive", type=Path, required=True)
    parser.add_argument("--exchange-archive", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = promote(
            args.candidate_dir,
            args.local_dir,
            args.shared_dir,
            args.local_archive,
            args.exchange_archive,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
