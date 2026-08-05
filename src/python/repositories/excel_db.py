"""
Backward-compatible Excel database adapter.

This module used to carry a near-duplicate implementation of the workbook
repository. The canonical implementation now lives in ``excel_repo.py``.
Keep this shim so existing imports continue to work while ownership is unified.
"""

from repositories.excel_repo import *  # noqa: F401,F403
from repositories.excel_repo import ExcelRepo


class ExcelDatabase(ExcelRepo):
    """Compatibility alias for legacy call sites."""


__all__ = [name for name in globals() if not name.startswith("_")]
