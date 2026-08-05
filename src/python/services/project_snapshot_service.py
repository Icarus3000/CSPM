from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from services.paths import AppPaths


MANIFEST_FILE = "manifest.json"


class ProjectSnapshotService:
    """
    Create and restore full project snapshots required for operational continuity.

    Snapshot scope intentionally includes:
    - Core database (Excel workbook)
    - Runtime state (data/state + session draft)
    - Human + machine specs (docs/BIBLE.md + docs/spec + schema)
    - Raw import sources when present (data/raw + imports)
    """

    def __init__(self, paths: AppPaths):
        self.paths = paths

    def create_snapshot(self, reason: str = "manual") -> Optional[Path]:
        snapshot_dir = self._next_snapshot_dir()
        snapshot_dir.mkdir(parents=True, exist_ok=False)

        sources = self._snapshot_sources()
        copied_files: List[Dict[str, Any]] = []
        source_report: List[Dict[str, Any]] = []

        for source in sources:
            rel = source["path"]
            required = bool(source.get("required", False))
            src = self.paths.root / rel
            dst = snapshot_dir / rel

            if not src.exists():
                source_report.append(
                    {
                        "path": rel,
                        "required": required,
                        "exists": False,
                        "kind": "missing",
                    }
                )
                continue

            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied_files.append(self._file_record(dst, rel))
                source_report.append(
                    {
                        "path": rel,
                        "required": required,
                        "exists": True,
                        "kind": "file",
                    }
                )
                continue

            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)
                source_report.append(
                    {
                        "path": rel,
                        "required": required,
                        "exists": True,
                        "kind": "dir",
                    }
                )
                for child in sorted(dst.rglob("*")):
                    if not child.is_file():
                        continue
                    child_rel = child.relative_to(snapshot_dir).as_posix()
                    copied_files.append(self._file_record(child, child_rel))

        manifest = {
            "schema": "cspm.project_snapshot.v1",
            "snapshot_id": snapshot_dir.name,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "reason": (reason or "manual"),
            "root_path": str(self.paths.root),
            "sources": source_report,
            "files": copied_files,
            "summary": {
                "file_count": len(copied_files),
                "total_bytes": sum(int(row.get("bytes", 0)) for row in copied_files),
                "contains_core_database": any(
                    row.get("path") == "data/CSPM.xlsm" for row in copied_files
                ),
            },
            "restore_order": [
                "data/CSPM.xlsm",
                "data/state/",
                "data/raw/",
                "data/imports/",
                "imports/",
                "session_draft_snapshot.json",
                "docs/BIBLE.md",
                "docs/spec/",
                "schema/",
                "docs/ROADMAP.md",
                "docs/CHANGELOG.md",
                "user_settings.json",
            ],
        }
        (snapshot_dir / MANIFEST_FILE).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return snapshot_dir

    def list_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        snapshots_dir = self.paths.backups_snapshots_dir()
        if not snapshots_dir.exists():
            return []

        out: List[Dict[str, Any]] = []
        dirs = [p for p in snapshots_dir.iterdir() if p.is_dir()]
        dirs.sort(reverse=True, key=lambda p: p.name)

        capped = max(1, int(limit or 1))
        for p in dirs[:capped]:
            manifest = self._load_manifest(p)
            if manifest:
                summary = manifest.get("summary", {})
                out.append(
                    {
                        "snapshotId": str(manifest.get("snapshot_id", p.name)),
                        "createdAtUtc": str(manifest.get("created_at_utc", "")),
                        "reason": str(manifest.get("reason", "")),
                        "path": str(p),
                        "fileCount": int(summary.get("file_count", 0)),
                        "totalBytes": int(summary.get("total_bytes", 0)),
                        "containsCoreDatabase": bool(summary.get("contains_core_database", False)),
                    }
                )
            else:
                out.append(
                    {
                        "snapshotId": p.name,
                        "createdAtUtc": "",
                        "reason": "",
                        "path": str(p),
                        "fileCount": 0,
                        "totalBytes": 0,
                        "containsCoreDatabase": False,
                    }
                )
        return out

    def restore_snapshot(self, snapshot_id: str) -> bool:
        source_dir = self._resolve_snapshot_dir(snapshot_id)
        if source_dir is None or not source_dir.exists():
            return False

        # Safety net before applying restore.
        self.create_snapshot("pre-restore")

        manifest = self._load_manifest(source_dir)
        if manifest and isinstance(manifest.get("sources"), list):
            source_rows = cast(List[Dict[str, Any]], manifest["sources"])
        else:
            source_rows = self._snapshot_sources()

        for source in source_rows:
            rel = str(source.get("path", "")).strip()
            if not rel:
                continue
            src = source_dir / rel
            if not src.exists():
                continue
            dst = self.paths.root / rel
            self._copy_item(src, dst)
        return True

    def _snapshot_sources(self) -> List[Dict[str, Any]]:
        return [
            {"path": "data/CSPM.xlsm", "required": True},
            {"path": "data/state", "required": True},
            {"path": "session_draft_snapshot.json", "required": False},
            {"path": "docs/BIBLE.md", "required": True},
            {"path": "docs/spec", "required": True},
            {"path": "schema", "required": True},
            {"path": "data/raw", "required": False},
            {"path": "data/imports", "required": False},
            {"path": "imports", "required": False},
            {"path": "docs/ROADMAP.md", "required": True},
            {"path": "docs/CHANGELOG.md", "required": False},
            {"path": "user_settings.json", "required": False},
        ]

    def _next_snapshot_dir(self) -> Path:
        base = self.paths.backups_snapshots_dir()
        base.mkdir(parents=True, exist_ok=True)

        stem = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = base / stem
        suffix = 1
        while candidate.exists():
            candidate = base / f"{stem}_{suffix:02d}"
            suffix += 1
        return candidate

    def _resolve_snapshot_dir(self, snapshot_id: str) -> Optional[Path]:
        raw = str(snapshot_id or "").strip()
        if raw == "":
            return None
        p = Path(raw)
        if p.exists() and p.is_dir():
            return p
        candidate = self.paths.backups_snapshots_dir() / raw
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    def _copy_item(self, src: Path, dst: Path) -> None:
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True)

    def _load_manifest(self, snapshot_dir: Path) -> Optional[Dict[str, Any]]:
        manifest_path = snapshot_dir / MANIFEST_FILE
        if not manifest_path.exists():
            return None
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            return None
        return None

    def _file_record(self, file_path: Path, rel_path: str) -> Dict[str, Any]:
        size = 0
        try:
            size = int(file_path.stat().st_size)
        except Exception:
            size = 0
        return {
            "path": rel_path,
            "bytes": size,
            "sha256": self._sha256(file_path),
        }

    def _sha256(self, file_path: Path) -> str:
        h = hashlib.sha256()
        try:
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""
