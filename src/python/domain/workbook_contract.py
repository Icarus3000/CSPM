from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from domain import schema_constants as sc
from domain.ap_schema import (
    AP_BILLS_HEADERS,
    AP_BILLS_SHEET,
    AP_BILLS_TABLE,
    AP_PAYMENTS_HEADERS,
    AP_PAYMENTS_SHEET,
    AP_PAYMENTS_TABLE,
)


@dataclass(frozen=True)
class WorkbookTableContract:
    sheet: str
    table: str
    primary_key: str | None
    columns: Tuple[str, ...]
    identity_policy: str = "stable_primary_key"


def _table(
    sheet: str,
    table: str,
    primary_key: str | None,
    identity_policy: str = "stable_primary_key",
) -> WorkbookTableContract:
    return WorkbookTableContract(
        sheet,
        table,
        primary_key,
        tuple(sc.TABLE_COLUMNS[table]),
        identity_policy,
    )


# One pre-conflict structure for runtime schema migration, integrity checking,
# and sanitized-template generation.  Conflict tables are intentionally absent.
CSPM_PRE_CONFLICT_TABLES: Tuple[WorkbookTableContract, ...] = (
    _table(sc.SHEET_PARENTS, sc.TBL_PARENTS, sc.COL_PARENT_ID),
    _table(sc.SHEET_CLIENTS, sc.TBL_CLIENTS, sc.COL_CLIENT_ID),
    _table(sc.SHEET_CLIENT_PROFILES, sc.TBL_CLIENT_PROFILES, sc.COL_PROFILE_CLIENT_ID),
    _table(sc.SHEET_MATTER_PARTIES, sc.TBL_MATTER_PARTIES, sc.COL_MATTER_PARTY_ID),
    _table(sc.SHEET_MATTERS, sc.TBL_MATTERS, sc.COL_MATTER_ID),
    _table(sc.SHEET_TIME, sc.TBL_TIME, sc.COL_TIME_ENTRY_ID),
    _table(sc.SHEET_TRADEMARKS, sc.TBL_TRADEMARKS, sc.COL_TM_ID),
    _table(sc.SHEET_TRANSACTIONS, sc.TBL_TRANSACTIONS_MASTER, sc.COL_TXN_ID),
    _table(sc.SHEET_TRANSACTION_ACCOUNTS, sc.TBL_TRANSACTION_ACCOUNTS, sc.COL_TXN_ACCOUNT_CODE),
    _table(sc.SHEET_TRANSACTION_CATEGORIES, sc.TBL_TRANSACTION_CATEGORIES, sc.COL_TXN_CATEGORY_LKP_CODE),
    _table(
        sc.SHEET_TRANSACTION_BUSINESS_UNITS,
        sc.TBL_TRANSACTION_BUSINESS_UNITS,
        sc.COL_TXN_BUSINESS_UNIT_NAME,
    ),
    _table(sc.SHEET_TRANSACTION_PAYEES, sc.TBL_TRANSACTION_PAYEES, sc.COL_TXN_PAYEE_NAME),
    _table(sc.SHEET_DISBURSEMENTS, sc.TBL_DISBURSEMENTS, sc.COL_DISB_ID),
    _table(sc.SHEET_LEDGER, sc.TBL_LEDGER, sc.COL_LEDGER_ID),
    _table(
        sc.SHEET_RECEIVABLES,
        sc.TBL_RECEIVABLES,
        None,
        "legacy_nonunique_register",
    ),
    _table(
        sc.SHEET_INVOICE_LOG,
        sc.TBL_INVOICE_LOG,
        None,
        "legacy_nonunique_register",
    ),
    _table(sc.SHEET_HST_LOG, sc.TBL_HST_LOG, sc.COL_HST_PERIOD_ID),
    _table(sc.SHEET_DRAFT_INVOICES, sc.TBL_DRAFT_INVOICES, sc.COL_DRAFT_ID),
    _table(sc.SHEET_CORP_ENTITIES, sc.TBL_CORP_ENTITIES, sc.COL_CORP_ENTITY_ID),
    _table(sc.SHEET_CORP_RELATIONSHIPS, sc.TBL_CORP_RELATIONSHIPS, sc.COL_CREL_ID),
    _table(sc.SHEET_CORP_TRANSACTIONS, sc.TBL_CORP_TRANSACTIONS, sc.COL_CTX_ID),
    WorkbookTableContract(AP_BILLS_SHEET, AP_BILLS_TABLE, "APBillID", tuple(AP_BILLS_HEADERS)),
    WorkbookTableContract(
        AP_PAYMENTS_SHEET,
        AP_PAYMENTS_TABLE,
        "APPaymentID",
        tuple(AP_PAYMENTS_HEADERS),
    ),
)


BOOL_COLUMNS = {
    "Active",
    "BillableAllowed",
    "BusinessDeductibleEligible",
    "ClientTaxExempt",
    "ColorClaimed",
    "DeductibleEligible",
    "GeneralOfficeExpense",
    "HistoricalAdoption",
    "HistoricalPayment",
    "HSTExempt",
    "IsBillingRecipient",
    "IsFileAnchor",
    "IsFlatFee",
    "JointInstructionsRequireAll",
    "JointNoConfidentialityConfirmed",
    "MedicalEligible",
    "ReconciliationMode",
    "RetainerRequired",
    "Shadow",
    "ShowTotalHours",
    "TaxExempt",
}

INT_COLUMNS = {"RawSeconds", "SortOrder"}

DATE_COLUMNS = {
    "AdvertisementDate",
    "AllowanceDate",
    "ApprovalDate",
    "Birthday",
    "ClearedAt",
    "Date",
    "DateClosed",
    "DateClientAdded",
    "DateOfEngagement",
    "DateOpened",
    "DueDate",
    "EngagementStartDate",
    "EndDate",
    "ExaminersReportDate",
    "FXRateDate",
    "FiledDate",
    "FilingDate",
    "FiscalYearEnd",
    "IncorporationDate",
    "InvoiceDate",
    "NoticeOfAllowanceDate",
    "OfficeActionResponseDeadline",
    "OppositionDeadline",
    "OppositionPeriodEndDate",
    "PaidDate",
    "PaymentDate",
    "PeriodEnd",
    "PeriodStart",
    "PublicationAdvertisementDate",
    "PublicationDate",
    "ReconciledAt",
    "RegistrationDate",
    "RenewalDeadline",
    "Section15Deadline",
    "Section8Deadline",
    "Section9Deadline",
    "SOUDeadline",
    "StartDate",
    "TxnDate",
    "UpcomingLocalDeadlineOfficeActionDate",
}

DATETIME_COLUMNS = {"AdoptedAt", "CreatedAt", "UpdatedAt"}

NUMBER_COLUMNS = {
    "AgencySplitPercent",
    "ClientRate",
    "AggregateBilled",
    "Amount",
    "AmountPaid",
    "AmountToYou",
    "Balance",
    "BalanceDue",
    "BaseAmount",
    "BaseSubtotal",
    "BaseTaxAmount",
    "BaseTotal",
    "BillClaimPct",
    "BillPct",
    "BillingsExclHST",
    "Collected",
    "CreditsAdj",
    "DefaultClientRate",
    "DefaultRate",
    "DefaultSharePct",
    "DiscountValue",
    "ExpensesExclHST",
    "FXRate",
    "FlatFeeAmount",
    "GrossToClient",
    "HST",
    "HSTCollected",
    "HSTPaid",
    "Hours",
    "NetTax",
    "NumberOfShares",
    "OriginalAmount",
    "OriginalSubtotal",
    "OriginalTaxAmount",
    "OriginalTotal",
    "OwnershipPercentage",
    "PricePerShare",
    "Receivable",
    "RetainerAmount",
    "SharePct",
    "SharesHeld",
    "Subtotal",
    "TaxAmount",
    "Total",
    "TotalClaimAmount",
    "TotalDisbursements",
    "TotalDue",
    "TotalExclHST",
    "TotalFees",
    "TotalInclHST",
    "TotalInvoiced",
    "TotalTax",
    "TotalValue",
    "WriteOff",
}


def column_type(column: str) -> str:
    if column in BOOL_COLUMNS:
        return "bool-int"
    if column in INT_COLUMNS:
        return "int"
    if column in DATETIME_COLUMNS:
        return "datetime"
    if column in DATE_COLUMNS:
        return "date"
    if column in NUMBER_COLUMNS:
        return "number"
    return "text"


def table_contract_map() -> Dict[str, WorkbookTableContract]:
    return {contract.table: contract for contract in CSPM_PRE_CONFLICT_TABLES}
