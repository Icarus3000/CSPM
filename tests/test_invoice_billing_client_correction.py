import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from domain import schema_constants as sc
from services.invoice_draft_service import InvoiceDraftService


class _BillingCorrectionRepo:
    def __init__(self, *, finalized=True):
        self.bulk_writes = []
        self._next_id = 0
        self.profiles = {
            "CONC": {
                "clientId": "CONC",
                "clientName": "Concierge Club",
                "displayName": "Concierge Club",
                "parentClientId": "LEVI",
                "parentClientName": "Leviathan Private Network",
                "active": 1,
            },
            "LEVI": {
                "clientId": "LEVI",
                "clientName": "Leviathan Private Network",
                "displayName": "Leviathan Private Network",
                "fullAddress": "7 St. Thomas Street, Suite 307\nToronto, Ontario M5S 2B7",
                "primaryEmail": "billing@example.test",
                "active": 1,
            },
        }
        invoice_ref = "26-0095" if finalized else ""
        status = "Billed" if finalized else "Draft"
        self.tables = {
            sc.TBL_TIME: [{
                sc.COL_TIME_ENTRY_ID: "TIME-95",
                sc.COL_TIME_DATE: "2026-07-29",
                sc.COL_TIME_CLIENT_ID: "CONC",
                sc.COL_TIME_MATTER_ID: "MAT-RESEARCH",
                sc.COL_TIME_PARENT_ID: "LEVI",
                sc.COL_TIME_DESC: "Legal research",
                sc.COL_TIME_HOURS: "0.8",
                sc.COL_TIME_GROSS: "380.00",
                sc.COL_TIME_NET: "380.00",
                sc.COL_TIME_HST: "49.40",
                sc.COL_TIME_TOTAL: "429.40",
                sc.COL_TIME_STATUS: status,
                sc.COL_TIME_INVOICE_REF: invoice_ref,
                sc.COL_TIME_INVOICE_STATUS: status,
            }],
            sc.TBL_DISBURSEMENTS: [],
            sc.TBL_MATTERS: [{
                sc.COL_MATTER_ID: "MAT-RESEARCH",
                sc.COL_MATTER_CLIENT_ID: "CONC",
                sc.COL_MATTER_CLIENT_NAME: "Concierge Club",
                sc.COL_MATTER_PARENT_ID: "LEVI",
            }],
            sc.TBL_DRAFT_INVOICES: [],
            sc.TBL_INVOICE_LOG: [{
                sc.COL_INV_INVOICE_NUM: "26-0095",
                sc.COL_INV_CLIENT_NAME: "Concierge Club",
                sc.COL_INV_SUB_CLIENT: "",
                sc.COL_INV_BILL_TO_CLIENT: "",
                sc.COL_INV_BILL_TO_SNAPSHOT: "",
                sc.COL_INV_INVOICE_DATE: "2026-07-31",
                sc.COL_INV_TOTAL_FEES: "380.00",
                sc.COL_INV_TOTAL_TAX: "49.40",
                sc.COL_INV_AGGREGATE_BILLED: "429.40",
            }] if finalized else [],
            sc.TBL_RECEIVABLES: [{
                sc.COL_RECV_INVOICE_NUM: "26-0095",
                sc.COL_RECV_DATE: "2026-07-31",
                sc.COL_RECV_CLIENT: "Concierge Club",
                sc.COL_RECV_WORK_CLIENT: "",
                sc.COL_RECV_TOTAL_INVOICED: "429.40",
                sc.COL_RECV_AMOUNT_PAID: "0.00",
                sc.COL_RECV_CREDITS_ADJ: "0.00",
                sc.COL_RECV_BALANCE_DUE: "429.40",
                sc.COL_RECV_STATUS: "Unpaid",
            }] if finalized else [],
            sc.TBL_LEDGER: [{
                sc.COL_LEDGER_ID: "LED-95",
                sc.COL_LEDGER_CLIENT_VENDOR: "Concierge Club",
                sc.COL_LEDGER_CATEGORY: "Revenue",
                sc.COL_LEDGER_REFERENCE: "26-0095",
                sc.COL_LEDGER_BILLINGS_EXCL_HST: "380.00",
                sc.COL_LEDGER_HST_COLLECTED: "49.40",
                sc.COL_LEDGER_RECEIVABLE: "429.40",
                sc.COL_LEDGER_WORK_CLIENT: "",
            }] if finalized else [],
            sc.TBL_TRANSACTIONS_MASTER: [{
                sc.COL_TXN_ID: "TXN-95",
                sc.COL_TXN_INVOICE_REF: "26-0095",
                sc.COL_TXN_TYPE: "Income",
                sc.COL_TXN_CATEGORY_CODE: "INC_LEGAL_FEES",
                sc.COL_TXN_CLIENT: "Concierge Club",
            }] if finalized else [],
        }

    def _read_table_rows(self, table):
        return deepcopy(self.tables.get(table, []))

    def _read_table_rows_bulk(self, tables):
        return {table: self._read_table_rows(table) for table in tables}

    def _write_table_rows(self, table, rows):
        self.tables[table] = deepcopy(rows)

    def _write_table_rows_bulk(self, table_rows):
        snapshot = {}
        for table, rows in table_rows.items():
            copied = deepcopy(rows)
            self.tables[table] = copied
            snapshot[table] = copied
        self.bulk_writes.append(snapshot)

    def _new_id(self, prefix):
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    def get_client_profile(self, client_key):
        lookup = str(client_key or "").strip().casefold()
        for client_id, profile in self.profiles.items():
            if lookup in {
                client_id.casefold(),
                str(profile.get("clientName") or "").casefold(),
                str(profile.get("displayName") or "").casefold(),
            }:
                return {"ok": True, "client": deepcopy(profile)}
        return {"ok": False, "message": f"Client not found: {client_key}", "client": {}}

    def list_client_directory(self):
        return [deepcopy(profile) for profile in self.profiles.values()]

    def list_invoice_bill_to_options(self, _entry_ids):
        return []


def test_parent_bill_to_is_frozen_for_ordinary_draft_and_used_by_finalization():
    repo = _BillingCorrectionRepo(finalized=False)
    service = InvoiceDraftService(repo)

    draft_num = service.create_draft("CONC", "Concierge Club", ["TIME-95"])
    draft = service.get_draft(draft_num)
    snapshot = json.loads(draft[sc.COL_DRAFT_BILL_TO_SNAPSHOT])

    assert snapshot["clientId"] == "LEVI"
    assert snapshot["clientName"] == "Leviathan Private Network"
    assert snapshot["selectionSource"] == "ordinary-matter-draft"

    assert service.finalize_draft(draft_num, "26-0095", "C:/test.pdf") is True
    receivable = repo.tables[sc.TBL_RECEIVABLES][0]
    invoice = repo.tables[sc.TBL_INVOICE_LOG][0]
    ledger = repo.tables[sc.TBL_LEDGER][0]

    assert receivable[sc.COL_RECV_CLIENT] == "Leviathan Private Network"
    assert receivable[sc.COL_RECV_WORK_CLIENT] == "Concierge Club"
    assert invoice[sc.COL_INV_CLIENT_NAME] == "Concierge Club"
    assert invoice[sc.COL_INV_SUB_CLIENT] == "Concierge Club"
    assert invoice[sc.COL_INV_BILL_TO_CLIENT] == "Leviathan Private Network"
    assert ledger[sc.COL_LEDGER_CLIENT_VENDOR] == "Leviathan Private Network"
    assert ledger[sc.COL_LEDGER_WORK_CLIENT] == "Concierge Club"


def test_unpaid_invoice_correction_updates_all_billing_records_atomically():
    repo = _BillingCorrectionRepo()
    repo.tables[sc.TBL_TRANSACTIONS_MASTER].append({
        sc.COL_TXN_ID: "TXN-STRAY-RECEIPT",
        sc.COL_TXN_INVOICE_REF: "26-0095",
        sc.COL_TXN_TYPE: "Income",
        sc.COL_TXN_CATEGORY_CODE: "INC_LEGAL_FEES",
        sc.COL_TXN_CLIENT: "Concierge Club",
        sc.COL_TXN_FROM_ACCOUNT: "Operating Account",
        sc.COL_TXN_CLEARED_AT: "2026-08-01",
        sc.COL_TXN_NOTES: "Payment applied to invoice 26-0095",
    })
    service = InvoiceDraftService(repo)

    context = service.invoice_billing_correction_context("26-0095")
    assert context["eligible"] is True
    assert context["billingMismatch"] is True
    assert context["currentBillingClient"] == "Concierge Club"
    assert context["workClient"] == "Concierge Club"
    assert context["recommendedClientId"] == "LEVI"

    result = service.correct_finalized_invoice_billing_client(
        "26-0095",
        "LEVI",
        "PDF and linked matter identify the parent billing client.",
    )

    assert result["changed"] is True
    assert len(repo.bulk_writes) == 1
    assert set(repo.bulk_writes[0]) == {
        sc.TBL_INVOICE_LOG,
        sc.TBL_RECEIVABLES,
        sc.TBL_LEDGER,
        sc.TBL_TRANSACTIONS_MASTER,
    }
    invoice = repo.tables[sc.TBL_INVOICE_LOG][0]
    receivable = repo.tables[sc.TBL_RECEIVABLES][0]
    ledger = repo.tables[sc.TBL_LEDGER][0]
    transaction = repo.tables[sc.TBL_TRANSACTIONS_MASTER][0]
    receipt = repo.tables[sc.TBL_TRANSACTIONS_MASTER][1]

    assert invoice[sc.COL_INV_CLIENT_NAME] == "Concierge Club"
    assert invoice[sc.COL_INV_SUB_CLIENT] == "Concierge Club"
    assert invoice[sc.COL_INV_BILL_TO_CLIENT] == "Leviathan Private Network"
    assert receivable[sc.COL_RECV_CLIENT] == "Leviathan Private Network"
    assert receivable[sc.COL_RECV_WORK_CLIENT] == "Concierge Club"
    assert ledger[sc.COL_LEDGER_CLIENT_VENDOR] == "Leviathan Private Network"
    assert ledger[sc.COL_LEDGER_WORK_CLIENT] == "Concierge Club"
    assert transaction[sc.COL_TXN_CLIENT] == "Leviathan Private Network"
    assert receipt[sc.COL_TXN_CLIENT] == "Concierge Club"
    assert result["transactionRowsUpdated"] == 1

    snapshot = json.loads(invoice[sc.COL_INV_BILL_TO_SNAPSHOT])
    assert snapshot["clientId"] == "LEVI"
    assert snapshot["selectionSource"] == "invoice-billing-client-correction"
    assert snapshot["billingCorrections"][-1]["fromClient"] == "Concierge Club"
    assert snapshot["billingCorrections"][-1]["toClient"] == "Leviathan Private Network"
    assert snapshot["billingCorrections"][-1]["reason"].startswith("PDF and linked matter")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (sc.COL_RECV_AMOUNT_PAID, "1.00"),
        (sc.COL_RECV_CREDITS_ADJ, "1.00"),
        (sc.COL_RECV_STATUS, "Paid"),
    ],
)
def test_billing_client_correction_rejects_paid_credited_or_closed_invoice(field, value):
    repo = _BillingCorrectionRepo()
    repo.tables[sc.TBL_RECEIVABLES][0][field] = value
    service = InvoiceDraftService(repo)

    context = service.invoice_billing_correction_context("26-0095")
    assert context["eligible"] is False
    with pytest.raises(ValueError, match="completely unpaid"):
        service.correct_finalized_invoice_billing_client(
            "26-0095",
            "LEVI",
            "Correct the billing client.",
        )
    assert repo.bulk_writes == []


def test_invoice_directory_exposes_guarded_billing_client_correction_workflow():
    qml = (PROJECT_ROOT / "src" / "qml" / "views" / "InvoiceReversalView.qml").read_text(
        encoding="utf-8"
    )
    controller = (
        PROJECT_ROOT / "src" / "python" / "backend" / "controllers" / "billing_controller.py"
    ).read_text(encoding="utf-8")

    assert "Correct Billing Client" in qml
    assert "currentBillingClient" in qml
    assert "recommendedClientName" in qml
    assert "correctInvoiceBillingClient" in qml
    assert "does not change the amount, date, work client, matter, or existing PDF" in qml
    assert "def loadInvoiceBillingCorrectionContext" in controller
    assert "def correctInvoiceBillingClient" in controller
