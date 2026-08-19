"""Crash-isolated Practice Briefing snapshot worker.

``openpyxl`` parsing happens in a short-lived helper process so a native parser
fault cannot terminate the GUI process while the native splash is visible.
The parent passes a private copied data directory; this worker may therefore
run the repository's defensive schema checks without touching live workbooks.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _read_request(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Startup briefing worker request must be an object.")
    return payload


def collect_startup_briefing(request: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-safe, read-only briefing snapshot from copied workbooks."""
    root = Path(str(request.get("root") or "")).resolve()
    data_dir = Path(str(request.get("dataDir") or "")).resolve()
    filters = request.get("filters") if isinstance(request.get("filters"), dict) else {}
    if not root.is_dir():
        raise ValueError(f"Startup briefing worker root is unavailable: {root}")
    if not (data_dir / "CSPM.xlsm").is_file():
        raise ValueError(f"Startup briefing workbook is unavailable: {data_dir / 'CSPM.xlsm'}")

    from repositories.excel_repo import ExcelRepo
    from services.paths import AppPaths

    paths = AppPaths(root, override_data_dir=data_dir)
    payload = ExcelRepo(paths).practice_briefing(dict(filters))
    if not isinstance(payload, dict) or not bool(payload.get("ok")):
        raise RuntimeError("The Practice Briefing data snapshot could not be read.")
    return dict(payload)


def run(request_path: Path, result_path: Path) -> int:
    try:
        payload = collect_startup_briefing(_read_request(request_path))
    except BaseException as exc:
        _write_result(
            result_path,
            {
                "ok": False,
                "error": str(exc) or type(exc).__name__,
                "traceback": traceback.format_exc(),
            },
        )
        return 1

    _write_result(result_path, {"ok": True, "payload": payload})
    return 0


def run_from_argv(argv: list[str] | None = None) -> int:
    values = list(sys.argv if argv is None else argv)
    try:
        marker_index = values.index("--startup-briefing-worker")
        request_path = Path(values[marker_index + 1])
        result_path = Path(values[marker_index + 2])
    except (ValueError, IndexError):
        return 2
    return run(request_path, result_path)

