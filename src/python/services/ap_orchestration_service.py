from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from domain.ap_lifecycle import APValidationError, clean_text, money
from repositories.ap_workbook_repository import APWorkbookRepository


class ExpenseGateway(Protocol):
    def save_ap_expense(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_transactions(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...
    def delete_ledger_entry(self, ledger_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class APOrchestrationResult:
    ok: bool
    bill: dict[str, Any]
    transaction: dict[str, Any]
    message: str
    idempotent: bool = False


class APOrchestrationService:
    """Coordinates governed AP records with the existing expense gateway.

    Transactions Master and its matter-linked Disbursements projection remain owned by
    the existing ExcelRepo gateway. APBills and APPayments remain owned by
    APWorkbookRepository. A deterministic transaction identity makes a retry safe when
    the transaction save succeeds but the AP bill save is interrupted.
    """

    def __init__(self, ap_repository: APWorkbookRepository, expense_gateway: ExpenseGateway):
        self.ap_repository = ap_repository
        self.expense_gateway = expense_gateway

    @staticmethod
    def deterministic_transaction_id(bill_id: str) -> str:
        normalized = clean_text(bill_id).casefold().encode("utf-8")
        if not normalized:
            raise APValidationError("APBillID is required.")
        token = hashlib.sha256(normalized).hexdigest()[:20].upper()
        return f"TXN-AP-{token}"

    @classmethod
    def build_expense_payload(cls, bill: Mapping[str, Any]) -> dict[str, Any]:
        bill_id = clean_text(bill.get("APBillID"))
        transaction_id = (
            clean_text(bill.get("ExpenseTransactionID"))
            or cls.deterministic_transaction_id(bill_id)
        )
        total = bill.get("Total")
        if total in (None, ""):
            subtotal = float(bill.get("Subtotal") or 0)
            tax = float(bill.get("TaxAmount") or 0)
            total = round(subtotal + tax, 2)
        return {
            "transactionId": transaction_id,
            "txnDate": clean_text(bill.get("InvoiceDate")),
            "class": clean_text(bill.get("Class")) or "Business",
            "businessUnit": clean_text(bill.get("BusinessUnit")),
            "type": "Expense",
            "fromAccount": clean_text(bill.get("SourceAccount") or bill.get("FromAccount")),
            "toAccount": clean_text(bill.get("ToAccount")),
            "payee": clean_text(bill.get("Vendor")),
            "parent": clean_text(bill.get("Parent")),
            "client": clean_text(bill.get("Client") or bill.get("ClientID")),
            "matter": clean_text(bill.get("Matter") or bill.get("MatterID")),
            "categoryCode": clean_text(bill.get("CategoryCode")),
            "categoryName": clean_text(bill.get("CategoryName")),
            "amount": total,
            "taxAmount": bill.get("TaxAmount") or 0,
            "taxFlag": clean_text(bill.get("TaxFlag")) or "None",
            "hstExempt": 1 if bool(bill.get("TaxExempt") or bill.get("HSTExempt")) else 0,
            "generalOfficeExpense": 1 if clean_text(bill.get("ExpenseTreatment")) == "office" else 0,
            "invoiceRef": clean_text(bill.get("VendorInvoiceNumber")),
            "billClaimPct": bill.get("BillClaimPct") or 0,
            "expenseDetails": clean_text(bill.get("Notes")),
            "notes": clean_text(bill.get("Notes")),
            "status": clean_text(bill.get("TransactionStatus")) or "Pending",
            "currency": clean_text(bill.get("Currency")) or "CAD",
        }

    @staticmethod
    def _same_identity(existing: Mapping[str, Any], bill: Mapping[str, Any], transaction_id: str) -> bool:
        return (
            clean_text(existing.get("APBillID")).casefold()
            == clean_text(bill.get("APBillID")).casefold()
            and clean_text(existing.get("ExpenseTransactionID")).casefold()
            == clean_text(transaction_id).casefold()
            and clean_text(existing.get("Vendor")).casefold()
            == clean_text(bill.get("Vendor")).casefold()
            and clean_text(existing.get("VendorInvoiceNumber")).casefold()
            == clean_text(bill.get("VendorInvoiceNumber")).casefold()
        )

    def create_bill(self, bill: Mapping[str, Any]) -> APOrchestrationResult:
        bill_id = clean_text(bill.get("APBillID"))
        if not bill_id:
            raise APValidationError("APBillID is required.")

        transaction_payload = self.build_expense_payload(bill)
        expected_transaction_id = clean_text(transaction_payload.get("transactionId"))
        existing = self.ap_repository.get_bill(bill_id)
        if existing is not None:
            if self._same_identity(existing, bill, expected_transaction_id):
                return APOrchestrationResult(
                    ok=True,
                    bill=dict(existing),
                    transaction={
                        "ok": True,
                        "transactionId": expected_transaction_id,
                        "idempotent": True,
                    },
                    message="AP bill already exists with the expected transaction link.",
                    idempotent=True,
                )
            raise APValidationError(f"Duplicate AP bill ID with conflicting data: {bill_id}")

        transaction_result = dict(
            self.expense_gateway.save_ap_expense(transaction_payload) or {}
        )
        if not transaction_result.get("ok"):
            raise APValidationError(
                clean_text(transaction_result.get("message"))
                or "The expense transaction was not saved."
            )
        returned_transaction_id = clean_text(
            transaction_result.get("transactionId")
            or transaction_result.get("txnId")
            or transaction_payload.get("transactionId")
        )
        if not returned_transaction_id:
            raise APValidationError("The expense gateway did not return a TransactionID.")
        if returned_transaction_id.casefold() != expected_transaction_id.casefold():
            raise APValidationError(
                "The expense gateway returned an unexpected TransactionID. "
                "The AP bill was not created."
            )

        bill_payload = dict(bill)
        bill_payload["ExpenseTransactionID"] = returned_transaction_id
        saved_bill = self.ap_repository.create_bill(bill_payload)
        return APOrchestrationResult(
            ok=True,
            bill=saved_bill,
            transaction=transaction_result,
            message="AP bill and expense transaction saved.",
            idempotent=False,
        )

    def _transaction_for_id(self, transaction_id: str) -> dict[str, Any] | None:
        target = clean_text(transaction_id).casefold()
        if not target or not hasattr(self.expense_gateway, "list_transactions"):
            return None
        try:
            rows = self.expense_gateway.list_transactions({"query": transaction_id})
        except TypeError:
            rows = self.expense_gateway.list_transactions()
        for row in rows or []:
            candidate = clean_text(
                row.get("transactionId") or row.get("TransactionID") or row.get("txnId")
            ).casefold()
            if candidate == target:
                return dict(row)
        return None

    def bill_details(self, bill_id: str) -> dict[str, Any]:
        bill = self.ap_repository.get_bill(bill_id)
        if bill is None:
            raise APValidationError(f"Unknown AP bill ID: {bill_id}")
        transaction_id = clean_text(bill.get("ExpenseTransactionID"))
        transaction = self._transaction_for_id(transaction_id) if transaction_id else None
        payments = self.ap_repository.list_payments(bill_id)
        active_payments = self.ap_repository.list_active_payments(bill_id)
        return {
            "ok": True,
            "bill": dict(bill),
            "transaction": dict(transaction or {}),
            "payments": payments,
            "activePayments": active_payments,
            "message": "Supplier bill details loaded.",
        }

    def update_bill(self, bill: Mapping[str, Any]) -> APOrchestrationResult:
        bill_id = clean_text(bill.get("APBillID"))
        existing = self.ap_repository.get_bill(bill_id)
        if existing is None:
            raise APValidationError(f"Unknown AP bill ID: {bill_id}")
        if self.ap_repository.list_active_payments(bill_id):
            if (
                money(bill.get("Subtotal"), "subtotal")
                != money(existing.get("Subtotal"), "existing subtotal")
                or money(bill.get("TaxAmount"), "tax amount")
                != money(existing.get("TaxAmount"), "existing tax amount")
            ):
                raise APValidationError(
                    "Reverse active payments before changing a bill subtotal or tax amount."
                )
        transaction_id = clean_text(existing.get("ExpenseTransactionID"))
        if not transaction_id:
            raise APValidationError("This AP bill has no linked expense transaction and cannot be edited safely.")
        payload = dict(bill)
        payload["ExpenseTransactionID"] = transaction_id
        transaction_payload = self.build_expense_payload(payload)
        transaction_result = dict(self.expense_gateway.save_ap_expense(transaction_payload) or {})
        if not transaction_result.get("ok"):
            raise APValidationError(
                clean_text(transaction_result.get("message"))
                or "The linked expense transaction was not updated."
            )
        returned_transaction_id = clean_text(
            transaction_result.get("transactionId")
            or transaction_result.get("txnId")
            or transaction_payload.get("transactionId")
        )
        if returned_transaction_id.casefold() != transaction_id.casefold():
            raise APValidationError("The expense gateway returned an unexpected TransactionID during bill update.")
        updated_bill = self.ap_repository.update_bill(payload)
        return APOrchestrationResult(
            ok=True,
            bill=updated_bill,
            transaction=transaction_result,
            message="Supplier bill and linked expense transaction updated.",
        )

    def delete_bill(self, bill_id: str) -> dict[str, Any]:
        bill = self.ap_repository.get_bill(bill_id)
        if bill is None:
            raise APValidationError(f"Unknown AP bill ID: {bill_id}")
        active_payments = self.ap_repository.list_active_payments(bill_id)
        if active_payments:
            raise APValidationError("Reverse the active AP payments before permanently deleting this bill.")
        transaction_id = clean_text(bill.get("ExpenseTransactionID"))
        if not transaction_id:
            raise APValidationError("This AP bill has no linked expense transaction and cannot be deleted safely.")
        transaction = self._transaction_for_id(transaction_id)
        if transaction is None:
            raise APValidationError("The linked expense transaction could not be found; the bill was left unchanged.")
        deleted_transaction = dict(self.expense_gateway.delete_ledger_entry(transaction_id) or {})
        if not deleted_transaction.get("ok"):
            raise APValidationError(
                clean_text(deleted_transaction.get("message"))
                or "The linked expense transaction could not be deleted."
            )
        try:
            result = self.ap_repository.delete_bill(bill_id)
        except Exception as exc:
            restore_result = dict(self.expense_gateway.save_ap_expense(transaction) or {})
            if not restore_result.get("ok"):
                raise APValidationError(
                    "The bill deletion failed after the expense transaction was removed, and the "
                    "transaction restoration also failed. Manual recovery is required."
                ) from exc
            raise
        result["message"] = "Supplier bill and linked expense transaction deleted."
        return result

    def record_payment(self, payment: Mapping[str, Any]) -> dict[str, Any]:
        return self.ap_repository.post_payment(payment)

    def reverse_payment(self, payment_id: str, reversal_id: str, reason: str) -> dict[str, Any]:
        return self.ap_repository.reverse_payment(payment_id, reversal_id, reason)
