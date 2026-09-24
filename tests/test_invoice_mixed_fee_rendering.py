from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from backend.controllers.billing_controller import BillingController
from domain import schema_constants as sc
from services.invoice_document_service import InvoiceDocumentService
from services.invoice_draft_service import InvoiceDraftService


DRAFT_NUM = "DRAFT-2026-MIXED"
CLIENT_ID = "CLIENT-MIXED"
MATTER_ID = "MATTER-MIXED"


class _MixedInvoiceRepo:
    def __init__(self) -> None:
        self._ids = 0
        self.tables = {
            sc.TBL_DRAFT_INVOICES: [{
                sc.COL_DRAFT_ID: "DRAFT-ID-MIXED",
                sc.COL_DRAFT_INVOICE_NUM: DRAFT_NUM,
                sc.COL_DRAFT_CLIENT_ID: CLIENT_ID,
                sc.COL_DRAFT_CLIENT_NAME: "Truexperiences Tours Inc.",
                sc.COL_DRAFT_DATE: "2026-09-24",
                sc.COL_DRAFT_DISCOUNT_TYPE: "Flat",
                sc.COL_DRAFT_DISCOUNT_VALUE: "270.00",
                sc.COL_DRAFT_AGENCY_SPLIT_PERCENT: "0.00",
                sc.COL_DRAFT_GROUPING_PREF: "matter",
                sc.COL_DRAFT_IS_FLAT_FEE: "False",
                sc.COL_DRAFT_SHOW_TOTAL_HOURS: "True",
                sc.COL_DRAFT_TOTAL_FEES: "0.00",
                sc.COL_DRAFT_TOTAL_TAX: "0.00",
                sc.COL_DRAFT_TOTAL_DUE: "0.00",
                sc.COL_DRAFT_BILL_TO_SNAPSHOT: "",
                sc.COL_DRAFT_REISSUE_INVOICE_NUM: "",
            }],
            sc.TBL_TIME: [
                self._time_row("TIME-1", "2026-08-10", "Telephone conference", "0.4", "475.00", "190.00", "24.70"),
                self._time_row("TIME-2", "2026-08-12", "Review TMOB decision", "0.8", "475.00", "380.00", "49.40"),
                self._time_row(
                    "FLAT-1",
                    "2026-09-23",
                    "Draft and file CIPO TM Application for TRAVEL GENIUS",
                    "0.0",
                    "0.00",
                    "950.00",
                    "123.50",
                    lock_audit=(
                        "EntryType:Fee || FeeOrigin:InvoiceDraft || "
                        "DraftOwnerID:DRAFT-ID-MIXED || DraftRef:DRAFT-2026-MIXED || "
                        "RequestID:CFR_mixed_additive || CustomFeeLineID:FLAT-1 || "
                        "CustomFeeState:Draft || FeeTreatment:Additive"
                    ),
                ),
            ],
            sc.TBL_DISBURSEMENTS: [{
                sc.COL_DISB_ID: "DISB-1",
                sc.COL_DISB_DATE: "2026-09-23",
                sc.COL_DISB_CLIENT_ID: CLIENT_ID,
                sc.COL_DISB_MATTER_ID: MATTER_ID,
                sc.COL_DISB_DESCRIPTION: "CIPO Filing Fees - supplier invoice 20576109",
                sc.COL_DISB_AMOUNT: "491.06",
                sc.COL_DISB_TAX_EXEMPT: "True",
                sc.COL_DISB_INVOICE_REF: DRAFT_NUM,
                sc.COL_DISB_REISSUE_INVOICE_NUM: "",
                sc.COL_DISB_SOURCE_TRANSACTION_ID: "TXN-CIPO-1",
            }],
            sc.TBL_MATTERS: [{
                sc.COL_MATTER_ID: MATTER_ID,
                sc.COL_MATTER_CLIENT_ID: CLIENT_ID,
                sc.COL_MATTER_PARENT_ID: "",
                sc.COL_MATTER_NUMBER: "TRUE-TMK-26-0087",
                sc.COL_MATTER_NAME: "2026 CIPO Application - Travel Genius",
            }],
            sc.TBL_INVOICE_LOG: [],
            sc.TBL_RECEIVABLES: [],
            sc.TBL_LEDGER: [],
            sc.TBL_TRANSACTIONS_MASTER: [{
                sc.COL_TXN_ID: "TXN-CIPO-1",
                sc.COL_TXN_PAYEE: "CIPO",
            }],
        }

    @staticmethod
    def _time_row(entry_id, date, description, hours, rate, net, tax, lock_audit=""):
        return {
            sc.COL_TIME_ENTRY_ID: entry_id,
            sc.COL_TIME_DATE: date,
            sc.COL_TIME_CLIENT_ID: CLIENT_ID,
            sc.COL_TIME_MATTER_ID: MATTER_ID,
            sc.COL_TIME_PARENT_ID: "",
            sc.COL_TIME_DESC: description,
            sc.COL_TIME_HOURS: hours,
            sc.COL_TIME_RATE: rate,
            sc.COL_TIME_GROSS: net,
            sc.COL_TIME_NET: net,
            sc.COL_TIME_HST: tax,
            sc.COL_TIME_TOTAL: str(float(net) + float(tax)),
            sc.COL_TIME_STATUS: "Draft",
            sc.COL_TIME_INVOICE_REF: DRAFT_NUM,
            sc.COL_TIME_INVOICE_STATUS: "Draft",
            sc.COL_TIME_PAYMENT_STATUS: "",
            sc.COL_TIME_INVOICE_TOTAL: "0.00",
            sc.COL_TIME_INVOICE_AMOUNT_PAID: "0.00",
            sc.COL_TIME_INVOICE_BALANCE_DUE: "0.00",
            sc.COL_TIME_INVOICE_DATE: "",
            sc.COL_TIME_REISSUE_INVOICE_NUM: "",
            sc.COL_TIME_LOCK_AUDIT: lock_audit,
        }

    def _read_table_rows(self, table):
        key = getattr(table, "table", table)
        return copy.deepcopy(self.tables.get(key, []))

    def _read_table_rows_bulk(self, tables):
        return {table: self._read_table_rows(table) for table in tables}

    def _write_table_rows(self, table, rows):
        key = getattr(table, "table", table)
        self.tables[key] = copy.deepcopy(rows)

    def _write_table_rows_bulk(self, table_rows):
        for table, rows in table_rows.items():
            self.tables[table] = copy.deepcopy(rows)

    def _new_id(self, prefix):
        self._ids += 1
        return f"{prefix}-{self._ids}"

    def get_client_profile(self, client_id):
        if str(client_id) != CLIENT_ID:
            return {"ok": False}
        return {
            "ok": True,
            "client": {
                "clientId": CLIENT_ID,
                "clientName": "Truexperiences Tours Inc.",
                "displayName": "Truexperiences Tours Inc.",
                "addressLine1": "1 Test Street",
                "city": "Toronto",
                "stateProvince": "ON",
                "postalCode": "M5V 1A1",
                "country": "Canada",
            },
        }

    def get_matter_profile(self, matter_id):
        if str(matter_id) != MATTER_ID:
            return {"ok": False}
        return {
            "ok": True,
            "matter": {
                "matterId": MATTER_ID,
                "matterNumber": "TRUE-TMK-26-0087",
                "matterName": "2026 CIPO Application - Travel Genius",
                "displayName": "2026 CIPO Application - Travel Genius",
                "description": "2026 CIPO Application - Travel Genius",
                "clientId": CLIENT_ID,
            },
        }


def _controller(repo: _MixedInvoiceRepo, service: InvoiceDraftService) -> BillingController:
    documents = InvoiceDocumentService(str(PROJECT_ROOT / "src" / "templates" / "invoices"))
    return BillingController(repo, service, documents)


def test_mixed_hourly_additive_flat_fee_and_disbursement_render_separately():
    repo = _MixedInvoiceRepo()
    service = InvoiceDraftService(repo)
    service.recalculate_draft_totals(DRAFT_NUM)
    draft = service.get_draft(DRAFT_NUM)

    assert draft[sc.COL_DRAFT_TOTAL_FEES] == "1741.06"
    assert draft[sc.COL_DRAFT_TOTAL_TAX] == "162.50"
    assert draft[sc.COL_DRAFT_TOTAL_DUE] == "1903.56"

    controller = _controller(repo, service)
    payload = controller._build_invoice_payload(DRAFT_NUM)

    assert payload["is_flat_fee"] is False
    assert payload["has_any_flat_fee"] is True
    assert payload["total_hours"] == pytest.approx(1.2)
    assert payload["gross_professional_fees"] == 1520.0
    assert payload["discount_amount"] == 270.0
    assert payload["net_professional_fees"] == 1250.0
    assert payload["disbursement_total"] == 491.06
    assert payload["total_tax"] == 162.5
    assert payload["total_due"] == 1903.56
    assert len(payload["hourly_matters"][0]["line_items"]) == 2
    assert len(payload["additive_flat_fee_lines"]) == 1
    assert len(payload["disbursement_lines"]) == 1
    assert payload["disbursement_lines"][0]["supplierName"] == "CIPO"
    assert payload["disbursement_lines"][0]["description"] == (
        "CIPO Filing Fees - CIPO invoice 20576109 (Tax Exempt)."
    )

    html = controller._doc_svc.generate_html("Concept_A2", payload)
    assert "Flat Fees" in html
    assert "Disbursements" in html
    assert "CIPO Filing Fees - CIPO invoice 20576109 (Tax Exempt)." in html
    assert "supplier invoice 20576109" not in html
    assert "Total Professional Time" not in html
    assert "$1,520.00" in html
    assert "$491.06" in html
    assert "$1,903.56" in html
    assert "$2,011.06" not in html


def test_finalization_records_professional_fees_and_disbursements_separately():
    repo = _MixedInvoiceRepo()
    service = InvoiceDraftService(repo)

    assert service.finalize_draft(DRAFT_NUM, "26-0109", "") is True

    invoice = repo.tables[sc.TBL_INVOICE_LOG][0]
    ledger = repo.tables[sc.TBL_LEDGER][0]
    assert invoice[sc.COL_INV_TOTAL_FEES] == "1250.00"
    assert invoice[sc.COL_INV_TOTAL_DISBURSEMENTS] == "491.06"
    assert invoice[sc.COL_INV_TOTAL_TAX] == "162.50"
    assert invoice[sc.COL_INV_AGGREGATE_BILLED] == "1903.56"
    assert ledger[sc.COL_LEDGER_BILLINGS_EXCL_HST] == "1741.06"
    assert ledger[sc.COL_LEDGER_HST_COLLECTED] == "162.50"
    assert ledger[sc.COL_LEDGER_RECEIVABLE] == "1903.56"


def test_legacy_amount_only_fee_is_additive_not_an_invoice_override():
    repo = _MixedInvoiceRepo()
    repo.tables[sc.TBL_TIME][2][sc.COL_TIME_LOCK_AUDIT] = ""
    service = InvoiceDraftService(repo)
    controller = _controller(repo, service)

    payload = controller._build_invoice_payload(DRAFT_NUM)

    assert payload["is_flat_fee"] is False
    assert payload["has_any_flat_fee"] is True
    assert payload["gross_professional_fees"] == 1520.0
    assert payload["additive_flat_fee_lines"][0]["amount"] == 950.0


def test_total_professional_time_can_be_hidden_on_an_hourly_only_invoice():
    repo = _MixedInvoiceRepo()
    repo.tables[sc.TBL_TIME] = repo.tables[sc.TBL_TIME][:2]
    repo.tables[sc.TBL_DISBURSEMENTS] = []
    repo.tables[sc.TBL_DRAFT_INVOICES][0][sc.COL_DRAFT_SHOW_TOTAL_HOURS] = "False"
    service = InvoiceDraftService(repo)
    controller = _controller(repo, service)

    payload = controller._build_invoice_payload(DRAFT_NUM)
    assert payload["has_any_flat_fee"] is False
    assert payload["show_total_hours"] is False
    assert "Total Professional Time" not in controller._doc_svc.generate_html("Concept_A2", payload)

    controller.updateDraftMeta(DRAFT_NUM, {"showTotalHours": True})
    refreshed = controller._build_invoice_payload(DRAFT_NUM)
    assert refreshed["show_total_hours"] is True
    assert "Total Professional Time" in controller._doc_svc.generate_html("Concept_A2", refreshed)
