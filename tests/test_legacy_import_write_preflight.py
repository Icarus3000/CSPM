from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.app_controller import AppController


class _WriteLease:
    def __init__(self, error: str = "") -> None:
        self.error = error

    def assert_write_lease(self) -> None:
        if self.error:
            raise PermissionError(self.error)


def test_legacy_import_preflight_reports_writer_checkout() -> None:
    controller = SimpleNamespace(_sync_service=_WriteLease())

    result = AppController.legacyDocketsImportWritePreflight(controller)

    assert result == {"ok": True, "message": "Shared data is checked out for writing."}


def test_legacy_import_preflight_preserves_read_only_reason() -> None:
    message = "Both the local replica and cloud authority changed."
    controller = SimpleNamespace(_sync_service=_WriteLease(message))

    result = AppController.legacyDocketsImportWritePreflight(controller)

    assert result == {"ok": False, "message": message}


def test_import_ui_checks_write_access_before_opening_progress() -> None:
    qml = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "qml"
        / "views"
        / "LegacyDocketsImportView.qml"
    ).read_text(encoding="utf-8")
    for function_name in ("function startImport()", "function startFilteredImport(allowedRows)"):
        function_start = qml.index(function_name)
        next_function = qml.find("\n    function ", function_start + len(function_name))
        body = qml[function_start : next_function if next_function >= 0 else len(qml)]
        assert body.index("legacyDocketsImportWritePreflight") < body.index("progressPopup.open()")
