from __future__ import annotations

from services.paths import AppPaths
from services.workspace_dump_service import WorkspaceDumpService


def main() -> int:
    root = AppPaths.project_root()
    svc = WorkspaceDumpService(AppPaths(root))
    out = svc.dump_workspace()
    print(f"Dump written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
