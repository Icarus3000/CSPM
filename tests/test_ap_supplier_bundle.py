from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    # Append rather than prepend: this avoids shadowing Python's stdlib
    # ``platform`` module with CSPM's own compatibility package.
    sys.path.append(str(SOURCE_ROOT))

from services.ap_orchestration_service import APOrchestrationService


class _Repo:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_bill(self, bill_id: str):
        return self.rows.get(bill_id)

    def list_bills(self):
        return list(self.rows.values())

    def create_bill(self, bill: dict):
        saved = dict(bill)
        self.rows[saved["APBillID"]] = saved
        return saved

    def update_bill(self, bill: dict):
        saved = dict(bill)
        self.rows[saved["APBillID"]] = saved
        return saved

    def delete_bill(self, bill_id: str):
        self.rows.pop(bill_id, None)
        return {"ok": True}


class _Gateway:
    def __init__(self) -> None:
        self.expense = None
        self.disbursement = None

    def _assert_write_permitted(self):
        return None

    def save_ap_expense(self, payload: dict):
        self.expense = dict(payload)
        return {"ok": True, "transactionId": payload["transactionId"]}

    def create_supplier_disbursement(self, payload: dict):
        self.disbursement = dict(payload)
        return {"ok": True, "disbursementId": "DISB-1"}


class _HistoricalGateway:
    def __init__(self, transactions: list[dict], disbursements: list[dict], ledger_rows: list[dict]) -> None:
        self.transactions = transactions
        self.disbursements = disbursements
        self.ledger_rows = ledger_rows

    def list_transactions(self, _filters=None):
        return list(self.transactions)

    def _read_table_rows(self, table):
        table_name = getattr(table, "table", str(table))
        if table_name == "tblDisbursements":
            return list(self.disbursements)
        if table_name == "tblLedger":
            return list(self.ledger_rows)
        return []


def test_usd_supplier_bill_uses_cad_expense_and_single_client_wip_entry() -> None:
    repo = _Repo()
    gateway = _Gateway()
    service = APOrchestrationService(repo, gateway)

    result = service.create_bill({
        "APBillID": "APB-USD-1",
        "Vendor": "Spencer Fane LLP",
        "VendorInvoiceNumber": "1557960",
        "InvoiceDate": "2026-07-17",
        "Subtotal": 1513.00,
        "TaxAmount": 0,
        "Total": 1513.00,
        "TaxExempt": True,
        "Currency": "USD",
        "FXRate": "1.4408425",
        "MatterID": "FERR-TMK-26-0001",
        "BillClaimPct": 100,
        "ClientTaxExempt": False,
        "CategoryCode": "EXP_LEGAL",
        "CategoryName": "Legal expense",
        "ExpenseTreatment": "matter",
    })

    assert result.ok is True
    assert gateway.expense["fromAccount"] == "AP_PAYABLE"
    assert gateway.expense["currency"] == "CAD"
    assert gateway.expense["amount"] == 2179.99
    assert gateway.disbursement["Amount"] == 2179.99
    assert gateway.disbursement["OriginalCurrency"] == "USD"
    assert repo.rows["APB-USD-1"]["DisbursementID"] == "DISB-1"


def test_historical_candidate_follows_verified_ledger_invoice_link_when_legacy_expense_has_no_matter() -> None:
    gateway = _HistoricalGateway(
        transactions=[{
            "transactionId": "TRX-260717083805",
            "txnDate": "2026-07-17",
            "type": "Expense",
            "payee": "Spencer Fane",
            "client": "Spencer Fane",
            "matter": "",
            "invoiceRef": "1557960",
            "amount": 2179.99,
            "taxAmount": 0,
            "currency": "CAD",
            "status": "Cleared",
        }],
        disbursements=[{
            "DisbursementID": "LEG-DISB-6AAB53B587E531D605CC",
            "ClientName": "Ferreira Inc.",
            "SubClient": "",
            "MatterID": "FERR-TMK-26-0001",
            "Amount": 2179.99,
            "InvoiceRef": "26-0077",
            "APBillID": "",
        }],
        ledger_rows=[{
            "TrxID": "TRX-260717083805",
            "Reference": "26-0077",
            "ExternalRefID": "1557960",
            "WorkClient": "Ferreira Inc.",
        }],
    )
    gateway._read_table_rows = lambda table: (
        [{
            "MatterID": "f9a2f5ae-e651-4d1f-868a-ddd4c44aab6e",
            "MatterNumber": "FERR-TMK-26-0001",
            "ClientID": "FERR",
            "ClientName": "Ferreira Inc.",
        }]
        if getattr(table, "table", str(table)) == "tblMatters"
        else (_HistoricalGateway._read_table_rows(gateway, table))
    )

    candidates = APOrchestrationService(_Repo(), gateway).list_historical_candidates("Spencer Fane")

    assert len(candidates) == 1
    assert candidates[0]["disbursementId"] == "LEG-DISB-6AAB53B587E531D605CC"
    assert candidates[0]["clientInvoiceRef"] == "26-0077"
    assert candidates[0]["matchMethod"] == "legacy-ledger-invoice"
    assert candidates[0]["matterId"] == "f9a2f5ae-e651-4d1f-868a-ddd4c44aab6e"
    assert candidates[0]["clientId"] == "FERR"
