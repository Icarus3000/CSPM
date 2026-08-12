"""Promote a complete PyInstaller package when Windows rejects directory rename.

The standard builder first quarantines the previous ``dist`` directory and then
tries to rename a complete staging directory into place.  Some Windows hosts
deny that rename even though the staged package is valid.  This fallback copies
only a fully hash-verified staged release, preserves the old package in
``to_delete``, and restores it if promotion cannot be verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ensure_within_project(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Path is outside the project root: {resolved}") from exc
    return resolved


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _tree_manifest(root: Path) -> dict[str, object]:
    entries: list[str] = []
    total_bytes = 0
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: str(item).casefold()):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        entries.append(f"{relative}|{size}|{_file_hash(path)}")
        total_bytes += size
    if not entries:
        raise ValueError(f"Release package is empty: {root}")
    manifest_digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest().upper()
    return {"fileCount": len(entries), "totalBytes": total_bytes, "sha256": manifest_digest}


def _validate_release_package(package_dir: Path) -> None:
    required = (
        package_dir / "CSPM" / "CSPM.exe",
        package_dir / "CSPM" / "CSPM_Recovery" / "CSPM_Recovery.exe",
        package_dir / "CSPM" / "_internal" / "assets" / "CS.svg",
        package_dir / "CSPM" / "_internal" / "assets" / "splash_logo.svg",
        package_dir / "CSPM" / "data" / "CSPM.xlsm",
        package_dir / "CSPM" / "data" / "Dockets.xlsm",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"Staged release is incomplete: {missing}")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def promote(source: Path, destination: Path, *, dry_run: bool) -> dict[str, object]:
    source = _ensure_within_project(source)
    destination = _ensure_within_project(destination)
    if not source.is_dir():
        raise ValueError(f"Staged release package is missing: {source}")
    if destination.name != "dist":
        raise ValueError(f"Release destination must be the project dist directory: {destination}")
    _validate_release_package(source)
    source_manifest = _tree_manifest(source)
    current_manifest = _tree_manifest(destination) if destination.is_dir() else None
    result: dict[str, object] = {
        "operation": "hash-verified manual release promotion",
        "source": str(source),
        "destination": str(destination),
        "sourceManifest": source_manifest,
        "currentManifest": current_manifest,
        "dryRun": dry_run,
    }
    if dry_run:
        result["ok"] = True
        return result

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = PROJECT_ROOT / f".release_promotion_staging_{stamp}"
    archive = PROJECT_ROOT / "to_delete" / f"dist__manual_replaced_release_{stamp}"
    if staging.exists() or archive.exists():
        raise ValueError("Generated promotion path already exists; retry the command.")
    shutil.copytree(source, staging, copy_function=shutil.copy2)
    staging_manifest = _tree_manifest(staging)
    if staging_manifest != source_manifest:
        raise RuntimeError("Staged copy does not match the verified release source.")

    moved_current = False
    try:
        if destination.exists():
            shutil.move(str(destination), str(archive))
            moved_current = True
        shutil.copytree(staging, destination, copy_function=shutil.copy2)
        destination_manifest = _tree_manifest(destination)
        if destination_manifest != source_manifest:
            raise RuntimeError("Promoted release package does not match the verified source.")
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        if moved_current and archive.exists():
            shutil.move(str(archive), str(destination))
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    result.update(
        {
            "ok": True,
            "archive": str(archive) if moved_current else None,
            "postPromotionManifest": destination_manifest,
            "promotedAtUtc": datetime.now(timezone.utc).isoformat(),
        }
    )
    _write_json(PROJECT_ROOT / "to_delete" / f"release_promotion_{stamp}.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = promote(args.source, args.destination, dry_run=args.dry_run)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
