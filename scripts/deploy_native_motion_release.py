"""Preserve, install, or restore a governed CSPM runtime without copying user data.

Reports and rollback configuration are local evidence and must stay outside Git.
The existing release deployment helper remains the only runtime replacement path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
USER_DIRECTORIES = frozenset(("data", "backups", "logs"))
USER_FILENAMES = frozenset((
    "user_settings.json", "machine_id.json", "candidate-machine.json",
    "candidate-profile.json", "prefs.json", "motion.json", "sync_state.json",
    "cloud_checkout_machine.json", "session_draft_snapshot.json",
    "runtime_session_state.json",
))
DATA_SUFFIXES = frozenset((".xls", ".xlsx", ".xlsm", ".xlsb", ".db", ".db3", ".sqlite", ".sqlite3"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _private(relative: Path) -> bool:
    return (relative.parts[0].lower() in USER_DIRECTORIES
            or relative.name.lower() in USER_FILENAMES
            or relative.name.lower().startswith("session_draft_snapshot"))


def _files(root: Path):
    if not root.is_dir() or root.is_symlink():
        raise ValueError("A real package directory is required")
    for directory, names, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            item = base / name
            if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                raise ValueError("Package links and junctions are prohibited")
        for name in filenames:
            item = base / name
            if item.is_symlink():
                raise ValueError("Package links are prohibited")
            yield item, item.relative_to(root)


def runtime_manifest(root: Path) -> dict:
    rows = [dict(path=relative.as_posix(), bytes=item.stat().st_size, sha256=sha256(item))
            for item, relative in _files(root) if not _private(relative)]
    rows.sort(key=lambda row: row["path"].casefold())
    if not any(row["path"] == "CSPM.exe" for row in rows):
        raise ValueError("Package is missing CSPM.exe")
    identity = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()
    return dict(schemaVersion=1, files=rows, fileCount=len(rows),
                bytes=sum(row["bytes"] for row in rows), manifestSha256=identity)


def _disjoint(*roots: Path) -> None:
    resolved = [root.resolve() for root in roots]
    if any(left == right or left in right.parents or right in left.parents
           for index, left in enumerate(resolved) for right in resolved[index + 1:]):
        raise ValueError("Package, installation, and rollback paths must not overlap")


def assert_idle(*roots: Path) -> None:
    """Read process paths; never terminate a process or print its command line."""
    if sys.platform != "win32":
        raise RuntimeError("Deployment process verification requires Windows")
    command = ("$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | "
               "Where-Object { $_.Name -in @('CSPM.exe','CSPM_Recovery.exe','QtWebEngineProcess.exe') } | "
               "Select-Object Name,ProcessId,ExecutablePath) | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, check=True)
    processes = json.loads(result.stdout.strip() or "[]")
    if isinstance(processes, dict):
        processes = [processes]
    roots = tuple(root.resolve() for root in roots)
    for process in processes:
        executable = process.get("ExecutablePath")
        if not executable:
            if str(process.get("Name", "")).lower().startswith("cspm"):
                raise RuntimeError("Cannot verify the path of a running CSPM process")
            continue
        path = Path(executable).resolve()
        if any(path == root or root in path.parents for root in roots):
            raise RuntimeError(f"Close the CSPM package process before deployment (PID {process['ProcessId']})")


def _motion_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "CSPM-Motion" / "motion.json"


def _settings_path() -> Path:
    if os.environ.get("CSPM_RUNTIME_DIR", "").strip():
        return Path(os.environ["CSPM_RUNTIME_DIR"]) / "user_settings.json"
    if os.environ.get("LOCALAPPDATA", "").strip():
        return Path(os.environ["LOCALAPPDATA"]) / "CSPM" / "user_settings.json"
    return Path.home() / ".cspm_data" / "user_settings.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")


def snapshot(installed: Path, rollback: Path) -> dict:
    installed, rollback = installed.resolve(), rollback.resolve()
    _disjoint(installed, rollback)
    if rollback.exists():
        raise FileExistsError("Rollback location already exists; it will never be overwritten")
    assert_idle(installed)
    _check_runtime_datasets(installed)
    before = runtime_manifest(installed)
    rollback.mkdir(parents=True, exist_ok=False)
    package = rollback / "package"
    package.mkdir()
    configuration = rollback / "configuration"
    configuration.mkdir()
    settings = []
    for item, relative in _files(installed):
        if relative.parts[0].lower() in USER_DIRECTORIES:
            continue
        destination = (configuration / "installation" / relative if _private(relative) else package / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        if _private(relative):
            settings.append(dict(path=destination.relative_to(rollback).as_posix(), sha256=sha256(destination)))
    for label, source in (("motion", _motion_path()), ("settings", _settings_path())):
        entry = dict(kind=label, originalPath=str(source.resolve()), existed=source.is_file())
        if source.is_file():
            destination = configuration / (label + ".json")
            shutil.copy2(source, destination)
            entry.update(path=destination.relative_to(rollback).as_posix(), sha256=sha256(destination))
        settings.append(entry)
    after = runtime_manifest(package)
    if before != after or before != runtime_manifest(installed):
        raise RuntimeError("Installation changed during snapshot; rollback is not verified")
    manifest = dict(schemaVersion=1, capturedUtc=datetime.now(timezone.utc).isoformat(),
                    installation=str(installed), runtime=after, configuration=settings,
                    datasetsCopied=False)
    _write_json(rollback / "rollback-manifest.json", manifest)
    verify_snapshot(rollback)
    return dict(action="snapshot", rollback=str(rollback), runtime=after, verified=True, datasetsCopied=False)


def _safe_relative(value: str) -> Path:
    normalized = PurePosixPath(value)
    if normalized.is_absolute() or not normalized.parts or any(part in ("..", ".") for part in normalized.parts):
        raise ValueError("Invalid rollback manifest path")
    path = Path(*normalized.parts)
    if path.is_absolute() or path.drive:
        raise ValueError("Invalid rollback manifest path")
    return path


def verify_snapshot(rollback: Path) -> dict:
    manifest = json.loads((rollback / "rollback-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1 or manifest.get("datasetsCopied") is not False:
        raise ValueError("Unsupported rollback manifest")
    if runtime_manifest(rollback / "package") != manifest["runtime"]:
        raise ValueError("Rollback runtime hash verification failed")
    for entry in manifest["configuration"]:
        if "path" in entry:
            source = rollback / _safe_relative(entry["path"])
            if rollback.resolve() not in source.resolve().parents or sha256(source) != entry["sha256"]:
                raise ValueError("Rollback configuration hash verification failed")
    return manifest


def _approved_templates(package: Path) -> dict:
    approval = package / "_internal" / "src" / "templates" / "template_approval.json"
    if not approval.is_file():
        return {}
    metadata = json.loads(approval.read_text(encoding="utf-8"))
    return {entry["approved_filename"]: entry["sha256"].upper()
            for entry in metadata.get("templates", []) if entry.get("human_approval_status") == "APPROVED"}


def _check_runtime_datasets(package: Path) -> None:
    approved = _approved_templates(package)
    for item, relative in _files(package):
        if _private(relative) or item.suffix.lower() not in DATA_SUFFIXES:
            continue
        parts = tuple(part.lower() for part in relative.parts)
        if (parts[:-1] != ("_internal", "src", "templates")
                or relative.name not in approved or sha256(item) != approved[relative.name]):
            raise ValueError("Unexpected dataset outside user data; cannot preserve it as runtime")


def validate_package(package: Path) -> dict:
    """Only governed empty templates may be present as workbook files."""
    approved = _approved_templates(package)
    for item, relative in _files(package):
        parts = tuple(part.lower() for part in relative.parts)
        if relative.name.lower() in USER_FILENAMES or relative.name.lower() == "native-motion-candidate.json":
            raise ValueError("Deployable release contains a private or candidate configuration")
        if parts[0] in ("logs", "backups"):
            raise ValueError("Deployable release contains runtime logs or backups")
        if item.suffix.lower() in DATA_SUFFIXES or parts[0] == "data":
            permitted = (len(parts) == 2 and parts[0] == "data") or (parts[:-1] == ("_internal", "src", "templates"))
            if not permitted or relative.name not in approved or sha256(item) != approved[relative.name]:
                raise ValueError("Deployable release contains an unapproved dataset or workbook")
    return runtime_manifest(package)


def _release_helper():
    specification = importlib.util.spec_from_file_location("cspm_governed_release", ROOT / "scripts" / "build_release.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.deploy_to_programs


def _deploy(package: Path, target: Path, expected: dict, *, restore: bool = False) -> Path:
    # The governed helper protects data/logs/backups but prunes other stale files.
    # A local overlay carries existing private configuration so it is preserved.
    overlay = target.parent / ("." + target.name + "-deployment-" + uuid.uuid4().hex)
    overlay.mkdir(parents=True, exist_ok=False)
    for item, relative in _files(package):
        if _private(relative) and not (relative.parts[0].lower() == "data" and not restore):
            continue
        destination = overlay / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(item, destination)
        except OSError:
            shutil.copy2(item, destination)
    for item, relative in _files(target):
        if _private(relative) and relative.parts[0].lower() not in USER_DIRECTORIES:
            destination = overlay / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
    assert_idle(package, target)
    _release_helper()(overlay, target)
    if runtime_manifest(target) != expected:
        raise RuntimeError("Post-deployment runtime manifest differs; use the verified rollback")
    return overlay


def install(package: Path, target: Path, rollback: Path) -> dict:
    package, target, rollback = package.resolve(), target.resolve(), rollback.resolve()
    _disjoint(package, target, rollback)
    assert_idle(package, target, rollback)
    saved = verify_snapshot(rollback)
    if Path(saved["installation"]).resolve() != target or runtime_manifest(target) != saved["runtime"]:
        raise ValueError("Verified rollback does not match the current installation")
    expected = validate_package(package)
    before_private = {relative.as_posix(): sha256(item) for item, relative in _files(target) if _private(relative)}
    overlay = _deploy(package, target, expected)
    if any(not (target / path).is_file() or sha256(target / path) != digest for path, digest in before_private.items()):
        raise RuntimeError("Private installation files changed during deployment")
    verify_snapshot(rollback)
    return dict(action="install", target=str(target), rollback=str(rollback), runtime=expected,
                overlay=str(overlay), verified=True, existingPrivateFilesUnchanged=True)


def restore(rollback: Path, target: Path) -> dict:
    rollback, target = rollback.resolve(), target.resolve()
    _disjoint(rollback, target)
    assert_idle(rollback, target)
    saved = verify_snapshot(rollback)
    if Path(saved["installation"]).resolve() != target:
        raise ValueError("Rollback belongs to a different installation")
    preserved = rollback.with_name(rollback.name + "-before-restore-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    snapshot(target, preserved)
    before_private = {relative.as_posix(): sha256(item) for item, relative in _files(target) if _private(relative)}
    overlay = _deploy(rollback / "package", target, saved["runtime"], restore=True)
    if any(not (target / path).is_file() or sha256(target / path) != digest for path, digest in before_private.items()):
        raise RuntimeError("Private installation files changed during restoration")
    motion = next(entry for entry in saved["configuration"] if entry.get("kind") == "motion")
    preference = _motion_path()
    preference.parent.mkdir(parents=True, exist_ok=True)
    temporary = preference.with_name("motion-restore-" + uuid.uuid4().hex + ".tmp")
    if motion["existed"]:
        shutil.copy2(rollback / _safe_relative(motion["path"]), temporary)
    else:
        temporary.write_text(json.dumps(dict(schemaVersion=1, engine="legacy")), encoding="utf-8")
    os.replace(temporary, preference)
    verify_snapshot(rollback)
    return dict(action="restore", target=str(target), rollback=str(rollback), preservedNewerRuntime=str(preserved),
                runtime=saved["runtime"], overlay=str(overlay), verified=True, existingPrivateFilesUnchanged=True,
                motionPreference="saved preference restored" if motion["existed"] else "legacy")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--snapshot", type=Path, metavar="INSTALLED")
    modes.add_argument("--install", type=Path, metavar="PACKAGE")
    modes.add_argument("--restore", type=Path, metavar="ROLLBACK")
    modes.add_argument("--manifest", type=Path, metavar="PACKAGE")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--rollback", type=Path)
    parser.add_argument("--report", type=Path, help="New local JSON evidence file; existing files are not overwritten")
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report exists; choose a new local evidence path")
    if args.snapshot and not args.rollback:
        parser.error("--snapshot requires --rollback")
    if args.install and (not args.target or not args.rollback):
        parser.error("--install requires --target and a verified --rollback")
    if args.restore and not args.target:
        parser.error("--restore requires --target")
    try:
        if args.snapshot:
            result = snapshot(args.snapshot, args.rollback)
        elif args.install:
            result = install(args.install, args.target, args.rollback)
        elif args.restore:
            result = restore(args.restore, args.target)
        else:
            result = dict(action="manifest", runtime=runtime_manifest(args.manifest), verified=True)
        if args.report:
            _write_json(args.report, result)
        summary = {key: value for key, value in result.items() if key != "runtime"}
        summary["runtime"] = {key: value for key, value in result["runtime"].items() if key != "files"}
        print(json.dumps(summary, indent=2))
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
