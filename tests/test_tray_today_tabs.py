"""Today's mini-popup never promotes historical or recovered dockets into today."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/python"))
from backend.controllers import tray_controller as tray_module
from backend.controllers.tray_controller import TrayActiveTimer, TrayController
from domain import schema_constants as sc
from tray.elapsed_time import TimerState


@pytest.fixture
def make_tray():
    qt = QCoreApplication.instance() or QCoreApplication([])
    controllers = []

    def create(repo=None):
        controller = TrayController(SimpleNamespace(_excel_repo=repo, _theme_name="Dark"))
        controllers.append(controller)
        controller._timer.stop()
        return controller

    yield create
    for controller in controllers:
        controller._timer.stop()
        controller._sqlite_edit_debounce_timer.stop()
        controller._exit_failsafe_timer.stop()
    qt.processEvents()


def row(entry_id, date, status="Draft"):
    return {
        sc.COL_TIME_ENTRY_ID: entry_id,
        sc.COL_TIME_DATE: date,
        sc.COL_TIME_STATUS: status,
        sc.COL_TIME_CLIENT_ID: "client",
        sc.COL_TIME_MATTER_ID: "matter",
        sc.COL_TIME_HOURS: 0.5,
        sc.COL_TIME_SECONDS: 1800,
        sc.COL_TIME_DESC: entry_id,
    }


def test_history_only_opens_with_no_tabs_or_previous_entry(make_tray):
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    rows = [row("yesterday", yesterday)]
    controller = make_tray(SimpleNamespace(_read_table_rows=lambda _table: rows))
    assert controller.todayDocketTabs == []
    assert controller.selectedTabId == ""
    assert not controller.hasDisplayEntry
    assert controller.displayStatus == "IDLE"
    assert controller.displayDescription == ""
    assert controller.recordedTodayFormatted == "0.0 h"
    assert rows == [row("yesterday", yesterday)]


def test_hydration_includes_only_today_and_excludes_merged(make_tray):
    today = dt.date.today()
    rows = [row("old", today - dt.timedelta(days=1)), row("today", today),
            row("merged", today, "Merged"), row("future", today + dt.timedelta(days=1))]
    controller = make_tray(SimpleNamespace(_read_table_rows=lambda _table: rows))
    assert [tab["entryId"] for tab in controller.todayDocketTabs] == ["today"]
    assert controller.displayDescription == "today"


def test_saving_or_editing_history_cannot_force_it_into_today(make_tray):
    controller = make_tray()
    payload = {"entryId": "entry", "date": dt.date.today().isoformat(),
               "hours": 1, "description": "today", "stoppedTimer": True}
    controller.onDocketSaved(payload)
    assert len(controller.todayDocketTabs) == 1
    controller._entries[0].is_today_tab = True  # Old transient flags cannot override Date.
    controller.onDocketSaved({**payload, "date": (dt.date.today() - dt.timedelta(days=1)).isoformat()})
    assert controller.todayDocketTabs == []
    assert controller.selectedTabId == ""
    assert not controller.hasDisplayEntry
    assert controller.displayElapsedSeconds == 0
    assert controller.recordedTodayFormatted == "0.0 h"
    assert len(controller._entries) == 1  # Historical storage remains intact.


def test_refresh_with_no_today_rows_clears_previous_display(make_tray):
    rows = [row("today", dt.date.today())]
    controller = make_tray(SimpleNamespace(_read_table_rows=lambda _table: rows))
    assert controller.hasDisplayEntry
    rows.clear()
    controller.refreshTodayDockets()
    assert controller.todayDocketTabs == []
    assert controller.selectedTabId == ""
    assert not controller.hasDisplayEntry


def test_closing_last_explicit_draft_leaves_empty_strip(make_tray):
    controller = make_tray()
    assert controller.todayDocketTabs == []
    tab_id = controller.createNewBlankDocketTab()
    assert [tab["tabId"] for tab in controller.todayDocketTabs] == [tab_id]
    assert controller.closeOrHideDocketTab(tab_id)
    assert controller.todayDocketTabs == []
    assert controller.selectedTabId == ""


def test_midnight_filters_saved_entries_timers_and_drafts_without_losing_them(make_tray, monkeypatch):
    controller = make_tray()
    today = dt.date.today()
    controller.onDocketSaved({"entryId": "saved", "date": today.isoformat(), "hours": 1})
    controller.createNewBlankDocketTab()
    timer = TrayActiveTimer("live", "client", "Client", "matter", "Matter", TimerState(300, True, 0))
    controller._timers.append(timer)
    assert len(controller.todayDocketTabs) == 3

    class NextDay(dt.date):
        @classmethod
        def today(cls):
            return today + dt.timedelta(days=1)

    monkeypatch.setattr(tray_module.datetime, "date", NextDay)
    assert controller.todayDocketTabs == []
    assert controller.selectedTabId == ""
    assert not controller.hasDisplayEntry
    assert controller.displayStatus == "IDLE"
    assert len(controller._entries) == len(controller._draft_tabs) == len(controller._timers) == 1


def test_old_recovery_stays_available_and_heartbeats_keep_original_date(make_tray):
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    recovery = {"entryId": "crashed", "Date": yesterday, "ClientID": "client", "MatterID": "matter",
                "heartbeatSeconds": 300, "Description": "Recovered history"}
    paused = {**recovery, "entryId": "paused"}
    sqlite = MagicMock()
    sqlite.upsert_live_docket_heartbeat.return_value = {"ok": True}
    repo = SimpleNamespace(_read_table_rows=lambda _table: [], _get_sqlite_repo=lambda: sqlite,
        reconcile_unsynced_dockets_on_startup=lambda: {"restoredPausedDockets": [paused], "crashRecoveryDockets": [recovery]})
    controller = make_tray(repo)
    assert controller.todayDocketTabs == []
    assert not controller.hasDisplayEntry
    assert controller.hasCrashRecoveryPrompt
    assert controller.activeCrashRecoveryDocket["date"] == yesterday
    assert len(controller._timers) == 2
    assert controller.hasUnsavedOrActiveDocketOnClose()
    for timer in controller._timers:
        assert timer.recorded_date == yesterday
        assert controller._upsert_timer_to_sqlite(timer)["ok"]
        assert sqlite.upsert_live_docket_heartbeat.call_args.args[0]["date"] == yesterday


def test_today_running_timer_remains_selectable(make_tray):
    controller = make_tray()
    controller.syncMainTimerState({"ownerId": "test", "isRunning": True, "elapsedSeconds": 60,
                                  "clientId": "client", "matterId": "matter"})
    tabs = controller.todayDocketTabs
    assert len(tabs) == 1
    assert tabs[0]["date"] == dt.date.today().isoformat()
    assert tabs[0]["status"] == "RUNNING"
    assert controller.selectDocketTab(tabs[0]["tabId"])
    assert controller.hasDisplayEntry
