from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.paths import AppPaths


class WorkspaceDumpService:
    def __init__(self, paths: AppPaths):
        self.paths = paths

    def dump_workspace(self) -> Path:
        out_dir = self.paths.dumps_workspace_dir()
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_path = out_dir / f"workspace_dump_{ts}.txt"

        root = self.paths.root
        lines = []
        lines.append("WORKSPACE DUMP")
        lines.append(f"Root: {root}")
        lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
        lines.append("")

        lines.append("FOLDERS:")
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                rel = p.relative_to(root)
                lines.append(f"  [D] {rel}")

        lines.append("")
        lines.append("FILES:")
        for p in sorted(root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root)
                try:
                    size = p.stat().st_size
                except Exception:
                    size = -1
                lines.append(f"  [F] {rel} ({size} bytes)")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path
