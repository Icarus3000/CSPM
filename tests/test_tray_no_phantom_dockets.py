"""Regression tests: no phantom dockets from the tray, and tray Cancel never deletes saved dockets.

Background (2026-10-19): closing CSPM force-saved a paused tray timer that carried a
previous day's 2:48:00 onto another client/matter, creating a billable phantom docket
("Auto-saved on system shutdown"). These tests lock in the fixed behaviour:

* exit/shutdown never writes CSPM.xlsm / Dockets.xlsm — unsaved time is kept as a local
  draft and restored as a paused tab next launch;
* a paused main docket form never spawns a tray timer;
* changing client/matter never carries saved time to another docket;
* tray Cancel only discards UNSAVED time and refuses saved dockets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import openpyxl
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "tests"))

from backend.controllers.tray_controller import TrayController  # noqa: E402
from domain import schema_constants as sc  # noqa: E402
from repositories.excel_repo import TBL_CLIENTS, TBL_MATTERS, TBL_TIME  # noqa: E402
from test_tray_timer_and_legacy_dockets_sync import _create_isolated_cspm_repo  # noqa: E402

CLIENT_1 = "Megatech Integrated Services Ltd."
MATTER_1 = "MEGA-COR-26-0093 \u2014 Corporate Reorganization"
CLIENT_2 = "1377041 Ontario Inc."
MATTER_2 = "1371-GEN-26-0109 \u2014 General Advice"


def _setup(tmp_path: Path, *, sqlite_available: bool = False):
    _app = QCoreApplication.instance() or QCoreApplication([])
    paths, repo, legacy_path = _create_isolated_cspm_repo(tmp_path)
    repo._upsert_row_by_key(
        TBL_CLIENTS,
        sc.COL_CLIENT_ID,
        "1377",
        {sc.COL_CLIENT_ID: "1377", sc.COL_CLIENT_NAME: CLIENT_2, sc.COL_CLIENT_ACTIVE: True},
    )
    repo._upsert_row_by_key(
        TBL_MATTERS,
        sc.COL_MATTER_ID,
        "MAT-002",
        {
            sc.COL_MATTER_ID: "MAT-002",
            sc.COL_MATTER_NUMBER: "1371-GEN-26-0109",
            sc.COL_MATTER_CLIENT_ID: "1377",
            sc.COL_MATTER_CLIENT_NAME: CLIENT_2,
            sc.COL_MATTER_NAME: "General Advice",
            sc.COL_MATTER_STATUS: "Open",
            sc.COL_MATTER_DEF_RATE: 475.0,
            sc.COL_MATTER_DEF_SHARE: 100.0,
        },
    )
    if not sqlite_available:
        # Production today: the packaged exe has no working SQLite layer.
        repo._get_sqlite_repo = lambda: None
    app_controller = SimpleNamespace(
        _excel_repo=repo,
        _paths=paths,
        _theme_name="Dark",
        _tray_icon=MagicMock(),
        saveTimeDocketEntry=lambda payload: repo.add_time_entry(payload),
    )
    return paths, repo, legacy_path, app_controller


def _time_rows(repo) -> list[dict]:
    return list(repo._read_table_rows(TBL_TIME) or [])


def _legacy_row_count(legacy_path: Path) -> int:
    wb = openpyxl.load_workbook(legacy_path, read_only=True)
    try:
        return int(wb.worksheets[0].max_row or 0)
    finally:
        wb.close()


def _recovery_entries(paths) -> dict:
    p = paths.timer_recovery_path()
    if not p.exists():
        return {}
    return dict(json.loads(p.read_text(encoding="utf-8")).get("entries") or {})


def test_shutdown_keeps_unsaved_timer_as_local_draft_and_creates_no_docket(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    legacy_rows_before = _legacy_row_count(legacy_path)

    tray = TrayController(app_controller)
    assert tray.startNewTimerWithManualTime(CLIENT_1, MATTER_1, "", "2h 48m")
    assert tray.hasRunningTimer is True
    tray.shutdown()

    # Nothing billable was written anywhere.
    assert _time_rows(repo) == []
    assert _legacy_row_count(legacy_path) == legacy_rows_before
    # The unsaved time was kept locally as a PAUSED draft.
    entries = _recovery_entries(paths)
    assert len(entries) == 1
    rec = next(iter(entries.values()))
    assert rec["entry_status"] == "PAUSED"
    assert int(rec["raw_seconds"]) >= 10080
    assert rec.get("description", "") == ""  # no placeholder text is ever written

    # Next launch restores it as a paused tab (once), still unsaved.
    tray2 = TrayController(app_controller)
    assert len(tray2.activeTimers) == 1
    restored = tray2.activeTimers[0]
    assert restored.isRunning is False
    assert restored.elapsedSeconds >= 10080
    assert "Megatech" in restored.clientName
    rec_result = tray2.reconcileUnsyncedDocketsOnStartup()
    assert rec_result["restoredLocalDrafts"] == 1
    assert len(tray2.activeTimers) == 1  # no duplicate on the second reconcile
    assert _time_rows(repo) == []
    tray2._pause_sync_quit_completed = True
    tray2.shutdown()


def test_paused_main_form_never_spawns_tray_timer_or_phantom(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    tray = TrayController(app_controller)

    # Main docket form merely DISPLAYING a saved 2:48 docket (not running).
    tray.syncMainTimerState({
        "ownerId": "main_timer",
        "isRunning": False,
        "elapsedSeconds": 10080,
        "clientName": CLIENT_2,
        "matterName": "1371-GEN-26-0109",
        "description": "",
        "entryId": "",
    })
    assert len(tray.activeTimers) == 0
    assert tray.hasUnsavedOrActiveDocketOnClose() is False
    tray.shutdown()
    assert _time_rows(repo) == []
    assert _recovery_entries(paths) == {}


def test_main_form_switching_client_never_carries_seconds(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    tray = TrayController(app_controller)

    tray.syncMainTimerState({
        "ownerId": "main_timer",
        "isRunning": True,
        "elapsedSeconds": 600,
        "clientName": CLIENT_1,
        "matterName": "MEGA-COR-26-0093",
    })
    assert len(tray.activeTimers) == 1
    tray.syncMainTimerState({
        "ownerId": "main_timer",
        "isRunning": False,
        "elapsedSeconds": 600,
        "clientName": CLIENT_2,
        "matterName": "1371-GEN-26-0109",
    })
    # The original timer keeps its own client/matter and time; nothing moved to 1377041.
    assert len(tray.activeTimers) == 1
    kept = tray.activeTimers[0]
    assert "Megatech" in kept.clientName
    assert "1377041" not in kept.clientName
    assert kept.elapsedSeconds >= 600
    tray._pause_sync_quit_completed = True
    tray.shutdown()


def test_relabel_of_resumed_saved_docket_opens_new_draft(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    tray = TrayController(app_controller)
    tray.startNewTimerWithManualTime(CLIENT_1, MATTER_1, "Research memo", "2h 48m")
    tray.stopAndSavePrimaryTimer()
    assert len(_time_rows(repo)) == 1
    saved_id = tray.recordedEntries[0].entry_id

    tray.restart_recorded_timer(saved_id)
    resumed = tray.activeTimers[0]
    assert resumed.linked_entry_id == saved_id
    assert resumed.saved_seconds == 10080
    tray.pause_timer(resumed.timer_id)

    tray.setSelectedTabClientAndMatter(CLIENT_2, "1371-GEN-26-0109", "")
    # The resumed docket was NOT re-labelled; a fresh 00:00:00 draft holds the new client.
    assert "Megatech" in resumed.clientName
    assert tray.selectedTabId.startswith("draft:")
    draft = tray._find_selected_draft()
    assert draft is not None and int(draft.get("elapsedSeconds") or 0) == 0
    assert "1377041" in str(draft.get("clientName") or "")
    tray._pause_sync_quit_completed = True
    tray.shutdown()


def test_tray_cancel_refuses_saved_docket_and_discards_only_added_time(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    tray = TrayController(app_controller)
    tray.startNewTimerWithManualTime(CLIENT_1, MATTER_1, "Research memo", "2h 48m")
    tray.stopAndSavePrimaryTimer()
    saved_id = tray.recordedEntries[0].entry_id
    legacy_rows_after_save = _legacy_row_count(legacy_path)

    # Saved docket: tray Cancel is refused and nothing is deleted.
    info = tray.describeDocketTabForCancel(f"entry:{saved_id}")
    assert info["kind"] == "saved" and info["canCancel"] is False
    res = tray.cancelUnsavedDocketTab(f"entry:{saved_id}", "discard")
    assert res["ok"] is False and res["savedLocked"] is True
    assert repo._find_time_entry(saved_id) is not None
    assert _legacy_row_count(legacy_path) == legacy_rows_after_save

    # Resume it, add time, then Cancel -> only the added time is discarded.
    tray.restart_recorded_timer(saved_id)
    resumed = tray.activeTimers[0]
    assert tray.setPrimaryManualTime("3h 30m")
    info2 = tray.describeDocketTabForCancel(f"timer:{resumed.timer_id}")
    assert info2["kind"] == "resumed_saved"
    assert info2["savedSeconds"] == 10080
    res2 = tray.cancelUnsavedDocketTab(f"timer:{resumed.timer_id}", "discard")
    assert res2["ok"] is True
    assert len(tray.activeTimers) == 0
    row = repo._find_time_entry(saved_id)
    assert row is not None
    assert int(float(row.get(sc.COL_TIME_SECONDS) or 0)) == 10080
    assert any(e.entry_id == saved_id for e in tray.recordedEntries)
    assert _legacy_row_count(legacy_path) == legacy_rows_after_save
    tray.shutdown()


def test_tray_cancel_unsaved_timer_reset_then_discard(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    tray = TrayController(app_controller)
    tray.startNewTimerWithManualTime(CLIENT_1, MATTER_1, "", "30m")
    t = tray.activeTimers[0]
    tab_id = f"timer:{t.timer_id}"
    assert tray.describeDocketTabForCancel(tab_id)["kind"] == "timer"

    res_reset = tray.cancelUnsavedDocketTab(tab_id, "reset_zero")
    assert res_reset["ok"] is True
    assert t.elapsedSeconds == 0 and t.isRunning is False
    assert len(tray.activeTimers) == 1  # tab kept

    res_discard = tray.cancelUnsavedDocketTab(tab_id, "discard")
    assert res_discard["ok"] is True
    assert len(tray.activeTimers) == 0
    assert _time_rows(repo) == []
    assert _recovery_entries(paths) == {}
    tray.shutdown()


def test_close_safeguard_pause_keeps_drafts_and_discard_drops_them(tmp_path: Path) -> None:
    paths, repo, legacy_path, app_controller = _setup(tmp_path)
    legacy_rows_before = _legacy_row_count(legacy_path)

    tray = TrayController(app_controller)
    tray.startNewTimerWithManualTime(CLIENT_1, MATTER_1, "", "45m")
    assert tray.hasUnsavedOrActiveDocketOnClose() is True
    res = tray.resolveCloseSafeguard("pause_keep_drafts_and_quit")
    assert res["ok"] is True and res["preservedCount"] == 1
    assert tray.hasRunningTimer is False
    tray.shutdown()
    assert _time_rows(repo) == []
    assert _legacy_row_count(legacy_path) == legacy_rows_before
    assert len(_recovery_entries(paths)) == 1

    tray2 = TrayController(app_controller)
    assert len(tray2.activeTimers) == 1
    res2 = tray2.resolveCloseSafeguard("discard_and_quit")
    assert res2["ok"] is True and res2["discardedCount"] == 1
    tray2.shutdown()
    assert _time_rows(repo) == []
    assert _recovery_entries(paths) == {}
