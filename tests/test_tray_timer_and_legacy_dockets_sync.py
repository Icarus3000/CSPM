from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import openpyxl
from openpyxl.worksheet.table import Table, TableStyleInfo
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))

from backend.controllers.tray_controller import TrayController
from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo, TBL_CLIENTS, TBL_MATTERS, TBL_PARENTS
from services.legacy_dockets_sync_service import (
    LEGACY_DOCKETS_COLUMNS,
    LEGACY_DOCKETS_SHEET,
    LEGACY_DOCKETS_TABLE,
    LegacyDocketsSyncService,
)
from services.paths import AppPaths


def _create_mock_legacy_dockets_workbook(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = LEGACY_DOCKETS_SHEET
    ws.append(list(LEGACY_DOCKETS_COLUMNS))
    ws.append(
        [
            dt.datetime(2026, 10, 15, 0, 0),
            "Existing Seed Client",
            None,
            "Seed docket row",
            1.0,
            475,
            1,
            "=([@[Time (in hrs)]]*[@[Hourly Rate/Flat Fee]])*[@Percentage]",
            "=[@[Amount to CS]]*1.13",
            None,
            "SEED-MAT-26-0001",
            3600,
            "Hourly",
        ]
    )
    ws.cell(row=2, column=1).number_format = "[$-409]mmmm\\ d\\,\\ yyyy;@"
    ws.cell(row=2, column=5).number_format = "0.00"
    ws.cell(row=2, column=6).number_format = "$#,##0.00"
    ws.cell(row=2, column=7).number_format = "0%"
    ws.cell(row=2, column=8).number_format = "_($* #,##0.00_);_($* (#,##0.00);_($* \"-\"??_);_(@_)"
    ws.cell(row=2, column=9).number_format = "$#,##0.00"

    tbl = Table(displayName=LEGACY_DOCKETS_TABLE, ref="A1:M2")
    tbl.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(tbl)
    wb.save(path)
    wb.close()
    return path


def _create_isolated_cspm_repo(tmp_path: Path) -> tuple[AppPaths, ExcelRepo, Path]:
    paths = AppPaths(tmp_path, override_data_dir=tmp_path / "data")
    legacy_path = _create_mock_legacy_dockets_workbook(paths.dockets_workbook_path())

    repo = ExcelRepo(paths)
    repo.ensure_schema()

    repo._upsert_row_by_key(
        TBL_PARENTS,
        sc.COL_PARENT_ID,
        "PAR-001",
        {
            sc.COL_PARENT_ID: "PAR-001",
            sc.COL_PARENT_NAME: "Megatech Group",
            sc.COL_PARENT_DEF_RATE: 475.0,
            sc.COL_PARENT_DEF_SHARE: 100.0,
            sc.COL_PARENT_ACTIVE: True,
        },
    )
    repo._upsert_row_by_key(
        TBL_CLIENTS,
        sc.COL_CLIENT_ID,
        "CLI-001",
        {
            sc.COL_CLIENT_ID: "CLI-001",
            sc.COL_CLIENT_NAME: "Megatech Integrated Services Ltd.",
            sc.COL_CLIENT_ACTIVE: True,
        },
    )
    repo._upsert_row_by_key(
        TBL_MATTERS,
        sc.COL_MATTER_ID,
        "MAT-001",
        {
            sc.COL_MATTER_ID: "MAT-001",
            sc.COL_MATTER_NUMBER: "MEGA-COR-26-0093",
            sc.COL_MATTER_CLIENT_ID: "CLI-001",
            sc.COL_MATTER_CLIENT_NAME: "Megatech Integrated Services Ltd.",
            sc.COL_MATTER_PARENT_ID: "PAR-001",
            sc.COL_MATTER_PARENT_NAME: "Megatech Group",
            sc.COL_MATTER_NAME: "Corporate Reorganization",
            sc.COL_MATTER_STATUS: "Open",
            sc.COL_MATTER_DEF_RATE: 475.0,
            sc.COL_MATTER_DEF_SHARE: 100.0,
        },
    )
    return paths, repo, legacy_path


def test_main_timer_syncs_to_tray_indicator_and_minimalist_popup(tmp_path: Path) -> None:
    _app = QCoreApplication.instance() or QCoreApplication([])
    mock_icon = MagicMock()
    mock_app_controller = SimpleNamespace(_excel_repo=None, _theme_name="Dark", _tray_icon=mock_icon)
    tray = TrayController(mock_app_controller)

    # Initially idle (no running timer)
    assert tray.hasRunningTimer is False
    assert tray.hasActiveOrPausedTimer is False

    # 1. Start main timer from main app
    tray.syncMainTimerState(
        {
            "ownerId": "TDV_TEST_1",
            "isRunning": True,
            "elapsedSeconds": 125,
            "clientId": "CLI-001",
            "clientName": "Megatech Integrated Services Ltd.",
            "matterId": "MAT-001",
            "matterName": "MEGA-COR-26-0093 - Corporate Reorganization",
            "description": "Drafting s. 85 rollover resolution",
        }
    )

    assert tray.hasRunningTimer is True
    assert tray.hasActiveOrPausedTimer is True
    assert tray.hasDisplayEntry is True
    assert tray.displayStatus == "RUNNING"
    assert tray.displayElapsedSeconds == 125
    assert tray.displayElapsedFormatted == "00:02:05"
    assert tray.displayClientName == "Megatech Integrated Services Ltd."
    assert tray.displayMatterName == "MEGA-COR-26-0093 — Corporate Reorganization"
    assert tray.displayDescription == "Drafting s. 85 rollover resolution"
    assert "RUNNING (00:02:05)" in tray.trayTooltipText
    assert "Megatech Integrated Services Ltd." in tray.trayTooltipText
    mock_icon.setToolTip.assert_called_with(tray.trayTooltipText)

    # 2. Simulate 1-second tick update
    tray._timers[0]._state.started_at_monotonic -= 1.0
    tray.update_timers()
    assert tray.displayElapsedSeconds >= 126
    assert tray.displayElapsedFormatted == "00:02:06"
    assert "00:02:06" in tray.trayTooltipText

    # 3. Edit description from tray popup and verify signal emission to main app
    received_commands: list[dict] = []
    tray.mainTimerCommandRequested.connect(lambda cmd: received_commands.append(dict(cmd)))

    tray.updatePrimaryDescription("Updated narrative from system tray mini-popup")
    assert tray.displayDescription == "Updated narrative from system tray mini-popup"
    assert received_commands[-1]["action"] == "description"
    assert received_commands[-1]["description"] == "Updated narrative from system tray mini-popup"

    # 4. Pause from main app
    tray.syncMainTimerState(
        {
            "ownerId": "TDV_TEST_1",
            "isRunning": False,
            "elapsedSeconds": 180,
            "clientId": "CLI-001",
            "clientName": "Megatech Integrated Services Ltd.",
            "matterId": "MAT-001",
            "matterName": "MEGA-COR-26-0093 - Corporate Reorganization",
            "description": "Updated narrative from system tray mini-popup",
        }
    )
    assert tray.hasRunningTimer is False
    assert tray.hasActiveOrPausedTimer is True
    assert tray.displayStatus == "PAUSED"
    assert tray.displayElapsedFormatted == "00:03:00"
    assert "PAUSED (00:03:00)" in tray.trayTooltipText

    # 5. Stop and save docket -> popup transitions to LATEST entry when no timer is running
    tray.onDocketSaved(
        {
            "entryId": "TM-0001",
            "clientName": "Megatech Integrated Services Ltd.",
            "matterName": "MEGA-COR-26-0093 - Corporate Reorganization",
            "description": "Final saved docket description",
            "rawSeconds": 1800,
            "hours": 0.5,
            "date": "2026-10-18",
            "stoppedTimer": True,
        }
    )
    assert tray.hasRunningTimer is False
    assert tray.hasActiveOrPausedTimer is False
    assert tray.hasDisplayEntry is True
    assert tray.displayStatus == "LATEST"
    assert tray.displayElapsedFormatted == "00:30:00"
    assert tray.displayClientName == "Megatech Integrated Services Ltd."
    assert tray.displayMatterName == "MEGA-COR-26-0093 — Corporate Reorganization"
    assert tray.displayDescription == "Final saved docket description"

    # 6. Verify compact minimalist flyout dimensions (340x218)
    assert TrayController.FLYOUT_WIDTH == 340
    assert TrayController.FLYOUT_HEIGHT == 218

    tray.shutdown()


def test_saved_and_updated_dockets_auto_sync_to_legacy_dockets_xlsm(tmp_path: Path) -> None:
    paths, repo, legacy_path = _create_isolated_cspm_repo(tmp_path)

    # 1. Add a new time entry in CSPM
    add_res = repo.add_time_entry(
        {
            "date": "2026-10-18",
            "clientId": "CLI-001",
            "clientName": "Megatech Integrated Services Ltd.",
            "matterId": "MAT-001",
            "matterName": "MEGA-COR-26-0093",
            "parentId": "PAR-001",
            "description": "Prepare share subscription and set-off resolutions",
            "rawSeconds": 5400,
            "hours": 1.5,
            "useExactHours": True,
            "clientRate": 475.0,
            "sharePct": 100.0,
            "status": "Draft",
        }
    )
    entry_id = add_res["entryId"]
    assert entry_id

    # Verify Table1_1 in mock Dockets.xlsm has the new row and updated ref
    wb = openpyxl.load_workbook(legacy_path, keep_vba=True, data_only=False)
    ws = wb[LEGACY_DOCKETS_SHEET]
    assert ws.tables[LEGACY_DOCKETS_TABLE].ref == "A1:M3"
    assert ws.cell(row=3, column=1).value == dt.datetime(2026, 10, 18, 0, 0)
    assert ws.cell(row=3, column=1).number_format == "[$-409]mmmm\\ d\\,\\ yyyy;@"
    assert ws.cell(row=3, column=2).value == "Megatech Group"
    assert ws.cell(row=3, column=3).value == "Megatech Integrated Services Ltd."
    assert ws.cell(row=3, column=4).value == "Prepare share subscription and set-off resolutions"
    assert float(ws.cell(row=3, column=5).value) == 1.5
    assert float(ws.cell(row=3, column=6).value) == 475.0
    assert float(ws.cell(row=3, column=7).value) == 1.0
    assert ws.cell(row=3, column=7).number_format == "0%"
    assert str(ws.cell(row=3, column=8).value).startswith("=")
    assert str(ws.cell(row=3, column=9).value).startswith("=")
    assert ws.cell(row=3, column=10).value is None
    assert ws.cell(row=3, column=11).value == "MEGA-COR-26-0093"
    assert int(ws.cell(row=3, column=12).value) == 5400
    assert ws.cell(row=3, column=13).value == "Hourly"
    LegacyDocketsSyncService._close_workbook(wb)

    # 2. Update the existing time entry in CSPM and verify Table1_1 updates in place without duplicating
    updated = repo.update_time_entry(
        entry_id,
        {
            "date": "2026-10-18",
            "hours": 2.2,
            "rawSeconds": 7920,
            "description": "Prepare and finalize share subscription and set-off resolutions",
            "invoiceRef": "26-0042",
        },
    )
    assert updated.get("ok") is True

    wb2 = openpyxl.load_workbook(legacy_path, keep_vba=True, data_only=False)
    ws2 = wb2[LEGACY_DOCKETS_SHEET]
    assert ws2.tables[LEGACY_DOCKETS_TABLE].ref == "A1:M3"
    assert ws2.max_row == 3
    assert ws2.cell(row=3, column=4).value == "Prepare and finalize share subscription and set-off resolutions"
    assert float(ws2.cell(row=3, column=5).value) == 2.2
    assert ws2.cell(row=3, column=10).value == "26-0042"
    assert ws2.cell(row=3, column=11).value == "MEGA-COR-26-0093"
    assert int(ws2.cell(row=3, column=12).value) == 7920
    LegacyDocketsSyncService._close_workbook(wb2)


def test_legacy_dockets_lock_resilience_queues_and_flushes(tmp_path: Path) -> None:
    paths, repo, legacy_path = _create_isolated_cspm_repo(tmp_path)

    # Simulate Excel holding a lock file (~$Dockets.xlsm)
    lock_file = legacy_path.parent / f"~${legacy_path.name}"
    lock_file.write_bytes(b"locked-by-excel")

    add_res = repo.add_time_entry(
        {
            "date": "2026-10-18",
            "clientId": "CLI-001",
            "clientName": "Megatech Integrated Services Ltd.",
            "matterId": "MAT-001",
            "matterName": "MEGA-COR-26-0093",
            "parentId": "PAR-001",
            "description": "Telephone call with client while Dockets.xlsm is open in Excel",
            "rawSeconds": 2880,
            "hours": 0.8,
            "useExactHours": True,
            "clientRate": 475.0,
            "sharePct": 100.0,
            "status": "Draft",
        }
    )
    entry_id = add_res["entryId"]
    assert entry_id

    # CSPM.xlsm save succeeded and pending queue was written
    sync_service = LegacyDocketsSyncService(paths)
    pending_file = sync_service._pending_queue_path()
    assert pending_file.exists()

    # Remove lock file and flush pending syncs
    lock_file.unlink()
    flush_res = sync_service.flush_pending_syncs()
    assert len(flush_res) == 1
    assert flush_res[0]["ok"] is True

    wb = openpyxl.load_workbook(legacy_path, keep_vba=True, data_only=False)
    ws = wb[LEGACY_DOCKETS_SHEET]
    assert ws.tables[LEGACY_DOCKETS_TABLE].ref == "A1:M3"
    assert ws.cell(row=3, column=4).value == "Telephone call with client while Dockets.xlsm is open in Excel"
    assert int(ws.cell(row=3, column=12).value) == 2880
    LegacyDocketsSyncService._close_workbook(wb)

