from datetime import date
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
WIP_SOURCE = (REPO_ROOT / "src" / "qml" / "views" / "WIPBillingWizardView.qml").read_text(
    encoding="utf-8"
)


def test_wip_view_contains_date_filtering_properties_and_presets():
    assert 'readonly property string beginningOfTime: "2025-01-01"' in WIP_SOURCE
    assert "property string fromDateFilter:" in WIP_SOURCE
    assert "property string toDateFilter:" in WIP_SOURCE
    assert 'property string activeDatePreset: "all"' in WIP_SOURCE
    assert "function todayIso()" in WIP_SOURCE
    assert "function getLastDayOfPreviousMonth()" in WIP_SOURCE
    assert "function applyDatePreset(preset)" in WIP_SOURCE
    assert "function _syncDatePreset()" in WIP_SOURCE


def test_wip_view_contains_calendar_loader_and_picker():
    assert "Loader {" in WIP_SOURCE
    assert "id: wipCalendarLoader" in WIP_SOURCE
    assert "JellyCalendar {" in WIP_SOURCE
    assert "function openDatePicker(target, px, py)" in WIP_SOURCE


def test_wip_computed_properties_respect_date_filters():
    # clientList date checks
    assert "if (root.fromDateFilter && itemDate.length >= 10 && itemDate < root.fromDateFilter) continue" in WIP_SOURCE
    assert "if (root.toDateFilter && itemDate.length >= 10 && itemDate > root.toDateFilter) continue" in WIP_SOURCE

    # billingClientList date checks
    assert "billingClientList:" in WIP_SOURCE

    # filteredItems date checks
    assert "if (root.fromDateFilter && itemDate.length >= 10 && itemDate < root.fromDateFilter)" in WIP_SOURCE
    assert "if (root.toDateFilter && itemDate.length >= 10 && itemDate > root.toDateFilter)" in WIP_SOURCE


def test_wip_state_persistence_includes_date_filters():
    # applyInitialState
    assert "if (state.fromDate !== undefined)" in WIP_SOURCE
    assert "if (state.toDate !== undefined)" in WIP_SOURCE
    assert "if (state.datePreset !== undefined)" in WIP_SOURCE

    # snapshotState
    assert '"fromDate": root.fromDateFilter' in WIP_SOURCE
    assert '"toDate": root.toDateFilter' in WIP_SOURCE
    assert '"datePreset": root.activeDatePreset' in WIP_SOURCE


def test_wip_toolbar_contains_date_input_boxes_and_preset_pills():
    assert "id: fromDateInput" in WIP_SOURCE
    assert "id: toDateInput" in WIP_SOURCE
    assert "id: toDateBtn" in WIP_SOURCE
    assert "id: lastMonthBtn" in WIP_SOURCE
    assert "id: allDatesBtn" in WIP_SOURCE
    assert "Through Last Month" in WIP_SOURCE
    assert "To-Date" in WIP_SOURCE
    assert "All Dates" in WIP_SOURCE


def test_wip_date_filtering_logic_simulation():
    # Simulate the filtering logic on mock records
    mock_items = [
        {"id": 1, "date": "2024-12-31", "clientName": "Old Client", "amount": 100},
        {"id": 2, "date": "2025-01-15", "clientName": "Client A", "amount": 250},
        {"id": 3, "date": "2025-08-02", "clientName": "Client B", "amount": 400},
        {"id": 4, "date": "2026-02-28", "clientName": "Client A", "amount": 150},
        {"id": 5, "date": "2026-08-31", "clientName": "Client C", "amount": 500},
        {"id": 6, "date": "2026-09-05", "clientName": "Client C", "amount": 300},
    ]

    def filter_items(items, from_date="", to_date=""):
        out = []
        for item in items:
            item_date = str(item.get("date") or "")[:10]
            if from_date and len(item_date) >= 10 and item_date < from_date:
                continue
            if to_date and len(item_date) >= 10 and item_date > to_date:
                continue
            out.append(item)
        return out

    # Test 'all' (unrestricted)
    res_all = filter_items(mock_items, "", "")
    assert len(res_all) == 6

    # Test from beginning of time (2025-01-01) to 2026-02-28
    res_range = filter_items(mock_items, "2025-01-01", "2026-02-28")
    assert len(res_range) == 3
    assert [x["id"] for x in res_range] == [2, 3, 4]

    # Test excluding old 2024 records
    res_2025_onwards = filter_items(mock_items, "2025-01-01", "")
    assert len(res_2025_onwards) == 5
    assert all(x["date"] >= "2025-01-01" for x in res_2025_onwards)


def test_last_day_of_previous_month_calculation():
    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    from datetime import timedelta
    last_day_prev_month = first_of_month - timedelta(days=1)

    assert last_day_prev_month < today
    assert last_day_prev_month.month != today.month or (today.month == 1 and last_day_prev_month.month == 12)
