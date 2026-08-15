import sys
from pathlib import Path

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from repositories.excel_repo import (
    ExcelRepo,
    TBL_CLIENT_PROFILES,
    TBL_CLIENTS,
    TBL_DISBURSEMENTS,
    TBL_INVOICE_LOG,
    TBL_MATTERS,
    TBL_PARENTS,
    TBL_RECEIVABLES,
    TBL_TIME,
)
from services.report_pdf_exporter import generate_matter_time_ledger_pdf


class _LedgerRepo:
    _client_parent_lookup = ExcelRepo._client_parent_lookup
    _date_iso = ExcelRepo._date_iso
    _parse_date_value = ExcelRepo._parse_date_value
    _parse_float = ExcelRepo._parse_float

    def __init__(self):
        self.tables = {
            TBL_PARENTS.table: [
                {sc.COL_PARENT_ID: "P-SAME", sc.COL_PARENT_NAME: "North Shore Inc."},
                {sc.COL_PARENT_ID: "P-DISTINCT", sc.COL_PARENT_NAME: "North Shore Holdings"},
            ],
            TBL_CLIENTS.table: [
                {sc.COL_CLIENT_ID: "C-SAME", sc.COL_CLIENT_NAME: "North Shore Inc."},
                {sc.COL_CLIENT_ID: "C-DISTINCT", sc.COL_CLIENT_NAME: "North Shore Operating Ltd."},
            ],
            TBL_CLIENT_PROFILES.table: [
                {
                    sc.COL_PROFILE_CLIENT_ID: "C-SAME",
                    sc.COL_PROFILE_DISPLAY_NAME: "North   Shore Inc.",
                    sc.COL_PROFILE_PARENT_ID: "P-SAME",
                    sc.COL_PROFILE_PARENT_NAME: "North Shore Inc.",
                },
                {
                    sc.COL_PROFILE_CLIENT_ID: "C-DISTINCT",
                    sc.COL_PROFILE_DISPLAY_NAME: "North Shore Operating Ltd.",
                    sc.COL_PROFILE_PARENT_ID: "P-DISTINCT",
                    sc.COL_PROFILE_PARENT_NAME: "North Shore Holdings",
                },
            ],
            TBL_MATTERS.table: [
                {
                    sc.COL_MATTER_ID: "M-1",
                    sc.COL_MATTER_NUMBER: "NSH-TAX-26-0001",
                    sc.COL_MATTER_NAME: "Tax Planning",
                    sc.COL_MATTER_CLIENT_ID: "C-SAME",
                    sc.COL_MATTER_PARENT_ID: "P-SAME",
                },
                {
                    sc.COL_MATTER_ID: "M-2",
                    sc.COL_MATTER_NUMBER: "NSH-COR-26-0002",
                    sc.COL_MATTER_NAME: "Corporate Reorganization",
                    sc.COL_MATTER_CLIENT_ID: "C-DISTINCT",
                    sc.COL_MATTER_PARENT_ID: "P-DISTINCT",
                },
            ],
            TBL_TIME.table: [
                {
                    sc.COL_TIME_ENTRY_ID: "TIME-1",
                    sc.COL_TIME_DATE: "2026-08-15",
                    sc.COL_TIME_CLIENT_ID: "C-SAME",
                    sc.COL_TIME_MATTER_ID: "M-1",
                    sc.COL_TIME_PARENT_ID: "P-SAME",
                    sc.COL_TIME_DESC: "Tax planning review",
                    sc.COL_TIME_HOURS: 1.5,
                    sc.COL_TIME_RATE: 500,
                    sc.COL_TIME_GROSS: 750,
                    sc.COL_TIME_NET: 750,
                    sc.COL_TIME_TOTAL: 847.50,
                    sc.COL_TIME_STATUS: "Draft",
                },
                {
                    sc.COL_TIME_ENTRY_ID: "TIME-2",
                    sc.COL_TIME_DATE: "2026-08-15",
                    sc.COL_TIME_CLIENT_ID: "C-DISTINCT",
                    sc.COL_TIME_MATTER_ID: "M-2",
                    sc.COL_TIME_PARENT_ID: "P-DISTINCT",
                    sc.COL_TIME_DESC: "Reorganization call",
                    sc.COL_TIME_HOURS: 2.0,
                    sc.COL_TIME_RATE: 425,
                    sc.COL_TIME_GROSS: 850,
                    sc.COL_TIME_NET: 595,
                    sc.COL_TIME_TOTAL: 960.50,
                    sc.COL_TIME_STATUS: "Ready",
                },
                {
                    sc.COL_TIME_ENTRY_ID: "TIME-OLD",
                    sc.COL_TIME_DATE: "2026-08-14",
                    sc.COL_TIME_CLIENT_ID: "C-SAME",
                    sc.COL_TIME_MATTER_ID: "M-1",
                    sc.COL_TIME_PARENT_ID: "P-SAME",
                    sc.COL_TIME_DESC: "Older work",
                    sc.COL_TIME_HOURS: 0.5,
                    sc.COL_TIME_RATE: 500,
                    sc.COL_TIME_GROSS: 250,
                    sc.COL_TIME_NET: 250,
                    sc.COL_TIME_TOTAL: 282.50,
                    sc.COL_TIME_STATUS: "Draft",
                },
            ],
            TBL_DISBURSEMENTS.table: [],
            TBL_INVOICE_LOG.table: [],
            TBL_RECEIVABLES.table: [],
        }

    def ensure_schema(self):
        return None

    def _read_table_rows(self, table):
        table_key = getattr(table, "table", table)
        return [dict(row) for row in self.tables.get(table_key, [])]


def _today_time_payload(**overrides):
    payload = {
        "startDate": "2026-08-15",
        "endDate": "2026-08-15",
        "showTime": True,
        "showFees": False,
        "showDisbursements": False,
        "showInvoices": False,
        "showPayments": False,
        "showCredits": False,
    }
    payload.update(overrides)
    return payload


def test_matter_time_ledger_groups_today_and_enriches_docket_rows():
    result = ExcelRepo.get_client_ledger_report(_LedgerRepo(), _today_time_payload())

    assert result["ok"] is True
    assert {row["entryId"] for row in result["entries"]} == {"TIME-1", "TIME-2"}
    first = next(row for row in result["entries"] if row["entryId"] == "TIME-1")
    assert first["matterNumber"] == "NSH-TAX-26-0001"
    assert first["matterDisplay"] == "NSH-TAX-26-0001 — Tax Planning"
    assert first["rate"] == 500.0
    assert first["grossFee"] == 750.0
    assert first["docketStatus"] == "Draft"

    groups = result["matterTimeGroups"]
    assert [group["matterNumber"] for group in groups] == [
        "NSH-COR-26-0002",
        "NSH-TAX-26-0001",
    ]
    assert result["matterTimeTotals"] == {
        "entryCount": 2,
        "totalHours": 3.5,
        "totalGrossFee": 1600.0,
        "totalNetFee": 1345.0,
    }


def test_billing_client_is_omitted_only_when_it_duplicates_the_client_party():
    result = ExcelRepo.get_client_ledger_report(_LedgerRepo(), _today_time_payload())
    rows = {row["entryId"]: row for row in result["entries"]}

    # Different IDs but the same normalized display name are still one party.
    assert rows["TIME-1"]["billingClientDisplay"] == ""
    assert rows["TIME-2"]["billingClientDisplay"] == "North Shore Holdings"
    assert result["hasDistinctBillingClient"] is True

    same_client_only = ExcelRepo.get_client_ledger_report(
        _LedgerRepo(), _today_time_payload(clientId="C-SAME")
    )
    assert same_client_only["hasDistinctBillingClient"] is False
    assert same_client_only["matterTimeGroups"][0]["billingClientName"] == ""


def test_matter_time_ledger_pdf_is_grouped_and_branded(tmp_path):
    report = ExcelRepo.get_client_ledger_report(_LedgerRepo(), _today_time_payload())
    path = generate_matter_time_ledger_pdf(
        {
            "title": "Matter Time Ledger",
            "filterSummary": "Period: 2026-08-15 to 2026-08-15 · All Clients",
            "filters": {
                "fromDate": "2026-08-15",
                "toDate": "2026-08-15",
                "client": "All Clients",
                "billingClient": "All Billing Clients",
                "matter": "All Matters",
                "search": "",
            },
            "matterGroups": report["matterTimeGroups"],
            "totals": report["matterTimeTotals"],
            "config": {"title": "Matter Time Ledger", "firmName": "Cory Schneider Law Office"},
        },
        str(tmp_path),
        str(PROJECT_ROOT / "src" / "assets" / "app_icon_preview.png"),
    )

    pdf = Path(path)
    assert pdf.exists()
    assert pdf.read_bytes().startswith(b"%PDF-")
    reader = PdfReader(str(pdf))
    first_page = reader.pages[0]
    assert float(first_page.mediabox.height) > float(first_page.mediabox.width)
    assert len(first_page.images) >= 1
    # PDF extraction can insert a line break inside narrow header cells (for
    # example, ``REPORT\nPERIOD``).  Collapse whitespace before asserting the
    # document's semantic content instead of coupling the test to extraction
    # engine line wrapping.
    extracted = " ".join(
        " ".join((page.extract_text() or "").split())
        for page in reader.pages
    )
    for expected in (
        "REPORT PERIOD",
        "DATA SCOPE",
        "CLIENT",
        "BILLING CLIENT",
        "DESCRIPTION & STATUS",
        "RATE",
        "NET FEES",
        "Final Summary",
        "North Shore Holdings",
    ):
        assert expected in extracted


def test_matter_time_ledger_keeps_group_edges_and_final_summary_together(tmp_path):
    entries = [
        {
            "date": "2026-08-15",
            "description": f"Detailed work record {index}: review, correspondence, and next-step planning.",
            "hours": 0.2,
            "rate": 450,
            "grossFee": 90,
            "netFee": 90,
            "reference": f"REF-{index:02d}",
            "status": "Draft",
        }
        for index in range(1, 31)
    ]
    group = {
        "matterDisplay": "LONG-TEST-26-0001 — Long-form Matter",
        "clientName": "Long Form Client",
        "billingClientName": "",
        "entryCount": len(entries),
        "totalHours": 6.0,
        "totalGrossFee": 2700.0,
        "totalNetFee": 2700.0,
        "entries": entries,
    }
    path = generate_matter_time_ledger_pdf(
        {
            "filters": {"fromDate": "2026-08-15", "toDate": "2026-08-15"},
            "matterGroups": [group],
            "totals": {
                "entryCount": len(entries),
                "totalHours": 6.0,
                "totalGrossFee": 2700.0,
                "totalNetFee": 2700.0,
            },
            "config": {"title": "Matter Time Ledger", "firmName": "Cory Schneider Law Office"},
        },
        str(tmp_path),
        str(PROJECT_ROOT / "src" / "assets" / "app_icon_preview.png"),
    )
    pages = [" ".join((page.extract_text() or "").split()) for page in PdfReader(path).pages]
    assert len(pages) >= 2
    assert any("LONG-TEST-26-0001" in page and "Detailed work record 1:" in page for page in pages)
    assert any("Detailed work record 30:" in page and "Matter subtotal" in page for page in pages)
    summary_pages = [page for page in pages if "Final Summary" in page]
    assert len(summary_pages) == 1
    for expected in ("TOTAL DOCKETS", "TOTAL HOURS", "TOTAL GROSS FEES", "TOTAL NET FEES"):
        assert expected in summary_pages[0]


def test_time_today_route_and_zen_contract_are_present():
    home = (PROJECT_ROOT / "src" / "qml" / "components" / "DailyOperationsHome.qml").read_text(encoding="utf-8")
    modules = (PROJECT_ROOT / "src" / "qml" / "standards" / "ModulePathways.js").read_text(encoding="utf-8")
    panel = (PROJECT_ROOT / "src" / "qml" / "components" / "MatterTimeLedgerReportPanel.qml").read_text(encoding="utf-8")

    assert '"nodeId": "D18"' in home
    assert "openWorkspaceRequested" in home
    assert '"id": "D18", "label": "Matter Time Ledger"' in modules
    assert "showCenteredOnInitiatingMonitor" in panel
    assert '"reportId": "matter_time_ledger"' in panel
    assert "Matter subtotal" in panel
    assert "readonly property int fieldHeight: 56" in panel
    assert 'Qt.openUrlExternally("file:///"' in panel
    assert 'SemanticTheme.surface(root.t, "panel", "info", root.appStyle)' in panel
    assert panel.count("PillButton {") >= 4
    assert panel.count('text: root.busy ? "Exporting…" : "Export PDF"') == 2
    exporter = (PROJECT_ROOT / "src" / "python" / "services" / "report_pdf_exporter.py").read_text(encoding="utf-8")
    controller = (PROJECT_ROOT / "src" / "python" / "backend" / "app_controller.py").read_text(encoding="utf-8")
    assert "pagesize=letter" in exporter
    assert "KeepTogether" in exporter
    assert "colWidths=detail_widths" in exporter
    assert "headerLogoPreserveAspectRatio" in exporter
    assert '"assets" / "CS.svg"' in controller
