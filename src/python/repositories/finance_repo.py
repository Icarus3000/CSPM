from __future__ import annotations

import sys
import csv
import math
import json
import os
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import typing
if typing.TYPE_CHECKING:
    from openpyxl import Workbook, load_workbook
    from openpyxl.cell.cell import MergedCell
    from openpyxl.utils.cell import get_column_letter, range_boundaries
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.worksheet.worksheet import Worksheet
else:
    Workbook = None
    
    MergedCell = None
    get_column_letter = None
    range_boundaries = None
    Table = None
    TableStyleInfo = None
    Worksheet = None

def _lazy_load_heavy_libs():
    global Workbook, load_workbook, MergedCell, get_column_letter, range_boundaries, Table, TableStyleInfo, Worksheet
    if Workbook is None:
        from openpyxl import Workbook, load_workbook
        from openpyxl.cell.cell import MergedCell
        from openpyxl.utils.cell import get_column_letter, range_boundaries
        from openpyxl.worksheet.table import Table, TableStyleInfo
        from openpyxl.worksheet.worksheet import Worksheet


from uuid import uuid4

# Support direct execution via:
# python src/python/repositories/excel_repo.py
if __package__ in (None, ""):
    _THIS_FILE = Path(__file__).resolve()
    _PYTHON_ROOT = _THIS_FILE.parents[1]
    _PYTHON_ROOT_STR = str(_PYTHON_ROOT)
    if _PYTHON_ROOT_STR not in sys.path:
        sys.path.insert(0, _PYTHON_ROOT_STR)


from domain.money import calc_amounts, normalize_pct
from domain import schema_constants as sc
from services.paths import AppPaths
from repositories.excel_repo import ExcelRepo, TableRef

import logging
logger = logging.getLogger(__name__)

TBL_PARENTS = TableRef(sc.SHEET_PARENTS, sc.TBL_PARENTS)
TBL_CLIENTS = TableRef(sc.SHEET_CLIENTS, sc.TBL_CLIENTS)
TBL_CLIENT_PROFILES = TableRef(sc.SHEET_CLIENT_PROFILES, sc.TBL_CLIENT_PROFILES)
TBL_MATTERS = TableRef(sc.SHEET_MATTERS, sc.TBL_MATTERS)
TBL_TIME = TableRef(sc.SHEET_TIME, sc.TBL_TIME)
TBL_TRADEMARKS = TableRef(sc.SHEET_TRADEMARKS, sc.TBL_TRADEMARKS)
TBL_TRANSACTIONS_MASTER = TableRef(sc.SHEET_TRANSACTIONS, sc.TBL_TRANSACTIONS_MASTER)
TBL_TRANSACTION_ACCOUNTS = TableRef(sc.SHEET_TRANSACTION_ACCOUNTS, sc.TBL_TRANSACTION_ACCOUNTS)
TBL_TRANSACTION_CATEGORIES = TableRef(sc.SHEET_TRANSACTION_CATEGORIES, sc.TBL_TRANSACTION_CATEGORIES)
TBL_TRANSACTION_BUSINESS_UNITS = TableRef(sc.SHEET_TRANSACTION_BUSINESS_UNITS, sc.TBL_TRANSACTION_BUSINESS_UNITS)
TBL_TRANSACTION_PAYEES = TableRef(sc.SHEET_TRANSACTION_PAYEES, sc.TBL_TRANSACTION_PAYEES)

TABLES_IN_ORDER = [
    TBL_PARENTS,
    TBL_CLIENTS,
    TBL_CLIENT_PROFILES,
    TBL_MATTERS,
    TBL_TIME,
    TBL_TRADEMARKS,
    TBL_TRANSACTIONS_MASTER,
    TBL_TRANSACTION_ACCOUNTS,
    TBL_TRANSACTION_CATEGORIES,
    TBL_TRANSACTION_BUSINESS_UNITS,
    TBL_TRANSACTION_PAYEES,
]
TABLE_COLUMNS = sc.TABLE_COLUMNS
TABLE_ALIASES = sc.TABLE_ALIASES
TABLE_META_CACHE_SCHEMA_VERSION = 1


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_us_phone(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    digits = re.sub(r"\D+", "", text)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return text
    return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"


def _looks_like_email_address(value: Any) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", text))


def _normalize_search_text(value: Any) -> str:
    text = _clean_text(value).lower()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def _matter_token_fragment(value: Any, width: int = 3, fallback: str = "XXX") -> str:
    """Legacy compat shim – kept for any call-sites not yet migrated."""
    token = re.sub(r"[^A-Za-z0-9]+", "", _clean_text(value).upper())
    if not token:
        token = _clean_text(fallback).upper() or "X"
    if len(token) >= width:
        return token[:width]
    return (token + ("X" * width))[:width]


# ---------------------------------------------------------------------------
# Legacy matter-number helpers
# ---------------------------------------------------------------------------

# Hardcoded 3-char matter-type codes.  Keys are normalised lowercase.
_MATTER_TYPE_CODES: Dict[str, str] = {
    "trademark": "TMK",
    "trademarks": "TMK",
    "tmk": "TMK",
    "commercial": "COM",
    "com": "COM",
    "corporate": "CRP",
    "crp": "CRP",
    "corporation": "CRP",
    "estate": "EST",
    "estates": "EST",
    "est": "EST",
    "tax": "TAX",
    "taxation": "TAX",
    "taxes": "TAX",
    "audit": "AUD",
    "audits": "AUD",
    "aud": "AUD",
    "income": "INC",
    "inc": "INC",
    "general": "GEN",
    "gen": "GEN",
}

# Words that should be stripped from the *end* of a company name before coding
_COMPANY_NOISE_SUFFIXES = {
    "inc", "ltd", "llc", "llp", "lp", "corp", "co", "plc", "pte", "pty",
    "sa", "srl", "sas", "gmbh", "ag", "nv", "bv", "ab",
}


def _legacy_matter_type_code(matter_type: Any) -> str:
    """Return the canonical 3-char matter-type code for the given string."""
    key = re.sub(r"[^a-z]", "", _clean_text(matter_type).lower())
    return _MATTER_TYPE_CODES.get(key, "GEN")


def _legacy_raw_client_code(name: Any, entity_type: Any = "") -> str:
    """
    Derive an *uncollision-checked* 4-character client code from *name*.

    Rules
    -----
    Individual  (EntityType == "Individual"):
        last[:4].  If len(last) < 4, pad with first[:needed].
    Company / anything else:
        Strip trailing noise suffixes, then take first-word[:4].
    In both cases, keep alphanumerics (including digits), pad with "X",
    return exactly 4 uppercase characters.
    """
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", "", _clean_text(name)).strip()
    parts = cleaned.split()
    if not parts:
        return "XXXX"

    is_individual = _clean_text(entity_type).lower() == "individual"

    if is_individual:
        last = parts[-1].upper() if len(parts) >= 2 else parts[0].upper()
        raw = last[:4]
        if len(raw) < 4 and len(parts) >= 2:
            first = parts[0].upper()
            raw = raw + first[: 4 - len(raw)]
    else:
        # company: try the first meaningful word
        meaningful_parts = [p for p in parts if p.lower() not in _COMPANY_NOISE_SUFFIXES]
        main = (meaningful_parts[0] if meaningful_parts else parts[0]).upper()
        raw = main[:4]

    return (raw + "XXXX")[:4]


def _matter_year_two_digits(date_text: Any) -> str:
    text = _clean_text(date_text)
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if match:
        return match.group(1)[2:]
    return datetime.now().strftime("%y")


def _normalize_choice(value: Any, allowed: List[str], default_value: str = "") -> str:
    normalized_allowed: Dict[str, str] = {
        _clean_text(choice).lower(): _clean_text(choice)
        for choice in allowed
        if _clean_text(choice)
    }
    if not normalized_allowed:
        return _clean_text(value) or _clean_text(default_value)
    raw = _clean_text(value)
    if not raw:
        return _clean_text(default_value) if _clean_text(default_value) else next(iter(normalized_allowed.values()))
    return normalized_allowed.get(raw.lower(), "")


def _is_valid_iso_date(text: Any) -> bool:
    value = _clean_text(text)
    if not value:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except Exception:
        return False


def _to_code_token(value: Any, fallback: str = "X") -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", _clean_text(value).strip()).strip("_").upper()
    if token:
        return token
    return _clean_text(fallback).upper() or "X"


def _search_terms(value: Any) -> List[str]:
    normalized = _normalize_search_text(value)
    if not normalized:
        return []

    terms: List[str] = []
    seen = set()
    for raw_token in re.findall(r"[a-z0-9@._:/#\-]+", normalized, flags=re.IGNORECASE):
        token = raw_token.strip(" .,_-")
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)

    if " " in normalized and normalized not in seen:
        terms.insert(0, normalized)
    return terms


def _boolean_query_tokens(value: Any) -> List[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    return [tok for tok in re.findall(r"\(|\)|AND|OR|NOT|[^\s()]+", raw, flags=re.IGNORECASE) if tok]


def _boolean_to_postfix(tokens: List[str]) -> List[str]:
    precedence = {"OR": 1, "AND": 2, "NOT": 3}
    output: List[str] = []
    stack: List[str] = []

    for raw_tok in tokens:
        tok = str(raw_tok or "").strip()
        if not tok:
            continue
        upper = tok.upper()
        if upper in ("AND", "OR", "NOT"):
            if upper == "NOT":
                while stack and stack[-1] in precedence and precedence[stack[-1]] > precedence[upper]:
                    output.append(stack.pop())
            else:
                while stack and stack[-1] in precedence and precedence[stack[-1]] >= precedence[upper]:
                    output.append(stack.pop())
            stack.append(upper)
            continue
        if tok == "(":
            stack.append(tok)
            continue
        if tok == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            if stack and stack[-1] == "(":
                stack.pop()
            continue
        output.append(_normalize_search_text(tok))

    while stack:
        top = stack.pop()
        if top in ("(", ")"):
            continue
        output.append(top)
    return output


def _match_boolean_postfix(postfix: List[str], haystack: str) -> bool:
    if not postfix:
        return False
    stack: List[bool] = []

    for tok in postfix:
        upper = tok.upper()
        if upper == "NOT":
            value = stack.pop() if stack else False
            stack.append(not value)
            continue
        if upper in ("AND", "OR"):
            right = stack.pop() if stack else False
            left = stack.pop() if stack else False
            stack.append(left and right if upper == "AND" else left or right)
            continue
        needle = _normalize_search_text(tok)
        stack.append(bool(needle) and needle in haystack)

    return stack[-1] if stack else False


def _normalize_index(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except Exception:
        pass
    return fallback


def _safe_range_boundaries(ref: str) -> Tuple[int, int, int, int]:
    _lazy_load_heavy_libs()
    min_col_raw, min_row_raw, max_col_raw, max_row_raw = range_boundaries(ref)
    min_col = _normalize_index(min_col_raw, 1)
    min_row = _normalize_index(min_row_raw, 1)
    max_col = _normalize_index(max_col_raw, min_col)
    max_row = _normalize_index(max_row_raw, min_row)
    if max_col < min_col:
        max_col = min_col
    if max_row < min_row:
        max_row = min_row
    return min_col, min_row, max_col, max_row


def _set_cell_value(ws: Worksheet, row_idx: int, col_idx: int, value: Any) -> None:
    _lazy_load_heavy_libs()
    cell_obj = ws.cell(row=row_idx, column=col_idx)
    if isinstance(cell_obj, MergedCell):
        return
    cell_obj.value = value

class FinanceRepo:
    def __init__(self, db: ExcelRepo):
        self.db = db

    def list_transaction_accounts(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = [self.db._canonicalize_transaction_account_row(r) for r in self.db._read_table_rows(TBL_TRANSACTION_ACCOUNTS)]
        if not rows:
            seed_rows = self.db._load_seed_csv_rows("transactions_master.accounts.seed.csv")
            rows = [self.db._canonicalize_transaction_account_row(r) for r in seed_rows]
        out: List[Dict[str, Any]] = []
        for row in rows:
            active = self.db._to_bool_int(row.get(sc.COL_TXN_ACCOUNT_ACTIVE), default=1)
            if not include_inactive and active != 1:
                continue
            alias_text = _clean_text(row.get(sc.COL_TXN_ACCOUNT_ALIASES))
            aliases = [a.strip() for a in alias_text.split(",") if a.strip()]
            out.append(
                {
                    "accountCode": _clean_text(row.get(sc.COL_TXN_ACCOUNT_CODE)),
                    "accountName": _clean_text(row.get(sc.COL_TXN_ACCOUNT_NAME)),
                    "accountKind": _clean_text(row.get(sc.COL_TXN_ACCOUNT_KIND)),
                    "owner": _clean_text(row.get(sc.COL_TXN_ACCOUNT_OWNER)),
                    "active": active,
                    "aliases": aliases,
                }
            )
        out.sort(
            key=lambda row: (
                _normalize_search_text(row.get("accountName")),
                _normalize_search_text(row.get("accountCode")),
            )
        )
        return out

    def list_transaction_categories(
        self,
        txn_type: str = "",
        txn_class: str = "",
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        type_filter = _normalize_search_text(txn_type)
        class_filter = _normalize_search_text(txn_class)
        rows = [
            self.db._canonicalize_transaction_category_row(r)
            for r in self.db._read_table_rows(TBL_TRANSACTION_CATEGORIES)
        ]
        if not rows:
            seed_rows = self.db._load_seed_csv_rows("transactions_master.categories.seed.csv")
            rows = [self.db._canonicalize_transaction_category_row(r) for r in seed_rows]
        out: List[Dict[str, Any]] = []
        for row in rows:
            active = self.db._to_bool_int(row.get(sc.COL_TXN_CATEGORY_LKP_ACTIVE), default=1)
            if not include_inactive and active != 1:
                continue
            row_type = _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_TYPE))
            row_scope = _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_CLASS_SCOPE))
            if type_filter and not self._txn_scope_match(row_type, type_filter):
                continue
            if class_filter and not self._txn_scope_match(row_scope, class_filter):
                continue
            out.append(
                {
                    "categoryCode": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_CODE)),
                    "categoryName": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_NAME)),
                    "type": row_type,
                    "classScope": row_scope,
                    "taxFlagDefault": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_TAX_FLAG_DEFAULT)),
                    "billableAllowed": self.db._to_bool_int(
                        row.get(sc.COL_TXN_CATEGORY_LKP_BILLABLE_ALLOWED), default=0
                    ),
                    "medicalEligible": self.db._to_bool_int(
                        row.get(sc.COL_TXN_CATEGORY_LKP_MEDICAL_ELIGIBLE), default=0
                    ),
                    "deductibleEligible": self.db._to_bool_int(
                        row.get(sc.COL_TXN_CATEGORY_LKP_DEDUCTIBLE_ELIGIBLE), default=0
                    ),
                    "businessDeductibleEligible": self.db._to_bool_int(
                        row.get(sc.COL_TXN_CATEGORY_LKP_BUSINESS_DEDUCTIBLE_ELIGIBLE), default=0
                    ),
                    "active": active,
                    "sortOrder": self.db._parse_int(row.get(sc.COL_TXN_CATEGORY_LKP_SORT_ORDER)) or 0,
                    "notes": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_NOTES)),
                    "t2125LineNumber": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_T2125_LINE_NUM)),
                    "t2125LineLabel": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_T2125_LINE_LABEL)),
                    "gifiSchedule125Code": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_GIFI_S125_CODE)),
                    "gifiSchedule125Label": _clean_text(row.get(sc.COL_TXN_CATEGORY_LKP_GIFI_S125_LABEL)),
                    "deductiblePct": float(self.db._parse_float(row.get(sc.COL_TXN_CATEGORY_LKP_DEDUCTIBLE_PCT)) or 100.0),
                    "itcClaimablePct": float(self.db._parse_float(row.get(sc.COL_TXN_CATEGORY_LKP_ITC_CLAIMABLE_PCT)) or 100.0),
                }
            )
        out.sort(
            key=lambda row: (
                int(row.get("sortOrder", 0)),
                _normalize_search_text(row.get("categoryName")),
                _normalize_search_text(row.get("categoryCode")),
            )
        )
        return out

    def list_transaction_business_units(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = [
            self.db._canonicalize_transaction_business_unit_row(r)
            for r in self.db._read_table_rows(TBL_TRANSACTION_BUSINESS_UNITS)
        ]
        if not rows:
            seed_rows = self.db._load_seed_csv_rows("transactions_master.business_units.seed.csv")
            rows = [self.db._canonicalize_transaction_business_unit_row(r) for r in seed_rows]
        out: List[Dict[str, Any]] = []
        for row in rows:
            active = self.db._to_bool_int(row.get(sc.COL_TXN_BUSINESS_UNIT_ACTIVE), default=1)
            if not include_inactive and active != 1:
                continue
            out.append(
                {
                    "businessUnit": _clean_text(row.get(sc.COL_TXN_BUSINESS_UNIT_NAME)),
                    "owner": _clean_text(row.get(sc.COL_TXN_BUSINESS_UNIT_OWNER)),
                    "active": active,
                }
            )
        out.sort(key=lambda row: _normalize_search_text(row.get("businessUnit")))
        return out

    def list_transaction_payees(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        rows = [self.db._canonicalize_transaction_payee_row(r) for r in self.db._read_table_rows(TBL_TRANSACTION_PAYEES)]
        if not rows:
            seed_rows = self.db._load_seed_csv_rows("transactions_master.payees.seed.csv")
            rows = [self.db._canonicalize_transaction_payee_row(r) for r in seed_rows]
        out: List[Dict[str, Any]] = []
        for row in rows:
            active = self.db._to_bool_int(row.get(sc.COL_TXN_PAYEE_ACTIVE), default=1)
            if not include_inactive and active != 1:
                continue
            out.append(
                {
                    "payeeName": _clean_text(row.get(sc.COL_TXN_PAYEE_NAME)),
                    "defaultCategoryCode": _clean_text(row.get(sc.COL_TXN_PAYEE_DEFAULT_CATEGORY_CODE)),
                    "active": active,
                }
            )
        out.sort(key=lambda row: _normalize_search_text(row.get("payeeName")))
        return out

    def list_transactions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return self.db.list_transactions(filters)

    def save_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.save_transaction(payload)

    def _canonicalize_transaction_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._canonicalize_transaction_row(row)

    def _canonicalize_transaction_account_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._canonicalize_transaction_account_row(row)

    def _canonicalize_transaction_category_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._canonicalize_transaction_category_row(row)

    def _canonicalize_transaction_business_unit_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._canonicalize_transaction_business_unit_row(row)

    def _canonicalize_transaction_payee_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._canonicalize_transaction_payee_row(row)

    def _txn_scope_match(self, source_scope: str, expected: str) -> bool:
        return self.db._txn_scope_match(source_scope, expected)

    def _normalize_transaction_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db._normalize_transaction_payload(payload)

    def _validate_transaction_status_transition(
        self,
        old_status: str,
        new_status: str,
        has_existing: bool,
    ) -> None:
        return self.db._validate_transaction_status_transition(old_status, new_status, has_existing)

    def _find_transaction_row(self, transaction_key: str) -> Optional[Dict[str, Any]]:
        return self.db._find_transaction_row(transaction_key)

    def _transaction_category_lookup_maps(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        return self.db._transaction_category_lookup_maps()

    def list_billing_entities(self) -> List[Dict[str, Any]]:
        return self.db.list_billing_entities()

    def get_billing_entity(self, biller_code: str) -> Optional[Dict[str, Any]]:
        return self.db.get_billing_entity(biller_code)

    def save_billing_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.save_billing_entity(payload)

    def list_shareholder_loan_entries(self, biller_entity: str = "PC") -> List[Dict[str, Any]]:
        return self.db.list_shareholder_loan_entries(biller_entity)

    def append_shareholder_loan_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.append_shareholder_loan_entry(payload)

    def list_cca_assets(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_cca_assets(biller_entity)

    def save_cca_asset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.save_cca_asset(payload)

    def record_equipment_ucc_rollover(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.record_equipment_ucc_rollover(payload)

    def list_hst_log(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_hst_log(biller_entity)

    def save_hst_filing_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.db.save_hst_filing_record(payload)

    def list_invoices(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_invoices(biller_entity)

    def list_disbursements(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_disbursements(biller_entity)

    def list_receivables(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_receivables(biller_entity)

    def list_ap_bills(self, biller_entity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_ap_bills(biller_entity)


