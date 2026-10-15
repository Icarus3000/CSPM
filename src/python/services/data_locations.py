"""Host-local data selectors for launchers and Linux OneDrive discovery.

Discovery only reports complete, locally available packages. It never copies
data, claims a checkout, selects between different sources, or reads account
credentials. Explicit launcher selectors override saved machine-specific paths;
the isolated candidate policy is applied afterwards by the controller.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Mapping


DATA_ENVIRONMENT_KEYS = {
    "localDataDir": "CSPM_LOCAL_DATA_DIR",
    "masterDataDir": "CSPM_MASTER_DATA_DIR",
}
GOVERNED_WORKBOOKS = ("CSPM.xlsm", "Dockets.xlsm")


def environment_data_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    if os.name != "nt" and (re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("\\\\")):
        raise ValueError(f"{name} must name a Linux folder on this computer.")
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute data-folder path.")
    return path


def apply_environment_data_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Keep startup, deferred settings and later reloads on the same selectors."""
    resolved = dict(settings)
    for setting, environment_key in DATA_ENVIRONMENT_KEYS.items():
        selected = environment_data_path(environment_key)
        if selected is not None:
            resolved[setting] = str(selected)
    return resolved


def complete_workbook_package(folder: Path) -> bool:
    try:
        return all((folder / name).is_file() and (folder / name).stat().st_size > 0 for name in GOVERNED_WORKBOOKS)
    except OSError:
        return False


def fresh_replica_can_checkout(local: Path, master: Path | None) -> bool:
    """Only a missing workbook pair may bootstrap without the setup dialog.

    An incomplete existing pair is preserved for explicit recovery. Hash and
    ancestor validation still belongs to SyncService after it owns the lease.
    """
    if master is None or not complete_workbook_package(master):
        return False
    try:
        return local.resolve() != master.resolve() and not any(
            (local / name).exists() or (local / name).is_symlink()
            for name in GOVERNED_WORKBOOKS
        )
    except OSError:
        return False


def _is_fuse_mount(folder: Path) -> bool:
    """Identify a FUSE ancestor without querying remote files or credentials."""
    try:
        best: tuple[int, str] = (-1, "")
        folder = folder.resolve()
        for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
            before, after = line.split(" - ", 1)
            mountpoint = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), before.split()[4])
            mount = Path(mountpoint)
            if folder == mount or mount in folder.parents:
                depth = len(mount.parts)
                if depth > best[0]:
                    best = (depth, after.split()[0])
        return best[1].startswith("fuse")
    except (OSError, ValueError, IndexError):
        return False


def discover_onedrive_data_dirs(home: Path | None = None) -> list[Path]:
    """Return complete packages beneath native Linux OneDrive sync roots.

    Rclone/FUSE mounts are deliberately excluded: the writable replica and
    checkout marker need ordinary local filesystem semantics. Multiple results
    are returned for the caller to review without silently choosing a practice.
    """
    home = home or Path.home()
    roots = [home / "OneDrive"]
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))
    for config in sorted(config_home.glob("onedrive*/config")):
        try:
            for line in config.read_text(encoding="utf-8").splitlines():
                match = re.match(r'^\s*sync_dir\s*=\s*(".*")\s*(?:#.*)?$', line)
                if match:
                    value = json.loads(match.group(1))
                    # Expand against the inspected home, including fixture homes.
                    root = home / value[2:] if value.startswith("~/") else Path(value)
                    if root.is_absolute():
                        roots.append(root)
                    break
        except (OSError, ValueError, TypeError):
            continue
    found: list[Path] = []
    for root in roots:
        folder = root / "CSPM_Shared_Data"
        if not _is_fuse_mount(folder) and complete_workbook_package(folder):
            resolved = folder.resolve()
            if resolved not in found:
                found.append(resolved)
    return found
