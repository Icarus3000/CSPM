from collections import Counter
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

from services.dockets_import_service import DocketsImportService


def test_core_docket_match_ignores_migrated_client_and_matter_labels() -> None:
    service = DocketsImportService(object())
    target_key = service._time_core_duplicate_key(
        {
            "date": date(2026, 8, 11),
            "description": "Review a will; email client.",
            "hours": 2.1,
            "clientRate": 475,
            "sharePct": 100,
            "amountToYou": 997.50,
        }
    )
    source_key = service._time_core_duplicate_key(
        {
            "date": "2026-08-11",
            "description": "  Review a will; email client. ",
            "hours": 2.1,
            "clientRate": 475,
            "sharePct": 1,
            "amountToYou": 997.50,
        }
    )

    assert source_key == target_key


def test_analysis_consumes_each_core_match_once_and_marks_only_true_missing_dockets_safe() -> None:
    service = DocketsImportService(object())
    source_row = {
        "Date": date(2026, 8, 11),
        "Client": "Legacy Client Name",
        "Sub-Client": "",
        "Matter_ID": "LEG-001",
        "Description": "Review a will; email client.",
        "Time (in hrs)": 2.1,
        "Hourly Rate/Flat Fee": 475,
        "Percentage": 1,
        "Amount to CS": 997.50,
    }
    core_key = service._time_core_duplicate_key(
        {
            "date": source_row["Date"],
            "description": source_row["Description"],
            "hours": source_row["Time (in hrs)"],
            "clientRate": source_row["Hourly Rate/Flat Fee"],
            "sharePct": 100,
            "amountToYou": source_row["Amount to CS"],
        }
    )
    service._time_core_duplicate_counts = Counter({core_key: 1})
    service._duplicate_maps = {"time": {}}
    service._legacy_matter_map = {}
    service._map_client_parent = lambda *_args: ("Current Client Name", "")
    service._parse_sheet = lambda _wb, _sheet: [source_row]

    rows = []
    service._analyze_dockets(None, "all", None, None, [], [], rows, [])
    assert rows[0]["action"] == "skip"
    assert rows[0]["safeDocketCandidate"] is False

    service._time_core_duplicate_counts = Counter()
    rows = []
    service._analyze_dockets(None, "all", None, None, [], [], rows, [])
    assert rows[0]["action"] == "add"
    assert rows[0]["safeDocketCandidate"] is True
