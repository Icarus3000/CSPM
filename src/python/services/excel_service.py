from __future__ import annotations

from typing import Any, Dict

from repositories.excel_repo import ExcelRepo
from services.paths import AppPaths


class ExcelService:
    """
    Backward-compatible service shim.
    Canonical workbook behavior is implemented in repositories/excel_repo.py.
    """

    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.repo = ExcelRepo(paths)

    def ensure_workbook(self) -> None:
        self.repo.ensure_schema()

    def ensure_schema(self) -> None:
        self.repo.ensure_schema()

    def append_time_entry(self, payload: Dict[str, Any]) -> None:
        self.repo.add_time_entry(payload)
