import sys
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo, TBL_CLIENTS, TBL_LEDGER, TBL_TIME
from services.report_pdf_exporter import generate_productivity_report_pdf
from backend.app_controller import AppController


class _ProductivityRepo:
    """Small read-only table double for the Productivity Report calculation."""

    _parse_date_value = ExcelRepo._parse_date_value
    _parse_float = ExcelRepo._parse_float

    def __init__(self):
        self.tables = {
            TBL_TIME.table: [
                {
                    sc.COL_TIME_DATE: "2026-01-10",
                    sc.COL_TIME_CLIENT_ID: "C-1",
                    sc.COL_TIME_HOURS: 1.0,
                    sc.COL_TIME_GROSS: 100.0,
                    sc.COL_TIME_INVOICE_REF: "26-0100",
                },
                {
                    sc.COL_TIME_DATE: "2026-01-11",
                    sc.COL_TIME_CLIENT_ID: "C-1",
                    sc.COL_TIME_HOURS: 2.0,
                    sc.COL_TIME_GROSS: 100.0,
                    sc.COL_TIME_INVOICE_REF: "26-0100",
                },
                {
                    sc.COL_TIME_DATE: "2026-01-15",
                    sc.COL_TIME_CLIENT_ID: "C-2",
                    sc.COL_TIME_HOURS: 0.5,
                    sc.COL_TIME_GROSS: 50.0,
                    sc.COL_TIME_INVOICE_REF: "",
                },
            ],
            TBL_LEDGER.table: [
                # This pair represents the original invoice billings and a
                # write-down. The realized value must be $150, not $200.
                {sc.COL_LEDGER_REFERENCE: "26-0100", sc.COL_LEDGER_BILLINGS_EXCL_HST: 200.0},
                {sc.COL_LEDGER_REFERENCE: "26-0100", sc.COL_LEDGER_BILLINGS_EXCL_HST: -50.0},
                # Payment records have a zero billing field and must not
                # change the realization factor.
                {sc.COL_LEDGER_REFERENCE: "26-0100", sc.COL_LEDGER_BILLINGS_EXCL_HST: 0.0},
            ],
            TBL_CLIENTS.table: [
                {sc.COL_CLIENT_ID: "C-1", sc.COL_CLIENT_NAME: "Acme Holdings"},
                {sc.COL_CLIENT_ID: "C-2", sc.COL_CLIENT_NAME: "North Shore Inc."},
            ],
        }

    def _read_table_rows(self, table):
        return [dict(row) for row in self.tables[table.table]]

    @staticmethod
    def _canonicalize_time_row(row):
        return dict(row)

    @staticmethod
    def _canonicalize_client_row(row):
        return dict(row)


class _SettingsSignal:
    def __init__(self):
        self.count = 0

    def emit(self):
        self.count += 1


class _ProductivitySettingsDouble:
    """Minimal controller state for settings-only forecast tests."""

    _bounded_productivity_setting = staticmethod(AppController._bounded_productivity_setting)
    _productivity_bool_setting = staticmethod(AppController._productivity_bool_setting)
    _productivity_forecast_settings_payload = AppController._productivity_forecast_settings_payload
    productivityForecastBasisDays = property(AppController.productivityForecastBasisDays.fget)
    setProductivityForecastSettings = AppController.setProductivityForecastSettings

    def __init__(self, settings):
        self._settings_data = dict(settings)
        self._settings_load_complete = True
        self.settingsChanged = _SettingsSignal()
        self.saved = False

    def load_settings(self):
        self._settings_load_complete = True

    def save_settings(self):
        self.saved = True


def test_productivity_report_matches_legacy_realization_and_trend_windows():
    result = ExcelRepo.productivity_report(
        _ProductivityRepo(),
        {"startDate": "2026-01-01", "endDate": "2026-01-15", "annualTarget": "350000"},
    )

    assert result["ok"] is True
    assert result["summary"] == {
        "totalProduction": 200.0,
        "billableHours": 3.5,
        "realizedRate": 57.14,
        "entryCount": 3,
    }
    assert result["forecast"]["annualBasisDays"] == 336
    assert result["forecast"]["annualProjection"] == 4480.0
    assert result["topClients"] == [
        {"name": "Acme Holdings", "amount": 150.0},
        {"name": "North Shore Inc.", "amount": 50.0},
    ]
    assert result["monthlyProduction"][-1] == {"date": "2026-01-01", "label": "Jan", "amount": 200.0}
    daily = {row["date"]: row["amount"] for row in result["dailyProduction"]}
    assert daily["2026-01-10"] == 75.0
    assert daily["2026-01-11"] == 75.0
    assert daily["2026-01-15"] == 50.0


def test_productivity_report_rejects_an_invalid_date_range():
    result = ExcelRepo.productivity_report(
        _ProductivityRepo(),
        {"startDate": "2026-02-01", "endDate": "2026-01-01", "annualTarget": "350000"},
    )

    assert result["ok"] is False
    assert "End Date" in result["message"]


def test_productivity_report_uses_the_configured_forecast_basis():
    result = ExcelRepo.productivity_report(
        _ProductivityRepo(),
        {
            "startDate": "2026-01-01",
            "endDate": "2026-01-15",
            "annualTarget": "350000",
            "annualBasisDays": 365,
        },
    )

    assert result["ok"] is True
    assert result["forecast"]["annualBasisDays"] == 365
    assert result["forecast"]["annualProjection"] == 4866.67


def test_productivity_report_rejects_an_invalid_forecast_basis():
    result = ExcelRepo.productivity_report(
        _ProductivityRepo(),
        {
            "startDate": "2026-01-01",
            "endDate": "2026-01-15",
            "annualBasisDays": 367,
        },
    )

    assert result["ok"] is False
    assert "Forecast basis" in result["message"]


def test_schedule_based_productivity_basis_counts_only_scheduled_workdays():
    settings = _ProductivitySettingsDouble({
        "productivityForecastBasisDays": 336,
        "productivityForecastWorkDaysPerWeek": 6,
        "productivityForecastVacationDays": 6,
        "productivityForecastHolidayDays": 10,
        "productivityForecastOtherUnavailableDays": 4,
        "productivityForecastManualOverrideEnabled": False,
    })

    result = settings._productivity_forecast_settings_payload()

    # A full vacation week on a six-day schedule is six days. The usual
    # seventh day off was never part of the 52 x 6 scheduled-day total.
    assert result["calculatedBasisDays"] == (52 * 6) - 6 - 10 - 4
    assert result["effectiveBasisDays"] == 292
    assert result["manualBasisDays"] == 336


def test_productivity_schedule_preserves_legacy_basis_until_calculation_is_enabled():
    settings = _ProductivitySettingsDouble({
        "productivityForecastBasisDays": 336,
        "productivityForecastWorkDaysPerWeek": 5,
        "productivityForecastVacationDays": 15,
        "productivityForecastHolidayDays": 10,
        "productivityForecastOtherUnavailableDays": 5,
    })

    result = settings.setProductivityForecastSettings({
        "workDaysPerWeek": 5,
        "vacationDays": 15,
        "holidayDays": 10,
        "otherUnavailableDays": 5,
        "manualOverrideEnabled": True,
        "manualBasisDays": 336,
    })

    assert result["ok"] is True
    assert result["calculatedBasisDays"] == 230
    assert result["effectiveBasisDays"] == 336
    assert settings.saved is True
    assert settings.settingsChanged.count == 1


def test_productivity_pdf_is_single_native_pdf(tmp_path):
    output = generate_productivity_report_pdf(
        {
            "startDate": "2026-01-01",
            "endDate": "2026-01-15",
            "summary": {"totalProduction": 200.0, "billableHours": 3.5, "realizedRate": 57.14},
            "forecast": {
                "annualTarget": 350000.0,
                "dailyPace": 13.33,
                "annualBasisDays": 336,
                "annualProjection": 4480.0,
                "percentToTarget": -98.7,
            },
            "topClients": [{"name": "Acme Holdings", "amount": 150.0}],
            "monthlyProduction": [{"label": "Jan", "amount": 200.0}],
            "dailyProduction": [{"label": "15-Jan", "amount": 50.0}],
            "config": {"firmName": "Cory Schneider Law Office"},
        },
        str(tmp_path),
        "",
    )

    pdf_path = Path(output)
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_productivity_d10_cannot_fall_back_to_the_generic_placeholder_form():
    """Keep D10's native panel loadable and its generic fallback hidden."""
    panel_source = (PROJECT_ROOT / "src" / "qml" / "components" / "ProductivityReportPanel.qml").read_text(
        encoding="utf-8"
    )
    host_source = (PROJECT_ROOT / "src" / "qml" / "views" / "PlaceholderSubmenuView.qml").read_text(
        encoding="utf-8"
    )

    assert 'source: "../components/ProductivityReportPanel.qml"' in host_source
    assert "&& !root.activeIsProductivityDashboard()" in host_source
    assert not re.search(r"font\\.pixelSize:\\s*\\d+\\.\\d+", panel_source)


def test_productivity_panel_uses_a_fixed_canvas_with_a_parameter_rail_and_zen_window():
    panel_source = (PROJECT_ROOT / "src" / "qml" / "components" / "ProductivityReportPanel.qml").read_text(
        encoding="utf-8"
    )

    assert "ScrollView" not in panel_source
    assert "id: parameterRail" in panel_source
    assert 'text: root.isLoading ? "Generating…" : "Generate Report"' not in panel_source
    assert panel_source.count("onEditingFinished: root.generateReport()") == 3
    assert panel_source.count("onDatePickerDatePicked: function(_pickedDate, _isoText)") == 2
    assert "id: zenWindow" in panel_source
    assert 'text: "Zen View"' in panel_source
    assert "onClicked: root.openZenView()" in panel_source
    assert "active: zenWindow.visible && root.zenAvailable" in panel_source
    assert "function applyReportSnapshot(snapshot)" in panel_source
    assert "parent: root.isZenMode" not in panel_source
    assert "LIVE DATA · READ ONLY" in panel_source
    assert panel_source.count("Layout.preferredHeight: 56") == 3


def test_productivity_zen_uses_fixed_sections_without_a_recursive_row_width():
    source = (PROJECT_ROOT / "src" / "qml" / "components" / "ProductivityZenView.qml").read_text(
        encoding="utf-8"
    )

    assert "Layout.preferredWidth: Math.round(parent.width * 0.43)" not in source
    assert "Layout.preferredWidth: Math.max(360, Math.round(root.width * 0.42))" in source
    assert "Layout.minimumHeight: 240" in source
    assert "Layout.minimumHeight: 170" in source
    assert source.count("clip: true") >= 2


def test_daily_operations_productivity_card_opens_d10_from_anywhere_on_the_card():
    home_source = (PROJECT_ROOT / "src" / "qml" / "components" / "DailyOperationsHome.qml").read_text(
        encoding="utf-8"
    )

    assert "id: productivityCard" in home_source
    assert "id: productivityClickArea" in home_source
    assert "anchors.fill: parent" in home_source
    assert "cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor" in home_source
    assert 'onClicked: root.openScreenRequested("finance", "D10")' in home_source
