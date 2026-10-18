from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


def _dec(value: Any, default: str = "0.00") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    try:
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        if not cleaned:
            return Decimal(default)
        return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default)


def _money_float(value: Any) -> float:
    return float(_dec(value))


def _iso_date(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return fallback
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text:
        return fallback
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text[:10]


class TaxComplianceService:
    """Storage-agnostic corporate, Shareholder Loan (GIFI 2781), Dual HST (RT0001),
    and Dual Income Tax (T2125 / T2 / Form T2057) compliance service.

    Operates strictly on in-memory dicts and Decimal arithmetic using repository
    methods implemented on both ExcelRepo/FinanceRepo and SQLiteRepository.
    """

    CORPORATE_GROUND_TRUTH: Dict[str, Any] = {
        "legalName": "CORY SCHNEIDER LAW PROFESSIONAL CORPORATION",
        "practiceName": "CORY SCHNEIDER LAW OFFICE",
        "ocn": "1001781977",
        "companyKey": "448389332",
        "bin": "1001782016",
        "incorporationDate": "2026-10-17",
        "cutoverDate": "2026-11-01",
        "fiscalYearEnd": "December 31",
        "solePropAddress": "14 Parsons Court, Thornhill, ON L4K 6Z4",
        "pcAddress": "7 Saint Thomas Street, Suite 307, Toronto, ON M5S 2B7",
        "solePropHstNumber": "78621 8222 RT0001",
        "shareholderName": "Cory Adam Schneider",
        "shareClasses": [
            {
                "classCode": "CLASS_1_COMMON",
                "className": "Class 1 Common Shares",
                "voting": True,
                "issuedShares": 100,
                "issueDate": "2026-10-17",
                "consideration": 1.00,
                "statedCapital": 1.00,
                "puc": 1.00,
                "redemptionAmount": None,
                "gifiLine": "3500",
                "paymentMethod": "OBCA s. 23(3) set-off against start-up outlays (Notice #1 / Doc #10)",
                "uncertificated": True,
            },
            {
                "classCode": "CLASS_A1_SPECIAL",
                "className": "Class A1 Fixed Value Special Shares (Voting)",
                "voting": True,
                "issuedShares": 100,
                "issueDate": "2026-11-01",
                "consideration": 100.00,
                "electedAmount": 1.00,
                "statedCapital": 1.00,
                "puc": 1.00,
                "redemptionAmount": 100.00,
                "gifiLine": "3520",
                "paymentMethod": "ITA s. 85(1) rollover of practice Goodwill (Form T2057) + OBCA s. 24(3) stated capital addition",
                "uncertificated": True,
            },
        ],
    }

    DEFAULT_CATEGORY_TAX_MAP: Dict[str, Dict[str, Any]] = {
        "EXP_LSO_FEES": {
            "t2125Line": "8760",
            "t2125Label": "Business taxes, licences, and memberships",
            "gifiCode": "8760",
            "gifiLabel": "Business taxes, licences, and memberships",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_INSURANCE": {
            "t2125Line": "8690",
            "t2125Label": "Insurance",
            "gifiCode": "8690",
            "gifiLabel": "Insurance",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("0.00"),
        },
        "EXP_SOFTWARE_SUBSCRIPTIONS": {
            "t2125Line": "8810",
            "t2125Label": "Office expenses",
            "gifiCode": "8810",
            "gifiLabel": "Office expenses",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_OFFICE_SUPPLIES": {
            "t2125Line": "8810",
            "t2125Label": "Office expenses",
            "gifiCode": "8810",
            "gifiLabel": "Office expenses",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_TELECOM_INTERNET": {
            "t2125Line": "9225",
            "t2125Label": "Telephone and utilities",
            "gifiCode": "9225",
            "gifiLabel": "Utilities and telecommunications",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_BANK_CHARGES_INTEREST": {
            "t2125Line": "8710",
            "t2125Label": "Interest and bank charges",
            "gifiCode": "8710",
            "gifiLabel": "Interest and bank charges",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("0.00"),
        },
        "EXP_ACCOUNTING_LEGAL": {
            "t2125Line": "8860",
            "t2125Label": "Legal, accounting, and other professional fees",
            "gifiCode": "8860",
            "gifiLabel": "Professional fees",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_ADVERTISING_MARKETING": {
            "t2125Line": "8521",
            "t2125Label": "Advertising",
            "gifiCode": "8521",
            "gifiLabel": "Advertising and promotion",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_TRAVEL_PARKING": {
            "t2125Line": "9200",
            "t2125Label": "Travel",
            "gifiCode": "9200",
            "gifiLabel": "Travel expenses",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
        "EXP_MEALS_ENTERTAINMENT": {
            "t2125Line": "8523",
            "t2125Label": "Meals and entertainment (50% deductible)",
            "gifiCode": "8523",
            "gifiLabel": "Meals and entertainment",
            "deductiblePct": Decimal("50.00"),
            "itcPct": Decimal("50.00"),
        },
        "GOV_INCORPORATION_FILING": {
            "t2125Line": "",
            "t2125Label": "Non-deductible / Corporate Organization Filing Fee",
            "gifiCode": "8760",
            "gifiLabel": "Business taxes, licences, and statutory incorporation fees",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("0.00"),
        },
        "CORP_ORG_EXPENSE": {
            "t2125Line": "",
            "t2125Label": "Corporate Pre-Incorporation / Organization Expense",
            "gifiCode": "8860",
            "gifiLabel": "Professional and corporate search fees",
            "deductiblePct": Decimal("100.00"),
            "itcPct": Decimal("100.00"),
        },
    }

    def __init__(self, repo: Any):
        self.repo = repo

    # ------------------------------------------------------------------
    # Internal Category Lookup Helpers
    # ------------------------------------------------------------------
    def _category_metadata_map(self) -> Dict[str, Dict[str, Any]]:
        mapping: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in self.DEFAULT_CATEGORY_TAX_MAP.items()
        }
        list_fn = getattr(self.repo, "list_transaction_categories", None)
        if callable(list_fn):
            try:
                rows = list_fn(include_inactive=True)
            except TypeError:
                rows = list_fn()
            except Exception:
                rows = []
            for r in rows or []:
                code = str(r.get("categoryCode") or r.get("CategoryCode") or "").strip().upper()
                if not code:
                    continue
                t2125_line = str(r.get("t2125LineNumber") or r.get("T2125LineNumber") or "").strip()
                t2125_label = str(r.get("t2125LineLabel") or r.get("T2125LineLabel") or r.get("categoryName") or r.get("CategoryName") or "").strip()
                gifi_code = str(r.get("gifiSchedule125Code") or r.get("GIFISchedule125Code") or "").strip()
                gifi_label = str(r.get("gifiSchedule125Label") or r.get("GIFISchedule125Label") or r.get("categoryName") or r.get("CategoryName") or "").strip()
                ded_pct = _dec(r.get("deductiblePct") if "deductiblePct" in r else r.get("DeductiblePct", 100), "100.00")
                itc_pct = _dec(r.get("itcClaimablePct") if "itcClaimablePct" in r else r.get("ITCClaimablePct", 100), "100.00")
                fallback = mapping.get(code, {})
                mapping[code] = {
                    "t2125Line": t2125_line or fallback.get("t2125Line", "8810"),
                    "t2125Label": t2125_label or fallback.get("t2125Label", "Office expenses"),
                    "gifiCode": gifi_code or fallback.get("gifiCode", "8810"),
                    "gifiLabel": gifi_label or fallback.get("gifiLabel", "Office expenses"),
                    "deductiblePct": ded_pct,
                    "itcPct": itc_pct,
                }
        return mapping

    # ------------------------------------------------------------------
    # 1. Shareholder Loan Ledger (GIFI 2781)
    # ------------------------------------------------------------------
    def _normalize_shl_row(self, row: Dict[str, Any], running_dec: Decimal) -> Dict[str, Any]:
        entry_id = str(row.get("shlEntryId") or row.get("EntryID") or "").strip()
        entry_date = _iso_date(row.get("entryDate") or row.get("Date"))
        biller = str(row.get("billerEntity") or row.get("BillerEntity") or "PC").strip().upper()
        raw_type = str(row.get("entryType") or row.get("EntryType") or "EXPENSE_PAID_PERSONALLY").strip().upper()
        pre_tax = _dec(row.get("preTaxAmount") if "preTaxAmount" in row else row.get("PreTaxAmount", 0))
        hst_amt = _dec(row.get("hstAmount") if "hstAmount" in row else row.get("HSTAmount", 0))

        credit_val = _dec(row.get("grossCreditToLoan", 0))
        debit_val = _dec(row.get("debitRepaymentFromCorp", 0))
        loan_delta = _dec(row.get("LoanDelta", 0))

        if credit_val == Decimal("0.00") and debit_val == Decimal("0.00") and loan_delta != Decimal("0.00"):
            if loan_delta > Decimal("0.00"):
                credit_val = loan_delta
            else:
                debit_val = abs(loan_delta)

        gross_val = credit_val if credit_val > Decimal("0.00") else debit_val
        signed_delta = credit_val - debit_val
        direction = "CREDIT_DUE_TO_SH" if signed_delta >= Decimal("0.00") else "DEBIT_REPAID_OR_OFFSET"

        itc_flag = row.get("hstItcEligible")
        if itc_flag is None:
            itc_eligible = hst_amt > Decimal("0.00")
        elif isinstance(itc_flag, bool):
            itc_eligible = itc_flag
        else:
            itc_eligible = str(itc_flag).strip().upper() in {"TRUE", "1", "YES"}

        vendor = str(row.get("vendor") or row.get("VendorOrCounterparty") or "").strip()
        receipt_ref = str(row.get("receiptRef") or row.get("ReceiptRef") or "").strip()
        desc = str(row.get("description") or row.get("Description") or "").strip()
        category_code = str(row.get("categoryCode") or row.get("CategoryCode") or "").strip()
        gifi_code = str(row.get("gifiCode") or row.get("GIFICode") or "2781").strip()
        linked_txn = str(row.get("linkedTransactionId") or row.get("LinkedTransactionID") or "").strip()
        linked_ap = str(row.get("linkedApBillId") or row.get("LinkedAPBillID") or "").strip()
        notes = str(row.get("notes") or row.get("Notes") or "").strip()

        return {
            "shlEntryId": entry_id,
            "SHLEntryID": entry_id,
            "entryDate": entry_date,
            "EffectiveDate": entry_date,
            "billerEntity": biller,
            "BillerEntity": biller,
            "shareholderName": "Cory Adam Schneider",
            "ShareholderName": "Cory Adam Schneider",
            "entryType": raw_type,
            "EntryType": raw_type,
            "direction": direction,
            "Direction": direction,
            "description": desc,
            "Description": desc,
            "vendor": vendor,
            "VendorPayee": vendor,
            "receiptRef": receipt_ref,
            "ReferenceNumber": receipt_ref,
            "categoryCode": category_code,
            "CategoryCode": category_code,
            "gifiCode": gifi_code,
            "GIFILine": "2781",
            "preTaxAmount": float(pre_tax),
            "PreTaxAmount": float(pre_tax),
            "hstAmount": float(hst_amt),
            "HSTITCAmount": float(hst_amt if itc_eligible else Decimal("0.00")),
            "hstItcEligible": itc_eligible,
            "grossAmount": float(gross_val),
            "GrossAmount": float(gross_val),
            "grossCreditToLoan": float(credit_val),
            "debitRepaymentFromCorp": float(debit_val),
            "signedDelta": float(signed_delta),
            "SignedDelta": float(signed_delta),
            "runningLoanBalance": float(running_dec),
            "RunningBalance": float(running_dec),
            "linkedTransactionId": linked_txn,
            "SourceTxnID": linked_txn,
            "linkedApBillId": linked_ap,
            "SourceAPBillID": linked_ap,
            "notes": notes,
            "Notes": notes,
        }

    def get_shareholder_loan_ledger(self, biller_entity: str = "PC") -> Dict[str, Any]:
        target = str(biller_entity or "PC").strip().upper()
        try:
            raw_entries = self.repo.list_shareholder_loan_entries(target)
        except TypeError:
            raw_entries = self.repo.list_shareholder_loan_entries()

        normalized_rows: List[Dict[str, Any]] = []
        running = Decimal("0.00")
        total_pre_tax = Decimal("0.00")
        total_itc = Decimal("0.00")
        total_credits = Decimal("0.00")
        total_setoffs = Decimal("0.00")
        total_repayments = Decimal("0.00")
        total_ucc_rollovers = Decimal("0.00")

        for raw in raw_entries or []:
            credit = _dec(raw.get("grossCreditToLoan", 0))
            debit = _dec(raw.get("debitRepaymentFromCorp", 0))
            delta = _dec(raw.get("LoanDelta", 0))
            if credit == Decimal("0.00") and debit == Decimal("0.00") and delta != Decimal("0.00"):
                if delta > Decimal("0.00"):
                    credit = delta
                else:
                    debit = abs(delta)
            running = (running + credit - debit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item = self._normalize_shl_row(raw, running)
            normalized_rows.append(item)

            pre_tax = _dec(item["preTaxAmount"])
            hst_amt = _dec(item["hstAmount"]) if item["hstItcEligible"] else Decimal("0.00")
            etype = item["entryType"].upper()

            if credit > Decimal("0.00"):
                total_credits += credit
                total_pre_tax += pre_tax
                total_itc += hst_amt
                if "UCC" in etype or "ROLLOVER" in etype or "SECTION_85" in etype:
                    total_ucc_rollovers += credit

            if debit > Decimal("0.00"):
                if "SHARE" in etype or "SUBSCRIPTION" in etype or "SETOFF" in etype:
                    total_setoffs += debit
                else:
                    total_repayments += debit

        return {
            "ok": True,
            "billerEntity": target,
            "shareholderName": "Cory Adam Schneider",
            "gifiLine": "2781",
            "gifiLabel": "Due to individual shareholder(s) (GIFI 2781)",
            "entries": normalized_rows,
            "entryCount": len(normalized_rows),
            "totalPreTaxExpenses": float(total_pre_tax),
            "totalClaimableHstItc": float(total_itc),
            "totalGrossCredits": float(total_credits),
            "totalShareSubscriptionSetoffs": float(total_setoffs),
            "totalRepayments": float(total_repayments),
            "totalEquipmentUccRollovers": float(total_ucc_rollovers),
            "closingBalance": float(running),
            "gifi2781Balance": float(running),
        }

    def record_personal_paid_corporate_expense(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload or {})
        entry_date = _iso_date(
            data.get("entryDate") or data.get("EffectiveDate") or data.get("Date"),
            date.today().strftime("%Y-%m-%d"),
        )
        vendor = str(data.get("vendor") or data.get("VendorPayee") or data.get("VendorOrCounterparty") or "").strip()
        description = str(data.get("description") or data.get("Description") or "").strip()
        if not description:
            raise ValueError("Expense description is required.")
        receipt_ref = str(data.get("receiptRef") or data.get("ReferenceNumber") or data.get("ReceiptRef") or "").strip()
        category_code = str(data.get("categoryCode") or data.get("CategoryCode") or "EXP_OFFICE_SUPPLIES").strip().upper()
        gifi_code = str(data.get("gifiCode") or data.get("GIFICode") or "8810").strip()
        notes = str(data.get("notes") or data.get("Notes") or "").strip()

        pre_tax = _dec(data.get("preTaxAmount") if "preTaxAmount" in data else data.get("PreTaxAmount", 0))
        hst_itc = _dec(data.get("hstAmount") if "hstAmount" in data else data.get("HSTITCAmount", data.get("HSTAmount", 0)))
        if pre_tax < Decimal("0.00") or hst_itc < Decimal("0.00"):
            raise ValueError("Pre-tax and HST amounts cannot be negative.")

        raw_gross = data.get("grossAmount") if "grossAmount" in data else data.get("GrossAmount")
        computed_gross = (pre_tax + hst_itc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if raw_gross not in (None, ""):
            gross = _dec(raw_gross)
            if abs(gross - computed_gross) > Decimal("0.01"):
                raise ValueError(
                    f"PreTaxAmount (${pre_tax:.2f}) + HSTITCAmount (${hst_itc:.2f}) must equal GrossAmount (${gross:.2f})."
                )
        else:
            gross = computed_gross

        if gross <= Decimal("0.00"):
            raise ValueError("Gross corporate expense amount must be greater than $0.00.")

        # 1. Record the corporate expense in tblTransactionsMaster (AccountCode = SHL_CORY_2781, BillerEntity = PC)
        txn_id = ""
        save_txn_fn = getattr(self.repo, "save_transaction", None)
        if callable(save_txn_fn):
            try:
                txn_res = save_txn_fn({
                    "TxnDate": entry_date,
                    "date": entry_date,
                    "Class": "Business",
                    "BusinessUnit": "Cory Legal",
                    "Type": "Expense",
                    "FromAccount": "SHL_CORY_2781",
                    "account": "SHL_CORY_2781",
                    "Payee": vendor or "Corporate Vendor",
                    "CategoryCode": category_code,
                    "Member": "Cory",
                    "Amount": float(gross),
                    "TaxAmount": float(hst_itc),
                    "TaxFlag": "HST" if hst_itc > Decimal("0.00") else "Exempt",
                    "HSTExempt": 0 if hst_itc > Decimal("0.00") else 1,
                    "GeneralOfficeExpense": 1,
                    "ExpenseDetails": description,
                    "Notes": f"Paid personally by shareholder; credited to Shareholder Loan (GIFI 2781). Ref: {receipt_ref}".strip(),
                    "Status": "Posted",
                    "Currency": "CAD",
                    "BillerEntity": "PC",
                })
                if isinstance(txn_res, dict):
                    txn_id = str(txn_res.get("transactionId") or txn_res.get("TransactionID") or "").strip()
            except Exception:
                txn_id = ""

        # 2. Append to tblShareholderLoanLedger
        entry_type = str(data.get("entryType") or data.get("EntryType") or "EXPENSE_PAID_PERSONALLY").strip().upper()
        shl_entry = self.repo.append_shareholder_loan_entry({
            "entryDate": entry_date,
            "Date": entry_date,
            "billerEntity": "PC",
            "entryType": entry_type,
            "EntryType": entry_type,
            "description": description,
            "Description": description,
            "vendor": vendor,
            "VendorOrCounterparty": vendor,
            "receiptRef": receipt_ref,
            "ReceiptRef": receipt_ref,
            "categoryCode": category_code,
            "CategoryCode": category_code,
            "gifiCode": gifi_code,
            "GIFICode": "2781",
            "preTaxAmount": float(pre_tax),
            "PreTaxAmount": float(pre_tax),
            "hstAmount": float(hst_itc),
            "HSTAmount": float(hst_itc),
            "hstItcEligible": hst_itc > Decimal("0.00"),
            "grossCreditToLoan": float(gross),
            "GrossAmount": float(gross),
            "LoanDelta": float(gross),
            "debitRepaymentFromCorp": 0.0,
            "linkedTransactionId": txn_id,
            "LinkedTransactionID": txn_id,
            "notes": notes,
            "Notes": notes,
        })
        ledger = self.get_shareholder_loan_ledger("PC")
        return {
            "ok": True,
            "entry": shl_entry,
            "linkedTransactionId": txn_id,
            "closingBalance": ledger["closingBalance"],
            "ledger": ledger,
        }

    def record_shareholder_loan_repayment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload or {})
        entry_date = _iso_date(
            data.get("entryDate") or data.get("EffectiveDate") or data.get("Date"),
            date.today().strftime("%Y-%m-%d"),
        )
        amount = _dec(
            data.get("amount")
            if "amount" in data
            else data.get("debitRepaymentFromCorp", data.get("GrossAmount", data.get("grossAmount", 0)))
        )
        if amount <= Decimal("0.00"):
            raise ValueError("Shareholder loan repayment amount must be greater than $0.00.")

        bank_account = str(data.get("bankAccountCode") or "TD_PC_CHQ").strip() or "TD_PC_CHQ"
        reference = str(data.get("receiptRef") or data.get("ReferenceNumber") or "E-TRANSFER").strip()
        description = str(
            data.get("description")
            or data.get("Description")
            or f"Tax-free corporate repayment of Shareholder Loan (GIFI 2781) from {bank_account}"
        ).strip()
        notes = str(data.get("notes") or data.get("Notes") or "Tax-free return of shareholder advances under ITA s. 15(2)").strip()

        # 1. Record bank transfer in tblTransactionsMaster
        txn_id = ""
        save_txn_fn = getattr(self.repo, "save_transaction", None)
        if callable(save_txn_fn):
            try:
                txn_res = save_txn_fn({
                    "TxnDate": entry_date,
                    "date": entry_date,
                    "Class": "Business",
                    "BusinessUnit": "Cory Legal",
                    "Type": "Transfer",
                    "FromAccount": bank_account,
                    "account": bank_account,
                    "ToAccount": "SHL_CORY_2781",
                    "toAccount": "SHL_CORY_2781",
                    "Payee": "Cory Adam Schneider",
                    "CategoryCode": "SHL_REPAYMENT",
                    "Member": "Cory",
                    "Amount": float(amount),
                    "TaxAmount": 0.0,
                    "TaxFlag": "Exempt",
                    "HSTExempt": 1,
                    "GeneralOfficeExpense": 0,
                    "ExpenseDetails": description,
                    "Notes": f"{notes} | Ref: {reference}".strip(),
                    "Status": "Posted",
                    "Currency": "CAD",
                    "BillerEntity": "PC",
                })
                if isinstance(txn_res, dict):
                    txn_id = str(txn_res.get("transactionId") or txn_res.get("TransactionID") or "").strip()
            except Exception:
                txn_id = ""

        # 2. Append debit row to tblShareholderLoanLedger
        shl_entry = self.repo.append_shareholder_loan_entry({
            "entryDate": entry_date,
            "Date": entry_date,
            "billerEntity": "PC",
            "entryType": "REPAYMENT_TO_SHAREHOLDER",
            "EntryType": "REPAYMENT",
            "description": description,
            "Description": description,
            "vendor": "Cory Adam Schneider",
            "VendorOrCounterparty": "Cory Adam Schneider",
            "SourceAccount": bank_account,
            "receiptRef": reference,
            "ReceiptRef": reference,
            "categoryCode": "SHL_REPAYMENT",
            "CategoryCode": "SHL_REPAYMENT",
            "gifiCode": "2781",
            "GIFICode": "2781",
            "preTaxAmount": 0.0,
            "PreTaxAmount": 0.0,
            "hstAmount": 0.0,
            "HSTAmount": 0.0,
            "hstItcEligible": False,
            "grossCreditToLoan": 0.0,
            "debitRepaymentFromCorp": float(amount),
            "GrossAmount": float(amount),
            "LoanDelta": float(-amount),
            "linkedTransactionId": txn_id,
            "LinkedTransactionID": txn_id,
            "notes": notes,
            "Notes": notes,
        })
        ledger = self.get_shareholder_loan_ledger("PC")
        return {
            "ok": True,
            "entry": shl_entry,
            "linkedTransactionId": txn_id,
            "closingBalance": ledger["closingBalance"],
            "ledger": ledger,
        }

    def record_equipment_ucc_rollover(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        res = self.repo.record_equipment_ucc_rollover(payload or {})
        ledger = self.get_shareholder_loan_ledger("PC")
        return {
            "ok": True,
            **dict(res or {}),
            "closingBalance": ledger["closingBalance"],
            "ledger": ledger,
        }

    # ------------------------------------------------------------------
    # 2. Dual HST Return Helper (SOLE_PROP vs. PC RT0001)
    # ------------------------------------------------------------------
    def calculate_hst_return(
        self,
        biller_entity: str = "PC",
        start_date: str = "2026-10-17",
        end_date: str = "2026-12-31",
        basis: str = "accrual",
    ) -> Dict[str, Any]:
        target_biller = str(biller_entity or "PC").strip().upper()
        if target_biller not in {"SOLE_PROP", "PC"}:
            target_biller = "PC"

        p_start = _iso_date(start_date, "2026-10-17" if target_biller == "PC" else "2026-01-01")
        p_end = _iso_date(end_date, "2026-12-31")
        cat_map = self._category_metadata_map()

        entity_info: Dict[str, Any] = {}
        get_entity_fn = getattr(self.repo, "get_billing_entity", None)
        if callable(get_entity_fn):
            try:
                entity_info = dict(get_entity_fn(target_biller) or {})
            except Exception:
                entity_info = {}

        hst_account = (
            str(entity_info.get("hstNumber") or entity_info.get("HSTNumber") or "").strip()
            or ("Pending CRA BN (Effective Nov 1, 2026)" if target_biller == "PC" else "78621 8222 RT0001")
        )

        # A. Sales & HST Collected (Line 101, Line 103, Line 105)
        try:
            invoices = self.repo.list_invoices(target_biller)
        except TypeError:
            invoices = [
                inv for inv in self.repo.list_invoices()
                if str(inv.get("billerEntity") or inv.get("BillerEntity") or "SOLE_PROP").upper() == target_biller
            ]

        line_101_sales = Decimal("0.00")
        line_103_hst_collected = Decimal("0.00")
        sales_items: List[Dict[str, Any]] = []

        for inv in invoices or []:
            status = str(inv.get("paymentStatus") or inv.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "reversed", "cancelled", "draft"}:
                continue
            inv_date = _iso_date(inv.get("invoiceDate") or inv.get("InvoiceDate"))
            if p_start and inv_date and inv_date < p_start:
                continue
            if p_end and inv_date and inv_date > p_end:
                continue

            fees = _dec(inv.get("aggregateBilled") if "aggregateBilled" in inv else inv.get("TotalFees", 0))
            disb = _dec(inv.get("disbursementsPreHst") if "disbursementsPreHst" in inv else inv.get("TotalDisbursements", 0))
            hst_fees = _dec(inv.get("hstOnBilled") if "hstOnBilled" in inv else inv.get("TotalTax", 0))
            hst_disb = _dec(inv.get("hstOnDisbursements", 0))

            pre_tax_rev = fees + disb
            hst_total = hst_fees + hst_disb
            line_101_sales += pre_tax_rev
            line_103_hst_collected += hst_total

            sales_items.append({
                "invoiceNum": str(inv.get("invoiceNum") or inv.get("InvoiceNum") or ""),
                "invoiceDate": inv_date,
                "clientName": str(inv.get("billToClient") or inv.get("clientName") or inv.get("ClientName") or ""),
                "preTaxRevenue": float(pre_tax_rev),
                "hstCollected": float(hst_total),
                "totalInvoiceAmount": float(pre_tax_rev + hst_total),
                "billerEntity": target_biller,
            })

        line_104_adjustments = Decimal("0.00")
        line_105_total_hst = line_103_hst_collected + line_104_adjustments

        # B. Eligible Input Tax Credits (Line 106, Line 107, Line 108)
        line_106_itcs = Decimal("0.00")
        itc_items: List[Dict[str, Any]] = []
        seen_txn_ids: set[str] = set()
        seen_ap_ids: set[str] = set()

        # B1. Shareholder Loan Ledger ITCs (PC only — e.g., $45.50 LSO Certificate of Authorization HST ITC)
        if target_biller == "PC":
            shl_ledger = self.get_shareholder_loan_ledger("PC")
            for entry in shl_ledger.get("entries", []):
                e_date = _iso_date(entry.get("entryDate"))
                if p_start and e_date and e_date < p_start:
                    continue
                if p_end and e_date and e_date > p_end:
                    continue
                linked_txn = str(entry.get("linkedTransactionId") or "").strip()
                linked_ap = str(entry.get("linkedApBillId") or "").strip()
                if linked_txn:
                    seen_txn_ids.add(linked_txn)
                if linked_ap:
                    seen_ap_ids.add(linked_ap)

                hst_amt = _dec(entry.get("hstAmount", 0))
                if hst_amt > Decimal("0.00") and entry.get("hstItcEligible", True):
                    cat_code = str(entry.get("categoryCode") or "").strip().upper()
                    itc_pct = cat_map.get(cat_code, {}).get("itcPct", Decimal("100.00"))
                    claimable_itc = (hst_amt * itc_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if claimable_itc > Decimal("0.00"):
                        line_106_itcs += claimable_itc
                        itc_items.append({
                            "source": "Shareholder Loan (GIFI 2781)",
                            "referenceId": str(entry.get("shlEntryId") or ""),
                            "date": e_date,
                            "vendor": str(entry.get("vendor") or ""),
                            "description": str(entry.get("description") or ""),
                            "categoryCode": cat_code,
                            "preTaxAmount": float(_dec(entry.get("preTaxAmount", 0))),
                            "hstPaid": float(hst_amt),
                            "itcClaimablePct": float(itc_pct),
                            "itcClaimed": float(claimable_itc),
                        })

        # B2. Accounts Payable Bills for target_biller
        try:
            ap_bills = self.repo.list_ap_bills(target_biller)
        except TypeError:
            ap_bills = [
                b for b in self.repo.list_ap_bills()
                if str(b.get("billerEntity") or b.get("BillerEntity") or "SOLE_PROP").upper() == target_biller
            ]

        for bill in ap_bills or []:
            bill_id = str(bill.get("apBillId") or bill.get("APBillID") or "").strip()
            if bill_id in seen_ap_ids:
                continue
            status = str(bill.get("status") or bill.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "cancelled", "reversed"}:
                continue
            b_date = _iso_date(bill.get("invoiceDate") or bill.get("InvoiceDate"))
            if p_start and b_date and b_date < p_start:
                continue
            if p_end and b_date and b_date > p_end:
                continue

            exp_txn_id = str(bill.get("ExpenseTransactionID") or bill.get("expenseTransactionId") or "").strip()
            if exp_txn_id:
                seen_txn_ids.add(exp_txn_id)
            seen_ap_ids.add(bill_id)

            tax_amt = _dec(bill.get("taxTotal") if "taxTotal" in bill else bill.get("TaxAmount", 0))
            if tax_amt > Decimal("0.00"):
                cat_code = str(bill.get("categoryCode") or bill.get("CategoryCode") or "").strip().upper()
                itc_pct = cat_map.get(cat_code, {}).get("itcPct", Decimal("100.00"))
                claimable_itc = (tax_amt * itc_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if claimable_itc > Decimal("0.00"):
                    line_106_itcs += claimable_itc
                    itc_items.append({
                        "source": "Accounts Payable",
                        "referenceId": bill_id,
                        "date": b_date,
                        "vendor": str(bill.get("vendorName") or bill.get("Vendor") or ""),
                        "description": f"AP Bill #{bill.get('invoiceNumber') or bill.get('VendorInvoiceNumber') or bill_id}",
                        "categoryCode": cat_code,
                        "preTaxAmount": float(_dec(bill.get("subtotalExclTax") if "subtotalExclTax" in bill else bill.get("Subtotal", 0))),
                        "hstPaid": float(tax_amt),
                        "itcClaimablePct": float(itc_pct),
                        "itcClaimed": float(claimable_itc),
                    })

        # B3. Transactions Master for target_biller
        list_txns_fn = getattr(self.repo, "list_transactions", None)
        if callable(list_txns_fn):
            try:
                txns = list_txns_fn({"biller_entity": target_biller})
            except Exception:
                txns = list_txns_fn()
            for txn in txns or []:
                txn_id = str(txn.get("TransactionID") or txn.get("transactionId") or "").strip()
                if not txn_id or txn_id in seen_txn_ids:
                    continue
                row_biller = str(txn.get("BillerEntity") or txn.get("billerEntity") or "").strip().upper()
                t_date = _iso_date(txn.get("TxnDate") or txn.get("date"))
                if not row_biller:
                    row_biller = "PC" if t_date >= "2026-11-01" else "SOLE_PROP"
                if row_biller != target_biller:
                    continue
                if p_start and t_date and t_date < p_start:
                    continue
                if p_end and t_date and t_date > p_end:
                    continue
                t_class = str(txn.get("Class") or txn.get("class") or "Business").strip().lower()
                t_type = str(txn.get("Type") or txn.get("type") or "").strip().lower()
                t_status = str(txn.get("Status") or txn.get("status") or "Posted").strip().lower()
                if t_class != "business" or t_type != "expense" or t_status in {"void", "voided"}:
                    continue

                tax_amt = _dec(txn.get("TaxAmount") if "TaxAmount" in txn else txn.get("taxAmount", 0))
                if tax_amt > Decimal("0.00"):
                    cat_code = str(txn.get("CategoryCode") or txn.get("categoryCode") or "").strip().upper()
                    itc_pct = cat_map.get(cat_code, {}).get("itcPct", Decimal("100.00"))
                    claimable_itc = (tax_amt * itc_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if claimable_itc > Decimal("0.00"):
                        line_106_itcs += claimable_itc
                        gross_amt = _dec(txn.get("Amount") if "Amount" in txn else txn.get("amount", 0))
                        itc_items.append({
                            "source": "Transactions Master",
                            "referenceId": txn_id,
                            "date": t_date,
                            "vendor": str(txn.get("Payee") or txn.get("payee") or ""),
                            "description": str(txn.get("ExpenseDetails") or txn.get("description") or ""),
                            "categoryCode": cat_code,
                            "preTaxAmount": float(max(Decimal("0.00"), gross_amt - tax_amt)),
                            "hstPaid": float(tax_amt),
                            "itcClaimablePct": float(itc_pct),
                            "itcClaimed": float(claimable_itc),
                        })

        line_107_itc_adjustments = Decimal("0.00")
        line_108_total_itcs = line_106_itcs + line_107_itc_adjustments
        line_109_net_tax = line_105_total_hst - line_108_total_itcs

        if line_109_net_tax < Decimal("0.00"):
            line_111_refund = abs(line_109_net_tax)
            line_113_balance_owing = Decimal("0.00")
            position_label = "Refund Claimed (Line 111)"
        elif line_109_net_tax > Decimal("0.00"):
            line_111_refund = Decimal("0.00")
            line_113_balance_owing = line_109_net_tax
            position_label = "Balance Owing (Line 113)"
        else:
            line_111_refund = Decimal("0.00")
            line_113_balance_owing = Decimal("0.00")
            position_label = "Nil Return ($0.00)"

        try:
            filing_history = self.repo.list_hst_log(target_biller)
        except Exception:
            filing_history = []

        return {
            "ok": True,
            "billerEntity": target_biller,
            "legalName": entity_info.get("legalName") or entity_info.get("LegalName") or (
                "Cory Schneider Law Professional Corporation" if target_biller == "PC" else "Cory Schneider"
            ),
            "practiceName": "Cory Schneider Law Office",
            "hstAccountNumber": hst_account,
            "periodStart": p_start,
            "periodEnd": p_end,
            "basis": basis,
            "line101SalesRevenue": float(line_101_sales),
            "line103HstCollected": float(line_103_hst_collected),
            "line104Adjustments": float(line_104_adjustments),
            "line105TotalHst": float(line_105_total_hst),
            "line106EligibleItcs": float(line_106_itcs),
            "line107ItcAdjustments": float(line_107_itc_adjustments),
            "line108TotalItcs": float(line_108_total_itcs),
            "line109NetTax": float(line_109_net_tax),
            "line111RefundClaimed": float(line_111_refund),
            "line113BalanceOwing": float(line_113_balance_owing),
            "positionLabel": position_label,
            "isRefund": line_109_net_tax < Decimal("0.00"),
            "salesItems": sales_items,
            "itcItems": itc_items,
            "filingHistory": filing_history,
        }

    def save_hst_return_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload or {})
        biller = str(data.get("billerEntity") or data.get("BillerEntity") or "PC").strip().upper()
        p_start = _iso_date(data.get("periodStart") or data.get("PeriodStart"), "2026-10-17")
        p_end = _iso_date(data.get("periodEnd") or data.get("PeriodEnd"), "2026-12-31")
        calc = self.calculate_hst_return(biller, p_start, p_end)
        save_payload = {
            "periodId": data.get("periodId") or f"HST-{biller}-{p_start}-{p_end}",
            "PeriodID": data.get("periodId") or f"HST-{biller}-{p_start}-{p_end}",
            "billerEntity": biller,
            "BillerEntity": biller,
            "hstAccountNumber": calc["hstAccountNumber"],
            "periodStart": p_start,
            "PeriodStart": p_start,
            "periodEnd": p_end,
            "PeriodEnd": p_end,
            "filingDate": _iso_date(data.get("filingDate") or data.get("FiledDate"), date.today().strftime("%Y-%m-%d")),
            "FiledDate": _iso_date(data.get("filingDate") or data.get("FiledDate"), date.today().strftime("%Y-%m-%d")),
            "line101SalesRevenue": calc["line101SalesRevenue"],
            "Line101Sales": calc["line101SalesRevenue"],
            "hstCollected": calc["line105TotalHst"],
            "Line103HSTCollected": calc["line103HstCollected"],
            "Line105TotalHST": calc["line105TotalHst"],
            "hstItcs": calc["line108TotalItcs"],
            "Line106ITCs": calc["line106EligibleItcs"],
            "Line108TotalITCs": calc["line108TotalItcs"],
            "netRemitted": calc["line109NetTax"],
            "NetTax": calc["line109NetTax"],
            "Line113Balance": calc["line109NetTax"],
            "confirmationNum": str(data.get("confirmationNum") or data.get("ConfNum") or "").strip(),
            "ConfNum": str(data.get("confirmationNum") or data.get("ConfNum") or "").strip(),
            "status": str(data.get("status") or data.get("Status") or "Filed").strip(),
            "Status": str(data.get("status") or data.get("Status") or "Filed").strip(),
        }
        saved = self.repo.save_hst_filing_record(save_payload)
        return {"ok": True, "saved": saved, "hstReturn": self.calculate_hst_return(biller, p_start, p_end)}

    # ------------------------------------------------------------------
    # 3. Sole Proprietorship T2125 + Schedule 3 Helper
    # ------------------------------------------------------------------
    def calculate_t2125_summary(self, tax_year: int = 2026) -> Dict[str, Any]:
        yr = int(tax_year or 2026)
        start_iso = f"{yr:04d}-01-01"
        end_iso = f"{yr:04d}-12-31"
        cat_map = self._category_metadata_map()

        try:
            invoices = self.repo.list_invoices("SOLE_PROP")
        except TypeError:
            invoices = [
                inv for inv in self.repo.list_invoices()
                if str(inv.get("billerEntity") or inv.get("BillerEntity") or "SOLE_PROP").upper() == "SOLE_PROP"
            ]

        gross_fees = Decimal("0.00")
        billed_disb = Decimal("0.00")
        for inv in invoices or []:
            status = str(inv.get("paymentStatus") or inv.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "reversed", "cancelled", "draft"}:
                continue
            inv_date = _iso_date(inv.get("invoiceDate") or inv.get("InvoiceDate"))
            if inv_date and (inv_date < start_iso or inv_date > end_iso):
                continue
            gross_fees += _dec(inv.get("aggregateBilled") if "aggregateBilled" in inv else inv.get("TotalFees", 0))
            billed_disb += _dec(inv.get("disbursementsPreHst") if "disbursementsPreHst" in inv else inv.get("TotalDisbursements", 0))

        gross_professional_income = gross_fees + billed_disb

        # Expense aggregation by T2125 line
        line_buckets: Dict[str, Dict[str, Any]] = {
            "8521": {"line": "8521", "label": "Advertising", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8523": {"line": "8523", "label": "Meals and entertainment (50% deductible)", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8690": {"line": "8690", "label": "Insurance (LAWPRO & practice coverage)", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8710": {"line": "8710", "label": "Interest and bank charges", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8760": {"line": "8760", "label": "Business taxes, licences, and LSO memberships", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8810": {"line": "8810", "label": "Office expenses & legal software", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8860": {"line": "8860", "label": "Legal, accounting, and professional fees", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "8960": {"line": "8960", "label": "Repairs and maintenance", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "9200": {"line": "9200", "label": "Travel & parking", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "9225": {"line": "9225", "label": "Telephone, internet, and utilities", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            "9270": {"line": "9270", "label": "Other business expenses", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
        }

        seen_txn_ids: set[str] = set()
        try:
            ap_bills = self.repo.list_ap_bills("SOLE_PROP")
        except TypeError:
            ap_bills = [
                b for b in self.repo.list_ap_bills()
                if str(b.get("billerEntity") or b.get("BillerEntity") or "SOLE_PROP").upper() == "SOLE_PROP"
            ]

        for bill in ap_bills or []:
            status = str(bill.get("status") or bill.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "cancelled", "reversed"}:
                continue
            b_date = _iso_date(bill.get("invoiceDate") or bill.get("InvoiceDate"))
            if b_date and (b_date < start_iso or b_date > end_iso):
                continue
            exp_txn = str(bill.get("ExpenseTransactionID") or bill.get("expenseTransactionId") or "").strip()
            if exp_txn:
                seen_txn_ids.add(exp_txn)
            cat_code = str(bill.get("categoryCode") or bill.get("CategoryCode") or "EXP_OFFICE_SUPPLIES").strip().upper()
            meta = cat_map.get(cat_code, {})
            t_line = str(meta.get("t2125Line") or "8810").strip()
            if not t_line:
                continue
            pre_tax = _dec(bill.get("subtotalExclTax") if "subtotalExclTax" in bill else bill.get("Subtotal", 0))
            ded_pct = meta.get("deductiblePct", Decimal("100.00"))
            ded_amt = (pre_tax * ded_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            bucket = line_buckets.setdefault(
                t_line,
                {"line": t_line, "label": meta.get("t2125Label") or "Other expenses", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
            )
            bucket["grossPreTax"] += pre_tax
            bucket["deductibleAmount"] += ded_amt

        list_txns_fn = getattr(self.repo, "list_transactions", None)
        if callable(list_txns_fn):
            try:
                txns = list_txns_fn({"biller_entity": "SOLE_PROP"})
            except Exception:
                txns = list_txns_fn()
            for txn in txns or []:
                txn_id = str(txn.get("TransactionID") or txn.get("transactionId") or "").strip()
                if not txn_id or txn_id in seen_txn_ids:
                    continue
                row_biller = str(txn.get("BillerEntity") or txn.get("billerEntity") or "").strip().upper()
                t_date = _iso_date(txn.get("TxnDate") or txn.get("date"))
                if not row_biller:
                    row_biller = "PC" if t_date >= "2026-11-01" else "SOLE_PROP"
                if row_biller != "SOLE_PROP":
                    continue
                if t_date and (t_date < start_iso or t_date > end_iso):
                    continue
                t_class = str(txn.get("Class") or txn.get("class") or "Business").strip().lower()
                t_type = str(txn.get("Type") or txn.get("type") or "").strip().lower()
                t_status = str(txn.get("Status") or txn.get("status") or "Posted").strip().lower()
                if t_class != "business" or t_type != "expense" or t_status in {"void", "voided"}:
                    continue
                cat_code = str(txn.get("CategoryCode") or txn.get("categoryCode") or "EXP_OFFICE_SUPPLIES").strip().upper()
                meta = cat_map.get(cat_code, {})
                t_line = str(meta.get("t2125Line") or "8810").strip()
                if not t_line:
                    continue
                gross_amt = _dec(txn.get("Amount") if "Amount" in txn else txn.get("amount", 0))
                tax_amt = _dec(txn.get("TaxAmount") if "TaxAmount" in txn else txn.get("taxAmount", 0))
                pre_tax = max(Decimal("0.00"), gross_amt - tax_amt)
                ded_pct = meta.get("deductiblePct", Decimal("100.00"))
                ded_amt = (pre_tax * ded_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                bucket = line_buckets.setdefault(
                    t_line,
                    {"line": t_line, "label": meta.get("t2125Label") or "Other expenses", "grossPreTax": Decimal("0.00"), "deductibleAmount": Decimal("0.00")},
                )
                bucket["grossPreTax"] += pre_tax
                bucket["deductibleAmount"] += ded_amt

        # CCA (Line 9936)
        try:
            cca_assets = self.repo.list_cca_assets("SOLE_PROP")
        except Exception:
            cca_assets = []
        cca_claimed_total = sum(
            (_dec(a.get("ccaClaimed") if "ccaClaimed" in a else a.get("CCAClaimed", 0)) for a in cca_assets or []),
            Decimal("0.00"),
        )

        expense_lines = []
        total_operating_expenses = Decimal("0.00")
        for key in sorted(line_buckets.keys()):
            b = line_buckets[key]
            total_operating_expenses += b["deductibleAmount"]
            expense_lines.append({
                "line": b["line"],
                "label": b["label"],
                "grossPreTax": float(b["grossPreTax"]),
                "deductibleAmount": float(b["deductibleAmount"]),
            })

        total_deductible_expenses = total_operating_expenses + cca_claimed_total
        net_professional_income = gross_professional_income - total_deductible_expenses

        schedule_3_goodwill_rollover = {
            "applicable": yr == 2026,
            "dispositionDate": "2026-11-01",
            "propertyType": "Qualified Small Business / Professional Practice Goodwill (ITA s. 85(1) Rollover)",
            "transfereeCorporation": "Cory Schneider Law Professional Corporation (OCN 1001781977)",
            "fairMarketValue": 100.00,
            "proceedsOfDispositionElected": 1.00,
            "adjustedCostBase": 0.00,
            "outlaysAndExpenses": 0.00,
            "capitalGain": 1.00,
            "inclusionRatePct": 50.0,
            "taxableCapitalGain": 0.50,
            "shareConsiderationReceived": "100 Class A1 Fixed Value Special Shares (Voting) (Redemption FMV $100.00, Elected PUC/Stated Capital $1.00)",
            "nonShareBoot": 0.00,
            "formT2057Deadline": "2027-06-15",
        }

        return {
            "ok": True,
            "taxYear": yr,
            "billerEntity": "SOLE_PROP",
            "proprietorName": "Cory Adam Schneider",
            "businessName": "Cory Schneider Law Office",
            "hstNumber": "78621 8222 RT0001",
            "address": "14 Parsons Court, Thornhill, ON L4K 6Z4",
            "fiscalPeriodStart": start_iso,
            "fiscalPeriodEnd": "2026-10-31 (Active Cutover) / 2026-12-31 (Pre-Nov 1 AR & WIP Run-Off)",
            "line8000GrossFees": float(gross_fees),
            "billedDisbursementsRecovery": float(billed_disb),
            "line8299GrossProfessionalIncome": float(gross_professional_income),
            "expenseLines": expense_lines,
            "totalOperatingExpenses": float(total_operating_expenses),
            "line9936CcaClaimed": float(cca_claimed_total),
            "totalDeductibleExpenses": float(total_deductible_expenses),
            "line9946NetProfessionalIncome": float(net_professional_income),
            "ccaAssets": cca_assets,
            "schedule3CapitalGains": schedule_3_goodwill_rollover,
        }

    # ------------------------------------------------------------------
    # 4. Professional Corporation T2 (Schedules 100, 125, 50, 8 & Form T2057)
    # ------------------------------------------------------------------
    def calculate_t2_summary(self, tax_year: int = 2026) -> Dict[str, Any]:
        yr = int(tax_year or 2026)
        start_iso = "2026-10-17" if yr == 2026 else f"{yr:04d}-01-01"
        end_iso = f"{yr:04d}-12-31"
        cat_map = self._category_metadata_map()

        # 1. PC Revenue (Schedule 125 GIFI 8000 / 8299)
        try:
            invoices = self.repo.list_invoices("PC")
        except TypeError:
            invoices = [
                inv for inv in self.repo.list_invoices()
                if str(inv.get("billerEntity") or inv.get("BillerEntity") or "SOLE_PROP").upper() == "PC"
            ]

        gifi_8000_fees = Decimal("0.00")
        gifi_8089_disb = Decimal("0.00")
        for inv in invoices or []:
            status = str(inv.get("paymentStatus") or inv.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "reversed", "cancelled", "draft"}:
                continue
            inv_date = _iso_date(inv.get("invoiceDate") or inv.get("InvoiceDate"))
            if inv_date and (inv_date < start_iso or inv_date > end_iso):
                continue
            gifi_8000_fees += _dec(inv.get("aggregateBilled") if "aggregateBilled" in inv else inv.get("TotalFees", 0))
            gifi_8089_disb += _dec(inv.get("disbursementsPreHst") if "disbursementsPreHst" in inv else inv.get("TotalDisbursements", 0))

        gifi_8299_total_revenue = gifi_8000_fees + gifi_8089_disb

        # 2. Schedule 125 GIFI Operating Expenses (including Shareholder Loan pre-tax corporate expenses)
        gifi_buckets: Dict[str, Dict[str, Any]] = {
            "8521": {"gifiCode": "8521", "label": "Advertising and promotion", "amount": Decimal("0.00")},
            "8523": {"gifiCode": "8523", "label": "Meals and entertainment (50% deductible)", "amount": Decimal("0.00")},
            "8670": {"gifiCode": "8670", "label": "Amortization of tangible assets", "amount": Decimal("0.00")},
            "8690": {"gifiCode": "8690", "label": "Insurance (LAWPRO & practice coverage)", "amount": Decimal("0.00")},
            "8710": {"gifiCode": "8710", "label": "Interest and bank charges", "amount": Decimal("0.00")},
            "8760": {"gifiCode": "8760", "label": "Business taxes, licences, LSO & statutory incorporation fees", "amount": Decimal("0.00")},
            "8810": {"gifiCode": "8810", "label": "Office expenses & software subscriptions", "amount": Decimal("0.00")},
            "8860": {"gifiCode": "8860", "label": "Professional, legal, accounting & NUANS search fees", "amount": Decimal("0.00")},
            "9200": {"gifiCode": "9200", "label": "Travel expenses", "amount": Decimal("0.00")},
            "9225": {"gifiCode": "9225", "label": "Telephone and telecommunications", "amount": Decimal("0.00")},
        }

        seen_txn_ids: set[str] = set()
        seen_ap_ids: set[str] = set()

        shl_ledger = self.get_shareholder_loan_ledger("PC")
        for entry in shl_ledger.get("entries", []):
            e_date = _iso_date(entry.get("entryDate"))
            if e_date and (e_date < start_iso or e_date > end_iso):
                continue
            linked_txn = str(entry.get("linkedTransactionId") or "").strip()
            linked_ap = str(entry.get("linkedApBillId") or "").strip()
            if linked_txn:
                seen_txn_ids.add(linked_txn)
            if linked_ap:
                seen_ap_ids.add(linked_ap)

            etype = str(entry.get("entryType") or "").upper()
            if "UCC" in etype or "ROLLOVER" in etype or "SECTION_85" in etype or "REPAYMENT" in etype or "SHARE" in etype or "SETOFF" in etype:
                continue

            pre_tax = _dec(entry.get("preTaxAmount", 0))
            if pre_tax <= Decimal("0.00"):
                continue
            cat_code = str(entry.get("categoryCode") or "").strip().upper()
            meta = cat_map.get(cat_code, {})
            row_gifi = str(entry.get("gifiCode") or "").strip()
            if row_gifi in {"2781", "3500", "3520", "1774", "1787", ""}:
                row_gifi = str(meta.get("gifiCode") or "8760").strip()
            ded_pct = meta.get("deductiblePct", Decimal("100.00"))
            ded_amt = (pre_tax * ded_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            bucket = gifi_buckets.setdefault(
                row_gifi,
                {"gifiCode": row_gifi, "label": meta.get("gifiLabel") or "Other operating expenses", "amount": Decimal("0.00")},
            )
            bucket["amount"] += ded_amt

        # AP Bills for PC
        try:
            ap_bills = self.repo.list_ap_bills("PC")
        except TypeError:
            ap_bills = [
                b for b in self.repo.list_ap_bills()
                if str(b.get("billerEntity") or b.get("BillerEntity") or "SOLE_PROP").upper() == "PC"
            ]

        unpaid_ap_balance = Decimal("0.00")
        for bill in ap_bills or []:
            bill_id = str(bill.get("apBillId") or bill.get("APBillID") or "").strip()
            status = str(bill.get("status") or bill.get("Status") or "Open").strip().lower()
            if status in {"void", "voided", "cancelled", "reversed"}:
                continue
            b_date = _iso_date(bill.get("invoiceDate") or bill.get("InvoiceDate"))
            if b_date and b_date <= end_iso:
                unpaid_ap_balance += _dec(bill.get("balanceTotal") if "balanceTotal" in bill else bill.get("Balance", 0))
            if bill_id in seen_ap_ids:
                continue
            if b_date and (b_date < start_iso or b_date > end_iso):
                continue
            exp_txn = str(bill.get("ExpenseTransactionID") or bill.get("expenseTransactionId") or "").strip()
            if exp_txn:
                seen_txn_ids.add(exp_txn)
            seen_ap_ids.add(bill_id)
            cat_code = str(bill.get("categoryCode") or bill.get("CategoryCode") or "EXP_OFFICE_SUPPLIES").strip().upper()
            meta = cat_map.get(cat_code, {})
            g_code = str(meta.get("gifiCode") or "8810").strip()
            pre_tax = _dec(bill.get("subtotalExclTax") if "subtotalExclTax" in bill else bill.get("Subtotal", 0))
            ded_pct = meta.get("deductiblePct", Decimal("100.00"))
            ded_amt = (pre_tax * ded_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            bucket = gifi_buckets.setdefault(
                g_code,
                {"gifiCode": g_code, "label": meta.get("gifiLabel") or "Operating expenses", "amount": Decimal("0.00")},
            )
            bucket["amount"] += ded_amt

        # Transactions Master for PC
        list_txns_fn = getattr(self.repo, "list_transactions", None)
        if callable(list_txns_fn):
            try:
                txns = list_txns_fn({"biller_entity": "PC"})
            except Exception:
                txns = list_txns_fn()
            for txn in txns or []:
                txn_id = str(txn.get("TransactionID") or txn.get("transactionId") or "").strip()
                if not txn_id or txn_id in seen_txn_ids:
                    continue
                row_biller = str(txn.get("BillerEntity") or txn.get("billerEntity") or "").strip().upper()
                t_date = _iso_date(txn.get("TxnDate") or txn.get("date"))
                if not row_biller:
                    row_biller = "PC" if t_date >= "2026-11-01" else "SOLE_PROP"
                if row_biller != "PC":
                    continue
                if t_date and (t_date < start_iso or t_date > end_iso):
                    continue
                t_class = str(txn.get("Class") or txn.get("class") or "Business").strip().lower()
                t_type = str(txn.get("Type") or txn.get("type") or "").strip().lower()
                t_status = str(txn.get("Status") or txn.get("status") or "Posted").strip().lower()
                if t_class != "business" or t_type != "expense" or t_status in {"void", "voided"}:
                    continue
                cat_code = str(txn.get("CategoryCode") or txn.get("categoryCode") or "EXP_OFFICE_SUPPLIES").strip().upper()
                meta = cat_map.get(cat_code, {})
                g_code = str(meta.get("gifiCode") or "8810").strip()
                gross_amt = _dec(txn.get("Amount") if "Amount" in txn else txn.get("amount", 0))
                tax_amt = _dec(txn.get("TaxAmount") if "TaxAmount" in txn else txn.get("taxAmount", 0))
                pre_tax = max(Decimal("0.00"), gross_amt - tax_amt)
                ded_pct = meta.get("deductiblePct", Decimal("100.00"))
                ded_amt = (pre_tax * ded_pct / Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                bucket = gifi_buckets.setdefault(
                    g_code,
                    {"gifiCode": g_code, "label": meta.get("gifiLabel") or "Operating expenses", "amount": Decimal("0.00")},
                )
                bucket["amount"] += ded_amt

        # Schedule 8 CCA for PC
        try:
            pc_cca_assets = self.repo.list_cca_assets("PC")
        except Exception:
            pc_cca_assets = []
        pc_cca_claimed = sum(
            (_dec(a.get("ccaClaimed") if "ccaClaimed" in a else a.get("CCAClaimed", 0)) for a in pc_cca_assets or []),
            Decimal("0.00"),
        )
        pc_equipment_cost = sum(
            (_dec(a.get("originalCost") if "originalCost" in a else a.get("OriginalCost", 0)) for a in pc_cca_assets or []),
            Decimal("0.00"),
        )

        schedule_125_lines = []
        gifi_9367_total_expenses = Decimal("0.00")
        for g_code in sorted(gifi_buckets.keys()):
            b = gifi_buckets[g_code]
            gifi_9367_total_expenses += b["amount"]
            schedule_125_lines.append({
                "gifiCode": b["gifiCode"],
                "label": b["label"],
                "amount": float(b["amount"]),
            })

        gifi_9999_net_income = gifi_8299_total_revenue - gifi_9367_total_expenses - pc_cca_claimed

        # Schedule 100 Balance Sheet GIFI
        try:
            pc_receivables = self.repo.list_receivables("PC")
        except TypeError:
            pc_receivables = [
                r for r in self.repo.list_receivables()
                if str(r.get("billerEntity") or r.get("BillerEntity") or "SOLE_PROP").upper() == "PC"
            ]
        gifi_1060_ar = sum(
            (_dec(r.get("balanceDue") if "balanceDue" in r else r.get("BalanceDue", 0)) for r in pc_receivables or []),
            Decimal("0.00"),
        )

        pc_hst = self.calculate_hst_return("PC", start_iso, end_iso)
        hst_net = _dec(pc_hst.get("line109NetTax", 0))
        hst_itc_receivable = abs(hst_net) if hst_net < Decimal("0.00") else Decimal("0.00")
        hst_payable = hst_net if hst_net > Decimal("0.00") else Decimal("0.00")

        gifi_2781_shl = _dec(shl_ledger.get("closingBalance", 0))
        gifi_3500_common_shares = Decimal("1.00")
        gifi_3520_special_shares = Decimal("1.00")
        gifi_2000_goodwill_elected = Decimal("1.00")

        # Cash / Bank position derived from balancing or actual collected receipts minus bank outflows
        gifi_1001_cash = max(
            Decimal("0.00"),
            (gifi_2781_shl + gifi_3500_common_shares + gifi_3520_special_shares + gifi_9999_net_income + unpaid_ap_balance + hst_payable)
            - (gifi_1060_ar + hst_itc_receivable + (pc_equipment_cost - pc_cca_claimed) + gifi_2000_goodwill_elected),
        )
        total_assets = (
            gifi_1001_cash
            + gifi_1060_ar
            + hst_itc_receivable
            + (pc_equipment_cost - pc_cca_claimed)
            + gifi_2000_goodwill_elected
        )
        total_liabilities = unpaid_ap_balance + hst_payable + gifi_2781_shl
        total_equity = gifi_3500_common_shares + gifi_3520_special_shares + gifi_9999_net_income

        schedule_100_lines = [
            {"section": "Assets", "gifiCode": "1001", "label": "Cash and deposits", "amount": float(gifi_1001_cash)},
            {"section": "Assets", "gifiCode": "1060", "label": "Accounts receivable (PC invoices)", "amount": float(gifi_1060_ar)},
            {"section": "Assets", "gifiCode": "1300", "label": "HST Input Tax Credits (ITC) receivable", "amount": float(hst_itc_receivable)},
            {"section": "Assets", "gifiCode": "1740", "label": "Machinery, equipment, furniture and fixtures (at cost/UCC)", "amount": float(pc_equipment_cost)},
            {"section": "Assets", "gifiCode": "2001", "label": "Goodwill / intangible assets (s. 85(1) elected cost)", "amount": float(gifi_2000_goodwill_elected)},
            {"section": "Assets", "gifiCode": "2599", "label": "Total Assets", "amount": float(total_assets)},
            {"section": "Liabilities", "gifiCode": "2620", "label": "Accounts payable and accrued liabilities", "amount": float(unpaid_ap_balance)},
            {"section": "Liabilities", "gifiCode": "2680", "label": "Taxes / HST payable", "amount": float(hst_payable)},
            {"section": "Liabilities", "gifiCode": "2781", "label": "Due to individual shareholder (Cory Adam Schneider)", "amount": float(gifi_2781_shl)},
            {"section": "Liabilities", "gifiCode": "3499", "label": "Total Liabilities", "amount": float(total_liabilities)},
            {"section": "Shareholder Equity", "gifiCode": "3500", "label": "Common shares (100 Class 1 Common Shares — OBCA s. 23(3) set-off)", "amount": float(gifi_3500_common_shares)},
            {"section": "Shareholder Equity", "gifiCode": "3520", "label": "Preferred / special shares (100 Class A1 Fixed Value Special Shares — s. 85(1) PUC)", "amount": float(gifi_3520_special_shares)},
            {"section": "Shareholder Equity", "gifiCode": "3600", "label": "Retained earnings / (deficit)", "amount": float(gifi_9999_net_income)},
            {"section": "Shareholder Equity", "gifiCode": "3620", "label": "Total Shareholder Equity", "amount": float(total_equity)},
        ]

        schedule_50_shareholders = [
            {
                "shareholderName": "Cory Adam Schneider",
                "sinOrBn": "Individual Shareholder (Sole Director & Officer)",
                "shareClass": "Class 1 Common Shares (Voting, Participating)",
                "sharesHeld": 100,
                "ownershipPct": 100.0,
                "issueDate": "2026-10-17",
                "statedCapital": 1.00,
                "paidUpCapital": 1.00,
                "redemptionAmount": None,
                "gifiCode": "3500",
                "certificateStatus": "Uncertificated (OBCA s. 54(1) / Notice #1)",
            },
            {
                "shareholderName": "Cory Adam Schneider",
                "sinOrBn": "Individual Shareholder (Sole Director & Officer)",
                "shareClass": "Class A1 Fixed Value Special Shares (Voting, Non-Participating)",
                "sharesHeld": 100,
                "ownershipPct": 100.0,
                "issueDate": "2026-11-01",
                "statedCapital": 1.00,
                "paidUpCapital": 1.00,
                "redemptionAmount": 100.00,
                "gifiCode": "3520",
                "certificateStatus": "Uncertificated (OBCA s. 54(1) & s. 24(3))",
            },
        ]

        form_t2057_helper = {
            "formCode": "T2057",
            "title": "Election on Disposition of Property by a Taxpayer to a Taxable Canadian Corporation (ITA s. 85(1))",
            "transferorName": "Cory Adam Schneider",
            "transfereeName": "Cory Schneider Law Professional Corporation",
            "transfereeOcn": "1001781977",
            "effectiveRolloverDate": "2026-11-01",
            "filingDeadline": "2027-06-15",
            "status": "Prepared — File on or before June 15, 2027",
            "electedProperties": [
                {
                    "propertyDescription": "Goodwill of the Legal Practice (Cory Schneider Law Office)",
                    "propertyCategory": "Goodwill / Class 14.1 Eligible Capital Property",
                    "fairMarketValue": 100.00,
                    "costAmount": 0.00,
                    "electedAmount": 1.00,
                    "nonShareBootDescription": "None ($0.00)",
                    "nonShareBootFmv": 0.00,
                    "shareConsiderationDescription": "100 Class A1 Fixed Value Special Shares (Voting)",
                    "shareConsiderationFmv": 100.00,
                    "statedCapitalAdditionObca24_3": 1.00,
                }
            ],
            "nonT2057CutoverRules": [
                "Office & Computer Equipment: Transferred on 2026-11-01 at tax cost (UCC) outside of Form T2057 and credited dollar-for-dollar to Shareholder Loan (GIFI 2781) with zero recapture.",
                "Pre-Nov 1, 2026 Billed AR & Unbilled WIP: Excluded from s. 85 rollover; billed and collected through SOLE_PROP (T2125).",
                "100 Class 1 Common Shares: Issued on 2026-10-17 for $1.00 paid via OBCA s. 23(3) set-off against start-up outlays (Notice #1 / Doc #10).",
            ],
        }

        return {
            "ok": True,
            "taxYear": yr,
            "billerEntity": "PC",
            "legalName": "CORY SCHNEIDER LAW PROFESSIONAL CORPORATION",
            "practiceName": "CORY SCHNEIDER LAW OFFICE",
            "ocn": "1001781977",
            "companyKey": "448389332",
            "bin": "1001782016",
            "incorporationDate": "2026-10-17",
            "fiscalPeriodStart": start_iso,
            "fiscalPeriodEnd": end_iso,
            "t2FilingDeadline": f"{yr + 1:04d}-06-30",
            "taxBalanceDueDate": f"{yr + 1:04d}-03-31",
            "gifi8000TradeSales": float(gifi_8000_fees),
            "gifi8089DisbursementRecovery": float(gifi_8089_disb),
            "gifi8299TotalRevenue": float(gifi_8299_total_revenue),
            "schedule125Lines": schedule_125_lines,
            "gifi9367TotalOperatingExpenses": float(gifi_9367_total_expenses),
            "schedule8CcaClaimed": float(pc_cca_claimed),
            "gifi9999NetIncomeBeforeTax": float(gifi_9999_net_income),
            "schedule100Lines": schedule_100_lines,
            "gifi2781ShareholderLoanBalance": float(gifi_2781_shl),
            "gifi3500CommonShares": float(gifi_3500_common_shares),
            "gifi3520SpecialShares": float(gifi_3520_special_shares),
            "schedule50Shareholders": schedule_50_shareholders,
            "schedule8CcaAssets": pc_cca_assets,
            "formT2057Helper": form_t2057_helper,
        }
