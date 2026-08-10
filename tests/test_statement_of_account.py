import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    # Append rather than prepend: the repository has a ``platform`` package,
    # while pytest itself correctly needs the Python standard-library module.
    sys.path.append(str(SOURCE_ROOT))

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
