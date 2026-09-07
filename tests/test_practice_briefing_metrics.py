"""Regression coverage for practice briefing productivity accumulation and WIP calculations."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))

import domain.schema_constants as sc
from repositories.excel_repo import ExcelRepo, TBL_TIME, TBL_MATTERS
from services.paths import AppPaths


class TestPracticeBriefingMetrics(unittest.TestCase):
    def test_practice_briefing_accumulates_billed_and_unbilled_productivity(self):
        paths = AppPaths(PROJECT_ROOT)
        repo = ExcelRepo(paths)

        today = date.today()
        today_iso = today.isoformat()
        earlier_ytd_iso = date(today.year, 1, 15).isoformat() if today.month > 1 or today.day > 15 else today_iso

        mock_matters = [
            {
                sc.COL_MATTER_ID: "M01",
                sc.COL_MATTER_NUMBER: "MAT-01",
                sc.COL_MATTER_NAME: "Alpha Matter",
                sc.COL_MATTER_CLIENT_NAME: "Client Alpha",
            },
            {
                sc.COL_MATTER_ID: "M02",
                sc.COL_MATTER_NUMBER: "MAT-02",
                sc.COL_MATTER_NAME: "Beta Matter",
                sc.COL_MATTER_CLIENT_NAME: "Client Beta",
            },
        ]

        mock_time = [
            # Billed entry earlier this year: must contribute to YTD productivity, but NOT to open WIP
            {
                sc.COL_TIME_ENTRY_ID: "T01",
                sc.COL_TIME_MATTER_ID: "M01",
                sc.COL_TIME_DATE: earlier_ytd_iso,
                sc.COL_TIME_DESC: "Billed trial prep",
                sc.COL_TIME_HOURS: 10.0,
                sc.COL_TIME_GROSS: 4500.0,
                sc.COL_TIME_NET: 4500.0,
                sc.COL_TIME_STATUS: "billed",
                sc.COL_TIME_INVOICE_STATUS: "billed",
                sc.COL_TIME_INVOICE_REF: "INV-2026-001",
            },
            # Unbilled entry today: must contribute to both today/YTD productivity AND open WIP
            {
                sc.COL_TIME_ENTRY_ID: "T02",
                sc.COL_TIME_MATTER_ID: "M01",
                sc.COL_TIME_DATE: today_iso,
                sc.COL_TIME_DESC: "Research client memo",
                sc.COL_TIME_HOURS: 2.5,
                sc.COL_TIME_GROSS: 1125.0,
                sc.COL_TIME_NET: 1125.0,
                sc.COL_TIME_STATUS: "unbilled",
                sc.COL_TIME_INVOICE_STATUS: "",
                sc.COL_TIME_INVOICE_REF: "",
            },
            # Unbilled entry on second matter from 45 days ago: triggers stale review (age > 28)
            {
                sc.COL_TIME_ENTRY_ID: "T03",
                sc.COL_TIME_MATTER_ID: "M02",
                sc.COL_TIME_DATE: (today - timedelta(days=45)).isoformat(),
                sc.COL_TIME_DESC: "Drafting agreement",
                sc.COL_TIME_HOURS: 4.0,
                sc.COL_TIME_GROSS: 1800.0,
                sc.COL_TIME_NET: 1800.0,
                sc.COL_TIME_STATUS: "open",
                sc.COL_TIME_INVOICE_STATUS: "",
                sc.COL_TIME_INVOICE_REF: "",
            },
        ]

        def mock_read_rows(table_name):
            if table_name == TBL_MATTERS:
                return mock_matters
            if table_name == TBL_TIME:
                return mock_time
            return []

        repo._read_table_rows = MagicMock(side_effect=mock_read_rows)
        repo._load_deadlines = MagicMock(return_value=[])
        repo.home_dashboard_summary = MagicMock(return_value={"activeClientCount": 2})
        repo.ar_aging_report = MagicMock(return_value={"rows": [], "summary": {}})

        briefing = repo.practice_briefing()

        self.assertTrue(briefing["ok"])

        # 1. Productivity: YTD must include BOTH billed ($4500) and unbilled ($1125 + $1800) = $7425, 16.5 hrs
        prod = briefing["productivitySummary"]
        self.assertEqual(prod["ytd"]["hours"], 16.5)
        self.assertEqual(prod["ytd"]["gross"], 7425.0)

        # Today must include only today's work: 2.5 hrs, $1125
        self.assertEqual(prod["today"]["hours"], 2.5)
        self.assertEqual(prod["today"]["gross"], 1125.0)

        # 2. Total WIP: only the unbilled entries ($1125 + $1800) = $2925.0, 2 entries across 2 matters
        self.assertEqual(briefing["totalWipAmount"], 2925.0)
        self.assertEqual(briefing["totalWipCount"], 2)
        self.assertEqual(briefing["totalWipMatterCount"], 2)

        # 3. Ready to Bill WIP: M02 is 45 days old (> 28 days threshold), M01 is today (not stale, < $5k)
        # So readyToBillMatters has only M02 ($1800)
        self.assertEqual(briefing["readyToBillMatterCount"], 1)
        self.assertEqual(briefing["readyToBillWipAmount"], 1800.0)
        self.assertEqual(len(briefing["readyToBillMatters"]), 1)
        self.assertEqual(briefing["readyToBillMatters"][0]["matterId"], "M02")

    def test_daily_operations_home_qml_contract(self):
        """DailyOperationsHome.qml must bind Total WIP and review helpers cleanly."""
        home_qml = (PROJECT_ROOT / "src" / "qml" / "components" / "DailyOperationsHome.qml").read_text(encoding="utf-8")

        self.assertIn('"label": "Total WIP"', home_qml)
        self.assertIn("function totalWipValue()", home_qml)
        self.assertIn("function readyToBillWipValue()", home_qml)
        self.assertIn("function readyToBillCount()", home_qml)
        self.assertIn('"totalWipAmount": 0.0', home_qml)


if __name__ == "__main__":
    unittest.main()
