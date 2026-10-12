"""AP mutations obey the same writer ownership as the accounting gateway."""
from __future__ import annotations

from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from backend import data_verification
from backend.controllers.ap_controller import APController
from repositories.ap_workbook_repository import APWorkbookRepository


ROOT = Path(__file__).resolve().parents[1]
BILL = {
    "APBillID": "APB-SYNTHETIC-LEASE",
    "Vendor": "Synthetic writer guard vendor",
    "VendorInvoiceNumber": "SYNTHETIC-LEASE-001",
    "InvoiceDate": "2026-10-12",
    "Subtotal": 100,
    "TaxAmount": 13,
    "ExpenseTransactionID": "TXN-SYNTHETIC-LEASE",
}
PAYMENT = {
    "APPaymentID": "APP-SYNTHETIC-LEASE",
    "APBillID": BILL["APBillID"],
    "PaymentDate": "2026-10-12",
    "Amount": 25,
    "FromAccount": "Synthetic account",
}
MUTATIONS = (
    ("create_bill", ({**BILL, "APBillID": "APB-SYNTHETIC-SECOND", "VendorInvoiceNumber": "SYNTHETIC-LEASE-002"},)),
    ("update_bill", ({**BILL, "Notes": "Synthetic update"},)),
    ("delete_bill", (BILL["APBillID"],)),
    ("post_payment", (PAYMENT,)),
    ("reverse_payment", (PAYMENT["APPaymentID"], "APP-SYNTHETIC-REVERSAL", "Synthetic reversal")),
    ("update_payment_metadata", (PAYMENT["APPaymentID"], {"PaymentTransactionID": "TXN-SYNTHETIC-PAYMENT"})),
)


@pytest.fixture(autouse=True)
def isolated_policy(monkeypatch):
    monkeypatch.setenv(data_verification.ENVIRONMENT_KEY, "0")


@pytest.fixture
def workbook_path(tmp_path):
    target = tmp_path / "CSPM.xlsm"
    shutil.copyfile(ROOT / "src/templates/CSPM.xlsm", target)
    return target


def refuse_lease():
    raise PermissionError("Synthetic session does not own the writer checkout")


@pytest.mark.parametrize("method,args", MUTATIONS)
def test_non_writer_cannot_change_any_ap_record(workbook_path, method, args):
    before = workbook_path.read_bytes()
    repository = APWorkbookRepository(workbook_path, write_guard=refuse_lease)
    with pytest.raises(PermissionError, match="does not own"):
        getattr(repository, method)(*args)
    assert workbook_path.read_bytes() == before


@pytest.mark.parametrize("method,args", MUTATIONS)
def test_lease_lost_before_commit_preserves_workbook(workbook_path, method, args):
    seed = APWorkbookRepository(workbook_path)
    seed.create_bill(BILL)
    if method in {"reverse_payment", "update_payment_metadata"}:
        seed.post_payment(PAYMENT)
    before = workbook_path.read_bytes()
    checks = []

    def lose_lease_before_save():
        checks.append("checked")
        if len(checks) > 1:
            refuse_lease()

    repository = APWorkbookRepository(workbook_path, write_guard=lose_lease_before_save)
    with pytest.raises(PermissionError, match="does not own"):
        getattr(repository, method)(*args)
    assert len(checks) == 2
    assert workbook_path.read_bytes() == before


def test_owner_can_save_and_reread_ap_bill(workbook_path):
    checks = []
    repository = APWorkbookRepository(workbook_path, write_guard=lambda: checks.append("owned"))
    saved = repository.create_bill(BILL)
    assert saved["APBillID"] == BILL["APBillID"]
    assert repository.get_bill(BILL["APBillID"])["Balance"] == 113
    assert len(checks) == 2


def test_readonly_verification_blocks_even_an_owned_lease(workbook_path):
    checks = []
    before = workbook_path.read_bytes()
    repository = APWorkbookRepository(workbook_path, write_guard=lambda: checks.append("owned"))
    data_verification.configure(settings={"readOnlyVerification": True})
    with pytest.raises(PermissionError, match="verification is read-only"):
        repository.create_bill(BILL)
    assert not checks
    assert workbook_path.read_bytes() == before


def test_ap_controller_fallback_repository_keeps_gateway_guard(workbook_path):
    gateway = SimpleNamespace(path=workbook_path, _assert_write_permitted=refuse_lease)
    controller = APController(gateway)
    before = workbook_path.read_bytes()
    with pytest.raises(PermissionError, match="does not own"):
        controller._ap_repository.create_bill(BILL)
    assert workbook_path.read_bytes() == before
