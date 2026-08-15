from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from domain.ap_lifecycle import APValidationError, clean_text, money
from repositories.ap_workbook_repository import APWorkbookRepository
from services.ap_setoff_service import APSetoffService
from services.supplier_document_service import SupplierDocumentService


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

    def __init__(
        self,
        ap_repository: APWorkbookRepository,
        expense_gateway: ExpenseGateway,
        document_service: SupplierDocumentService | None = None,
    ):
        self.ap_repository = ap_repository
        self.expense_gateway = expense_gateway
        self._setoff_service = APSetoffService(expense_gateway)
        self.document_service = document_service

    @staticmethod
    def deterministic_transaction_id(bill_id: str) -> str:
        normalized = clean_text(bill_id).casefold().encode("utf-8")
        if not normalized:
            raise APValidationError("APBillID is required.")
        token = hashlib.sha256(normalized).hexdigest()[:20].upper()
        return f"TXN-AP-{token}"

    @staticmethod
    def normalize_bill_amounts(bill: Mapping[str, Any]) -> dict[str, Any]:
        """Derive the net expense and HST when the user enters a gross total.

        The QML form normally performs this calculation as the user types, but
        accounting writes must not depend on a UI signal having fired.  The
        explicit AmountEntryMode flag also makes API/direct callers safe.
        """
        normalized = dict(bill)
        entry_mode = clean_text(
            normalized.get("AmountEntryMode") or normalized.get("amountEntryMode")
        ).casefold()
        total_supplied = normalized.get("Total") not in (None, "")
        subtotal_supplied = normalized.get("Subtotal") not in (None, "")
        calculate_from_total = entry_mode == "total" or (
            total_supplied and not subtotal_supplied
        )
        if not calculate_from_total:
            return normalized

        total = money(normalized.get("Total"), "total")
        if total <= 0:
            raise APValidationError("A total-entered supplier bill must have a total greater than zero.")

        hst_exempt = bool(normalized.get("TaxExempt") or normalized.get("HSTExempt"))
        if hst_exempt:
            subtotal = total
            tax_amount = Decimal("0.00")
        else:
            tax_rate = Decimal("0.13")
            subtotal = (total / (Decimal("1.00") + tax_rate)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            # Derive tax as the residual so net plus tax always exactly equals
            # the entered, two-decimal supplier total.
            tax_amount = money(total - subtotal, "tax amount")

        normalized["Subtotal"] = float(subtotal)
        normalized["TaxAmount"] = float(tax_amount)
        normalized["Total"] = float(total)
        return normalized

    @staticmethod
    def _positive_money(value: Any, field: str) -> Decimal:
        amount = money(value, field)
        if amount <= 0:
            raise APValidationError(f"{field.capitalize()} must be greater than zero.")
        return amount

    @classmethod
    def prepare_governed_bill(cls, bill: Mapping[str, Any]) -> dict[str, Any]:
        """Keep invoice-currency evidence and CAD reporting values together."""
        prepared = cls.normalize_bill_amounts(bill)
        currency = clean_text(prepared.get("Currency") or prepared.get("OriginalCurrency") or "CAD").upper()
        if currency not in {"CAD", "USD"}:
            raise APValidationError("Supplier invoice currency must be CAD or USD.")
        original_subtotal = cls._positive_money(prepared.get("Subtotal"), "subtotal")
        original_tax = money(prepared.get("TaxAmount"), "tax amount")
        if original_tax < 0:
            raise APValidationError("Tax amount cannot be negative.")
        original_total = cls._positive_money(prepared.get("Total"), "total")
        if abs((original_subtotal + original_tax) - original_total) > Decimal("0.01"):
            raise APValidationError("Subtotal plus tax must equal the supplier invoice total.")
        supplied_rate = prepared.get("FXRate")
        try:
            rate = Decimal(str(supplied_rate if supplied_rate not in (None, "") else 1))
        except Exception as exc:
            raise APValidationError("Exchange rate must be a number.") from exc
        if currency == "CAD":
            rate = Decimal("1.00")
        elif rate <= 0:
            raise APValidationError("Enter the CAD exchange rate used for this USD supplier invoice.")
        if rate <= 0:
            raise APValidationError("Exchange rate must be greater than zero.")
        base_subtotal = (original_subtotal * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_tax = (original_tax * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        base_total = (original_total * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        claim_pct = money(prepared.get("BillClaimPct") if prepared.get("BillClaimPct") not in (None, "") else (100 if clean_text(prepared.get("MatterID") or prepared.get("Matter")) else 0), "client recovery percentage")
        if claim_pct < 0 or claim_pct > 100:
            raise APValidationError("Client recovery percentage must be between 0 and 100.")
        prepared.update({
            "Currency": currency,
            "OriginalCurrency": currency,
            "OriginalSubtotal": float(original_subtotal),
            "OriginalTaxAmount": float(original_tax),
            "OriginalTotal": float(original_total),
            "BaseCurrency": "CAD",
            "BaseSubtotal": float(base_subtotal),
            "BaseTaxAmount": float(base_tax),
            "BaseTotal": float(base_total),
            "FXRate": float(rate),
            "FXRateDate": clean_text(prepared.get("FXRateDate") or prepared.get("InvoiceDate")),
            "BillClaimPct": float(claim_pct),
        })
        return prepared

    def _attach_document(self, bill: dict[str, Any]) -> dict[str, Any]:
        source = bill.get("DocumentSourcePath") or bill.get("documentSourcePath")
        if not source:
            return bill
        write_guard = getattr(self.expense_gateway, "_assert_write_permitted", None)
        if callable(write_guard):
            # Do not make an orphan cloud document when this PC has not
            # acquired the governed shared-data checkout.
            write_guard()
        if self.document_service is None:
            raise APValidationError("Supplier document storage is not configured for this CSPM data folder.")
        evidence = self.document_service.attach_invoice(
            source,
            vendor=bill.get("Vendor"),
            invoice_number=bill.get("VendorInvoiceNumber"),
            invoice_date=bill.get("InvoiceDate"),
        )
        result = dict(bill)
        result.update(evidence)
        return result

    @classmethod
    def build_expense_payload(cls, bill: Mapping[str, Any]) -> dict[str, Any]:
        bill_id = clean_text(bill.get("APBillID"))
        transaction_id = (
            clean_text(bill.get("ExpenseTransactionID"))
            or cls.deterministic_transaction_id(bill_id)
        )
        total = bill.get("BaseTotal")
        if total in (None, ""):
            subtotal = float(bill.get("BaseSubtotal") if bill.get("BaseSubtotal") not in (None, "") else bill.get("Subtotal") or 0)
            tax = float(bill.get("BaseTaxAmount") if bill.get("BaseTaxAmount") not in (None, "") else bill.get("TaxAmount") or 0)
            total = round(subtotal + tax, 2)
        return {
            "transactionId": transaction_id,
            "txnDate": clean_text(bill.get("InvoiceDate")),
            "class": clean_text(bill.get("Class")) or "Business",
            "businessUnit": clean_text(bill.get("BusinessUnit")),
            "type": "Expense",
            # A supplier bill records an obligation, not a bank movement.  The
            # actual cash account is recorded only when a supplier payment is
            # posted later.
            "fromAccount": "AP_PAYABLE",
            "toAccount": clean_text(bill.get("ToAccount")),
            "payee": clean_text(bill.get("Vendor")),
            "parent": clean_text(bill.get("Parent")),
            "client": clean_text(bill.get("Client") or bill.get("ClientID")),
            "matter": clean_text(bill.get("Matter") or bill.get("MatterID")),
            "categoryCode": clean_text(bill.get("CategoryCode")),
            "categoryName": clean_text(bill.get("CategoryName")),
            "amount": total,
            "taxAmount": bill.get("BaseTaxAmount") if bill.get("BaseTaxAmount") not in (None, "") else bill.get("TaxAmount") or 0,
            "taxFlag": clean_text(bill.get("TaxFlag")),
            "hstExempt": 1 if bool(bill.get("TaxExempt") or bill.get("HSTExempt")) else 0,
            "generalOfficeExpense": 1 if clean_text(bill.get("ExpenseTreatment")) == "office" else 0,
            "invoiceRef": clean_text(bill.get("VendorInvoiceNumber")),
            "billClaimPct": bill.get("BillClaimPct") or 0,
            "expenseDetails": clean_text(bill.get("Notes")),
            "notes": clean_text(bill.get("Notes")),
            "status": clean_text(bill.get("TransactionStatus")) or "Pending",
            "currency": "CAD",
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
        normalized_bill = self._attach_document(self.prepare_governed_bill(bill))
        bill_id = clean_text(normalized_bill.get("APBillID"))
        if not bill_id:
            raise APValidationError("APBillID is required.")

        historic_transaction_id = clean_text(normalized_bill.get("HistoricalTransactionID"))
        if historic_transaction_id:
            return self.adopt_historical_bill(normalized_bill)

        transaction_payload = self.build_expense_payload(normalized_bill)
        expected_transaction_id = clean_text(transaction_payload.get("transactionId"))
        existing = self.ap_repository.get_bill(bill_id)
        if existing is not None:
            if self._same_identity(existing, normalized_bill, expected_transaction_id):
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

        # Persist the A/P obligation first. If creating the linked financial
        # rows fails, remove this still-unpaid bill again rather than leaving a
        # plausible-looking payable with no accounting trail.
        bill_payload = dict(normalized_bill)
        bill_payload["ExpenseTransactionID"] = expected_transaction_id
        saved_bill = self.ap_repository.create_bill(bill_payload)
        try:
            transaction_result = dict(
                self.expense_gateway.save_ap_expense(transaction_payload) or {}
            )
        except Exception:
            self.ap_repository.delete_bill(bill_id)
            raise
        if not transaction_result.get("ok"):
            self.ap_repository.delete_bill(bill_id)
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
            self.ap_repository.delete_bill(bill_id)
            raise APValidationError(
                "The expense gateway returned an unexpected TransactionID. "
                "The AP bill was not created."
            )

        disbursement_result: dict[str, Any] = {}
        if clean_text(normalized_bill.get("MatterID") or normalized_bill.get("Matter")) and float(normalized_bill.get("BillClaimPct") or 0) > 0:
            claim_amount = (Decimal(str(normalized_bill.get("BaseTotal") or 0)) * Decimal(str(normalized_bill.get("BillClaimPct") or 0)) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            try:
                disbursement_result = dict(self.expense_gateway.create_supplier_disbursement({
                    "APBillID": bill_id,
                    "MatterID": normalized_bill.get("MatterID") or normalized_bill.get("Matter"),
                    "Date": normalized_bill.get("InvoiceDate"),
                    "Amount": float(claim_amount),
                    "BillPct": normalized_bill.get("BillClaimPct"),
                    "ClientTaxExempt": normalized_bill.get("ClientTaxExempt"),
                    "Description": normalized_bill.get("DisbursementDescription") or normalized_bill.get("Vendor"),
                    "Vendor": normalized_bill.get("Vendor"),
                    "SupplierInvoiceRef": normalized_bill.get("VendorInvoiceNumber"),
                    "SourceTransactionID": returned_transaction_id,
                    "OriginalCurrency": normalized_bill.get("OriginalCurrency"),
                    "OriginalAmount": normalized_bill.get("OriginalTotal"),
                    "FXRate": normalized_bill.get("FXRate"),
                    "BaseSubtotal": normalized_bill.get("BaseSubtotal"),
                    "BaseTaxAmount": normalized_bill.get("BaseTaxAmount"),
                    "CategoryName": normalized_bill.get("CategoryName"),
                    "DocumentPath": normalized_bill.get("DocumentPath"),
                }) or {})
            except Exception as exc:
                # The supplier bill is not left as a usable record when its
                # recoverable WIP projection cannot be created.  The linked
                # expense is marked Void (rather than hard deleted) so audit
                # history explains the failed attempted bundle.
                try:
                    self.expense_gateway.save_transaction({
                        **(self._transaction_for_id(returned_transaction_id) or transaction_payload),
                        "transactionId": returned_transaction_id,
                        "status": "Void",
                        "voidReason": "Supplier bill rollback: client disbursement was not created.",
                    })
                    self.ap_repository.delete_bill(bill_id)
                except Exception:
                    pass
                raise APValidationError(f"Supplier bill was not completed because its client disbursement failed: {exc}") from exc
            if not disbursement_result.get("ok"):
                raise APValidationError("Supplier bill was not completed because its client disbursement was not saved.")
            saved_bill = self.ap_repository.update_bill({
                **saved_bill,
                "DisbursementID": clean_text(disbursement_result.get("disbursementId")),
                "ExpenseTransactionID": returned_transaction_id,
            })
        return APOrchestrationResult(
            ok=True,
            bill=saved_bill,
            transaction={**transaction_result, "disbursement": disbursement_result},
            message=("Supplier bill, business expense, and client WIP disbursement saved."
                if disbursement_result else "Supplier bill and business expense saved."),
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

    def list_historical_candidates(self, query: str = "") -> list[dict[str, Any]]:
        """Find legacy expenses/WIP rows that can be adopted without copying them.

        The result intentionally excludes transactions already governed by an
        A/P bill.  Adoption therefore turns historic evidence into linked
        records; it does not manufacture another expense or disbursement.
        """
        from domain import schema_constants as sc
        from repositories.excel_repo import TBL_DISBURSEMENTS, TBL_LEDGER, TBL_MATTERS

        term = clean_text(query).casefold()
        bills = self.ap_repository.list_bills()
        governed_transaction_ids = {
            clean_text(row.get("ExpenseTransactionID")).casefold()
            for row in bills if clean_text(row.get("ExpenseTransactionID"))
        }
        try:
            disbursements = self.expense_gateway._read_table_rows(TBL_DISBURSEMENTS)
        except Exception:
            disbursements = []
        try:
            ledger_rows = self.expense_gateway._read_table_rows(TBL_LEDGER)
        except Exception:
            ledger_rows = []
        try:
            matter_rows = self.expense_gateway._read_table_rows(TBL_MATTERS)
        except Exception:
            matter_rows = []

        def resolve_matter(legacy_reference: str) -> dict[str, Any] | None:
            """Resolve either a modern MatterID or a legacy MatterNumber.

            Imported disbursements historically stored the visible matter number
            while the current matter picker uses the stable MatterID.  Resolve
            only a unique result; ambiguity remains ineligible for adoption.
            """
            target = clean_text(legacy_reference).casefold()
            if not target:
                return None
            matches = [
                dict(row) for row in matter_rows
                if target in {
                    clean_text(row.get(sc.COL_MATTER_ID)).casefold(),
                    clean_text(row.get(sc.COL_MATTER_NUMBER)).casefold(),
                }
            ]
            return matches[0] if len(matches) == 1 else None
        candidates: list[dict[str, Any]] = []
        for transaction in self.expense_gateway.list_transactions({}) or []:
            txn_id = clean_text(transaction.get("transactionId") or transaction.get("TransactionID"))
            if not txn_id or txn_id.casefold() in governed_transaction_ids:
                continue
            if clean_text(transaction.get("type") or transaction.get("Type")).casefold() != "expense":
                continue
            haystack = " ".join(str(transaction.get(key) or "") for key in (
                "transactionId", "payee", "vendor", "invoiceRef", "notes", "expenseDetails", "matter", "client"
            )).casefold()
            if term and term not in haystack:
                continue
            amount = money(transaction.get("amount") or transaction.get("Amount") or 0, "historic expense amount")
            tax = money(transaction.get("taxAmount") or transaction.get("TaxAmount") or 0, "historic expense tax")
            base_total = amount + tax
            matter = clean_text(transaction.get("matter") or transaction.get("Matter"))
            supplier_invoice_ref = clean_text(transaction.get("invoiceRef") or transaction.get("InvoiceRef"))
            linked_disbursement: dict[str, Any] | None = None
            match_method = ""
            for disbursement in disbursements:
                if clean_text(disbursement.get(sc.COL_DISB_AP_BILL_ID)):
                    continue
                same_matter = matter and clean_text(disbursement.get(sc.COL_DISB_MATTER_ID)).casefold() == matter.casefold()
                same_amount = abs(money(disbursement.get(sc.COL_DISB_AMOUNT) or 0, "historic disbursement") - base_total) <= Decimal("0.01")
                if same_matter and same_amount:
                    linked_disbursement = dict(disbursement)
                    match_method = "matter"
                    break

            # Several legacy expense imports predate a dedicated Matter field.
            # They remain safe to adopt only where their source ledger row gives
            # a deterministic chain: expense transaction -> supplier invoice ->
            # client invoice -> work client -> one ungoverned disbursement.
            # Never fall back when a transaction has an explicit (but different)
            # matter: that would conceal a genuine data conflict.
            if linked_disbursement is None and not matter:
                ledger_linked: dict[str, dict[str, Any]] = {}
                for ledger in ledger_rows:
                    if clean_text(ledger.get(sc.COL_LEDGER_TRX_ID)).casefold() != txn_id.casefold():
                        continue
                    ledger_supplier_ref = clean_text(ledger.get(sc.COL_LEDGER_EXTERNAL_REF_ID))
                    if ledger_supplier_ref and supplier_invoice_ref and ledger_supplier_ref.casefold() != supplier_invoice_ref.casefold():
                        continue
                    client_invoice_ref = clean_text(ledger.get(sc.COL_LEDGER_REFERENCE))
                    work_client = clean_text(ledger.get(sc.COL_LEDGER_WORK_CLIENT))
                    if not client_invoice_ref or not work_client:
                        continue
                    for disbursement in disbursements:
                        if clean_text(disbursement.get(sc.COL_DISB_AP_BILL_ID)):
                            continue
                        same_amount = abs(
                            money(disbursement.get(sc.COL_DISB_AMOUNT) or 0, "historic disbursement") - base_total
                        ) <= Decimal("0.01")
                        same_invoice = clean_text(disbursement.get(sc.COL_DISB_INVOICE_REF)).casefold() == client_invoice_ref.casefold()
                        disbursement_clients = {
                            clean_text(disbursement.get(sc.COL_DISB_CLIENT_NAME)).casefold(),
                            clean_text(disbursement.get(sc.COL_DISB_SUB_CLIENT)).casefold(),
                        }
                        if same_amount and same_invoice and work_client.casefold() in disbursement_clients:
                            disbursement_id = clean_text(disbursement.get(sc.COL_DISB_ID))
                            if disbursement_id:
                                ledger_linked[disbursement_id.casefold()] = dict(disbursement)
                # Adoption stays blocked when the ledger chain leads to more
                # than one WIP row.  The caller must resolve that ambiguity.
                if len(ledger_linked) == 1:
                    linked_disbursement = next(iter(ledger_linked.values()))
                    match_method = "legacy-ledger-invoice"
            matched_matter = resolve_matter(
                clean_text((linked_disbursement or {}).get(sc.COL_DISB_MATTER_ID)) or matter
            )
            resolved_matter_id = clean_text((matched_matter or {}).get(sc.COL_MATTER_ID)) or matter
            resolved_client_id = clean_text((matched_matter or {}).get(sc.COL_MATTER_CLIENT_ID))
            resolved_client_name = clean_text((matched_matter or {}).get(sc.COL_MATTER_CLIENT_NAME))
            candidates.append({
                "transactionId": txn_id,
                "date": clean_text(transaction.get("txnDate") or transaction.get("Date")),
                "vendor": clean_text(transaction.get("payee") or transaction.get("Payee")),
                "invoiceRef": clean_text(transaction.get("invoiceRef") or transaction.get("InvoiceRef")),
                "notes": clean_text(transaction.get("notes") or transaction.get("Notes")),
                "matterId": resolved_matter_id,
                "matterNumber": clean_text((matched_matter or {}).get(sc.COL_MATTER_NUMBER))
                    or clean_text((linked_disbursement or {}).get(sc.COL_DISB_MATTER_ID))
                    or matter,
                "clientId": resolved_client_id or clean_text(transaction.get("client") or transaction.get("Client")),
                "clientName": resolved_client_name or clean_text((linked_disbursement or {}).get(sc.COL_DISB_CLIENT_NAME)),
                "baseSubtotal": float(amount),
                "baseTaxAmount": float(tax),
                "baseTotal": float(base_total),
                "currency": clean_text(transaction.get("currency") or transaction.get("Currency")) or "CAD",
                "fromAccount": clean_text(transaction.get("fromAccount") or transaction.get("FromAccount")),
                "status": clean_text(transaction.get("status") or transaction.get("Status")),
                "disbursementId": clean_text((linked_disbursement or {}).get(sc.COL_DISB_ID)),
                "clientInvoiceRef": clean_text((linked_disbursement or {}).get(sc.COL_DISB_INVOICE_REF)),
                "disbursementAmount": float(money((linked_disbursement or {}).get(sc.COL_DISB_AMOUNT) or 0, "historic disbursement")),
                "matchMethod": match_method,
                "label": " • ".join(filter(None, [
                    clean_text(transaction.get("txnDate") or transaction.get("Date")),
                    clean_text(transaction.get("payee") or transaction.get("Payee")) or "Supplier expense",
                    f"${float(base_total):,.2f} CAD",
                    txn_id,
                ])),
            })
        candidates.sort(key=lambda row: (row["date"], row["transactionId"]), reverse=True)
        return candidates

    def adopt_historical_bill(self, bill: Mapping[str, Any]) -> APOrchestrationResult:
        """Adopt a legacy supplier expense and WIP row without duplicating it."""
        normalized = dict(bill)
        bill_id = clean_text(normalized.get("APBillID"))
        transaction_id = clean_text(normalized.get("HistoricalTransactionID"))
        disbursement_id = clean_text(normalized.get("HistoricalDisbursementID"))
        if not bill_id or not transaction_id or not disbursement_id:
            raise APValidationError("Historical adoption requires the selected legacy expense and client disbursement.")
        source = self._transaction_for_id(transaction_id)
        if source is None:
            raise APValidationError("The selected historic expense transaction could not be found. Refresh and try again.")
        base_total = money(normalized.get("BaseTotal"), "CAD total")
        source_total = money(source.get("amount") or source.get("Amount"), "historic expense amount") + money(source.get("taxAmount") or source.get("TaxAmount") or 0, "historic expense tax")
        if abs(base_total - source_total) > Decimal("0.01"):
            raise APValidationError(
                f"The selected legacy expense totals ${float(source_total):,.2f} CAD, not ${float(base_total):,.2f} CAD. "
                "Correct the supplier invoice or choose the matching historic record; CSPM will not duplicate it."
            )
        existing = self.ap_repository.get_bill(bill_id)
        if existing is not None:
            if self._same_identity(existing, normalized, transaction_id):
                return APOrchestrationResult(True, existing, {"transactionId": transaction_id, "idempotent": True}, "Historic supplier bill is already adopted.", True)
            raise APValidationError(f"Duplicate AP bill ID with conflicting data: {bill_id}")
        if any(clean_text(row.get("ExpenseTransactionID")).casefold() == transaction_id.casefold() for row in self.ap_repository.list_bills()):
            raise APValidationError("This legacy expense is already linked to another A/P bill.")

        adopted_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        persisted = self.ap_repository.create_bill({
            **normalized,
            "ExpenseTransactionID": transaction_id,
            "HistoricalAdoption": "Yes",
            "AdoptedAt": adopted_at,
        })
        try:
            link = self.expense_gateway.link_historical_supplier_disbursement({
                "APBillID": bill_id,
                "DisbursementID": disbursement_id,
                "SourceTransactionID": transaction_id,
                "OriginalCurrency": normalized.get("OriginalCurrency"),
                "OriginalAmount": normalized.get("OriginalTotal"),
                "FXRate": normalized.get("FXRate"),
                "SupplierInvoiceRef": normalized.get("VendorInvoiceNumber"),
                "DocumentPath": normalized.get("DocumentPath"),
            })
        except Exception:
            self.ap_repository.delete_bill(bill_id)
            raise
        persisted = self.ap_repository.update_bill({
            **persisted,
            "DisbursementID": disbursement_id,
            "HistoricalAdoption": "Yes",
            "AdoptedAt": adopted_at,
        })

        payment: dict[str, Any] = {}
        if bool(normalized.get("HistoricalPaymentConfirmed")):
            payment = self.ap_repository.post_payment({
                "APPaymentID": clean_text(normalized.get("HistoricalAPPaymentID")) or f"APP-HIST-{bill_id}",
                "APBillID": bill_id,
                "PaymentDate": clean_text(normalized.get("HistoricalPaymentDate") or source.get("txnDate") or source.get("Date")),
                "Amount": normalized.get("OriginalTotal"),
                "BaseAmount": normalized.get("BaseTotal"),
                "FXRate": normalized.get("FXRate"),
                "FromAccount": clean_text(source.get("fromAccount") or source.get("FromAccount")),
                "Method": "Historical payment",
                "Reference": clean_text(normalized.get("HistoricalPaymentReference") or transaction_id),
                "Notes": "Historic payment adopted from the selected pre-A/P expense transaction; no new cash transfer was created.",
                "PaymentTransactionID": transaction_id,
                "HistoricalPayment": "Yes",
            })
        return APOrchestrationResult(
            True,
            persisted,
            {"transactionId": transaction_id, "disbursement": link, "payment": payment},
            "Historic supplier expense and client WIP were adopted with no duplicate financial entries.",
        )

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
        normalized_bill = self.normalize_bill_amounts(bill)
        bill_id = clean_text(normalized_bill.get("APBillID"))
        existing = self.ap_repository.get_bill(bill_id)
        if existing is None:
            raise APValidationError(f"Unknown AP bill ID: {bill_id}")
        if self.ap_repository.list_active_payments(bill_id):
            if (
                money(normalized_bill.get("Subtotal"), "subtotal")
                != money(existing.get("Subtotal"), "existing subtotal")
                or money(normalized_bill.get("TaxAmount"), "tax amount")
                != money(existing.get("TaxAmount"), "existing tax amount")
            ):
                raise APValidationError(
                    "Reverse active payments before changing a bill subtotal or tax amount."
                )
        transaction_id = clean_text(existing.get("ExpenseTransactionID"))
        if not transaction_id:
            raise APValidationError("This AP bill has no linked expense transaction and cannot be edited safely.")
        payload = dict(normalized_bill)
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
        payload = dict(payment or {})
        bill_id = clean_text(payload.get("APBillID"))
        payment_id = clean_text(payload.get("APPaymentID"))
        bill = self.ap_repository.get_bill(bill_id)
        if bill is None:
            raise APValidationError(f"Unknown AP bill ID: {bill_id}")
        amount = self._positive_money(payload.get("Amount"), "payment amount")
        currency = clean_text(bill.get("OriginalCurrency") or bill.get("Currency") or "CAD").upper()
        try:
            rate = Decimal(str(payload.get("FXRate") if payload.get("FXRate") not in (None, "") else bill.get("FXRate") or 1))
        except Exception as exc:
            raise APValidationError("Payment exchange rate must be a number.") from exc
        if currency == "CAD":
            rate = Decimal("1")
        if rate <= 0:
            raise APValidationError("Payment exchange rate must be greater than zero.")
        base_amount = (
            Decimal(str(payload.get("BaseAmount"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if payload.get("BaseAmount") not in (None, "")
            else (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )
        from_account = clean_text(payload.get("FromAccount"))
        if not from_account:
            raise APValidationError("Choose the bank, credit-card, or other payment account.")
        if not payment_id:
            raise APValidationError("APPaymentID is required.")

        # The AP row is the payable lifecycle authority.  A failure to create
        # its corresponding cash transfer is automatically reversed so it is
        # never silently left looking paid.
        saved = self.ap_repository.post_payment({
            **payload,
            "Amount": float(amount),
            "BaseAmount": float(base_amount),
            "FXRate": float(rate),
        })
        transaction_id = f"TXN-APP-{hashlib.sha256(payment_id.casefold().encode('utf-8')).hexdigest()[:20].upper()}"
        try:
            transaction_result = self.expense_gateway.save_transaction({
                "transactionId": transaction_id,
                "txnDate": clean_text(payload.get("PaymentDate")),
                "class": "Business",
                "businessUnit": clean_text(bill.get("BusinessUnit")) or "Cory Business",
                "type": "Transfer",
                "fromAccount": from_account,
                "toAccount": "AP_PAYABLE",
                "payee": clean_text(bill.get("Vendor")),
                "categoryCode": clean_text(bill.get("CategoryCode")) or "EXP_GENERAL",
                "categoryName": clean_text(bill.get("CategoryName")) or "Supplier payment",
                "member": "Joint",
                "amount": float(base_amount),
                "taxAmount": 0.0,
                "taxFlag": "None",
                "hstExempt": 1,
                "invoiceRef": clean_text(bill.get("VendorInvoiceNumber")),
                "expenseDetails": f"Supplier payment for A/P bill {bill_id}",
                "notes": clean_text(payload.get("Notes")) or f"{clean_text(payload.get('Method')) or 'Supplier payment'} applied to A/P bill {bill_id}",
                "status": "Cleared",
                "currency": "CAD",
                "clearedAt": clean_text(payload.get("PaymentDate")),
            })
            if not transaction_result.get("ok"):
                raise APValidationError(clean_text(transaction_result.get("message")) or "Supplier payment transfer was not saved.")
        except Exception as exc:
            try:
                self.ap_repository.reverse_payment(
                    payment_id,
                    f"APP-ROLLBACK-{payment_id}",
                    "Automatic rollback: the linked supplier-payment transfer was not saved.",
                )
            except Exception:
                pass
            raise APValidationError(f"Supplier payment was not posted because its cash transfer failed: {exc}") from exc
        saved = self.ap_repository.update_payment_metadata(payment_id, {
            "BaseAmount": float(base_amount),
            "FXRate": float(rate),
            "PaymentTransactionID": transaction_id,
        })
        return {
            **saved,
            "ok": True,
            "transactionId": transaction_id,
            "message": "Supplier payment and cash transfer recorded.",
        }

    def record_setoff(self, payment: Mapping[str, Any]) -> dict[str, Any]:
        return self._setoff_service.record(payment)

    def reverse_payment(self, payment_id: str, reversal_id: str, reason: str) -> dict[str, Any]:
        original = next(
            (row for row in self.ap_repository.list_payments() if clean_text(row.get("APPaymentID")).casefold() == clean_text(payment_id).casefold()),
            None,
        )
        result = self.ap_repository.reverse_payment(payment_id, reversal_id, reason)
        transaction_id = clean_text((original or {}).get("PaymentTransactionID"))
        if transaction_id:
            transaction = self._transaction_for_id(transaction_id)
            if transaction:
                transaction_result = self.expense_gateway.save_transaction({
                    **transaction,
                    "transactionId": transaction_id,
                    "status": "Void",
                    "voidReason": f"A/P payment reversed: {clean_text(reason)}",
                })
                if not transaction_result.get("ok"):
                    raise APValidationError("The payment was reversed in A/P, but its cash-transfer transaction could not be voided. Review the transaction before continuing.")
        return {**result, "message": "A/P payment reversed and the linked cash transfer voided."}

    def reverse_setoff(self, payment_id: str, reversal_id: str, reason: str) -> dict[str, Any]:
        return self._setoff_service.reverse(payment_id, reversal_id, reason)
