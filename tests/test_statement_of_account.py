import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    # Append rather than prepend: the repository has a ``platform`` package,
    # while pytest itself correctly needs the Python standard-library module.
    sys.path.append(str(SOURCE_ROOT))

from domain import schema_constants as sc
from repositories.excel_repo import ExcelRepo
from services.report_pdf_exporter import generate_statement_of_account_pdf


class _StatementRepo:
    """A small in-memory canonical-ledger contract for statement selection."""

    _money_round = ExcelRepo._money_round
    _parse_date_value = ExcelRepo._parse_date_value
    _statement_open_invoice_candidates = ExcelRepo._statement_open_invoice_candidates

    def _canonical_ar_ledger(self, _payload):
        return {
            "ok": True,
            "events": [
                {
                    "date": "2026-06-10",
                    "reference": "26-0101",
                    "invoice": "26-0101",
                    "type": "Invoice",
                    "debit": 500.0,
                    "credit": 0.0,
                    "status": "Unpaid",
                    "billingClient": "Leviathan Private Network",
                    "workClient": "Client One",
                    "workContexts": [{"client": "Client One", "matter": "Contract renewal", "matterId": "M-ONE"}],
                },
                {
                    "date": "2026-06-15",
                    "reference": "26-0101",
                    "invoice": "26-0101",
                    "type": "Payment",
                    "debit": 0.0,
                    "credit": 125.0,
                    "status": "Applied",
                    "billingClient": "Leviathan Private Network",
                    "workClient": "Client One",
                    "workContexts": [{"client": "Client One", "matter": "Contract renewal", "matterId": "M-ONE"}],
                },
                {
                    "date": "2026-07-04",
                    "reference": "26-0102",
                    "invoice": "26-0102",
                    "type": "Invoice",
                    "debit": 300.0,
                    "credit": 0.0,
                    "status": "Unpaid",
                    "billingClient": "Leviathan Private Network",
                    "workClient": "Client Two",
                    "workContexts": [{"client": "Client Two", "matter": "Tax planning", "matterId": "M-TWO"}],
                },
                {
                    "date": "2026-07-08",
                    "reference": "26-0103",
                    "invoice": "26-0103",
                    "type": "Invoice",
                    "debit": 100.0,
                    "credit": 0.0,
                    "status": "Paid",
                    "billingClient": "Leviathan Private Network",
                    "workClient": "Client Three",
                    "workContexts": [{"client": "Client Three", "matter": "Corporate cleanup", "matterId": "M-THREE"}],
                },
            ],
        }


def test_statement_defaults_to_all_open_invoices_and_allows_manual_invoice_selection():
    repo = _StatementRepo()

    default_report = ExcelRepo.statement_of_account_report(
        repo,
        {
            "billingClient": "Leviathan Private Network",
            "asOfDate": "2026-07-31",
        },
    )

    assert default_report["ok"] is True
    assert default_report["asOfDate"] == "2026-07-31"
    assert [row["invoice"] for row in default_report["availableInvoices"]] == ["26-0101", "26-0102"]
    assert default_report["summary"]["invoiceCount"] == 2
    assert default_report["summary"]["amountDue"] == 675.0
    assert default_report["rows"][0]["paidCredits"] == 125.0
    assert default_report["rows"][0]["balanceDue"] == 375.0
    assert default_report["rows"][0]["matterLinks"] == [{
        "clientName": "Client One", "matterName": "Contract renewal", "matterId": "M-ONE"
    }]
    assert default_report["rows"][0]["serviceFor"] == "Client One — Contract renewal"
    assert default_report["sections"][0]["columns"][0]["label"] == "Item"
    assert default_report["sections"][0]["columns"][1]["label"] == "Details"
    assert default_report["sections"][1]["columns"][2]["label"] == "Client & Matter"

    selected_report = ExcelRepo.statement_of_account_report(
        repo,
        {
            "billingClient": "Leviathan Private Network",
            "asOfDate": "2026-07-31",
            "selectedInvoiceNumbers": ["26-0102"],
        },
    )

    assert selected_report["selectionProvided"] is True
    assert [row["invoice"] for row in selected_report["rows"]] == ["26-0102"]
    assert selected_report["summary"]["invoiceCount"] == 1
    assert selected_report["summary"]["amountDue"] == 300.0


def test_statement_does_not_substitute_the_billing_client_for_a_missing_work_matter():
    class _NoContextRepo(_StatementRepo):
        def _canonical_ar_ledger(self, _payload):
            return {
                "ok": True,
                "events": [
                    {
                        "date": "2026-07-04",
                        "reference": "26-0199",
                        "invoice": "26-0199",
                        "type": "Invoice",
                        "debit": 300.0,
                        "credit": 0.0,
                        "status": "Unpaid",
                        "billingClient": "Leviathan Private Network",
                        "workClient": "Leviathan Private Network",
                    }
                ],
            }

    result = ExcelRepo.statement_of_account_report(
        _NoContextRepo(),
        {"billingClient": "Leviathan Private Network", "asOfDate": "2026-07-31"},
    )

    assert result["ok"] is True
    assert result["rows"][0]["serviceFor"] == "Client matter not recorded"
    assert result["rows"][0]["serviceFor"] != "Leviathan Private Network"


def test_statement_absorbs_background_adjustments_without_exposing_a_client_credit():
    class _BackgroundAdjustmentRepo(_StatementRepo):
        def _canonical_ar_ledger(self, _payload):
            return {
                "ok": True,
                "events": [
                    {
                        "date": "2026-05-31",
                        "reference": "26-0055",
                        "invoice": "26-0055",
                        "type": "Invoice",
                        "debit": 2361.71,
                        "credit": 0.0,
                        "status": "PENDING",
                        "billingClient": "Leviathan Private Network",
                        "workClient": "88 Queen",
                        "workContexts": [{"client": "88 Queen", "matter": "Tax Planning"}],
                        "statementValuesAvailable": True,
                        "statementInvoiceTotal": 2361.70,
                        "statementPaymentAmount": 0.0,
                        "statementBalanceDue": 2361.70,
                    }
                ],
            }

    result = ExcelRepo.statement_of_account_report(
        _BackgroundAdjustmentRepo(),
        {"billingClient": "Leviathan Private Network", "asOfDate": "2026-08-10"},
    )

    row = result["rows"][0]
    assert row["invoiceTotal"] == 2361.70
    assert row["paidCredits"] == 0.0
    assert row["paidCreditsFormatted"] == "\N{EM DASH}"
    assert row["balanceDue"] == 2361.70


def test_statement_resolves_client_and_plain_english_matter_from_billed_time():
    class _CanonicalContextRepo:
        _money_round = ExcelRepo._money_round
        _parse_date_value = ExcelRepo._parse_date_value
        _canonical_ar_ledger = ExcelRepo._canonical_ar_ledger
        _statement_open_invoice_candidates = ExcelRepo._statement_open_invoice_candidates
        _client_parent_lookup = ExcelRepo._client_parent_lookup

        def ensure_schema(self):
            return None

        def _read_legacy_docket_rows(self):
            return []

        def _read_table_rows(self, table_ref):
            table = getattr(table_ref, "table", table_ref)
            tables = {
                "tblReceivables": [{
                    sc.COL_RECV_INVOICE_NUM: "26-0200",
                    sc.COL_RECV_DATE: "2026-07-04",
                    sc.COL_RECV_CLIENT: "Leviathan Private Network",
                    sc.COL_RECV_WORK_CLIENT: "Leviathan Private Network",
                    sc.COL_RECV_TOTAL_INVOICED: 300.0,
                    sc.COL_RECV_AMOUNT_PAID: 0.0,
                    sc.COL_RECV_CREDITS_ADJ: 0.01,
                    sc.COL_RECV_BALANCE_DUE: 299.99,
                    sc.COL_RECV_STATUS: "Unpaid",
                }],
                "tblClients": [{
                    sc.COL_CLIENT_ID: "C-WORK",
                    sc.COL_CLIENT_NAME: "Client Two",
                }],
                "tblMatters": [{
                    sc.COL_MATTER_ID: "M-WORK",
                    sc.COL_MATTER_CLIENT_ID: "C-WORK",
                    sc.COL_MATTER_CLIENT_NAME: "Client Two",
                    sc.COL_MATTER_DESCRIPTION: "Tax planning",
                    sc.COL_MATTER_DISPLAY_NAME: "Legacy Matter CLIENT-TAX-26-0200",
                    sc.COL_MATTER_NAME: "Legacy Matter CLIENT-TAX-26-0200",
                }],
                "tblTimeEntries": [{
                    sc.COL_TIME_INVOICE_REF: "26-0200",
                    sc.COL_TIME_CLIENT_ID: "C-WORK",
                    sc.COL_TIME_MATTER_ID: "M-WORK",
                }],
            }
            return tables.get(table, [])

    result = ExcelRepo.statement_of_account_report(
        _CanonicalContextRepo(),
        {"billingClient": "Leviathan Private Network", "asOfDate": "2026-07-31"},
    )

    assert result["ok"] is True
    assert result["rows"][0]["serviceFor"] == "Client Two — Tax planning"
    assert result["rows"][0]["invoiceTotal"] == 299.99
    assert result["rows"][0]["paidCredits"] == 0.0
    assert result["rows"][0]["balanceDue"] == 299.99
    assert result["rows"][0]["matterLinks"] == [{
        "clientName": "Client Two", "matterName": "Tax planning", "matterId": "M-WORK"
    }]


def test_statement_does_not_append_a_reversed_legacy_matter_to_a_reissued_invoice():
    class _ReissuedContextRepo:
        _money_round = ExcelRepo._money_round
        _parse_date_value = ExcelRepo._parse_date_value
        _canonical_ar_ledger = ExcelRepo._canonical_ar_ledger
        _statement_open_invoice_candidates = ExcelRepo._statement_open_invoice_candidates
        _client_parent_lookup = ExcelRepo._client_parent_lookup

        def ensure_schema(self):
            return None

        def _read_legacy_docket_rows(self):
            # The historic 965 Canada row used the same number before the
            # invoice was reversed.  A different unresolved invoice requires
            # legacy lookup, but that must not revive this stale association.
            return [{
                "Invoice #": "26-0057",
                "Client": "965 Canada",
                "Matter": "965C-LEVI-TAX-26-0003",
            }]

        def _read_table_rows(self, table_ref):
            table = getattr(table_ref, "table", table_ref)
            tables = {
                "tblReceivables": [
                    {
                        sc.COL_RECV_INVOICE_NUM: "26-0057",
                        sc.COL_RECV_DATE: "2026-05-31",
                        sc.COL_RECV_CLIENT: "Leviathan Private Network",
                        sc.COL_RECV_TOTAL_INVOICED: 161.02,
                        sc.COL_RECV_AMOUNT_PAID: 0.0,
                        sc.COL_RECV_CREDITS_ADJ: 0.0,
                        sc.COL_RECV_BALANCE_DUE: 161.02,
                        sc.COL_RECV_STATUS: "Unpaid",
                    },
                    {
                        sc.COL_RECV_INVOICE_NUM: "26-0058",
                        sc.COL_RECV_DATE: "2026-05-31",
                        sc.COL_RECV_CLIENT: "Leviathan Private Network",
                        sc.COL_RECV_TOTAL_INVOICED: 100.0,
                        sc.COL_RECV_AMOUNT_PAID: 0.0,
                        sc.COL_RECV_CREDITS_ADJ: 0.0,
                        sc.COL_RECV_BALANCE_DUE: 100.0,
                        sc.COL_RECV_STATUS: "Unpaid",
                    },
                ],
                "tblClients": [
                    {sc.COL_CLIENT_ID: "C-AL", sc.COL_CLIENT_NAME: "AL ADVISOR"},
                    {sc.COL_CLIENT_ID: "C-965", sc.COL_CLIENT_NAME: "965 Canada"},
                ],
                "tblMatters": [
                    {
                        sc.COL_MATTER_ID: "M-AL",
                        sc.COL_MATTER_CLIENT_ID: "C-AL",
                        sc.COL_MATTER_CLIENT_NAME: "AL ADVISOR",
                        sc.COL_MATTER_DESCRIPTION: "Tax Planning",
                        sc.COL_MATTER_OPEN_DATE: "2026-05-01",
                    },
                    {
                        sc.COL_MATTER_ID: "M-965",
                        sc.COL_MATTER_CLIENT_ID: "C-965",
                        sc.COL_MATTER_CLIENT_NAME: "965 Canada",
                        sc.COL_MATTER_NUMBER: "965C-LEVI-TAX-26-0003",
                        sc.COL_MATTER_DESCRIPTION: "Tax Planning",
                        sc.COL_MATTER_OPEN_DATE: "2026-01-14",
                    },
                ],
                "tblTimeEntries": [{
                    sc.COL_TIME_INVOICE_REF: "26-0057",
                    sc.COL_TIME_CLIENT_ID: "C-AL",
                    sc.COL_TIME_MATTER_ID: "M-AL",
                }],
            }
            return tables.get(table, [])

    result = ExcelRepo.statement_of_account_report(
        _ReissuedContextRepo(),
        {"billingClient": "Leviathan Private Network", "asOfDate": "2026-07-31"},
    )

    reissued_row = next(row for row in result["rows"] if row["invoice"] == "26-0057")
    assert reissued_row["serviceFor"] == "AL ADVISOR \N{EM DASH} Tax Planning"
    assert reissued_row["matterLinks"] == [{
        "clientName": "AL ADVISOR", "matterName": "Tax Planning", "matterId": "M-AL"
    }]


def test_statement_pdf_is_rendered_from_selected_invoice_rows(tmp_path):
    output = generate_statement_of_account_pdf(
        {
            "client": "Leviathan Private Network",
            "statement": {
                "billingClient": "Leviathan Private Network",
                "asOfDate": date(2026, 7, 31).isoformat(),
                "invoiceCount": 1,
                "amountDue": 300.0,
                "amountDueFormatted": "$300.00",
            },
            "sections": [
                {
                    "sectionId": "detail",
                    "rows": [
                        {
                            "date": "2026-07-04",
                            "reference": "26-0102",
                            "serviceFor": "Client Two",
                            "invoiceTotalFormatted": "$300.00",
                            "paidCreditsFormatted": "—",
                            "balanceDueFormatted": "$300.00",
                        }
                    ],
                }
            ],
            "config": {"firmName": "Cory Schneider Law Office"},
        },
        str(tmp_path),
        "",
    )

    pdf_path = tmp_path / output.split("\\")[-1]
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_statement_pdf_uses_invoice_scale_header_logo(tmp_path, monkeypatch):
    captured_config = {}

    def capture_header(_canvas, _document, config, _logo_path):
        captured_config.update(config)

    monkeypatch.setattr("services.report_pdf_exporter._draw_header_footer", capture_header)
    generate_statement_of_account_pdf(
        {
            "statement": {"billingClient": "Example Client"},
            "sections": [],
            "config": {"firmName": "Cory Schneider Law Office"},
        },
        str(tmp_path),
        "",
    )

    assert captured_config["headerLogoWidth"] == 64.8
    assert captured_config["headerLogoHeight"] == 41.04
    assert captured_config["headerLogoBottomAligned"] is True
