from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
import re
from typing import Any, Iterable, Mapping

CENT = Decimal("0.01")

class APValidationError(ValueError):
    pass

class APBillStatus(str, Enum):
    DRAFT = "Draft"
    UNPAID = "Unpaid"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"
    VOIDED = "Voided"
    REVERSED = "Reversed"

def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()

def normalize_key_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).casefold())

def money(value: Any, field_name: str = "amount") -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(clean_text(value).replace("$", "").replace(",", ""))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise APValidationError(f"{field_name} must be a valid monetary amount.") from exc
    if not parsed.is_finite():
        raise APValidationError(f"{field_name} must be finite.")
    return parsed.quantize(CENT, rounding=ROUND_HALF_UP)

def iso_date(value: Any, field_name: str = "date") -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = clean_text(value)
    if not text:
        return ""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise APValidationError(f"{field_name} must use YYYY-MM-DD format.") from exc

def calculate_bill_total(subtotal: Any, tax_amount: Any) -> Decimal:
    subtotal_value = money(subtotal, "subtotal")
    tax_value = money(tax_amount, "tax amount")
    if subtotal_value < 0 or tax_value < 0:
        raise APValidationError("subtotal and tax amount cannot be negative.")
    return money(subtotal_value + tax_value, "bill total")

def calculate_payment_total(payments: Iterable[Mapping[str, Any]]) -> Decimal:
    total = Decimal("0.00")
    seen: set[str] = set()
    for payment in payments:
        payment_id = clean_text(payment.get("payment_id") or payment.get("PaymentID"))
        if not payment_id:
            raise APValidationError("Every AP payment requires a stable payment ID.")
        key = payment_id.casefold()
        if key in seen:
            raise APValidationError(f"Duplicate AP payment ID: {payment_id}")
        seen.add(key)
        amount = money(payment.get("amount", payment.get("Amount", 0)), "payment amount")
        if amount <= 0:
            raise APValidationError("AP payment amount must be greater than zero.")
        if not bool(payment.get("reversed") or payment.get("Reversed")):
            total += amount
    return money(total, "total paid")

def derive_bill_status(total: Any, total_paid: Any, *, posted: bool = True, voided: bool = False, reversed_bill: bool = False) -> APBillStatus:
    total_value = money(total, "bill total")
    paid_value = money(total_paid, "total paid")
    if total_value < 0 or paid_value < 0:
        raise APValidationError("Bill total and total paid cannot be negative.")
    if voided and reversed_bill:
        raise APValidationError("A bill cannot be both voided and reversed.")
    if reversed_bill:
        return APBillStatus.REVERSED
    if voided:
        if paid_value:
            raise APValidationError("A paid or partially paid bill cannot be voided directly.")
        return APBillStatus.VOIDED
    if not posted:
        if paid_value:
            raise APValidationError("A draft bill cannot have posted payments.")
        return APBillStatus.DRAFT
    if total_value <= 0:
        raise APValidationError("A posted AP bill must have a total greater than zero.")
    if paid_value == 0:
        return APBillStatus.UNPAID
    if paid_value < total_value:
        return APBillStatus.PARTIALLY_PAID
    if paid_value == total_value:
        return APBillStatus.PAID
    raise APValidationError("Total AP payments cannot exceed the bill total.")

def calculate_bill_balance(total: Any, total_paid: Any) -> Decimal:
    balance = money(total, "bill total") - money(total_paid, "total paid")
    if balance < 0:
        raise APValidationError("AP bill balance cannot be negative.")
    return money(balance, "bill balance")

def duplicate_bill_key(vendor: Any, vendor_invoice_number: Any, invoice_date: Any, total: Any) -> str:
    parts = [normalize_key_text(vendor), normalize_key_text(vendor_invoice_number), iso_date(invoice_date, "invoice date"), f"{money(total, 'bill total'):.2f}"]
    if not parts[0]:
        raise APValidationError("vendor is required for duplicate detection.")
    if not parts[1]:
        raise APValidationError("vendor invoice number is required for duplicate detection.")
    if not parts[2]:
        raise APValidationError("invoice date is required for duplicate detection.")
    return "|".join(parts)

@dataclass(frozen=True)
class APBillSnapshot:
    bill_id: str
    vendor: str
    vendor_invoice_number: str
    invoice_date: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    total_paid: Decimal
    balance: Decimal
    status: APBillStatus
    duplicate_key: str

def build_bill_snapshot(*, bill_id: Any, vendor: Any, vendor_invoice_number: Any, invoice_date: Any, subtotal: Any, tax_amount: Any, payments: Iterable[Mapping[str, Any]] = (), posted: bool = True, voided: bool = False, reversed_bill: bool = False) -> APBillSnapshot:
    bill_id_text = clean_text(bill_id)
    vendor_text = clean_text(vendor)
    invoice_number_text = clean_text(vendor_invoice_number)
    invoice_date_text = iso_date(invoice_date, "invoice date")
    if not bill_id_text:
        raise APValidationError("A stable AP bill ID is required.")
    if not vendor_text or not invoice_number_text:
        raise APValidationError("vendor and vendor invoice number are required.")
    total = calculate_bill_total(subtotal, tax_amount)
    total_paid = calculate_payment_total(payments)
    status = derive_bill_status(total, total_paid, posted=posted, voided=voided, reversed_bill=reversed_bill)
    return APBillSnapshot(bill_id_text, vendor_text, invoice_number_text, invoice_date_text, money(subtotal, "subtotal"), money(tax_amount, "tax amount"), total, total_paid, calculate_bill_balance(total, total_paid), status, duplicate_bill_key(vendor_text, invoice_number_text, invoice_date_text, total))
