from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "invoice_amount_repair", ROOT / "scripts" / "repair_finalized_invoice_amounts.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def snapshot():
    return {
        "tblReceivables": [
            {"InvoiceNum": "26-0101", "TotalInvoiced": "1106.02",
             "BalanceDue": "1106.02", "AmountPaid": "0", "CreditsAdj": "0"},
            {"InvoiceNum": "26-0101-SUPERSEDED", "TotalInvoiced": "1106.02",
             "BalanceDue": "0", "AmountPaid": "0", "CreditsAdj": "0"},
        ],
        "tblLedger": [
            {"Reference": "26-0101", "Category": "Revenue", "Receivable": "1106.02"},
            {"Reference": "26-0101", "Category": "Payment", "Receivable": "0"},
        ],
        "tblTransactionsMaster": [{"InvoiceRef": "26-0101-SUPERSEDED-V", "Amount": "-978.78"}],
    }


def test_scope_accepts_active_projection_and_numeric_storage_equivalence():
    before = snapshot()
    after = deepcopy(before)
    after["tblReceivables"][0].update(TotalInvoiced="1580.02", BalanceDue="1580.02", AmountPaid=0)
    after["tblLedger"][0]["Receivable"] = "1580.02"
    assert len(module.verify_scope(before, after, "26-0101")) == 3


@pytest.mark.parametrize("table,index,field,value", [
    ("tblReceivables", 0, "AmountPaid", "25"),
    ("tblReceivables", 0, "CreditsAdj", "25"),
    ("tblReceivables", 1, "TotalInvoiced", "1580.02"),
    ("tblLedger", 1, "Receivable", "25"),
    ("tblTransactionsMaster", 0, "Amount", "-1398.25"),
])
def test_scope_refuses_payment_credit_archive_and_contra_changes(table, index, field, value):
    before = snapshot()
    after = deepcopy(before)
    after[table][index][field] = value
    with pytest.raises(RuntimeError):
        module.verify_scope(before, after, "26-0101")


def test_scope_refuses_added_or_removed_records():
    before = snapshot()
    after = deepcopy(before)
    after["tblReceivables"].append(dict(after["tblReceivables"][0]))
    with pytest.raises(RuntimeError, match="row count"):
        module.verify_scope(before, after, "26-0101")


def test_billing_scope_changes_issuance_owner_and_preserves_transaction_money():
    before = snapshot()
    before["tblTransactionsMaster"].append({
        "InvoiceRef": "26-0101", "FromAccount": "ACCOUNTS_RECEIVABLE",
        "ToAccount": "LEGAL_REVENUE", "Type": "Income",
        "CategoryCode": "INC_LEGAL_FEES", "Client": "Work client", "Amount": "1106.02",
    })
    after = deepcopy(before)
    after["tblTransactionsMaster"][1]["Client"] = "LIHDC Professional Corporation"
    plan = {"26-0101": {"billingClient": "LIHD"}}
    assert len(module.verify_scope(before, after, plan)) == 1
    after["tblTransactionsMaster"][1]["Amount"] = "1580.02"
    with pytest.raises(RuntimeError, match="Unrelated mutation"):
        module.verify_scope(before, after, plan)


def test_billing_scope_refuses_bank_receipt_owner_change():
    before = snapshot()
    before["tblTransactionsMaster"].append({
        "InvoiceRef": "26-0101", "FromAccount": "OPERATING_BANK",
        "ToAccount": "LEGAL_REVENUE", "Type": "Income",
        "CategoryCode": "INC_LEGAL_FEES", "Client": "Work client",
    })
    after = deepcopy(before)
    after["tblTransactionsMaster"][1]["Client"] = "LIHDC Professional Corporation"
    with pytest.raises(RuntimeError, match="outside verified invoice issuance"):
        module.verify_scope(before, after, {"26-0101": {"billingClient": "LIHD"}})
