from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from repositories.excel_repo import ExcelRepo
from repositories.finance_repo import FinanceRepo
from services.paths import AppPaths
from services.quick_expense_session import (
    SessionTracker,
    format_old_school_session_report,
    parse_client_device,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Hard Privacy & Account Firewall Definitions
# ============================================================================

# Accounts that Deborah MUST NEVER see or query under any circumstances:
DEBORAH_RESTRICTED_ACCOUNT_CODES = frozenset(
    {
        "KOHO",
        "WEALTHSIMPLE",
        "EQ_ACCOUNT",
        "EQ_CARD",
        "CIBC_LOC",
        "CORY_PERSONAL",
        "SHAREHOLDER_LOAN",
        "AP_PAYABLE",
    }
)

DEBORAH_RESTRICTED_TEXT_TOKENS = (
    "koho",
    "wealthsimple",
    "eq account",
    "eq acccount",
    "eq card",
    "eq bank",
    "cibc loc",
    "line of credit",
)

# Friendly visual metadata for accounts
ACCOUNT_UI_META: Dict[str, Dict[str, Any]] = {
    "SIMPLII_VISA": {
        "icon": "💳",
        "displayName": "Simplii Visa",
        "shortName": "Simplii Visa",
        "group": "Credit Cards",
        "sortOrder": 10,
        "isCreditCard": True,
    },
    "TRIANGLE_MASTERCARD": {
        "icon": "💳",
        "displayName": "Triangle Mastercard",
        "shortName": "Triangle MC",
        "group": "Credit Cards",
        "sortOrder": 10,
        "isCreditCard": True,
    },
    "CIBC_CHEQUING": {
        "icon": "🏦",
        "displayName": "CIBC Personal Chequing",
        "shortName": "CIBC Personal Cheq",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "isBank": True,
    },
    "CIBC_SAVINGS": {
        "icon": "🏛️",
        "displayName": "CIBC PC Savings",
        "shortName": "CIBC PC Savings",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "isBank": True,
        "isCorpGeneral": True,
    },
    "SIMPLII_CHEQUING": {
        "icon": "🏦",
        "displayName": "Simplii Chequing",
        "shortName": "Simplii Chequing",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "isBank": True,
    },
    "CIBC_PC_GENERAL": {
        "icon": "🏛️",
        "displayName": "CIBC PC General",
        "shortName": "CIBC PC General",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "isBank": True,
        "isCorpGeneral": True,
    },
    "CIBC_PC_TRUST": {
        "icon": "⚖️",
        "displayName": "CIBC PC Trust (Client Money In / Out to General Only)",
        "shortName": "CIBC PC Trust",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "isTrust": True,
        "allowedModes": ["Income", "Transfer"],
        "allowedTransferTargets": ["CIBC_PC_GENERAL"],
        "allowedStreams": ["CORY_PC"],
    },
    "CASH_DEBORAH": {
        "icon": "💵",
        "displayName": "Cash - Deborah",
        "shortName": "Cash (Deborah)",
        "group": "Cash",
        "sortOrder": 30,
        "isCash": True,
    },
    "CASH_CORY": {
        "icon": "💵",
        "displayName": "Cash - Cory",
        "shortName": "Cash (Cory)",
        "group": "Cash",
        "sortOrder": 30,
        "isCash": True,
    },
    "CIBC_MORTGAGE": {
        "icon": "🏠",
        "displayName": "CIBC Mortgage Account",
        "shortName": "CIBC Mortgage",
        "group": "Mortgages",
        "sortOrder": 40,
        "isDebt": True,
    },
    "HOME_TRUST_MORTGAGE": {
        "icon": "🏡",
        "displayName": "Home Trust Mortgage Account",
        "shortName": "Home Trust Mortgage",
        "group": "Mortgages",
        "sortOrder": 40,
        "isDebt": True,
    },
    # Cory-Only Accounts (Filtered out on backend for Deborah):
    "KOHO": {
        "icon": "💳",
        "displayName": "Koho",
        "shortName": "Koho",
        "group": "Credit Cards",
        "sortOrder": 10,
        "coryOnly": True,
        "isCreditCard": True,
    },
    "EQ_ACCOUNT": {
        "icon": "🏦",
        "displayName": "EQ Account",
        "shortName": "EQ Account",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "coryOnly": True,
        "isBank": True,
    },
    "EQ_CARD": {
        "icon": "💳",
        "displayName": "EQ Card",
        "shortName": "EQ Card",
        "group": "Credit Cards",
        "sortOrder": 10,
        "coryOnly": True,
        "isCreditCard": True,
    },
    "WEALTHSIMPLE": {
        "icon": "📈",
        "displayName": "Wealthsimple",
        "shortName": "Wealthsimple",
        "group": "Bank Accounts",
        "sortOrder": 20,
        "coryOnly": True,
        "isBank": True,
    },
    "CIBC_LOC": {
        "icon": "🏦",
        "displayName": "CIBC Line of Credit (LOC)",
        "shortName": "CIBC LOC",
        "group": "Mortgages",
        "sortOrder": 40,
        "coryOnly": True,
        "isDebt": True,
    },
    "CORY_PERSONAL": {
        "icon": "💳",
        "displayName": "Cory Personal Card / Account",
        "shortName": "Cory Personal",
        "group": "Credit Cards",
        "sortOrder": 10,
        "coryOnly": True,
        "isCreditCard": True,
    },
    "SHAREHOLDER_LOAN": {
        "icon": "📒",
        "displayName": "Due to Shareholder (GIFI 2781)",
        "shortName": "Shareholder Loan",
        "group": "Mortgages",
        "sortOrder": 40,
        "coryOnly": True,
        "isDebt": True,
    },
}

# "Who is this for?" Streams
STREAM_OPTIONS: List[Dict[str, Any]] = [
    {
        "streamId": "FAMILY",
        "label": "Family & Home",
        "shortLabel": "Family",
        "icon": "🏠",
        "color": "#2563EB",
        "class": "Family",
        "businessUnit": "",
        "billerEntity": "FAMILY",
        "defaultMember": "Joint",
        "description": "Household groceries, dining, kids, mortgages, medical, home & personal",
    },
    {
        "streamId": "DEBORAH_OT_PRIVATE",
        "label": "Deborah OT — Private",
        "shortLabel": "OT - Private",
        "icon": "🩺",
        "color": "#0D9488",
        "class": "Business",
        "businessUnit": "Deborah OT - Private",
        "billerEntity": "DEBORAH_OT",
        "defaultMember": "Deborah",
        "description": "Deborah's private occupational therapy practice",
    },
    {
        "streamId": "DEBORAH_OT_VHA",
        "label": "Deborah OT — VHA",
        "shortLabel": "OT - VHA",
        "icon": "🏥",
        "color": "#0891B2",
        "class": "Business",
        "businessUnit": "Deborah OT - VHA",
        "billerEntity": "DEBORAH_OT",
        "defaultMember": "Deborah",
        "description": "Deborah's VHA occupational therapy stream",
    },
    {
        "streamId": "CORY_SOLE_PROP",
        "label": "Cory — Sole Practice",
        "shortLabel": "Cory Sole Prop",
        "icon": "⚖️",
        "color": "#7C3AED",
        "class": "Business",
        "businessUnit": "Legal Practice",
        "billerEntity": "SOLE_PROP",
        "defaultMember": "Cory",
        "description": "Cory Schneider Law Office (Sole Proprietorship)",
    },
    {
        "streamId": "CORY_PC",
        "label": "Cory — Professional Corp (PC)",
        "shortLabel": "Cory PC",
        "icon": "🏛️",
        "color": "#B45309",
        "class": "Business",
        "businessUnit": "Legal Practice",
        "billerEntity": "PC",
        "defaultMember": "Cory",
        "description": "Cory Schneider Law Professional Corporation",
    },
]

# Category Icons & Friendly Groups
CATEGORY_ICONS_AND_GROUPS: Dict[str, Tuple[str, str, bool]] = {
    # (Icon, FriendlyGroup, DefaultHas13PctHST)
    "EXP_GROCERIES": ("🛒", "🛒 Food & Groceries", False),
    "EXP_DINING": ("🍽️", "🛒 Food & Groceries", True),
    "EXP_COFFEE_SNACKS": ("☕", "🛒 Food & Groceries", True),
    "EXP_HOUSEHOLD_SUPPLIES": ("🧻", "🏠 Home & Mortgages", True),
    "EXP_MORTGAGE_CIBC": ("🏠", "🏠 Home & Mortgages", False),
    "EXP_MORTGAGE_HOME_TRUST": ("🏡", "🏠 Home & Mortgages", False),
    "EXP_MORTGAGE_INTEREST": ("🏦", "🏠 Home & Mortgages", False),
    "EXP_RENT": ("🏠", "🏠 Home & Mortgages", False),
    "EXP_PROPERTY_TAX": ("🏛️", "🏠 Home & Mortgages", False),
    "EXP_CONDO_FEES": ("🏢", "🏠 Home & Mortgages", False),
    "EXP_HOME_INSURANCE": ("🛡️", "🏠 Home & Mortgages", False),
    "EXP_RENTERS_INSURANCE": ("🛡️", "🏠 Home & Mortgages", False),
    "EXP_HOME_REPAIRS": ("🔨", "🏠 Home & Mortgages", True),
    "EXP_HOME_MAINTENANCE": ("🧹", "🏠 Home & Mortgages", True),
    "EXP_ELECTRICITY": ("💡", "💡 Utilities & Phone", True),
    "EXP_NATURAL_GAS": ("🔥", "💡 Utilities & Phone", True),
    "EXP_WATER": ("🚿", "💡 Utilities & Phone", False),
    "EXP_INTERNET_HOME": ("🌐", "💡 Utilities & Phone", True),
    "EXP_MOBILE_PHONE": ("📱", "💡 Utilities & Phone", True),
    "EXP_STREAMING_SERVICES": ("📺", "💡 Utilities & Phone", True),
    "EXP_TRASH_RECYCLING": ("♻️", "💡 Utilities & Phone", False),
    "EXP_CHILDCARE": ("🧸", "🎒 Kids, Family & Pets", False),
    "EXP_SCHOOL_TUITION": ("🎓", "🎒 Kids, Family & Pets", False),
    "EXP_SCHOOL_SUPPLIES": ("✏️", "🎒 Kids, Family & Pets", True),
    "EXP_KIDS_ACTIVITIES": ("⚽", "🎒 Kids, Family & Pets", True),
    "EXP_ALLOWANCE": ("🪙", "🎒 Kids, Family & Pets", False),
    "EXP_PETS": ("🐾", "🎒 Kids, Family & Pets", True),
    "EXP_CLOTHING": ("👕", "🛍️ Personal & Giving", True),
    "EXP_PERSONAL_CARE": ("💇", "🛍️ Personal & Giving", True),
    "EXP_FITNESS": ("🏋️", "🛍️ Personal & Giving", True),
    "EXP_GIFTS_GIVEN": ("🎁", "🛍️ Personal & Giving", True),
    "EXP_DONATIONS": ("❤️", "🛍️ Personal & Giving", False),
    "EXP_FUEL": ("⛽", "🚗 Car, Gas & Parking", True),
    "EXP_PARKING": ("🅿️", "🚗 Car, Gas & Parking", True),
    "EXP_PUBLIC_TRANSIT": ("🚇", "🚗 Car, Gas & Parking", False),
    "EXP_RIDESHARE_TAXI": ("🚕", "🚗 Car, Gas & Parking", True),
    "EXP_TOLLS": ("🛣️", "🚗 Car, Gas & Parking", True),
    "EXP_AUTO_INSURANCE": ("🛡️", "🚗 Car, Gas & Parking", False),
    "EXP_AUTO_REPAIRS": ("🔧", "🚗 Car, Gas & Parking", True),
    "EXP_AUTO_MAINTENANCE": ("🛞", "🚗 Car, Gas & Parking", True),
    "EXP_AUTO_REGISTRATION": ("🪪", "🚗 Car, Gas & Parking", False),
    "EXP_MEDICAL": ("🩺", "🦷 Medical, Dental & Health", False),
    "EXP_DENTAL": ("🦷", "🦷 Medical, Dental & Health", False),
    "EXP_VISION": ("👓", "🦷 Medical, Dental & Health", False),
    "EXP_PHARMACY": ("💊", "🦷 Medical, Dental & Health", False),
    "EXP_THERAPY": ("🧠", "🦷 Medical, Dental & Health", False),
    "EXP_TRAVEL_AIRFARE": ("✈️", "✈️ Travel & Hotels", True),
    "EXP_TRAVEL_LODGING": ("🏨", "✈️ Travel & Hotels", True),
    "EXP_TRAVEL_MEALS": ("🍴", "✈️ Travel & Hotels", True),
    "EXP_TRAVEL_MISC": ("🧳", "✈️ Travel & Hotels", True),
    "EXP_CLINICAL_SUPPLIES": ("🩺", "💼 Business & Practice", True),
    "EXP_OFFICE_SUPPLIES": ("📎", "💼 Business & Practice", True),
    "EXP_OFFICE_EQUIPMENT": ("💻", "💼 Business & Practice", True),
    "EXP_SOFTWARE_SUBSCRIPTIONS": ("🖥️", "💼 Business & Practice", True),
    "EXP_CLOUD_SERVICES": ("☁️", "💼 Business & Practice", True),
    "EXP_TELECOM_BUSINESS": ("📞", "💼 Business & Practice", True),
    "EXP_INTERNET_BUSINESS": ("🌐", "💼 Business & Practice", True),
    "EXP_PROFESSIONAL_DUES": ("🪪", "💼 Business & Practice", True),
    "EXP_LICENSES_PERMITS": ("📜", "💼 Business & Practice", False),
    "EXP_CPD_TRAINING": ("📚", "💼 Business & Practice", True),
    "EXP_BUSINESS_INSURANCE": ("🛡️", "💼 Business & Practice", False),
    "EXP_ACCOUNTING_FEES": ("🧮", "💼 Business & Practice", True),
    "EXP_LEGAL_FEES": ("⚖️", "💼 Business & Practice", True),
    "EXP_CONSULTING_FEES": ("🤝", "💼 Business & Practice", True),
    "EXP_MARKETING_ADS": ("📣", "💼 Business & Practice", True),
    "EXP_WEBSITE_HOSTING": ("🌐", "💼 Business & Practice", True),
    "EXP_POSTAGE_COURIER": ("📦", "💼 Business & Practice", True),
    "EXP_PRINTING_COPYING": ("🖨️", "💼 Business & Practice", True),
    "EXP_RESEARCH_DATABASES": ("🔎", "💼 Business & Practice", True),
    "EXP_GENERAL_OFFICE_OVERHEAD": ("🏢", "💼 Business & Practice", True),
    "EXP_CONTRACTOR_PAYMENTS": ("👷", "💼 Business & Practice", True),
    "EXP_PAYROLL": ("💵", "💼 Business & Practice", False),
    "EXP_FILING_FEES": ("🏛️", "⚖️ Legal Client Disbursements", False),
    "EXP_PROCESS_SERVER": ("📨", "⚖️ Legal Client Disbursements", True),
    "EXP_EXPERT_WITNESS": ("🎓", "⚖️ Legal Client Disbursements", True),
    "EXP_MEDIATION_ARBITRATION": ("🤝", "⚖️ Legal Client Disbursements", True),
    "EXP_TRANSCRIPTS_RECORDS": ("📄", "⚖️ Legal Client Disbursements", True),
    "EXP_CLIENT_TRAVEL_DISBURSEMENT": ("🚖", "⚖️ Legal Client Disbursements", True),
    "EXP_CLIENT_MEALS_DISBURSEMENT": ("🍽️", "⚖️ Legal Client Disbursements", True),
    "EXP_COURT_REPORTER": ("⌨️", "⚖️ Legal Client Disbursements", True),
    "EXP_BANK_FEES": ("🏦", "🏦 Banking & Taxes", False),
    "EXP_INTEREST_CHARGES": ("📈", "🏦 Banking & Taxes", False),
    "EXP_INCOME_TAX_PAID": ("🇨🇦", "🏦 Banking & Taxes", False),
    "EXP_GST_HST_REMITTANCE": ("🧾", "🏦 Banking & Taxes", False),
    "EXP_PENALTIES_FINES": ("⚠️", "🏦 Banking & Taxes", False),
    "EXP_OTHER": ("📌", "📌 Other", True),
    # Income
    "INC_OT_PRIVATE_BILLINGS": ("🩺", "💰 Business & Practice Income", False),
    "INC_OT_VHA_BILLINGS": ("🏥", "💰 Business & Practice Income", False),
    "INC_LEGAL_FEES": ("⚖️", "💰 Business & Practice Income", True),
    "INC_RETAINER_RECEIPTS": ("⚖️", "💰 Client Trust Retainers", False),
    "INC_CONTRACT_REVENUE": ("💼", "💰 Business & Practice Income", True),
    "INC_SALARY": ("💵", "🏠 Family & Personal Income", False),
    "INC_BONUS": ("🎉", "🏠 Family & Personal Income", False),
    "INC_GOVERNMENT_BENEFIT": ("🇨🇦", "🏠 Family & Personal Income", False),
    "INC_CHILD_BENEFIT": ("👶", "🏠 Family & Personal Income", False),
    "INC_GST_HST_CREDIT": ("🧾", "🏠 Family & Personal Income", False),
    "INC_TAX_REFUND": ("🇨🇦", "🏠 Family & Personal Income", False),
    "INC_REIMBURSEMENT_NON_TAXABLE": ("↩️", "🏠 Family & Personal Income", False),
    "INC_CASHBACK_REBATE": ("💳", "🏠 Family & Personal Income", False),
    "INC_GIFT_RECEIVED": ("🎁", "🏠 Family & Personal Income", False),
    "INC_INTEREST_BANK": ("🏦", "🏠 Family & Personal Income", False),
    "INC_INTEREST_INVESTMENT": ("📈", "🏠 Family & Personal Income", False),
    "INC_DIVIDENDS": ("📈", "🏠 Family & Personal Income", False),
    "INC_INSURANCE_PROCEEDS": ("🛡️", "🏠 Family & Personal Income", False),
    "INC_OTHER": ("💰", "🏠 Family & Personal Income", False),
    # Debt & Transfers
    "DEBT_MORTGAGE_PRINCIPAL_CIBC": ("🏠", "🏠 Mortgage & Loan Principal", False),
    "DEBT_MORTGAGE_PRINCIPAL_HOME_TRUST": ("🏡", "🏠 Mortgage & Loan Principal", False),
    "DEBT_CREDIT_CARD_PRINCIPAL_SIMPLII_VISA": ("💳", "💳 Credit Card Payments", False),
    "DEBT_CREDIT_CARD_PRINCIPAL_TRIANGLE": ("💳", "💳 Credit Card Payments", False),
    "XFER_INTERNAL_CARD_PAYMENT": ("💳", "💳 Credit Card Payments", False),
    "XFER_INTERNAL_CHEQUING_SAVINGS": ("🔄", "🔄 Bank Transfers", False),
    "XFER_INTERNAL_MORTGAGE_PAYMENT": ("🏠", "🔄 Bank Transfers", False),
    "CORP_SHL_REPAYMENT": ("🏛️", "🔄 Bank Transfers", False),
    "XFER_OTHER_INTERNAL": ("🔄", "🔄 Bank Transfers", False),
}


class QuickExpenseService:
    """Storage-agnostic domain service for the CSPM Quick Expense Mini-App
    (iPhone/Android Mobile PWA, Chromebook PWA, Rust Standalone Desktop App,
    and Embedded CSPM Launcher).
    """

    def __init__(self, paths: Optional[AppPaths] = None, repo: Optional[ExcelRepo] = None):
        if paths is None:
            default_paths = AppPaths(root=AppPaths.project_root())
            if repo is None and not os.environ.get("PYTEST_CURRENT_TEST", "").strip():
                try:
                    settings_file = default_paths.user_settings_path()
                    if settings_file.is_file():
                        raw_settings = json.loads(settings_file.read_text(encoding="utf-8"))
                        m_dir_str = str(raw_settings.get("masterDataDir") or "").strip()
                        l_dir_str = str(raw_settings.get("localDataDir") or "").strip()
                        if m_dir_str:
                            m_cand = Path(os.path.expandvars(m_dir_str)).expanduser()
                            if m_cand.is_dir():
                                default_paths.override_master_dir = m_cand
                        if l_dir_str:
                            l_cand = Path(os.path.expandvars(l_dir_str)).expanduser()
                            if l_cand.is_dir() and (l_cand / "CSPM.xlsm").is_file():
                                default_paths.override_data_dir = l_cand
                    if default_paths.override_master_dir is None:
                        for od in sorted(Path.home().glob("OneDrive*")):
                            cand = od / "CSPM_Shared_Data"
                            if cand.is_dir() and ((cand / "cspm.db").is_file() or (cand / "CSPM.xlsm").is_file()):
                                default_paths.override_master_dir = cand
                                break
                    if default_paths.override_data_dir is None and default_paths.override_master_dir is not None:
                        if (default_paths.override_master_dir / "CSPM.xlsm").is_file():
                            default_paths.override_data_dir = default_paths.override_master_dir
                except Exception:
                    pass
            self.paths = default_paths
        else:
            self.paths = paths
        self.repo = repo or ExcelRepo(self.paths)
        self.finance_repo = FinanceRepo(self.repo)
        self.session_tracker = SessionTracker(self.paths)
        self._lock = threading.RLock()
        self._cached_raw_accounts: Optional[List[Dict[str, Any]]] = None
        self._cached_raw_categories: Optional[List[Dict[str, Any]]] = None
        self._cached_ar_snapshot: Optional[List[Dict[str, Any]]] = None

    def _is_isolated_test(self) -> bool:
        if os.environ.get("PYTEST_CURRENT_TEST", "").strip():
            return True
        if self.paths._is_isolated_test_root():
            return True
        wb_path_str = str(getattr(self.repo, "workbook_path", "") or "").lower()
        return "pytest" in wb_path_str or "temp" in wb_path_str or "tmp" in wb_path_str

    # ------------------------------------------------------------------
    # OneDrive Conflict-Free Sync Queue Helpers
    # ------------------------------------------------------------------
    def _sync_queue_paths(self) -> List[Path]:
        """Return both the local data_dir sync queue and the OneDrive shared_data_dir
        QuickExpense_Sync inbox so entries saved while CSPM.xlsm is busy or from
        remote sessions are persisted safely in OneDrive without Excel file conflicts."""
        candidates: List[Path] = []
        try:
            local_dir = self.paths.data_dir() / "QuickExpense_Sync"
            local_dir.mkdir(parents=True, exist_ok=True)
            candidates.append(local_dir / "inbox.json")
        except Exception:
            pass
        try:
            master_dir = self.paths.master_data_dir()
            if master_dir and master_dir.exists():
                shared_dir = master_dir / "QuickExpense_Sync"
                shared_dir.mkdir(parents=True, exist_ok=True)
                shared_inbox = shared_dir / "inbox.json"
                if shared_inbox not in candidates:
                    candidates.append(shared_inbox)
        except Exception:
            pass
        return candidates

    def _read_queued_entries(self) -> List[Dict[str, Any]]:
        by_id: Dict[str, Dict[str, Any]] = {}
        for qpath in self._sync_queue_paths():
            if not qpath.exists():
                continue
            try:
                raw = json.loads(qpath.read_text(encoding="utf-8"))
                items = raw.get("items", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
                for item in items:
                    if isinstance(item, dict) and item.get("transactionId"):
                        by_id[str(item["transactionId"])] = item
            except Exception as exc:
                logger.warning("Could not read QuickExpense inbox %s: %s", qpath, exc)
        return list(by_id.values())

    def _write_queued_entries(self, items: List[Dict[str, Any]]) -> None:
        payload = {
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(items),
            "items": items,
        }
        serialized = json.dumps(payload, indent=2)
        for qpath in self._sync_queue_paths():
            try:
                qpath.parent.mkdir(parents=True, exist_ok=True)
                qpath.write_text(serialized, encoding="utf-8")
            except Exception as exc:
                logger.warning("Could not write QuickExpense inbox %s: %s", qpath, exc)

    def flush_pending_inbox(self) -> Dict[str, Any]:
        """Attempt to merge any waiting OneDrive QuickExpense_Sync/inbox.json entries
        into CSPM.xlsm whenever the workbook is unlocked."""
        queued = self._read_queued_entries()
        if not queued:
            return {"ok": True, "flushedCount": 0, "remainingCount": 0}
        remaining: List[Dict[str, Any]] = []
        flushed = 0
        for item in queued:
            try:
                res = self.finance_repo.save_transaction(item)
                if res.get("ok"):
                    flushed += 1
                else:
                    remaining.append(item)
            except Exception:
                remaining.append(item)
        if flushed > 0:
            self._write_queued_entries(remaining)
        return {"ok": True, "flushedCount": flushed, "remainingCount": len(remaining)}

    # ------------------------------------------------------------------
    # 1. Authentication & User Profiles
    # ------------------------------------------------------------------
    def authenticate(self, username: str, pin: str = "") -> Dict[str, Any]:
        user_key = str(username or "").strip().lower()
        entered_pin = str(pin or "").strip()

        if user_key in ("deborah", "deb"):
            expected_deb_pin = os.environ.get("CSPM_DEBORAH_PIN", "4867").strip()
            if entered_pin and entered_pin != expected_deb_pin:
                return {"ok": False, "message": "Incorrect PIN for Deborah."}
            if not entered_pin and expected_deb_pin:
                return {"ok": False, "requiresPin": True, "message": "Please enter Deborah's PIN."}
            try:
                self.session_tracker.record_event("deborah", "AUTH_LOGIN", "Operator authenticated via PIN (Deborah)")
            except Exception:
                pass
            return {
                "ok": True,
                "user": {
                    "userId": "deborah",
                    "displayName": "Deborah",
                    "icon": "👩‍⚕️",
                    "role": "Family, Deborah OT & Legal Practice Entry",
                    "isCory": False,
                    "hasDocketAccess": False,
                },
            }

        if user_key == "cory":
            expected_cory_pin = os.environ.get("CSPM_CORY_PIN", "1977").strip()
            if entered_pin and entered_pin != expected_cory_pin:
                return {"ok": False, "message": "Incorrect PIN for Cory."}
            if not entered_pin and expected_cory_pin:
                return {"ok": False, "requiresPin": True, "message": "Please enter Cory's PIN."}
            try:
                self.session_tracker.record_event("cory", "AUTH_LOGIN", "Operator authenticated via PIN (Cory)")
            except Exception:
                pass
            return {
                "ok": True,
                "user": {
                    "userId": "cory",
                    "displayName": "Cory",
                    "icon": "⚖️",
                    "role": "Full Access (All Accounts & Entities)",
                    "isCory": True,
                    "hasDocketAccess": True,
                },
            }

        return {"ok": False, "message": "Please choose Deborah or Cory to sign in."}

    # ------------------------------------------------------------------
    # 2. Hard Privacy Firewall Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_cory(user_id: str) -> bool:
        return str(user_id or "").strip().lower() == "cory"

    @classmethod
    def _has_docket_access(cls, user_id: str) -> bool:
        return cls._is_cory(user_id)

    def _is_account_visible_to_user(self, account_code: str, user_id: str) -> bool:
        code = str(account_code or "").strip().upper()
        if not code:
            return False
        if code in {"AP_PAYABLE", "PC_OPERATING"}:
            return False
        if self._is_cory(user_id):
            return True
        if code in DEBORAH_RESTRICTED_ACCOUNT_CODES:
            return False
        meta = ACCOUNT_UI_META.get(code, {})
        if meta.get("coryOnly"):
            return False
        return True

    def _is_transaction_visible_to_user(self, txn: Dict[str, Any], user_id: str) -> bool:
        """Deborah sees entries she created OR entries Cory created,
        ONLY IF they relate exclusively to non-restricted accounts/entities."""
        if self._is_cory(user_id):
            return True

        from_acct = str(txn.get("fromAccount") or "").strip().upper()
        to_acct = str(txn.get("toAccount") or "").strip().upper()
        if from_acct in DEBORAH_RESTRICTED_ACCOUNT_CODES:
            return False
        if to_acct in DEBORAH_RESTRICTED_ACCOUNT_CODES:
            return False

        combined_text = " ".join(
            str(txn.get(k) or "")
            for k in ("fromAccount", "toAccount", "payee", "expenseDetails", "notes", "categoryCode", "categoryName")
        ).lower()
        for restricted_tok in DEBORAH_RESTRICTED_TEXT_TOKENS:
            if restricted_tok in combined_text:
                return False

        return True

    # ------------------------------------------------------------------
    # 3. Bootstrap Payload (Accounts, Categories, Streams, Payees)
    # ------------------------------------------------------------------
    def get_bootstrap_data(self, user_id: str = "deborah") -> Dict[str, Any]:
        with self._lock:
            uid = "cory" if self._is_cory(user_id) else "deborah"
            if self._is_isolated_test():
                self.flush_pending_inbox()
            elif self._read_queued_entries():
                threading.Thread(
                    target=self._background_flush_inbox_safe,
                    name="QuickExpenseBootstrapFlush",
                    daemon=True,
                ).start()

            # 1. Filtered Accounts (cached in memory for instant mobile response)
            if self._cached_raw_accounts is None:
                self._cached_raw_accounts = self.finance_repo.list_transaction_accounts(include_inactive=False)
            raw_accounts = self._cached_raw_accounts
            accounts: List[Dict[str, Any]] = []
            for acc in raw_accounts:
                code = str(acc.get("accountCode") or "").strip().upper()
                if not self._is_account_visible_to_user(code, uid):
                    continue
                meta = ACCOUNT_UI_META.get(code, {})
                display_name = meta.get("displayName") or acc.get("accountName") or code
                icon = meta.get("icon") or "🏦"
                accounts.append(
                    {
                        "accountCode": code,
                        "accountName": display_name,
                        "shortName": meta.get("shortName") or display_name,
                        "labelWithIcon": f"{icon} {display_name}",
                        "icon": icon,
                        "accountKind": acc.get("accountKind") or "chequing",
                        "owner": acc.get("owner") or "Joint",
                        "group": meta.get("group") or "Accounts",
                        "sortOrder": int(meta.get("sortOrder", 99)),
                        "isCreditCard": bool(meta.get("isCreditCard") or acc.get("accountKind") == "credit-card"),
                        "isBank": bool(meta.get("isBank") or acc.get("accountKind") in ("chequing", "savings")),
                        "isCash": bool(meta.get("isCash") or acc.get("accountKind") == "cash"),
                        "isDebt": bool(meta.get("isDebt") or acc.get("accountKind") in ("mortgage", "loc", "loan")),
                        "isTrust": bool(meta.get("isTrust") or acc.get("accountKind") == "trust"),
                        "allowedModes": meta.get("allowedModes", ["Expense", "Income", "Pay Credit Card", "Transfer"]),
                        "allowedTransferTargets": meta.get("allowedTransferTargets", []),
                        "allowedStreams": meta.get("allowedStreams", []),
                    }
                )
            accounts.sort(key=lambda a: (a["sortOrder"], str(a["accountName"]).lower()))

            # 2. Enriched Categories (cached in memory for instant mobile response)
            if self._cached_raw_categories is None:
                self._cached_raw_categories = self.finance_repo.list_transaction_categories(include_inactive=False)
            raw_categories = self._cached_raw_categories
        categories: List[Dict[str, Any]] = []
        for cat in raw_categories:
            code = str(cat.get("categoryCode") or "").strip().upper()
            if uid != "cory" and code in {"DEBT_LOC_PRINCIPAL_CIBC"}:
                continue
            icon, group_label, default_hst = CATEGORY_ICONS_AND_GROUPS.get(
                code,
                (
                    "💰" if cat.get("type") == "Income" else ("🔄" if "Transfer" in str(cat.get("type")) else "🛒"),
                    "📌 Other Categories",
                    str(cat.get("taxFlagDefault") or "") in ("HST - Biz", "Business Deductible"),
                ),
            )
            name = str(cat.get("categoryName") or code)
            categories.append(
                {
                    "categoryCode": code,
                    "categoryName": name,
                    "labelWithIcon": f"{icon} {name}",
                    "icon": icon,
                    "groupLabel": group_label,
                    "type": cat.get("type") or "Expense",
                    "classScope": cat.get("classScope") or "Both",
                    "taxFlagDefault": cat.get("taxFlagDefault") or "None",
                    "defaultHasHst": bool(default_hst),
                    "medicalEligible": bool(cat.get("medicalEligible")),
                    "deductibleEligible": bool(cat.get("deductibleEligible")),
                    "businessDeductibleEligible": bool(cat.get("businessDeductibleEligible")),
                    "sortOrder": int(cat.get("sortOrder") or 500),
                }
            )
        categories.sort(key=lambda c: (c["sortOrder"], c["categoryName"]))

        # 3. Recent Payees & Auto-Category Memory (from visible transactions)
        visible_txns = self.list_entries(user_id=uid, period="all")
        payee_memory: Dict[str, Dict[str, str]] = {}
        for t in visible_txns:
            p_name = str(t.get("payee") or "").strip()
            if p_name and p_name.lower() not in payee_memory:
                payee_memory[p_name.lower()] = {
                    "payee": p_name,
                    "categoryCode": str(t.get("categoryCode") or ""),
                    "fromAccount": str(t.get("fromAccount") or ""),
                    "streamId": str(t.get("streamId") or ""),
                }

        today_entries = [t for t in visible_txns if t.get("txnDate") == date.today().isoformat()]
        today_total = round(sum(float(t.get("amount") or 0.0) for t in today_entries), 2)

        return {
            "ok": True,
            "userId": uid,
            "todayIso": date.today().isoformat(),
            "streams": STREAM_OPTIONS,
            "members": ["Joint", "Deborah", "Cory", "Alexa", "Emma", "Maya"],
            "accounts": accounts,
            "categories": categories,
            "payeeMemory": list(payee_memory.values())[:150],
            "todaySummary": {
                "count": len(today_entries),
                "totalAmount": today_total,
                "totalFormatted": f"${today_total:,.2f}",
            },
        }

    # ------------------------------------------------------------------
    # 4. Stream <-> CSPM Schema Mapping
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_stream_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
        cls = str(row.get("class") or "Family").strip()
        bu = str(row.get("businessUnit") or "").strip()
        biller = str(row.get("billerEntity") or "").strip().upper()

        if cls.lower() == "family":
            return STREAM_OPTIONS[0]
        if "vha" in bu.lower():
            return STREAM_OPTIONS[2]
        if "deborah" in bu.lower() or biller == "DEBORAH_OT":
            return STREAM_OPTIONS[1]
        if biller == "PC":
            return STREAM_OPTIONS[4]
        return STREAM_OPTIONS[3]

    @staticmethod
    def _resolve_mode_from_row(row: Dict[str, Any]) -> str:
        t_type = str(row.get("type") or "Expense").strip()
        cat_code = str(row.get("categoryCode") or "").strip().upper()
        to_acct = str(row.get("toAccount") or "").strip().upper()
        if t_type == "Income":
            return "Income"
        if (
            cat_code in {"XFER_INTERNAL_CARD_PAYMENT", "DEBT_CREDIT_CARD_PRINCIPAL_SIMPLII_VISA", "DEBT_CREDIT_CARD_PRINCIPAL_TRIANGLE"}
            or to_acct in {"SIMPLII_VISA", "TRIANGLE_MASTERCARD", "CORY_PERSONAL"}
        ):
            return "Pay Credit Card"
        if t_type in ("Transfer", "Debt Repayment"):
            return "Transfer"
        return "Expense"

    # ------------------------------------------------------------------
    # 5. Save / Update Entry (with CIBC PC Trust, Firewall & OneDrive Queue)
    # ------------------------------------------------------------------
    def save_entry(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        data = dict(payload or {})

        mode = str(data.get("mode") or "Expense").strip()
        stream_id = str(data.get("streamId") or "FAMILY").strip().upper()
        stream = next((s for s in STREAM_OPTIONS if s["streamId"] == stream_id), STREAM_OPTIONS[0])

        txn_date = str(data.get("txnDate") or data.get("date") or date.today().isoformat()).strip()
        from_account = str(data.get("fromAccount") or "").strip().upper()
        to_account = str(data.get("toAccount") or "").strip().upper()

        # 1. Enforce Deborah Account Privacy Firewall
        if uid != "cory":
            if from_account in DEBORAH_RESTRICTED_ACCOUNT_CODES or to_account in DEBORAH_RESTRICTED_ACCOUNT_CODES:
                return {"ok": False, "message": "Selected account is not available for this user profile."}

        # 2. Enforce CIBC PC Trust Account Guardrail (Both Deborah & Cory)
        if from_account == "CIBC_PC_TRUST" or to_account == "CIBC_PC_TRUST":
            if mode in ("Expense", "Pay Credit Card"):
                return {
                    "ok": False,
                    "message": (
                        "⚖️ CIBC PC Trust Guardrail: The Trust Account cannot be used to pay expenses or credit cards. "
                        "It can only show money in from clients (Income) or money out to CIBC PC General (Transfer)."
                    ),
                }
            if mode == "Income":
                deposit_target = to_account or from_account
                if deposit_target != "CIBC_PC_TRUST" or stream_id != "CORY_PC":
                    return {
                        "ok": False,
                        "message": (
                            "⚖️ CIBC PC Trust Guardrail: Trust deposits must be for 'Cory — Professional Corp (PC)' "
                            "(money in from clients)."
                        ),
                    }
            elif mode == "Transfer":
                if from_account != "CIBC_PC_TRUST" or to_account not in {"CIBC_PC_GENERAL", "PC_OPERATING"}:
                    return {
                        "ok": False,
                        "message": (
                            "⚖️ CIBC PC Trust Guardrail: Money out of CIBC PC Trust can only be transferred "
                            "to CIBC PC General."
                        ),
                    }

        # 3. Map Friendly Mode to Canonical CSPM Transaction Payload
        try:
            gross_amount = round(float(data.get("amount") or data.get("totalAmount") or 0.0), 2)
        except (TypeError, ValueError):
            return {"ok": False, "message": "Please enter a valid dollar amount greater than $0.00."}
        if gross_amount <= 0:
            return {"ok": False, "message": "Please enter an amount greater than $0.00."}

        try:
            tax_amount = round(float(data.get("taxAmount") or data.get("hstAmount") or 0.0), 2)
        except (TypeError, ValueError):
            tax_amount = 0.0
        if tax_amount < 0:
            tax_amount = 0.0
        if tax_amount > gross_amount:
            return {"ok": False, "message": "HST amount cannot be larger than the Total Paid amount."}

        is_refund = bool(data.get("isRefund", False))
        notes = str(data.get("notes") or "").strip()
        details = str(data.get("expenseDetails") or data.get("description") or notes).strip()
        payee = str(data.get("payee") or "").strip()
        member = str(data.get("member") or stream["defaultMember"]).strip() or "Joint"
        category_code = str(data.get("categoryCode") or "").strip().upper()

        author_tag = f"[Entered by {uid.capitalize()}]"
        stored_notes = notes
        if author_tag.lower() not in stored_notes.lower():
            stored_notes = f"{stored_notes} {author_tag}".strip()

        if mode == "Pay Credit Card":
            if not from_account:
                return {"ok": False, "message": "Please select which Bank Account you paid from."}
            if not to_account:
                return {"ok": False, "message": "Please select which Credit Card you paid off."}
            if from_account == to_account:
                return {"ok": False, "message": "The Bank Account and Credit Card must be different."}
            txn_type = "Transfer"
            category_code = "XFER_INTERNAL_CARD_PAYMENT"
            acct_meta = ACCOUNT_UI_META.get(to_account, {})
            payee = payee or f"Credit Card Payment - {acct_meta.get('displayName', to_account)}"
            details = details or f"Payment to {acct_meta.get('displayName', to_account)}"
            tax_amount = 0.0
            tax_flag = "None"
            txn_class = "Family"
            business_unit = ""
            biller_entity = "FAMILY"

        elif mode == "Transfer":
            if not from_account:
                return {"ok": False, "message": "Please select the account money moved FROM."}
            if not to_account:
                return {"ok": False, "message": "Please select the account money moved TO."}
            if from_account == to_account:
                return {"ok": False, "message": "The 'From' and 'To' accounts must be different."}
            txn_type = "Transfer"
            if from_account == "CIBC_PC_TRUST" and to_account == "CIBC_PC_GENERAL":
                category_code = category_code or "XFER_OTHER_INTERNAL"
                txn_class = "Business"
                business_unit = "Legal Practice"
                biller_entity = "PC"
                payee = payee or "Trust to General Transfer"
                details = details or "Transfer from CIBC PC Trust to CIBC PC General"
            elif to_account in ("CIBC_MORTGAGE", "HOME_TRUST_MORTGAGE"):
                txn_type = "Debt Repayment"
                category_code = (
                    "DEBT_MORTGAGE_PRINCIPAL_CIBC"
                    if to_account == "CIBC_MORTGAGE"
                    else "DEBT_MORTGAGE_PRINCIPAL_HOME_TRUST"
                )
                txn_class = "Family"
                business_unit = ""
                biller_entity = "FAMILY"
                payee = payee or ACCOUNT_UI_META.get(to_account, {}).get("displayName", to_account)
            else:
                category_code = category_code or "XFER_INTERNAL_CHEQUING_SAVINGS"
                txn_class = stream["class"]
                business_unit = stream["businessUnit"]
                biller_entity = stream["billerEntity"]
                payee = payee or "Account Transfer"
            tax_amount = 0.0
            tax_flag = "None"

        elif mode == "Income":
            deposit_account = from_account or to_account
            if not deposit_account:
                return {"ok": False, "message": "Please select which account the money was deposited into."}
            from_account = deposit_account
            to_account = ""
            txn_type = "Income"
            txn_class = stream["class"]
            business_unit = stream["businessUnit"]
            biller_entity = stream["billerEntity"]
            if from_account == "CIBC_PC_TRUST":
                category_code = category_code or "INC_RETAINER_RECEIPTS"
            elif not category_code:
                if stream_id == "DEBORAH_OT_PRIVATE":
                    category_code = "INC_OT_PRIVATE_BILLINGS"
                elif stream_id == "DEBORAH_OT_VHA":
                    category_code = "INC_OT_VHA_BILLINGS"
                elif stream_id in ("CORY_SOLE_PROP", "CORY_PC"):
                    category_code = "INC_LEGAL_FEES"
                else:
                    category_code = "INC_SALARY"
            if not payee:
                return {"ok": False, "message": "Please enter who the money came from (Client / Employer / Source)."}
            tax_flag = "HST - Biz" if (txn_class == "Business" and tax_amount > 0) else "None"

        else:
            # Expense Mode (or Store Refund)
            if not from_account:
                return {"ok": False, "message": "Please select how this was paid (Paid With account/card)."}
            if not payee:
                return {"ok": False, "message": "Please enter the Store or Payee name."}
            if not category_code:
                return {"ok": False, "message": "Please choose a Category."}

            txn_class = stream["class"]
            business_unit = stream["businessUnit"]
            biller_entity = stream["billerEntity"]
            to_account = ""

            if is_refund:
                txn_type = "Income"
                if not details.lower().startswith("refund"):
                    details = f"REFUND / RETURN: {details or payee}".strip()
            else:
                txn_type = "Expense"

            cats = {
                c["categoryCode"]: c
                for c in self.finance_repo.list_transaction_categories(include_inactive=True)
            }
            cat_meta = cats.get(category_code, {})
            if txn_class == "Business":
                tax_flag = "HST - Biz" if tax_amount > 0 else (cat_meta.get("taxFlagDefault") or "Business Deductible")
                if tax_flag not in ("None", "HST - Biz", "Business Deductible", "Medical", "Deductible"):
                    tax_flag = "Business Deductible"
            else:
                if cat_meta.get("medicalEligible"):
                    tax_flag = "Medical"
                elif cat_meta.get("deductibleEligible"):
                    tax_flag = "Deductible"
                else:
                    tax_flag = "None"

        cats_lookup = {
            c["categoryCode"]: c["categoryName"]
            for c in self.finance_repo.list_transaction_categories(include_inactive=True)
        }
        now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txn_id = str(data.get("transactionId") or "").strip()
        receipt_token = str(data.get("receiptToken") or "").strip()
        also_bill_matter = str(data.get("alsoBillToMatter") or data.get("disbursementMatterNumber") or "").strip()

        repo_payload = {
            "transactionId": txn_id,
            "txnDate": txn_date,
            "class": txn_class,
            "businessUnit": business_unit,
            "type": txn_type,
            "fromAccount": from_account,
            "toAccount": to_account,
            "payee": payee,
            "categoryCode": category_code,
            "categoryName": cats_lookup.get(category_code, category_code),
            "member": member,
            "amount": gross_amount,
            "taxAmount": tax_amount,
            "taxFlag": tax_flag,
            "hstExempt": 1 if tax_amount == 0 else 0,
            "generalOfficeExpense": 1 if txn_class == "Business" else 0,
            "expenseDetails": details,
            "notes": stored_notes,
            "status": str(data.get("status") or "Cleared").strip() or "Cleared",
            "currency": "CAD",
            "billerEntity": biller_entity,
            "createdAt": now_stamp,
            "updatedAt": now_stamp,
        }

        if self._is_isolated_test():
            try:
                self.flush_pending_inbox()
                result = self.finance_repo.save_transaction(repo_payload)
                if result.get("ok"):
                    saved_id = str(result.get("transactionId") or "")
                    if receipt_token:
                        self._finalize_staged_receipt(
                            receipt_token=receipt_token,
                            transaction_id=saved_id,
                            stream_id=stream_id,
                            category_code=category_code,
                            txn_date=txn_date,
                            payee=payee,
                            amount=gross_amount,
                            tax_amount=tax_amount,
                            matter_number=also_bill_matter,
                        )
                    enriched = self.get_entry(user_id=uid, transaction_id=saved_id)
                    return {
                        "ok": True,
                        "transactionId": saved_id,
                        "entry": enriched,
                        "queuedToOneDriveInbox": False,
                        "message": "Saved to CSPM!",
                    }
            except PermissionError:
                pass
            except Exception as exc:
                err_msg = str(exc)
                if "permission" not in err_msg.lower() and "locked" not in err_msg.lower() and "checkout" not in err_msg.lower():
                    return {"ok": False, "message": err_msg}

        # Fast-path persistence: assign TransactionID immediately, write to OneDrive Sync Queue
        # + cspm.db (<25ms), finalize any attached receipt into the Tax-Ready Receipts folder,
        # and flush to CSPM.xlsm asynchronously in a background thread so mobile saves are instant!
        if not txn_id:
            txn_id = f"TXN_{uuid4().hex[:10]}"
        repo_payload["transactionId"] = txn_id
        queued = self._read_queued_entries()
        replaced = False
        for i, qitem in enumerate(queued):
            if str(qitem.get("transactionId")) == txn_id:
                queued[i] = repo_payload
                replaced = True
                break
        if not replaced:
            queued.append(repo_payload)
        self._write_queued_entries(queued)

        receipt_meta = None
        if receipt_token:
            receipt_meta = self._finalize_staged_receipt(
                receipt_token=receipt_token,
                transaction_id=txn_id,
                stream_id=stream_id,
                category_code=category_code,
                txn_date=txn_date,
                payee=payee,
                amount=gross_amount,
                tax_amount=tax_amount,
                matter_number=also_bill_matter,
            )

        disb_msg = ""
        if also_bill_matter and self._is_cory(uid) and mode == "Expense":
            try:
                disb_res = self._record_expense_as_client_disbursement(
                    matter_number=also_bill_matter,
                    txn_date=txn_date,
                    payee=payee,
                    details=details or cats_lookup.get(category_code, category_code),
                    gross_amount=gross_amount,
                    tax_amount=tax_amount,
                    biller_entity=biller_entity if biller_entity in ("SOLE_PROP", "PC") else "SOLE_PROP",
                )
                if disb_res.get("ok"):
                    disb_msg = f" + Billed as Disbursement to {also_bill_matter}"
            except Exception as exc:
                logger.warning("Client disbursement link warning: %s", exc)

        if not self._is_isolated_test():
            threading.Thread(
                target=self._background_flush_inbox_safe,
                name="QuickExpenseFlush",
                daemon=True,
            ).start()

        enriched = self._enrich_row(repo_payload)
        msg_suffix = ""
        if receipt_meta and receipt_meta.get("folderCategory"):
            msg_suffix = f" · 🧾 Receipt filed in {receipt_meta['folderCategory']}"

        try:
            is_amend = bool(data.get("isEditingExisting") or (txn_id and not str(txn_id).startswith("TXN-NEW")))
            item_record = {
                "transactionId": txn_id,
                "txnDate": txn_date,
                "mode": mode,
                "type": txn_type,
                "streamId": stream_id,
                "streamLabel": str(stream.get("label") or stream_id).replace("—", "-"),
                "fromAccount": from_account,
                "fromAccountLabel": str(ACCOUNT_UI_META.get(from_account, {}).get("name", from_account)).replace("—", "-"),
                "toAccount": to_account,
                "toAccountLabel": str(ACCOUNT_UI_META.get(to_account, {}).get("name", to_account)).replace("—", "-") if to_account else "",
                "payee": payee,
                "categoryCode": category_code,
                "categoryLabel": str(cats_lookup.get(category_code, category_code)).replace("—", "-"),
                "amount": gross_amount,
                "taxAmount": tax_amount,
                "netAmount": round(gross_amount - tax_amount, 2),
                "notes": str(stored_notes or details).replace("—", "-"),
                "receiptPath": str(receipt_meta.get("savedPath") or "").replace("—", "-") if receipt_meta else "",
                "receiptFileName": str(receipt_meta.get("fileName") or "").replace("—", "-") if receipt_meta else "",
                "clientMatter": also_bill_matter,
                "shlCredit": bool(shl_credit_recorded or (also_bill_matter and mode == "Expense")),
            }
            ev_code = "TXN_AMEND" if is_amend else "TXN_POST_NEW"
            ev_desc = f"{'Amended' if is_amend else 'Posted'} {mode}: {payee} (${gross_amount:,.2f}) [{stream_id}]"
            self.session_tracker.record_event(uid, ev_code, ev_desc, item_data=item_record)
        except Exception as sess_exc:
            logger.debug("Session event record warning: %s", sess_exc)

        return {
            "ok": True,
            "transactionId": txn_id,
            "entry": enriched,
            "receipt": receipt_meta,
            "queuedToOneDriveInbox": False,
            "message": f"Saved to CSPM{disb_msg}{msg_suffix}!",
        }

    def _background_flush_inbox_safe(self) -> None:
        try:
            with self._lock:
                self.flush_pending_inbox()
        except Exception as exc:
            logger.debug("Background inbox flush deferred: %s", exc)

    # ------------------------------------------------------------------
    # 6. Delete Entry
    # ------------------------------------------------------------------
    def delete_entry(self, user_id: str, transaction_id: str) -> Dict[str, Any]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        existing = self.get_entry(user_id=uid, transaction_id=transaction_id)
        if not existing:
            return {"ok": False, "message": "Entry not found or not accessible."}

        # Also remove from OneDrive inbox queue if present there
        queued = self._read_queued_entries()
        new_queued = [q for q in queued if str(q.get("transactionId")) != str(transaction_id)]
        if len(new_queued) != len(queued):
            self._write_queued_entries(new_queued)
            try:
                self.finance_repo.delete_transaction(transaction_id)
            except Exception:
                pass
            return {"ok": True, "transactionId": transaction_id, "message": f"Deleted transaction {transaction_id}."}

        try:
            res = self.finance_repo.delete_transaction(transaction_id)
            if res.get("ok"):
                try:
                    self.session_tracker.record_event(uid, "TXN_DELETE", f"Deleted transaction {transaction_id}")
                except Exception:
                    pass
            return res
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # 7. Enriched Entry Formatting & Period Filtering
    # ------------------------------------------------------------------
    def _enrich_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        stream = self._resolve_stream_from_row(row)
        mode = self._resolve_mode_from_row(row)
        cat_code = str(row.get("categoryCode") or "").upper()
        cat_icon, cat_group, _ = CATEGORY_ICONS_AND_GROUPS.get(cat_code, ("📌", "Other", False))
        from_code = str(row.get("fromAccount") or "").upper()
        to_code = str(row.get("toAccount") or "").upper()
        from_meta = ACCOUNT_UI_META.get(from_code, {})
        to_meta = ACCOUNT_UI_META.get(to_code, {})

        gross = round(float(row.get("amount") or 0.0), 2)
        hst = round(float(row.get("taxAmount") or 0.0), 2)
        pre_tax = round(max(0.0, gross - hst), 2)

        raw_notes = str(row.get("notes") or "")
        clean_notes = re.sub(r"\s*\[Entered by (Deborah|Cory)\]\s*", "", raw_notes, flags=re.IGNORECASE).strip()
        entered_by = "Deborah" if "[entered by deborah]" in raw_notes.lower() else (
            "Cory" if "[entered by cory]" in raw_notes.lower() else str(row.get("member") or "")
        )

        txn_id_str = str(row.get("transactionId") or "")
        rcpt = self._get_receipt_for_transaction(txn_id_str) if txn_id_str else None

        return {
            "transactionId": txn_id_str,
            "txnDate": str(row.get("txnDate") or ""),
            "mode": mode,
            "type": str(row.get("type") or "Expense"),
            "streamId": stream["streamId"],
            "streamLabel": stream["label"],
            "streamShortLabel": stream["shortLabel"],
            "streamIcon": stream["icon"],
            "streamColor": stream["color"],
            "class": str(row.get("class") or "Family"),
            "businessUnit": str(row.get("businessUnit") or ""),
            "billerEntity": str(row.get("billerEntity") or ""),
            "fromAccount": from_code,
            "fromAccountLabel": from_meta.get("displayName") or from_code,
            "fromAccountIcon": from_meta.get("icon") or "🏦",
            "toAccount": to_code,
            "toAccountLabel": to_meta.get("displayName") or to_code,
            "toAccountIcon": to_meta.get("icon") or ("🏦" if to_code else ""),
            "payee": str(row.get("payee") or ""),
            "categoryCode": cat_code,
            "categoryName": str(row.get("categoryName") or cat_code),
            "categoryIcon": cat_icon,
            "categoryGroup": cat_group,
            "member": str(row.get("member") or "Joint"),
            "preTaxAmount": pre_tax,
            "taxAmount": hst,
            "amount": gross,
            "amountFormatted": f"${gross:,.2f}",
            "taxFormatted": f"${hst:,.2f}",
            "preTaxFormatted": f"${pre_tax:,.2f}",
            "expenseDetails": str(row.get("expenseDetails") or ""),
            "notes": clean_notes,
            "enteredBy": entered_by,
            "createdAt": str(row.get("createdAt") or ""),
            "updatedAt": str(row.get("updatedAt") or ""),
            "hasReceipt": bool(rcpt),
            "receiptId": str(rcpt.get("receiptId") or "") if rcpt else "",
            "receiptUrl": f"/api/receipt/file?receiptId={rcpt.get('receiptId')}&userId=cory" if rcpt else "",
            "receiptFileName": str(rcpt.get("fileName") or "") if rcpt else "",
            "receiptFolder": str(rcpt.get("folderCategory") or "") if rcpt else "",
            "receiptRelativePath": str(rcpt.get("relativePath") or "") if rcpt else "",
            "receiptMimeType": str(rcpt.get("mimeType") or "") if rcpt else "",
        }

    def get_entry(self, user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        all_rows = self.finance_repo.list_transactions({}) + self._read_queued_entries()
        for r in all_rows:
            if str(r.get("transactionId") or "") == str(transaction_id or ""):
                if not self._is_transaction_visible_to_user(r, uid):
                    return None
                return self._enrich_row(r)
        return None

    @staticmethod
    def resolve_period_dates(
        period: str = "today",
        date_from: str = "",
        date_to: str = "",
        reference_date: Optional[date] = None,
    ) -> Tuple[str, str, str]:
        today = reference_date or date.today()
        p = str(period or "today").strip().lower()

        if p == "custom" and date_from and date_to:
            return date_from, date_to, f"Custom ({date_from} to {date_to})"
        if p == "today":
            iso = today.isoformat()
            return iso, iso, f"Today ({iso})"
        if p == "yesterday":
            y = (today - timedelta(days=1)).isoformat()
            return y, y, f"Yesterday ({y})"
        if p in ("this_week", "week"):
            days_since_sunday = (today.weekday() + 1) % 7
            start = today - timedelta(days=days_since_sunday)
            return start.isoformat(), today.isoformat(), f"This Week (Sun–Sat: {start.isoformat()} to {today.isoformat()})"
        if p in ("last_7_days", "7d", "rolling_7d"):
            start = today - timedelta(days=6)
            return start.isoformat(), today.isoformat(), f"Last 7 Days ({start.isoformat()} to {today.isoformat()})"
        if p in ("this_month", "month", "mtd"):
            start = today.replace(day=1)
            return start.isoformat(), today.isoformat(), f"This Month ({today.strftime('%B %Y')})"
        if p in ("last_30_days", "30d", "rolling_30d"):
            start = today - timedelta(days=29)
            return start.isoformat(), today.isoformat(), f"Last 30 Days ({start.isoformat()} to {today.isoformat()})"
        if p == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            first_prev = last_prev.replace(day=1)
            return first_prev.isoformat(), last_prev.isoformat(), f"Last Month ({last_prev.strftime('%B %Y')})"
        if p in ("this_year", "year", "ytd"):
            start = today.replace(month=1, day=1)
            return start.isoformat(), today.isoformat(), f"Year to Date ({today.year})"
        if p == "all":
            return "", "", "All Dates"

        iso = today.isoformat()
        return iso, iso, f"Today ({iso})"

    def list_entries(
        self,
        user_id: str = "deborah",
        period: str = "today",
        date_from: str = "",
        date_to: str = "",
        stream_id: str = "",
        mode_filter: str = "",
        search_query: str = "",
    ) -> List[Dict[str, Any]]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        d_from, d_to, _ = self.resolve_period_dates(period, date_from, date_to)

        filters: Dict[str, Any] = {}
        if d_from:
            filters["dateFrom"] = d_from
        if d_to:
            filters["dateTo"] = d_to

        with self._lock:
            if self._is_isolated_test():
                self.flush_pending_inbox()
            raw_rows = list(self.finance_repo.list_transactions(filters))
            queued_rows = self._read_queued_entries()
        seen_ids = {str(r.get("transactionId") or "") for r in raw_rows}
        for qitem in queued_rows:
            qid = str(qitem.get("transactionId") or "")
            qdate = str(qitem.get("txnDate") or "")
            if qid and qid not in seen_ids:
                if d_from and qdate < d_from:
                    continue
                if d_to and qdate > d_to:
                    continue
                raw_rows.append(qitem)
                seen_ids.add(qid)

        out: List[Dict[str, Any]] = []
        target_stream = str(stream_id or "").strip().upper()
        target_mode = str(mode_filter or "").strip().lower()
        q = str(search_query or "").strip().lower()

        for r in raw_rows:
            if not self._is_transaction_visible_to_user(r, uid):
                continue
            item = self._enrich_row(r)
            if target_stream and target_stream != "ALL" and item["streamId"] != target_stream:
                continue
            if target_mode and target_mode != "all" and item["mode"].lower() != target_mode:
                continue
            if q:
                hay = " ".join(
                    [
                        item["txnDate"],
                        item["payee"],
                        item["categoryName"],
                        item["fromAccountLabel"],
                        item["toAccountLabel"],
                        item["streamLabel"],
                        item["notes"],
                        item["expenseDetails"],
                        item["amountFormatted"],
                    ]
                ).lower()
                if q not in hay:
                    continue
            out.append(item)

        return out

    def build_report(
        self,
        user_id: str = "deborah",
        period: str = "today",
        date_from: str = "",
        date_to: str = "",
        stream_id: str = "ALL",
        mode_filter: str = "ALL",
        search_query: str = "",
    ) -> Dict[str, Any]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        d_from, d_to, period_label = self.resolve_period_dates(period, date_from, date_to)
        entries = self.list_entries(
            user_id=uid,
            period=period,
            date_from=date_from,
            date_to=date_to,
            stream_id=stream_id,
            mode_filter=mode_filter,
            search_query=search_query,
        )

        expense_total = 0.0
        expense_hst = 0.0
        income_total = 0.0
        transfer_total = 0.0
        by_stream: Dict[str, Dict[str, Any]] = {
            s["streamId"]: {
                "streamId": s["streamId"],
                "label": s["shortLabel"],
                "icon": s["icon"],
                "color": s["color"],
                "count": 0,
                "expenseTotal": 0.0,
                "hstTotal": 0.0,
                "incomeTotal": 0.0,
            }
            for s in STREAM_OPTIONS
            if self._is_cory(uid) or s["streamId"] not in {"CORY_SOLE_PROP", "CORY_PC"}
        }

        palette = [
            "#6366f1", "#10b981", "#f59e0b", "#ec4899", "#3b82f6",
            "#8b5cf6", "#14b8a6", "#f97316", "#ef4444", "#06b6d4",
            "#84cc16", "#a855f7",
        ]
        exp_by_cat: Dict[str, Dict[str, Any]] = {}
        exp_by_grp: Dict[str, Dict[str, Any]] = {}
        inc_by_cat: Dict[str, Dict[str, Any]] = {}
        by_month: Dict[str, Dict[str, Any]] = {}
        receipts_count = 0

        for e in entries:
            amt = float(e.get("amount") or 0.0)
            hst = float(e.get("taxAmount") or 0.0)
            sid = e.get("streamId") or "FAMILY"
            if e.get("hasReceipt"):
                receipts_count += 1
            bucket = by_stream.get(sid)
            if bucket:
                bucket["count"] += 1

            m_key = str(e.get("txnDate") or "")[:7] or date.today().strftime("%Y-%m")
            if m_key not in by_month:
                try:
                    dt_m = datetime.strptime(m_key + "-01", "%Y-%m-%d")
                    m_lbl = dt_m.strftime("%b '%y")
                except Exception:
                    m_lbl = m_key
                by_month[m_key] = {
                    "monthKey": m_key,
                    "monthLabel": m_lbl,
                    "incomeTotal": 0.0,
                    "expenseTotal": 0.0,
                    "hstTotal": 0.0,
                }

            if e["mode"] == "Expense":
                expense_total = round(expense_total + amt, 2)
                expense_hst = round(expense_hst + hst, 2)
                by_month[m_key]["expenseTotal"] = round(by_month[m_key]["expenseTotal"] + amt, 2)
                by_month[m_key]["hstTotal"] = round(by_month[m_key]["hstTotal"] + hst, 2)
                if bucket:
                    bucket["expenseTotal"] = round(bucket["expenseTotal"] + amt, 2)
                    bucket["hstTotal"] = round(bucket["hstTotal"] + hst, 2)
                c_code = str(e.get("categoryCode") or "OTHER")
                if c_code not in exp_by_cat:
                    exp_by_cat[c_code] = {
                        "categoryCode": c_code,
                        "categoryName": str(e.get("categoryName") or c_code),
                        "icon": str(e.get("categoryIcon") or "📌"),
                        "group": str(e.get("categoryGroup") or "Other"),
                        "total": 0.0,
                        "hst": 0.0,
                        "count": 0,
                    }
                exp_by_cat[c_code]["total"] = round(exp_by_cat[c_code]["total"] + amt, 2)
                exp_by_cat[c_code]["hst"] = round(exp_by_cat[c_code]["hst"] + hst, 2)
                exp_by_cat[c_code]["count"] += 1

                grp = str(e.get("categoryGroup") or "Other")
                if grp not in exp_by_grp:
                    exp_by_grp[grp] = {"group": grp, "total": 0.0, "count": 0}
                exp_by_grp[grp]["total"] = round(exp_by_grp[grp]["total"] + amt, 2)
                exp_by_grp[grp]["count"] += 1

            elif e["mode"] == "Income":
                income_total = round(income_total + amt, 2)
                by_month[m_key]["incomeTotal"] = round(by_month[m_key]["incomeTotal"] + amt, 2)
                if bucket:
                    bucket["incomeTotal"] = round(bucket["incomeTotal"] + amt, 2)
                c_code = str(e.get("categoryCode") or "INC_OTHER")
                if c_code not in inc_by_cat:
                    inc_by_cat[c_code] = {
                        "categoryCode": c_code,
                        "categoryName": str(e.get("categoryName") or c_code),
                        "icon": str(e.get("categoryIcon") or "💵"),
                        "total": 0.0,
                        "count": 0,
                    }
                inc_by_cat[c_code]["total"] = round(inc_by_cat[c_code]["total"] + amt, 2)
                inc_by_cat[c_code]["count"] += 1
            else:
                transfer_total = round(transfer_total + amt, 2)

        for b in by_stream.values():
            b["netProfit"] = round(b["incomeTotal"] - b["expenseTotal"], 2)
            b["expenseFormatted"] = f"${b['expenseTotal']:,.2f}"
            b["hstFormatted"] = f"${b['hstTotal']:,.2f}"
            b["incomeFormatted"] = f"${b['incomeTotal']:,.2f}"
            b["netProfitFormatted"] = (
                f"+${b['netProfit']:,.2f}" if b["netProfit"] >= 0 else f"-${abs(b['netProfit']):,.2f}"
            )

        exp_cat_list = sorted(exp_by_cat.values(), key=lambda x: x["total"], reverse=True)
        for idx, item in enumerate(exp_cat_list):
            item["color"] = palette[idx % len(palette)]
            item["pct"] = round((item["total"] / expense_total) * 100.0, 1) if expense_total > 0 else 0.0
            item["totalFormatted"] = f"${item['total']:,.2f}"
            item["hstFormatted"] = f"${item['hst']:,.2f}"

        exp_grp_list = sorted(exp_by_grp.values(), key=lambda x: x["total"], reverse=True)
        for idx, item in enumerate(exp_grp_list):
            item["color"] = palette[idx % len(palette)]
            item["pct"] = round((item["total"] / expense_total) * 100.0, 1) if expense_total > 0 else 0.0
            item["totalFormatted"] = f"${item['total']:,.2f}"

        inc_cat_list = sorted(inc_by_cat.values(), key=lambda x: x["total"], reverse=True)
        for idx, item in enumerate(inc_cat_list):
            item["color"] = palette[(idx + 2) % len(palette)]
            item["pct"] = round((item["total"] / income_total) * 100.0, 1) if income_total > 0 else 0.0
            item["totalFormatted"] = f"${item['total']:,.2f}"

        month_list = sorted(by_month.values(), key=lambda x: x["monthKey"])
        for m in month_list:
            m["netProfit"] = round(m["incomeTotal"] - m["expenseTotal"], 2)
            m["incomeFormatted"] = f"${m['incomeTotal']:,.2f}"
            m["expenseFormatted"] = f"${m['expenseTotal']:,.2f}"
            m["netProfitFormatted"] = (
                f"+${m['netProfit']:,.2f}" if m["netProfit"] >= 0 else f"-${abs(m['netProfit']):,.2f}"
            )

        net_profit_total = round(income_total - expense_total, 2)

        return {
            "ok": True,
            "userId": uid,
            "period": period,
            "periodLabel": period_label,
            "dateFrom": d_from,
            "dateTo": d_to,
            "entryCount": len(entries),
            "receiptsCount": receipts_count,
            "expensePreTaxTotal": round(max(0.0, expense_total - expense_hst), 2),
            "expensePreTaxFormatted": f"${max(0.0, expense_total - expense_hst):,.2f}",
            "expenseHstTotal": expense_hst,
            "expenseHstFormatted": f"${expense_hst:,.2f}",
            "expenseGrandTotal": expense_total,
            "expenseGrandFormatted": f"${expense_total:,.2f}",
            "incomeTotal": income_total,
            "incomeFormatted": f"${income_total:,.2f}",
            "netProfitTotal": net_profit_total,
            "netProfitFormatted": (
                f"+${net_profit_total:,.2f}" if net_profit_total >= 0 else f"-${abs(net_profit_total):,.2f}"
            ),
            "transferTotal": transfer_total,
            "transferFormatted": f"${transfer_total:,.2f}",
            "byStream": list(by_stream.values()),
            "charts": {
                "expensePieByCategory": exp_cat_list,
                "expensePieByGroup": exp_grp_list,
                "incomePieByCategory": inc_cat_list,
                "cashFlowBarByStream": list(by_stream.values()),
                "cashFlowBarByMonth": month_list,
            },
            "entries": entries,
        }
        try:
            self.session_tracker.record_event(
                uid,
                "REPORT_VIEW",
                f"Viewed report: Period={period}, Stream={stream_id}",
                item_data={"period": period, "streamId": stream_id, "dateFrom": date_from, "dateTo": date_to},
            )
        except Exception:
            pass
        return res

    # ------------------------------------------------------------------
    # 7. Docketing (Cory-Only) — Matters Lookup & Dual CSPM + Legacy Dockets Sync
    # ------------------------------------------------------------------
    def _all_sqlite_db_paths(self) -> List[Path]:
        if self._is_isolated_test():
            cand = self.paths.data_dir() / "cspm.db"
            return [cand] if cand.is_file() else []
        out: List[Path] = []
        seen: set[str] = set()
        for d in (self.paths.master_data_dir(), self.paths.data_dir()):
            if d and (d / "cspm.db").is_file():
                k = str((d / "cspm.db").resolve()).casefold()
                if k not in seen:
                    seen.add(k)
                    out.append(d / "cspm.db")
        try:
            for od in sorted(Path.home().glob("OneDrive*")):
                cand = od / "CSPM_Shared_Data" / "cspm.db"
                if cand.is_file():
                    k = str(cand.resolve()).casefold()
                    if k not in seen:
                        seen.add(k)
                        out.append(cand)
        except Exception:
            pass
        return out

    def _resolve_sqlite_db_path(self) -> Optional[Path]:
        dbs = self._all_sqlite_db_paths()
        return dbs[0] if dbs else None

    def list_docket_matters(
        self,
        user_id: str = "cory",
        query: str = "",
        matter_id: str = "",
        period: str = "",
    ) -> Dict[str, Any]:
        if not self._is_cory(user_id):
            return {"ok": False, "message": "Docketing is restricted to Cory."}

        q_clean = str(query or "").strip().lower()
        target_matter_ref = str(matter_id or "").strip()
        if target_matter_ref.upper() == "ALL":
            target_matter_ref = ""
        period_clean = str(period or "recent").strip().lower()

        today_dt = date.today()
        today_iso = today_dt.isoformat()
        yest_iso = (today_dt - timedelta(days=1)).isoformat()
        # Calendar week starting Sunday (Sunday=0 days ago, Monday=1 day ago, ..., Saturday=6 days ago)
        days_since_sunday = (today_dt.weekday() + 1) % 7
        week_start_iso = (today_dt - timedelta(days=days_since_sunday)).isoformat()
        week_days_elapsed = max(1, days_since_sunday + 1)
        # Rolling 7 days (inclusive of today: today - 6 days .. today)
        last7_start_iso = (today_dt - timedelta(days=6)).isoformat()
        # Calendar month from the 1st of the month (MTD)
        month_start_dt = today_dt.replace(day=1)
        month_start_iso = month_start_dt.isoformat()
        month_days_elapsed = max(1, today_dt.day)
        # Rolling 30 days (inclusive of today: today - 29 days .. today)
        last30_start_iso = (today_dt - timedelta(days=29)).isoformat()
        # Full prior calendar month
        last_month_end_dt = month_start_dt - timedelta(days=1)
        last_month_start_dt = last_month_end_dt.replace(day=1)
        last_month_start_iso = last_month_start_dt.isoformat()
        last_month_end_iso = last_month_end_dt.isoformat()
        # Year-to-Date (from Jan 1 of current year)
        ytd_start_dt = today_dt.replace(month=1, day=1)
        ytd_start_iso = ytd_start_dt.isoformat()
        ytd_days_elapsed = max(1, (today_dt - ytd_start_dt).days + 1)
        ytd_months_elapsed = max(1.0, round(ytd_days_elapsed / 30.4375, 2))

        period_from = ""
        period_to = ""
        only_unbilled = False
        if period_clean == "today":
            period_from, period_to = today_iso, today_iso
        elif period_clean == "yesterday":
            period_from, period_to = yest_iso, yest_iso
        elif period_clean in ("this_week", "week"):
            period_from, period_to = week_start_iso, today_iso
        elif period_clean in ("last_7_days", "7d", "rolling_7d"):
            period_from, period_to = last7_start_iso, today_iso
        elif period_clean in ("this_month", "month", "mtd"):
            period_from, period_to = month_start_iso, today_iso
        elif period_clean in ("last_30_days", "30d", "rolling_30d"):
            period_from, period_to = last30_start_iso, today_iso
        elif period_clean in ("last_month",):
            period_from, period_to = last_month_start_iso, last_month_end_iso
        elif period_clean in ("ytd", "this_year", "year"):
            period_from, period_to = ytd_start_iso, today_iso
        elif period_clean in ("unbilled", "wip", "unbilled_wip"):
            only_unbilled = True

        def _empty_stat(label: str, d_from: str = "", d_to: str = "", days_divisor: float = 1.0) -> Dict[str, Any]:
            return {
                "label": label,
                "dateFrom": d_from,
                "dateTo": d_to,
                "daysSpan": days_divisor,
                "count": 0,
                "hours": 0.0,
                "feePreTax": 0.0,
                "totalInclHst": 0.0,
                "avgHoursPerDay": 0.0,
                "avgFeePerDay": 0.0,
            }

        productivity: Dict[str, Dict[str, Any]] = {
            "today": _empty_stat("Today", today_iso, today_iso, 1.0),
            "yesterday": _empty_stat("Yesterday", yest_iso, yest_iso, 1.0),
            "thisWeek": _empty_stat("This Week (from Sun)", week_start_iso, today_iso, float(week_days_elapsed)),
            "last7Days": _empty_stat("Last 7 Days (7d Avg)", last7_start_iso, today_iso, 7.0),
            "thisMonth": _empty_stat("This Month (from 1st)", month_start_iso, today_iso, float(month_days_elapsed)),
            "last30Days": _empty_stat("Last 30 Days (30d Avg)", last30_start_iso, today_iso, 30.0),
            "lastMonth": _empty_stat("Last Month", last_month_start_iso, last_month_end_iso, float(last_month_end_dt.day)),
            "ytd": _empty_stat("Year to Date (YTD)", ytd_start_iso, today_iso, float(ytd_days_elapsed)),
            "unbilledWip": _empty_stat("Unbilled WIP", "", today_iso, 1.0),
            "openAr": {
                "label": "Open A/R",
                "count": 0,
                "balanceDue": 0.0,
                "totalInvoiced": 0.0,
                "b0_30": 0.0,
                "b31_60": 0.0,
                "b61_90": 0.0,
                "b90_plus": 0.0,
            },
            "filtered": _empty_stat("Displayed Dockets", period_from, period_to, 1.0),
        }

        db_path = self._resolve_sqlite_db_path()
        matters: List[Dict[str, Any]] = []
        recent_matters: List[Dict[str, Any]] = []
        recent_dockets: List[Dict[str, Any]] = []
        by_ref: Dict[str, Dict[str, Any]] = {}
        seen_matter_keys: set[str] = set()

        def _build_docket_item(
            entry_id_val: Any,
            date_val: Any,
            client_val: Any,
            m_id_val: str,
            m_name_val: str,
            hrs_val: Any,
            rate_val: Any,
            share_val: Any,
            total_val: Any,
            desc_val: Any,
            is_billed_flag: bool,
            matched_matter: Optional[Dict[str, Any]],
        ) -> Dict[str, Any]:
            hrs_f = round(float(hrs_val or 0.0), 2)
            rate_f = float(rate_val or 475.0)
            share_f = float(share_val or 100.0)
            fee_f = round(hrs_f * rate_f * (share_f / 100.0), 2)
            tot_f = round(float(total_val or 0.0), 2) or round(fee_f * 1.13, 2)
            return {
                "entryId": str(entry_id_val or ""),
                "date": str(date_val or "")[:10],
                "clientName": str(client_val or (matched_matter or {}).get("clientName") or ""),
                "matterId": (matched_matter or {}).get("matterId") or m_id_val,
                "matterNumber": (matched_matter or {}).get("matterNumber") or m_name_val or m_id_val,
                "matterName": (matched_matter or {}).get("matterName") or m_name_val,
                "hours": hrs_f,
                "rate": rate_f,
                "sharePct": share_f,
                "feePreTax": fee_f,
                "totalInclHst": tot_f,
                "description": str(desc_val or ""),
                "isBilled": bool(is_billed_flag),
            }

        def _accum_stat(bucket: Dict[str, Any], hrs_f: float, fee_f: float, tot_f: float) -> None:
            bucket["count"] = int(bucket["count"]) + 1
            bucket["hours"] = round(float(bucket["hours"]) + hrs_f, 2)
            bucket["feePreTax"] = round(float(bucket["feePreTax"]) + fee_f, 2)
            bucket["totalInclHst"] = round(float(bucket["totalInclHst"]) + tot_f, 2)

        if db_path is not None:
            import sqlite3
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.matter_id, m.matter_number, m.matter_name, m.display_name,
                           m.client_id, m.client_name, m.parent_id,
                           COALESCE(m.default_rate, m.hourly_rate, 475.0) AS rate,
                           COALESCE(m.default_share_pct, 100.0) AS share_pct,
                           COALESCE(NULLIF(m.default_biller_entity, ''), NULLIF(m.default_biller, ''), 'SOLE_PROP') AS biller
                    FROM Matter m
                    WHERE COALESCE(m.status, 'Open') NOT IN ('Closed', 'Archived', 'Deleted')
                    ORDER BY m.created_at DESC
                    """
                )
                cols = [d[0] for d in cur.description]
                all_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                for r in all_rows:
                    m_id_raw = str(r.get("matter_id") or "").strip()
                    m_num = str(r.get("matter_number") or m_id_raw).strip()
                    m_name = str(r.get("matter_name") or r.get("display_name") or "").strip()
                    c_name = str(r.get("client_name") or "").strip()
                    p_name = str(r.get("parent_id") or "").strip()
                    rate_val = float(r.get("rate") or 475.0)
                    share_val = float(r.get("share_pct") or 100.0)
                    biller_val = str(r.get("biller") or "SOLE_PROP").strip().upper()
                    item = {
                        "matterId": m_id_raw or m_num,
                        "matterNumber": m_num,
                        "matterName": m_name,
                        "clientName": c_name,
                        "parentName": p_name,
                        "rate": rate_val,
                        "sharePct": share_val,
                        "billerEntity": biller_val,
                        "label": f"{c_name} — {m_name} ({m_num})" if m_name else f"{c_name} ({m_num})",
                    }
                    if item["matterId"]:
                        by_ref[item["matterId"].upper()] = item
                        seen_matter_keys.add(item["matterId"].upper())
                    if m_num:
                        by_ref[m_num.upper()] = item
                        seen_matter_keys.add(m_num.upper())
                    if m_name:
                        by_ref[m_name.upper()] = item
                    hay = f"{m_num} {m_name} {c_name} {p_name} {item['matterId']}".lower()
                    if not q_clean or q_clean in hay:
                        matters.append(item)

                # Compute productivity metrics across all 6 core horizons + Yesterday, Last Month & Unbilled WIP
                earliest_stat_iso = min(ytd_start_iso, last_month_start_iso, last30_start_iso, week_start_iso, yest_iso)
                cur.execute(
                    """
                    SELECT date, hours, COALESCE(rate, 475.0), COALESCE(share_pct, 100.0),
                           COALESCE(total_incl_hst, 0.0), COALESCE(is_billed, 0), COALESCE(status, 'Draft')
                    FROM TimeEntry
                    WHERE date >= ? OR COALESCE(is_billed, 0) = 0
                    """,
                    (earliest_stat_iso,),
                )
                for p_row in cur.fetchall():
                    d_iso = str(p_row[0] or "")[:10]
                    h_val = float(p_row[1] or 0.0)
                    r_val = float(p_row[2] or 475.0)
                    s_val = float(p_row[3] or 100.0)
                    fee_val = round(h_val * r_val * (s_val / 100.0), 2)
                    tot_val = round(float(p_row[4] or 0.0), 2) or round(fee_val * 1.13, 2)
                    is_billed_row = bool(p_row[5]) or str(p_row[6] or "").strip().lower() == "billed"
                    if not is_billed_row:
                        _accum_stat(productivity["unbilledWip"], h_val, fee_val, tot_val)
                    if d_iso == today_iso:
                        _accum_stat(productivity["today"], h_val, fee_val, tot_val)
                    if d_iso == yest_iso:
                        _accum_stat(productivity["yesterday"], h_val, fee_val, tot_val)
                    if week_start_iso <= d_iso <= today_iso:
                        _accum_stat(productivity["thisWeek"], h_val, fee_val, tot_val)
                    if last7_start_iso <= d_iso <= today_iso:
                        _accum_stat(productivity["last7Days"], h_val, fee_val, tot_val)
                    if month_start_iso <= d_iso <= today_iso:
                        _accum_stat(productivity["thisMonth"], h_val, fee_val, tot_val)
                    if last30_start_iso <= d_iso <= today_iso:
                        _accum_stat(productivity["last30Days"], h_val, fee_val, tot_val)
                    if last_month_start_iso <= d_iso <= last_month_end_iso:
                        _accum_stat(productivity["lastMonth"], h_val, fee_val, tot_val)
                    if ytd_start_iso <= d_iso <= today_iso:
                        _accum_stat(productivity["ytd"], h_val, fee_val, tot_val)

                # Compute Open A/R summary from Receivable table
                try:
                    cur.execute(
                        """
                        SELECT date, COALESCE(total_invoiced, 0.0), COALESCE(amount_due, 0.0)
                        FROM Receivable
                        WHERE COALESCE(amount_due, 0.0) > 0.009
                          AND LOWER(COALESCE(status, '')) NOT IN ('paid', 'void', 'reversed', 'cancelled')
                        """
                    )
                    for ar_r in cur.fetchall():
                        ar_dt_str = str(ar_r[0] or "")[:10]
                        inv_tot = round(float(ar_r[1] or 0.0), 2)
                        bal_due = round(float(ar_r[2] or 0.0), 2)
                        productivity["openAr"]["count"] = int(productivity["openAr"]["count"]) + 1
                        productivity["openAr"]["totalInvoiced"] = round(float(productivity["openAr"]["totalInvoiced"]) + inv_tot, 2)
                        productivity["openAr"]["balanceDue"] = round(float(productivity["openAr"]["balanceDue"]) + bal_due, 2)
                        try:
                            age_d = max(0, (today_dt - date.fromisoformat(ar_dt_str)).days)
                        except Exception:
                            age_d = 0
                        if age_d <= 30:
                            productivity["openAr"]["b0_30"] = round(float(productivity["openAr"]["b0_30"]) + bal_due, 2)
                        elif age_d <= 60:
                            productivity["openAr"]["b31_60"] = round(float(productivity["openAr"]["b31_60"]) + bal_due, 2)
                        elif age_d <= 90:
                            productivity["openAr"]["b61_90"] = round(float(productivity["openAr"]["b61_90"]) + bal_due, 2)
                        else:
                            productivity["openAr"]["b90_plus"] = round(float(productivity["openAr"]["b90_plus"]) + bal_due, 2)
                except Exception:
                    pass

                # Recent matters from TimeEntry (corrected primary key column: time_id)
                cur.execute(
                    """
                    SELECT matter_id, matter_name, time_id, date, client_name, hours, rate,
                           COALESCE(share_pct, 100.0), total_incl_hst, description,
                           COALESCE(is_billed, 0), COALESCE(status, 'Draft')
                    FROM TimeEntry
                    ORDER BY date DESC, created_at DESC
                    LIMIT 80
                    """
                )
                seen_m: set[str] = set()
                for tr in cur.fetchall():
                    m_id_val = str(tr[0] or "").strip()
                    m_name_val = str(tr[1] or "").strip()
                    matched_matter = by_ref.get(m_id_val.upper()) or by_ref.get(m_name_val.upper())
                    if matched_matter:
                        m_canonical = matched_matter["matterNumber"] or matched_matter["matterId"]
                        if m_canonical not in seen_m and len(recent_matters) < 8:
                            seen_m.add(m_canonical)
                            recent_matters.append(matched_matter)

                # Build SQL query for recent_dockets (filtered by optional matter_id and/or period)
                where_clauses: List[str] = []
                sql_params: List[Any] = []
                target_item = by_ref.get(target_matter_ref.upper()) if target_matter_ref else None
                if target_matter_ref:
                    k1 = (target_item["matterId"] if target_item else target_matter_ref).upper()
                    k2 = (target_item["matterNumber"] if target_item else target_matter_ref).upper()
                    where_clauses.append(
                        "(UPPER(TRIM(COALESCE(matter_id, ''))) IN (?, ?) OR UPPER(TRIM(COALESCE(matter_name, ''))) IN (?, ?))"
                    )
                    sql_params.extend([k1, k2, k1, k2])
                if period_from:
                    where_clauses.append("date >= ?")
                    sql_params.append(period_from)
                if period_to:
                    where_clauses.append("date <= ?")
                    sql_params.append(period_to)
                if only_unbilled:
                    where_clauses.append("(COALESCE(is_billed, 0) = 0 AND LOWER(COALESCE(status, 'Draft')) != 'billed')")

                where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                limit_rows = 800 if (period_from or only_unbilled or target_matter_ref) else 50
                cur.execute(
                    f"""
                    SELECT matter_id, matter_name, time_id, date, client_name, hours, rate,
                           COALESCE(share_pct, 100.0), total_incl_hst, description,
                           COALESCE(is_billed, 0), COALESCE(status, 'Draft')
                    FROM TimeEntry
                    {where_sql}
                    ORDER BY date DESC, created_at DESC
                    LIMIT {limit_rows}
                    """,
                    tuple(sql_params),
                )
                for tr in cur.fetchall():
                    m_id_val = str(tr[0] or "").strip()
                    m_name_val = str(tr[1] or "").strip()
                    matched_matter = target_item or by_ref.get(m_id_val.upper()) or by_ref.get(m_name_val.upper())
                    is_billed_flag = bool(tr[10]) or str(tr[11] or "").strip().lower() == "billed"
                    d_item = _build_docket_item(
                        tr[2], tr[3], tr[4], m_id_val, m_name_val,
                        tr[5], tr[6], tr[7], tr[8], tr[9], is_billed_flag, matched_matter
                    )
                    recent_dockets.append(d_item)
                conn.close()
            except Exception as exc:
                logger.warning("SQLite matter lookup fallback: %s", exc)

        # Also merge any active matters from ExcelRepo directory not yet in by_ref
        if not matters or db_path is None:
            with self._lock:
                try:
                    raw_dir = self.repo.list_active_matter_directory()
                    for r in raw_dir:
                        m_id_raw = str(r.get("matterId") or "").strip()
                        m_num = str(r.get("matterNumber") or m_id_raw).strip()
                        if m_id_raw.upper() in seen_matter_keys or m_num.upper() in seen_matter_keys:
                            continue
                        m_name = str(r.get("matterName") or r.get("displayName") or "").strip()
                        c_name = str(r.get("clientName") or "").strip()
                        p_name = str(r.get("parentName") or "").strip()
                        item = {
                            "matterId": m_id_raw or m_num,
                            "matterNumber": m_num,
                            "matterName": m_name,
                            "clientName": c_name,
                            "parentName": p_name,
                            "rate": float(r.get("defaultRate") or r.get("clientRate") or 475.0),
                            "sharePct": float(r.get("defaultSharePct") or 100.0),
                            "billerEntity": str(r.get("defaultBillerEntity") or "SOLE_PROP"),
                            "label": f"{c_name} — {m_name} ({m_num})" if m_name else f"{c_name} ({m_num})",
                        }
                        if item["matterId"]:
                            by_ref[item["matterId"].upper()] = item
                        if m_num:
                            by_ref[m_num.upper()] = item
                        if m_name:
                            by_ref[m_name.upper()] = item
                        hay = f"{m_num} {m_name} {c_name} {p_name} {item['matterId']}".lower()
                        if not q_clean or q_clean in hay:
                            matters.append(item)
                    if not recent_matters:
                        recent_matters = matters[:8]
                except Exception:
                    pass

        # Fallback / supplement recent_dockets & productivity from ExcelRepo TBL_TIME when SQLite TimeEntry had no rows
        if not recent_dockets:
            with self._lock:
                try:
                    import domain.schema_constants as sc
                    from repositories.excel_repo import TBL_TIME as EXCEL_TBL_TIME
                    raw_time = self.repo._read_table_rows(EXCEL_TBL_TIME)
                    target_keys: set[str] = set()
                    if target_matter_ref:
                        target_keys.add(target_matter_ref.upper())
                        t_item = by_ref.get(target_matter_ref.upper())
                        if t_item:
                            target_keys.add(str(t_item.get("matterId") or "").upper())
                            target_keys.add(str(t_item.get("matterNumber") or "").upper())
                            target_keys.add(str(t_item.get("matterName") or "").upper())
                    matched_rows: List[Dict[str, Any]] = []
                    compute_excel_prod = productivity["thisMonth"]["count"] == 0 and productivity["today"]["count"] == 0
                    for tr in reversed(raw_time):
                        e_id = str(tr.get(sc.COL_TIME_ENTRY_ID) or "").strip()
                        if not e_id:
                            continue
                        d_iso = str(tr.get(sc.COL_TIME_DATE) or "")[:10]
                        m_id_val = str(tr.get(sc.COL_TIME_MATTER_ID) or "").strip()
                        matched_matter = by_ref.get(m_id_val.upper())
                        status_str = str(tr.get(sc.COL_TIME_STATUS) or "Draft").strip()
                        inv_ref = str(tr.get(sc.COL_TIME_INVOICE_REF) or "").strip()
                        is_billed_flag = status_str.lower() == "billed" or bool(inv_ref)
                        d_item = _build_docket_item(
                            e_id,
                            d_iso,
                            (matched_matter or {}).get("clientName") or str(tr.get(sc.COL_TIME_CLIENT_ID) or ""),
                            m_id_val,
                            m_id_val,
                            tr.get(sc.COL_TIME_HOURS),
                            tr.get(sc.COL_TIME_RATE),
                            tr.get(sc.COL_TIME_SHARE_PCT),
                            tr.get(sc.COL_TIME_TOTAL),
                            tr.get(sc.COL_TIME_DESC),
                            is_billed_flag,
                            matched_matter,
                        )
                        if compute_excel_prod:
                            if not is_billed_flag:
                                _accum_stat(productivity["unbilledWip"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if d_iso == today_iso:
                                _accum_stat(productivity["today"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if d_iso == yest_iso:
                                _accum_stat(productivity["yesterday"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if week_start_iso <= d_iso <= today_iso:
                                _accum_stat(productivity["thisWeek"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if last7_start_iso <= d_iso <= today_iso:
                                _accum_stat(productivity["last7Days"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if month_start_iso <= d_iso <= today_iso:
                                _accum_stat(productivity["thisMonth"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if last30_start_iso <= d_iso <= today_iso:
                                _accum_stat(productivity["last30Days"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if last_month_start_iso <= d_iso <= last_month_end_iso:
                                _accum_stat(productivity["lastMonth"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                            if ytd_start_iso <= d_iso <= today_iso:
                                _accum_stat(productivity["ytd"], d_item["hours"], d_item["feePreTax"], d_item["totalInclHst"])
                        if target_keys and m_id_val.upper() not in target_keys:
                            continue
                        if only_unbilled and is_billed_flag:
                            continue
                        if period_from and d_iso < period_from:
                            continue
                        if period_to and d_iso > period_to:
                            continue
                        matched_rows.append(d_item)
                    matched_rows.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
                    max_excel_rows = 800 if (period_from or only_unbilled or target_matter_ref) else 50
                    recent_dockets = matched_rows[:max_excel_rows]
                except Exception:
                    pass

        for d_item in recent_dockets:
            _accum_stat(
                productivity["filtered"],
                float(d_item.get("hours") or 0.0),
                float(d_item.get("feePreTax") or 0.0),
                float(d_item.get("totalInclHst") or 0.0),
            )

        for key_b, b_stat in productivity.items():
            if "daysSpan" not in b_stat:
                continue
            d_span = max(1.0, float(b_stat.get("daysSpan") or 1.0))
            b_stat["avgHoursPerDay"] = round(float(b_stat.get("hours") or 0.0) / d_span, 1)
            b_stat["avgFeePerDay"] = round(float(b_stat.get("feePreTax") or 0.0) / d_span, 2)
            if key_b == "ytd":
                b_stat["avgHoursPerMonth"] = round(float(b_stat.get("hours") or 0.0) / ytd_months_elapsed, 1)
                b_stat["avgFeePerMonth"] = round(float(b_stat.get("feePreTax") or 0.0) / ytd_months_elapsed, 2)

        productivity["annualProjection"] = self.compute_annual_earnings_projection(
            ytd_stat=productivity["ytd"],
            today_dt=today_dt,
        )

        matters.sort(
            key=lambda m: (
                str(m.get("clientName") or "").lower(),
                str(m.get("matterName") or "").lower(),
                str(m.get("matterNumber") or "").lower(),
            )
        )

        max_ret_rows = 800 if (period_from or only_unbilled or target_matter_ref) else 50
        return {
            "ok": True,
            "matters": matters,
            "recentMatters": recent_matters[:8],
            "recentDockets": recent_dockets[:max_ret_rows],
            "productivity": productivity,
        }

    @staticmethod
    def _estimate_2026_personal_tax_and_cpp(net_business_income: float) -> Dict[str, float]:
        """Calculate 2026 Canadian Federal + Ontario personal income tax, Ontario Surtax,
        Ontario Health Premium, and Self-Employed CPP (CPP1 + CPP2) on T2125 net income."""
        net_inc = max(0.0, float(net_business_income or 0.0))
        if net_inc <= 0.0:
            return {
                "cppTotal": 0.0,
                "cppDeduction": 0.0,
                "federalTax": 0.0,
                "ontarioTax": 0.0,
                "totalPersonalTaxAndCpp": 0.0,
            }

        # 1. 2026 Self-Employed CPP1 ($3,500 .. $71,300 @ 11.9%) & CPP2 ($71,300 .. $81,200 @ 8.0%)
        cpp1_earn = min(max(0.0, net_inc - 3500.0), 71300.0 - 3500.0)
        cpp1_total = round(cpp1_earn * 0.119, 2)
        cpp2_earn = min(max(0.0, net_inc - 71300.0), 81200.0 - 71300.0)
        cpp2_total = round(cpp2_earn * 0.08, 2)
        cpp_total = round(cpp1_total + cpp2_total, 2)
        cpp_deduction = round(cpp1_total * 0.5 + cpp2_total, 2)
        cpp_credit_base = round(cpp1_total * 0.5, 2)

        taxable = max(0.0, net_inc - cpp_deduction)

        # 2. 2026 Federal Progressive Tax Brackets (14.5% lowest rate)
        fed_brackets = [
            (57375.0, 0.145),
            (114750.0, 0.205),
            (177882.0, 0.26),
            (253414.0, 0.29),
            (float("inf"), 0.33),
        ]
        fed_gross = 0.0
        prev = 0.0
        for cap, rate in fed_brackets:
            if taxable <= prev:
                break
            slice_amt = min(taxable, cap) - prev
            fed_gross += slice_amt * rate
            prev = cap
        # Federal Basic Personal Amount (phased from $16,129 down to $14,538 above $177,882)
        if taxable <= 177882.0:
            fed_bpa = 16129.0
        elif taxable >= 253414.0:
            fed_bpa = 14538.0
        else:
            fed_bpa = 16129.0 - (16129.0 - 14538.0) * ((taxable - 177882.0) / (253414.0 - 177882.0))
        fed_credits = (fed_bpa + cpp_credit_base) * 0.145
        fed_tax = round(max(0.0, fed_gross - fed_credits), 2)

        # 3. 2026 Ontario Progressive Brackets + Surtax + Ontario Health Premium
        on_brackets = [
            (52886.0, 0.0505),
            (105775.0, 0.0915),
            (150000.0, 0.1116),
            (220000.0, 0.1216),
            (float("inf"), 0.1316),
        ]
        on_gross = 0.0
        prev_on = 0.0
        for cap, rate in on_brackets:
            if taxable <= prev_on:
                break
            slice_amt = min(taxable, cap) - prev_on
            on_gross += slice_amt * rate
            prev_on = cap
        on_bpa = 12747.0
        on_basic = max(0.0, on_gross - (on_bpa + cpp_credit_base) * 0.0505)
        on_surtax = 0.0
        if on_basic > 5710.0:
            on_surtax += (on_basic - 5710.0) * 0.20
        if on_basic > 7307.0:
            on_surtax += (on_basic - 7307.0) * 0.36
        if taxable <= 20000.0:
            ohp = 0.0
        elif taxable <= 36000.0:
            ohp = min(300.0, (taxable - 20000.0) * 0.06)
        elif taxable <= 48000.0:
            ohp = min(450.0, 300.0 + (taxable - 36000.0) * 0.06)
        elif taxable <= 72000.0:
            ohp = min(600.0, 450.0 + (taxable - 48000.0) * 0.25)
        elif taxable <= 200000.0:
            ohp = min(750.0, 600.0 + (taxable - 72000.0) * 0.25)
        else:
            ohp = min(900.0, 750.0 + (taxable - 200000.0) * 0.25)
        on_tax = round(on_basic + on_surtax + ohp, 2)

        total_tax_cpp = round(fed_tax + on_tax + cpp_total, 2)
        return {
            "cppTotal": cpp_total,
            "cppDeduction": cpp_deduction,
            "federalTax": fed_tax,
            "ontarioTax": on_tax,
            "totalPersonalTaxAndCpp": total_tax_cpp,
        }

    def compute_annual_earnings_projection(
        self,
        ytd_stat: Dict[str, Any],
        today_dt: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Compute full-year projected gross earnings (with & without HST),
        CSPM logged vs. estimated annual practice expenses, and estimated net earnings
        after expenses and taxes (both with Nov 1 PC cutover and 100% personal T2125)."""
        t_dt = today_dt or date.today()
        year = t_dt.year
        is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        days_in_year = 366 if is_leap else 365
        days_elapsed = max(1, (t_dt - date(year, 1, 1)).days + 1)
        days_remaining = max(0, days_in_year - days_elapsed)
        pct_year_elapsed = round((days_elapsed / float(days_in_year)) * 100.0, 1)
        annual_factor = float(days_in_year) / float(days_elapsed)

        # Nov 1, 2026 Cutover split (Jan 1 - Oct 31 SOLE_PROP vs Nov 1 - Dec 31 PC)
        cutover_dt = date(year, 11, 1)
        sole_prop_days = max(0, (cutover_dt - date(year, 1, 1)).days)
        pc_days = max(0, days_in_year - sole_prop_days)
        sole_prop_share = round(sole_prop_days / float(days_in_year), 6)
        pc_share = round(pc_days / float(days_in_year), 6)

        ytd_hours = round(float(ytd_stat.get("hours") or 0.0), 1)
        ytd_gross_no_hst = round(float(ytd_stat.get("feePreTax") or 0.0), 2)
        ytd_gross_with_hst = round(float(ytd_stat.get("totalInclHst") or 0.0), 2)
        if ytd_gross_with_hst <= 0.0 and ytd_gross_no_hst > 0.0:
            ytd_gross_with_hst = round(ytd_gross_no_hst * 1.13, 2)
        ytd_hst_collected = round(max(0.0, ytd_gross_with_hst - ytd_gross_no_hst), 2)

        proj_hours = round(ytd_hours * annual_factor, 1)
        proj_gross_no_hst = round(ytd_gross_no_hst * annual_factor, 2)
        proj_gross_with_hst = round(ytd_gross_with_hst * annual_factor, 2)
        proj_hst_collected = round(max(0.0, proj_gross_with_hst - proj_gross_no_hst), 2)

        # Gather CSPM logged YTD practice expenses in <2ms via SQLite cspm.db (never block on openpyxl)
        logged_sp_pre = 0.0
        logged_sp_itc = 0.0
        logged_pc_pre = 749.95  # Verified Oct 17, 2026 PC startup outlays (GIFI 2781)
        logged_pc_itc = 45.50
        db_path = self._resolve_sqlite_db_path()
        if db_path is not None and db_path.is_file():
            import sqlite3
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COALESCE(business_unit, ''), COALESCE(biller_entity, ''),
                           COALESCE(amount, 0.0), COALESCE(tax_amount, 0.0)
                    FROM TransactionMaster
                    WHERE substr(COALESCE(date, ''), 1, 4) = ?
                      AND LOWER(COALESCE(type, '')) = 'expense'
                      AND LOWER(COALESCE(status, 'posted')) NOT IN ('void', 'voided', 'deleted')
                    """,
                    (str(year),),
                )
                sp_found = False
                for bu, biller_e, amt_v, hst_v in cur.fetchall():
                    bu_low = str(bu or "").strip().lower()
                    b_up = str(biller_e or "").strip().upper()
                    if "cory" in bu_low or "legal" in bu_low or "law" in bu_low or b_up in ("SOLE_PROP", "PC"):
                        gross_f = float(amt_v or 0.0)
                        hst_f = float(hst_v or 0.0)
                        pre_f = round(max(0.0, gross_f - hst_f), 2)
                        if b_up == "PC":
                            pass  # Already seeded in logged_pc_pre ($749.95) unless exceeding startup outlays
                        else:
                            sp_found = True
                            logged_sp_pre = round(logged_sp_pre + pre_f, 2)
                            logged_sp_itc = round(logged_sp_itc + hst_f, 2)
                if not sp_found:
                    cur.execute(
                        """
                        SELECT SUM(COALESCE(expenses_excl_hst, 0.0)), SUM(COALESCE(hst_paid, 0.0))
                        FROM ledger
                        WHERE substr(COALESCE(date, ''), 1, 4) = ?
                        """,
                        (str(year),),
                    )
                    l_row = cur.fetchone()
                    if l_row and (l_row[0] or l_row[1]):
                        logged_sp_pre = round(float(l_row[0] or 0.0), 2)
                        logged_sp_itc = round(float(l_row[1] or 0.0), 2)
                conn.close()
            except Exception:
                pass

        logged_ytd_exp_pre = round(logged_sp_pre + logged_pc_pre, 2)
        logged_ytd_exp_itc = round(logged_sp_itc + logged_pc_itc, 2)
        logged_ytd_exp_gross = round(logged_ytd_exp_pre + logged_ytd_exp_itc, 2)

        annualized_logged_exp_pre = round(logged_ytd_exp_pre * annual_factor, 2)
        annualized_logged_exp_itc = round(logged_ytd_exp_itc * annual_factor, 2)
        annualized_logged_exp_gross = round(annualized_logged_exp_pre + annualized_logged_exp_itc, 2)

        # Default estimated full-year pre-tax practice expenses (while CSPM expense logging is being caught up)
        default_est_exp_pre = round(max(30000.0, annualized_logged_exp_pre), 2)
        default_est_exp_itc = round(default_est_exp_pre * 0.065, 2)  # ~50% of practice expenses subject to 13% HST (LSO/LAWPRO/Office vs Insurance/Gov fees)

        def _build_scenario(exp_pre_tax: float, exp_itc: float) -> Dict[str, Any]:
            net_before_tax = round(max(0.0, proj_gross_no_hst - exp_pre_tax), 2)
            # 1. Dual Entity (Jan-Oct SOLE_PROP T2125 + Nov-Dec PC @ 12.2% SBD)
            sp_net = round(net_before_tax * sole_prop_share, 2)
            pc_net = round(max(0.0, net_before_tax - sp_net), 2)
            sp_tax_info = self._estimate_2026_personal_tax_and_cpp(sp_net)
            pc_corp_tax = round(pc_net * 0.122, 2)
            dual_total_tax_cpp = round(sp_tax_info["totalPersonalTaxAndCpp"] + pc_corp_tax, 2)
            dual_net_after_tax = round(net_before_tax - dual_total_tax_cpp, 2)
            dual_eff_tax_rate = round((dual_total_tax_cpp / net_before_tax) * 100.0, 1) if net_before_tax > 0 else 0.0

            # 2. 100% Personal T2125 Equivalent (all 12 months taxed personally)
            pers_tax_info = self._estimate_2026_personal_tax_and_cpp(net_before_tax)
            pers_total_tax_cpp = pers_tax_info["totalPersonalTaxAndCpp"]
            pers_net_after_tax = round(net_before_tax - pers_total_tax_cpp, 2)
            pers_eff_tax_rate = round((pers_total_tax_cpp / net_before_tax) * 100.0, 1) if net_before_tax > 0 else 0.0

            pc_deferral_savings = round(max(0.0, pers_total_tax_cpp - dual_total_tax_cpp), 2)
            net_hst_remittance = round(max(0.0, proj_hst_collected - exp_itc), 2)

            return {
                "expensesPreTax": exp_pre_tax,
                "expensesHstItc": exp_itc,
                "expensesWithHst": round(exp_pre_tax + exp_itc, 2),
                "netBeforeTax": net_before_tax,
                "netHstRemittance": net_hst_remittance,
                "dualEntity": {
                    "solePropNetBeforeTax": sp_net,
                    "pcNetBeforeTax": pc_net,
                    "personalTaxAndCpp": sp_tax_info["totalPersonalTaxAndCpp"],
                    "cppTotal": sp_tax_info["cppTotal"],
                    "pcCorporateTax12_2Pct": pc_corp_tax,
                    "totalTaxAndCpp": dual_total_tax_cpp,
                    "effectiveTaxRatePct": dual_eff_tax_rate,
                    "netAfterTaxAndExpenses": dual_net_after_tax,
                    "monthlyNetAfterTax": round(dual_net_after_tax / 12.0, 2),
                    "pcTaxDeferralSavings": pc_deferral_savings,
                },
                "personalOnly": {
                    "totalTaxAndCpp": pers_total_tax_cpp,
                    "cppTotal": pers_tax_info["cppTotal"],
                    "effectiveTaxRatePct": pers_eff_tax_rate,
                    "netAfterTaxAndExpenses": pers_net_after_tax,
                    "monthlyNetAfterTax": round(pers_net_after_tax / 12.0, 2),
                },
            }

        return {
            "year": year,
            "asOfDate": t_dt.isoformat(),
            "daysInYear": days_in_year,
            "daysElapsed": days_elapsed,
            "daysRemaining": days_remaining,
            "pctYearElapsed": pct_year_elapsed,
            "annualizationFactor": round(annual_factor, 4),
            "solePropShareOfYear": sole_prop_share,
            "pcShareOfYear": pc_share,
            "ytdHours": ytd_hours,
            "ytdGrossWithoutHst": ytd_gross_no_hst,
            "ytdGrossWithHst": ytd_gross_with_hst,
            "ytdHstCollected": ytd_hst_collected,
            "projectedHours": proj_hours,
            "projectedGrossWithoutHst": proj_gross_no_hst,
            "projectedGrossWithHst": proj_gross_with_hst,
            "projectedHstCollected": proj_hst_collected,
            "loggedYtdExpensesPreTax": logged_ytd_exp_pre,
            "loggedYtdExpensesHstItc": logged_ytd_exp_itc,
            "loggedYtdExpensesWithHst": logged_ytd_exp_gross,
            "annualizedLoggedExpensesPreTax": annualized_logged_exp_pre,
            "annualizedLoggedExpensesHstItc": annualized_logged_exp_itc,
            "annualizedLoggedExpensesWithHst": annualized_logged_exp_gross,
            "defaultEstimatedExpensesPreTax": default_est_exp_pre,
            "defaultEstimatedExpensesHstItc": default_est_exp_itc,
            "estimatedScenario": _build_scenario(default_est_exp_pre, default_est_exp_itc),
            "loggedPaceScenario": _build_scenario(annualized_logged_exp_pre, annualized_logged_exp_itc),
        }

    def get_wip_and_ar_overview(self, user_id: str = "cory") -> Dict[str, Any]:
        """Return comprehensive Unbilled WIP (by Matter/Client) and Open A/R (by Aging & Client/Invoice) in <15ms."""
        if not self._is_cory(user_id):
            return {"ok": False, "message": "WIP & A/R overview is restricted to Cory."}

        today_dt = date.today()
        db_path = self._resolve_sqlite_db_path()

        wip_summary = {
            "matterCount": 0,
            "docketCount": 0,
            "hours": 0.0,
            "feePreTax": 0.0,
            "disbPreTax": 0.0,
            "totalPreTax": 0.0,
            "totalInclHst": 0.0,
        }
        ar_summary = {
            "invoiceCount": 0,
            "clientCount": 0,
            "totalInvoiced": 0.0,
            "totalPaid": 0.0,
            "balanceDue": 0.0,
            "b0_30": {"label": "0–30 Days (Current)", "count": 0, "balanceDue": 0.0},
            "b31_60": {"label": "31–60 Days", "count": 0, "balanceDue": 0.0},
            "b61_90": {"label": "61–90 Days", "count": 0, "balanceDue": 0.0},
            "b90_plus": {"label": "90+ Days Overdue", "count": 0, "balanceDue": 0.0},
        }
        wip_by_matter_map: Dict[str, Dict[str, Any]] = {}
        ar_invoices: List[Dict[str, Any]] = []
        ar_by_client_map: Dict[str, Dict[str, Any]] = {}

        if db_path is not None:
            import sqlite3
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                # 1. Load Matter directory lookup
                by_ref: Dict[str, Dict[str, Any]] = {}
                cur.execute(
                    """
                    SELECT matter_id, matter_number, matter_name, display_name, client_name, parent_id,
                           COALESCE(default_rate, hourly_rate, 475.0), COALESCE(default_share_pct, 100.0),
                           COALESCE(NULLIF(default_biller_entity, ''), NULLIF(default_biller, ''), 'SOLE_PROP')
                    FROM Matter
                    """
                )
                for mr in cur.fetchall():
                    m_id = str(mr[0] or "").strip()
                    m_num = str(mr[1] or m_id).strip()
                    m_name = str(mr[2] or mr[3] or "").strip()
                    c_name = str(mr[4] or "").strip()
                    p_name = str(mr[5] or "").strip()
                    info = {
                        "matterId": m_id or m_num,
                        "matterNumber": m_num,
                        "matterName": m_name,
                        "clientName": c_name,
                        "parentName": p_name,
                        "rate": float(mr[6] or 475.0),
                        "sharePct": float(mr[7] or 100.0),
                        "billerEntity": str(mr[8] or "SOLE_PROP"),
                    }
                    if m_id:
                        by_ref[m_id.upper()] = info
                    if m_num:
                        by_ref[m_num.upper()] = info
                    if m_name:
                        by_ref[m_name.upper()] = info

                # 2. Load all Unbilled TimeEntry rows
                cur.execute(
                    """
                    SELECT time_id, date, matter_id, matter_name, client_name, hours,
                           COALESCE(rate, 475.0), COALESCE(share_pct, 100.0), COALESCE(total_incl_hst, 0.0),
                           description, COALESCE(biller_entity, 'SOLE_PROP')
                    FROM TimeEntry
                    WHERE COALESCE(is_billed, 0) = 0 AND LOWER(COALESCE(status, 'Draft')) != 'billed'
                    ORDER BY date DESC, created_at DESC
                    """
                )
                for tr in cur.fetchall():
                    t_id = str(tr[0] or "").strip()
                    d_iso = str(tr[1] or "")[:10]
                    m_id_raw = str(tr[2] or "").strip()
                    m_name_raw = str(tr[3] or "").strip()
                    c_name_raw = str(tr[4] or "").strip()
                    hrs = round(float(tr[5] or 0.0), 2)
                    rate = float(tr[6] or 475.0)
                    share = float(tr[7] or 100.0)
                    fee = round(hrs * rate * (share / 100.0), 2)
                    tot_hst = round(float(tr[8] or 0.0), 2) or round(fee * 1.13, 2)
                    desc = str(tr[9] or "").strip()
                    biller = str(tr[10] or "SOLE_PROP").strip().upper()

                    matched = by_ref.get(m_id_raw.upper()) or by_ref.get(m_name_raw.upper())
                    m_num = (matched or {}).get("matterNumber") or m_name_raw or m_id_raw or "UNASSIGNED"
                    m_id_canon = (matched or {}).get("matterId") or m_id_raw or m_num
                    c_name = c_name_raw or (matched or {}).get("clientName") or m_num
                    m_title = (matched or {}).get("matterName") or m_name_raw or ""
                    key = m_num.upper()

                    if key not in wip_by_matter_map:
                        wip_by_matter_map[key] = {
                            "matterId": m_id_canon,
                            "matterNumber": m_num,
                            "matterName": m_title,
                            "clientName": c_name,
                            "billerEntity": (matched or {}).get("billerEntity") or biller,
                            "docketCount": 0,
                            "hours": 0.0,
                            "feePreTax": 0.0,
                            "disbPreTax": 0.0,
                            "totalPreTax": 0.0,
                            "totalInclHst": 0.0,
                            "lastDate": d_iso,
                            "dockets": [],
                        }
                    bucket = wip_by_matter_map[key]
                    bucket["docketCount"] = int(bucket["docketCount"]) + 1
                    bucket["hours"] = round(float(bucket["hours"]) + hrs, 2)
                    bucket["feePreTax"] = round(float(bucket["feePreTax"]) + fee, 2)
                    bucket["totalPreTax"] = round(float(bucket["totalPreTax"]) + fee, 2)
                    bucket["totalInclHst"] = round(float(bucket["totalInclHst"]) + tot_hst, 2)
                    if d_iso > str(bucket.get("lastDate") or ""):
                        bucket["lastDate"] = d_iso
                    bucket["dockets"].append(
                        {
                            "entryId": t_id,
                            "date": d_iso,
                            "clientName": c_name,
                            "matterId": m_id_canon,
                            "matterNumber": m_num,
                            "matterName": m_title,
                            "hours": hrs,
                            "rate": rate,
                            "sharePct": share,
                            "feePreTax": fee,
                            "totalInclHst": tot_hst,
                            "description": desc,
                            "isBilled": False,
                        }
                    )

                    wip_summary["docketCount"] = int(wip_summary["docketCount"]) + 1
                    wip_summary["hours"] = round(float(wip_summary["hours"]) + hrs, 2)
                    wip_summary["feePreTax"] = round(float(wip_summary["feePreTax"]) + fee, 2)
                    wip_summary["totalPreTax"] = round(float(wip_summary["totalPreTax"]) + fee, 2)
                    wip_summary["totalInclHst"] = round(float(wip_summary["totalInclHst"]) + tot_hst, 2)

                # 3. Check unbilled disbursements (no invoice_ref)
                try:
                    cur.execute(
                        """
                        SELECT client_name, matter_id, description, COALESCE(amount, 0.0), date
                        FROM disbursements
                        WHERE TRIM(COALESCE(invoice_ref, '')) = ''
                          AND LOWER(TRIM(COALESCE(payment_status, ''))) NOT IN ('billed', 'paid')
                        """
                    )
                    for dr in cur.fetchall():
                        d_client = str(dr[0] or "").strip()
                        d_m_id = str(dr[1] or "").strip()
                        d_amt = round(float(dr[3] or 0.0), 2)
                        if d_amt <= 0:
                            continue
                        matched = by_ref.get(d_m_id.upper())
                        m_num = (matched or {}).get("matterNumber") or d_m_id or d_client or "UNASSIGNED"
                        key = m_num.upper()
                        if key not in wip_by_matter_map:
                            wip_by_matter_map[key] = {
                                "matterId": (matched or {}).get("matterId") or d_m_id or m_num,
                                "matterNumber": m_num,
                                "matterName": (matched or {}).get("matterName") or "",
                                "clientName": d_client or (matched or {}).get("clientName") or m_num,
                                "billerEntity": (matched or {}).get("billerEntity") or "SOLE_PROP",
                                "docketCount": 0,
                                "hours": 0.0,
                                "feePreTax": 0.0,
                                "disbPreTax": 0.0,
                                "totalPreTax": 0.0,
                                "totalInclHst": 0.0,
                                "lastDate": str(dr[4] or "")[:10],
                                "dockets": [],
                            }
                        bucket = wip_by_matter_map[key]
                        bucket["disbPreTax"] = round(float(bucket["disbPreTax"]) + d_amt, 2)
                        bucket["totalPreTax"] = round(float(bucket["totalPreTax"]) + d_amt, 2)
                        bucket["totalInclHst"] = round(float(bucket["totalInclHst"]) + d_amt, 2)
                        wip_summary["disbPreTax"] = round(float(wip_summary["disbPreTax"]) + d_amt, 2)
                        wip_summary["totalPreTax"] = round(float(wip_summary["totalPreTax"]) + d_amt, 2)
                        wip_summary["totalInclHst"] = round(float(wip_summary["totalInclHst"]) + d_amt, 2)
                except Exception:
                    pass

                # 4. Load Open A/R from Receivable + Invoice
                cur.execute(
                    """
                    SELECT r.invoice_id, r.client_name, r.work_client, r.date,
                           COALESCE(r.total_invoiced, 0.0), COALESCE(r.amount_due, 0.0),
                           COALESCE(r.amount_paid, 0.0), COALESCE(r.status, 'Open'),
                           COALESCE(r.biller_entity, i.biller_entity, 'SOLE_PROP'),
                           COALESCE(i.matter_id, ''), COALESCE(i.sub_client, '')
                    FROM Receivable r
                    LEFT JOIN Invoice i ON r.invoice_id = i.invoice_num
                    WHERE COALESCE(r.amount_due, 0.0) > 0.009
                      AND LOWER(COALESCE(r.status, '')) NOT IN ('paid', 'void', 'reversed', 'cancelled')
                    ORDER BY r.date DESC, r.invoice_id DESC
                    """
                )
                for ar_r in cur.fetchall():
                    inv_num = str(ar_r[0] or "").strip()
                    billing_client = str(ar_r[1] or "").strip()
                    work_client = str(ar_r[2] or ar_r[10] or billing_client).strip()
                    inv_date = str(ar_r[3] or "")[:10]
                    tot_inv = round(float(ar_r[4] or 0.0), 2)
                    bal_due = round(float(ar_r[5] or 0.0), 2)
                    amt_paid = round(float(ar_r[6] or 0.0), 2)
                    st_str = str(ar_r[7] or "Open").strip()
                    biller = str(ar_r[8] or "SOLE_PROP").strip().upper()
                    matter_ref = str(ar_r[9] or "").strip()

                    try:
                        age_days = max(0, (today_dt - date.fromisoformat(inv_date)).days)
                    except Exception:
                        age_days = 0

                    if age_days <= 30:
                        bucket_key = "b0_30"
                        bucket_label = "0–30d"
                    elif age_days <= 60:
                        bucket_key = "b31_60"
                        bucket_label = "31–60d"
                    elif age_days <= 90:
                        bucket_key = "b61_90"
                        bucket_label = "61–90d"
                    else:
                        bucket_key = "b90_plus"
                        bucket_label = "90+d"

                    ar_summary["invoiceCount"] = int(ar_summary["invoiceCount"]) + 1
                    ar_summary["totalInvoiced"] = round(float(ar_summary["totalInvoiced"]) + tot_inv, 2)
                    ar_summary["totalPaid"] = round(float(ar_summary["totalPaid"]) + amt_paid, 2)
                    ar_summary["balanceDue"] = round(float(ar_summary["balanceDue"]) + bal_due, 2)
                    ar_summary[bucket_key]["count"] = int(ar_summary[bucket_key]["count"]) + 1
                    ar_summary[bucket_key]["balanceDue"] = round(float(ar_summary[bucket_key]["balanceDue"]) + bal_due, 2)

                    client_disp = (
                        f"{work_client} (via {billing_client})"
                        if work_client and billing_client and work_client.lower() != billing_client.lower()
                        else (billing_client or work_client)
                    )
                    inv_obj = {
                        "invoiceNumber": inv_num,
                        "date": inv_date,
                        "billingClient": billing_client,
                        "workClient": work_client,
                        "clientDisplay": client_disp,
                        "matterRef": matter_ref,
                        "ageDays": age_days,
                        "bucketKey": bucket_key,
                        "bucketLabel": bucket_label,
                        "totalInvoiced": tot_inv,
                        "amountPaid": amt_paid,
                        "balanceDue": bal_due,
                        "status": st_str,
                        "billerEntity": biller,
                    }
                    ar_invoices.append(inv_obj)

                    grp_key = (billing_client or work_client or "Other").strip()
                    if grp_key not in ar_by_client_map:
                        ar_by_client_map[grp_key] = {
                            "clientName": grp_key,
                            "invoiceCount": 0,
                            "totalInvoiced": 0.0,
                            "balanceDue": 0.0,
                            "oldestAgeDays": 0,
                            "invoices": [],
                        }
                    c_grp = ar_by_client_map[grp_key]
                    c_grp["invoiceCount"] = int(c_grp["invoiceCount"]) + 1
                    c_grp["totalInvoiced"] = round(float(c_grp["totalInvoiced"]) + tot_inv, 2)
                    c_grp["balanceDue"] = round(float(c_grp["balanceDue"]) + bal_due, 2)
                    if age_days > int(c_grp["oldestAgeDays"]):
                        c_grp["oldestAgeDays"] = age_days
                    c_grp["invoices"].append(inv_obj)

                conn.close()
            except Exception as exc:
                logger.warning("get_wip_and_ar_overview warning: %s", exc)

        wip_by_matter = sorted(
            wip_by_matter_map.values(),
            key=lambda x: (float(x.get("totalPreTax") or 0.0), float(x.get("hours") or 0.0)),
            reverse=True,
        )
        wip_summary["matterCount"] = len(wip_by_matter)

        ar_by_client = sorted(
            ar_by_client_map.values(),
            key=lambda x: float(x.get("balanceDue") or 0.0),
            reverse=True,
        )
        ar_summary["clientCount"] = len(ar_by_client)

        return {
            "ok": True,
            "wipSummary": wip_summary,
            "wipByMatter": wip_by_matter,
            "arSummary": ar_summary,
            "arByClient": ar_by_client,
            "arInvoices": ar_invoices,
            "combinedPipeline": {
                "preTaxWipPlusAr": round(float(wip_summary["totalPreTax"]) + float(ar_summary["balanceDue"]), 2),
                "inclHstWipPlusAr": round(float(wip_summary["totalInclHst"]) + float(ar_summary["balanceDue"]), 2),
            },
        }

    def save_docket_entry(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update a time docket entry (Cory-only) across CSPM (cspm.db + CSPM.xlsm) AND Legacy Dockets.xlsm."""
        if not self._is_cory(user_id):
            return {"ok": False, "message": "Docketing is restricted to Cory."}

        raw_entry_id = str(payload.get("entryId") or payload.get("timeId") or "").strip() or None
        is_update = bool(raw_entry_id)
        matter_ref = str(payload.get("matterNumber") or payload.get("matterId") or payload.get("matter") or "").strip()
        date_str = str(payload.get("date") or payload.get("txnDate") or date.today().isoformat()).strip()
        description = str(payload.get("description") or "").strip()
        try:
            hours = round(float(payload.get("hours") or 0.0), 2)
        except Exception:
            hours = 0.0

        rate_raw = payload.get("rate")
        rate_override = float(rate_raw) if rate_raw not in (None, "") else None
        share_raw = payload.get("sharePct")
        share_override = float(share_raw) if share_raw not in (None, "") else None

        if not matter_ref:
            return {"ok": False, "message": "Please select a Matter first."}
        if hours <= 0:
            return {"ok": False, "message": "Please enter hours greater than 0 (e.g. 0.2, 0.5, 1.5)."}
        if not description:
            return {"ok": False, "message": "Please enter a docket narrative description."}

        add_docket_script = Path.home() / ".gemini" / "config" / "skills" / "cspm-docket" / "scripts" / "add_docket.py"
        is_isolated_test = self._is_isolated_test()
        verb = "updated" if is_update else "saved"

        # Fast-path (<30ms) for live mobile/desktop server:
        # 1. Immediately commit to cspm.db (TimeEntry & time_entries) so the phone gets an instant <50ms confirmation
        #    and live productivity / recent dockets reflect the change immediately.
        # 2. Spawn a non-blocking background worker thread on the server to finish updating CSPM.xlsm & Dockets.xlsm
        #    even if the user refreshes the phone screen, backs out, or closes the browser.
        db_paths = self._all_sqlite_db_paths()
        if not is_isolated_test and db_paths:
            import secrets
            import sqlite3
            entry_id = raw_entry_id or f"T_{secrets.token_hex(5)}"
            matched_m: Optional[Dict[str, Any]] = None
            prev_description: Optional[str] = None
            try:
                conn0 = sqlite3.connect(str(db_paths[0]))
                cur0 = conn0.cursor()
                cur0.execute(
                    """
                    SELECT m.matter_id, m.matter_number, m.matter_name, m.display_name,
                           m.client_id, m.client_name, m.parent_id,
                           COALESCE(m.default_rate, m.hourly_rate, 475.0) AS rate,
                           COALESCE(m.default_share_pct, 100.0) AS share_pct,
                           COALESCE(NULLIF(m.default_biller_entity, ''), NULLIF(m.default_biller, ''), 'SOLE_PROP') AS biller
                    FROM Matter m
                    WHERE UPPER(TRIM(COALESCE(m.matter_number, ''))) = UPPER(?)
                       OR UPPER(TRIM(COALESCE(m.matter_id, ''))) = UPPER(?)
                    LIMIT 1
                    """,
                    (matter_ref, matter_ref),
                )
                cols0 = [d[0] for d in cur0.description]
                r0 = cur0.fetchone()
                if r0:
                    matched_m = dict(zip(cols0, r0))
                if is_update:
                    cur0.execute("SELECT description FROM TimeEntry WHERE time_id = ?", (entry_id,))
                    pr = cur0.fetchone()
                    if pr and pr[0]:
                        prev_description = str(pr[0]).strip()
                conn0.close()
            except Exception as exc:
                logger.warning("Fast SQLite matter lookup warning: %s", exc)

            if matched_m:
                matter_id = str(matched_m.get("matter_id") or matter_ref)
                matter_number = str(matched_m.get("matter_number") or matter_id)
                client_id = str(matched_m.get("client_id") or "")
                client_name = str(matched_m.get("client_name") or matter_number)
                parent_id = str(matched_m.get("parent_id") or "")
                rate = float(rate_override if rate_override is not None else (matched_m.get("rate") or 475.0))
                share_pct = float(share_override if share_override is not None else (matched_m.get("share_pct") or 100.0))
                if 0 < share_pct <= 1.0:
                    share_pct = share_pct * 100.0
                biller_entity = str(matched_m.get("biller") or "SOLE_PROP")

                raw_seconds = int(round(hours * 3600))
                rate_cents = int(round(rate * 100))
                amount = round(hours * rate, 2)
                amount_cents = int(round(amount * 100))
                amount_to_you = round(amount * (share_pct / 100.0), 2)
                amount_to_you_cents = int(round(amount_to_you * 100))
                hst = round(amount_to_you * 0.13, 2)
                hst_cents = int(round(hst * 100))
                total_incl_hst = round(amount_to_you + hst, 2)
                total_incl_hst_cents = int(round(total_incl_hst * 100))
                now_utc = datetime.now().isoformat()
                row_sig = json.dumps(
                    {
                        "date": date_str,
                        "description": description,
                        "matter_id": matter_number,
                        "raw_seconds": raw_seconds,
                        "time_hrs": hours,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )

                with self._lock:
                    for db_p in db_paths:
                        try:
                            conn = sqlite3.connect(str(db_p))
                            cur = conn.cursor()
                            cur.execute("DELETE FROM TimeEntry WHERE time_id = ?", (entry_id,))
                            try:
                                cur.execute("DELETE FROM time_entries WHERE entry_id = ? OR time_id = ?", (entry_id, entry_id))
                            except Exception:
                                pass
                            cur.execute(
                                """
                                INSERT INTO TimeEntry (
                                    time_id, matter_id, matter_name, client_id, client_name, parent_id,
                                    date, hours, raw_seconds, rate, rate_cents, share_pct,
                                    amount, amount_cents, amount_to_you, amount_to_you_cents,
                                    hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                                    description, status, entry_status, started_at_utc, last_heartbeat_utc,
                                    legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                                    is_billed, billed_invoice_id, biller_entity, created_at, updated_at
                                ) VALUES (
                                    ?, ?, ?, ?, ?, ?,
                                    ?, ?, ?, ?, ?, ?,
                                    ?, ?, ?, ?,
                                    ?, ?, ?, ?,
                                    ?, ?, ?, ?, ?,
                                    ?, ?, ?,
                                    ?, ?, ?, ?, ?
                                )
                                """,
                                (
                                    entry_id, matter_id, matter_number, client_id, client_name, parent_id,
                                    date_str, hours, raw_seconds, rate, rate_cents, share_pct,
                                    amount, amount_cents, amount_to_you, amount_to_you_cents,
                                    hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                                    description, "Draft", "SAVED", None, now_utc,
                                    "SYNCED", now_utc, row_sig,
                                    0, "", biller_entity, now_utc, now_utc,
                                ),
                            )
                            try:
                                cur.execute(
                                    """
                                    INSERT INTO time_entries (
                                        entry_id, time_id, matter_id, matter_name, client_id, client_name, parent_id,
                                        date, hours, raw_seconds, rate, rate_cents, share_pct,
                                        amount, amount_cents, amount_to_you, amount_to_you_cents,
                                        hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                                        description, status, entry_status, started_at_utc, last_heartbeat_utc,
                                        legacy_dockets_sync_status, legacy_dockets_synced_at, legacy_dockets_row_signature,
                                        is_billed, billed_invoice_id, biller_entity, created_at, updated_at
                                    ) VALUES (
                                        ?, ?, ?, ?, ?, ?, ?,
                                        ?, ?, ?, ?, ?, ?,
                                        ?, ?, ?, ?,
                                        ?, ?, ?, ?,
                                        ?, ?, ?, ?, ?,
                                        ?, ?, ?,
                                        ?, ?, ?, ?, ?
                                    )
                                    """,
                                    (
                                        entry_id, entry_id, matter_id, matter_number, client_id, client_name, parent_id,
                                        date_str, hours, raw_seconds, rate, rate_cents, share_pct,
                                        amount, amount_cents, amount_to_you, amount_to_you_cents,
                                        hst, hst_cents, total_incl_hst, total_incl_hst_cents,
                                        description, "Draft", "SAVED", None, now_utc,
                                        "SYNCED", now_utc, row_sig,
                                        0, "", biller_entity, now_utc, now_utc,
                                    ),
                                )
                            except Exception:
                                pass
                            conn.commit()
                            conn.close()
                        except Exception as exc:
                            logger.warning("Fast SQLite insert warning (%s): %s", db_p, exc)

                summary = {
                    "entry_id": entry_id,
                    "date": date_str,
                    "client_id": client_id,
                    "client_name": client_name,
                    "matter_id": matter_id,
                    "matter_number": matter_number,
                    "parent_id": parent_id,
                    "hours": hours,
                    "raw_seconds": raw_seconds,
                    "rate": rate,
                    "share_pct": share_pct,
                    "amount": amount,
                    "amount_to_you": amount_to_you,
                    "hst": hst,
                    "total_incl_hst": total_incl_hst,
                    "biller_entity": biller_entity,
                    "description": description,
                }

                def _bg_sync_docket_workbooks() -> None:
                    with self._lock:
                        try:
                            if prev_description and prev_description != description and db_paths:
                                try:
                                    c_tmp = sqlite3.connect(str(db_paths[0]))
                                    c_tmp.execute("UPDATE TimeEntry SET description = ? WHERE time_id = ?", (prev_description, entry_id))
                                    c_tmp.commit()
                                    c_tmp.close()
                                except Exception:
                                    pass
                            if add_docket_script.is_file():
                                import importlib.util
                                try:
                                    import pythoncom
                                    pythoncom.CoInitialize()
                                except Exception:
                                    pass
                                spec = importlib.util.spec_from_file_location("cspm_add_docket_skill", str(add_docket_script))
                                if spec and spec.loader:
                                    mod = importlib.util.module_from_spec(spec)
                                    spec.loader.exec_module(mod)
                                    mod.add_docket(
                                        matter_ref=matter_number,
                                        date_str=date_str,
                                        hours=hours,
                                        description=description,
                                        rate_override=rate_override,
                                        share_pct_override=share_override,
                                        entry_id=entry_id,
                                        dry_run=False,
                                    )
                        except Exception as bg_exc:
                            logger.warning("Background docket workbook sync warning: %s", bg_exc)

                threading.Thread(
                    target=_bg_sync_docket_workbooks,
                    name=f"DocketWorkbookSync-{entry_id}",
                    daemon=True,
                ).start()

                try:
                    self.session_tracker.record_event(
                        "cory",
                        "DOCKET_POST",
                        f"Logged docket: {client_name} ({matter_number}) - {hours:.2f}h - {description[:40]}",
                        item_data={
                            "matter": matter_number,
                            "hours": hours,
                            "narrative": description,
                            "date": date_str,
                            "rate": rate,
                        },
                    )
                except Exception:
                    pass

                return {
                    "ok": True,
                    "entryId": entry_id,
                    "updated": is_update,
                    "summary": summary,
                    "syncedLegacyDockets": True,
                    "backgroundSyncQueued": True,
                    "message": (
                        f"Docket {verb}: {client_name} ({matter_number}) · "
                        f"{hours:.1f}h · ${amount_to_you:,.2f} fee (${total_incl_hst:,.2f} w/ HST)"
                    ),
                }

        with self._lock:
            entry_id = raw_entry_id
            if add_docket_script.is_file() and not is_isolated_test:
                try:
                    import importlib.util
                    try:
                        import pythoncom
                        pythoncom.CoInitialize()
                    except Exception:
                        pass
                    spec = importlib.util.spec_from_file_location("cspm_add_docket_skill", str(add_docket_script))
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        summary = mod.add_docket(
                            matter_ref=matter_ref,
                            date_str=date_str,
                            hours=hours,
                            description=description,
                            rate_override=rate_override,
                            share_pct_override=share_override,
                            entry_id=entry_id,
                            dry_run=False,
                        )
                        try:
                            self.session_tracker.record_event(
                                "cory",
                                "DOCKET_POST",
                                f"Logged docket: {summary.get('client_name')} ({summary.get('matter_number')}) - {hours:.2f}h - {description[:40]}",
                                item_data={
                                    "matter": summary.get("matter_number") or matter_ref,
                                    "hours": hours,
                                    "narrative": description,
                                    "date": date_str,
                                    "rate": rate_override or 475.0,
                                },
                            )
                        except Exception:
                            pass
                        return {
                            "ok": True,
                            "entryId": summary.get("entry_id"),
                            "updated": bool(entry_id),
                            "summary": summary,
                            "syncedLegacyDockets": True,
                            "message": (
                                f"Docket {verb} in CSPM + Legacy Dockets.xlsm: "
                                f"{summary.get('client_name')} ({summary.get('matter_number')}) · "
                                f"{hours:.1f}h · ${float(summary.get('total_incl_hst') or 0.0):,.2f}"
                            ),
                        }
                except Exception as exc:
                    logger.warning("add_docket.py skill fallback to ExcelRepo: %s", exc)

            # Fallback / isolated test environment via ExcelRepo
            if entry_id:
                upd_changes: Dict[str, Any] = {
                    "date": date_str,
                    "hours": hours,
                    "rawSeconds": int(round(hours * 3600)),
                    "description": description,
                }
                if rate_override is not None:
                    upd_changes["rate"] = rate_override
                if share_override is not None:
                    upd_changes["sharePct"] = share_override
                upd_res = self.repo.update_time_entry(entry_id, upd_changes)
                if upd_res.get("ok"):
                    return {
                        "ok": True,
                        "entryId": entry_id,
                        "updated": True,
                        "savedRow": upd_res.get("updatedRow"),
                        "syncedLegacyDockets": True,
                        "message": f"Docket {entry_id} updated ({hours:.1f}h) in CSPM & Legacy Dockets.",
                    }

            client_name = str(payload.get("clientName") or "").strip()
            parent_name = str(payload.get("parentName") or "").strip()
            matter_name = str(payload.get("matterName") or "").strip()
            if not client_name or not matter_name:
                for m in self.repo.list_active_matter_directory():
                    if str(m.get("matterId") or "").lower() == matter_ref.lower() or str(m.get("matterNumber") or "").lower() == matter_ref.lower():
                        client_name = client_name or str(m.get("clientName") or "")
                        parent_name = parent_name or str(m.get("parentName") or "")
                        matter_name = matter_name or str(m.get("matterName") or m.get("matterNumber") or "")
                        break
            res = self.repo.add_time_entry(
                {
                    "entryId": entry_id,
                    "date": date_str,
                    "clientName": client_name or matter_ref,
                    "parentName": parent_name,
                    "matterId": matter_ref,
                    "matterName": matter_name or matter_ref,
                    "allowClientOnlyDraft": 1,
                    "hours": hours,
                    "useExactHours": True,
                    "rawSeconds": int(round(hours * 3600)),
                    "rawSecondsMode": "replace",
                    "clientRate": rate_override or 475.0,
                    "sharePct": share_override or 100.0,
                    "description": description,
                    "forceDuplicate": True,
                }
            )
            if not res.get("ok"):
                return {"ok": False, "message": res.get("message") or "Could not save docket entry."}
            return {
                "ok": True,
                "entryId": res.get("entryId"),
                "updated": bool(entry_id),
                "savedRow": res.get("savedRow"),
                "syncedLegacyDockets": True,
                "message": f"Docket {verb} ({hours:.1f}h) in CSPM & Legacy Dockets.",
            }

    def delete_docket_entry(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a time docket entry (Cory-only) across CSPM (cspm.db + CSPM.xlsm) AND Legacy Dockets.xlsm."""
        if not self._is_cory(user_id):
            return {"ok": False, "message": "Docketing is restricted to Cory."}

        entry_id = str(payload.get("entryId") or payload.get("timeId") or "").strip()
        if not entry_id:
            return {"ok": False, "message": "Missing docket entryId to delete."}

        fb_payload = dict(payload or {})
        deleted_sqlite_raw = False
        is_isolated_test = self._is_isolated_test()

        with self._lock:
            import sqlite3
            for db_p in self._all_sqlite_db_paths():
                try:
                    conn = sqlite3.connect(str(db_p))
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT date, matter_id, matter_name, client_name, hours, raw_seconds,
                               description, COALESCE(is_billed, 0), COALESCE(status, 'Draft')
                        FROM TimeEntry
                        WHERE time_id = ?
                        """,
                        (entry_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        if bool(row[7]) or str(row[8] or "").strip().lower() == "billed":
                            conn.close()
                            return {
                                "ok": False,
                                "message": "Cannot delete a docket entry that has already been billed on an invoice.",
                            }
                        fb_payload.setdefault("date", str(row[0] or ""))
                        fb_payload.setdefault("matterId", str(row[1] or ""))
                        fb_payload.setdefault("matterNumber", str(row[2] or row[1] or ""))
                        fb_payload.setdefault("clientName", str(row[3] or ""))
                        fb_payload.setdefault("hours", float(row[4] or 0.0))
                        fb_payload.setdefault("rawSeconds", int(row[5] or 0))
                        fb_payload.setdefault("description", str(row[6] or ""))
                    cur.execute("DELETE FROM TimeEntry WHERE time_id = ?", (entry_id,))
                    if cur.rowcount > 0:
                        deleted_sqlite_raw = True
                    try:
                        cur.execute("DELETE FROM time_entries WHERE entry_id = ? OR time_id = ?", (entry_id, entry_id))
                        if cur.rowcount > 0:
                            deleted_sqlite_raw = True
                    except Exception:
                        pass
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    logger.warning("SQLite delete_docket_entry warning (%s): %s", db_p, exc)

            if not is_isolated_test and deleted_sqlite_raw:
                def _bg_delete_docket_workbooks() -> None:
                    with self._lock:
                        try:
                            self.repo.delete_time_entry(
                                entry_id,
                                remove_from_legacy_dockets=True,
                                fallback_payload=fb_payload,
                            )
                            master_dir = self.paths.master_data_dir()
                            master_xlsm = (master_dir / "CSPM.xlsm") if master_dir else None
                            if master_xlsm and master_xlsm.is_file():
                                if master_xlsm.resolve() != Path(self.repo.workbook_path).resolve():
                                    master_paths = AppPaths(root=self.paths.root, override_data_dir=master_dir)
                                    master_repo = ExcelRepo(master_paths)
                                    import domain.schema_constants as sc
                                    from repositories.excel_repo import TBL_TIME as EXCEL_TBL_TIME
                                    master_repo._delete_row_by_key_hard(EXCEL_TBL_TIME, sc.COL_TIME_ENTRY_ID, entry_id)
                        except Exception as bg_exc:
                            logger.warning("Background docket workbook delete warning: %s", bg_exc)

                threading.Thread(
                    target=_bg_delete_docket_workbooks,
                    name=f"DocketWorkbookDelete-{entry_id}",
                    daemon=True,
                ).start()

                return {
                    "ok": True,
                    "entryId": entry_id,
                    "deletedSqlite": True,
                    "deletedExcel": True,
                    "backgroundSyncQueued": True,
                    "summary": fb_payload,
                    "message": "Docket deleted from CSPM & Legacy Dockets.",
                }

            del_res = self.repo.delete_time_entry(
                entry_id,
                remove_from_legacy_dockets=True,
                fallback_payload=fb_payload,
            )

            # Also ensure master_data_dir/CSPM.xlsm has the row removed if distinct from self.repo.workbook_path
            deleted_master_xlsm = False
            if not is_isolated_test:
                master_dir = self.paths.master_data_dir()
                master_xlsm = (master_dir / "CSPM.xlsm") if master_dir else None
                if master_xlsm and master_xlsm.is_file():
                    try:
                        if master_xlsm.resolve() != Path(self.repo.workbook_path).resolve():
                            master_paths = AppPaths(root=self.paths.root, override_data_dir=master_dir)
                            master_repo = ExcelRepo(master_paths)
                            import domain.schema_constants as sc
                            from repositories.excel_repo import TBL_TIME as EXCEL_TBL_TIME
                            deleted_master_xlsm = bool(
                                master_repo._delete_row_by_key_hard(EXCEL_TBL_TIME, sc.COL_TIME_ENTRY_ID, entry_id)
                            )
                    except Exception:
                        pass

            if del_res.get("ok") or deleted_sqlite_raw or deleted_master_xlsm:
                return {
                    "ok": True,
                    "entryId": entry_id,
                    "deletedSqlite": deleted_sqlite_raw or bool(del_res.get("deletedSqlite")),
                    "deletedExcel": bool(del_res.get("deletedExcel")) or deleted_master_xlsm,
                    "summary": fb_payload,
                    "message": "Docket deleted from CSPM & Legacy Dockets.",
                }
            return {
                "ok": False,
                "message": del_res.get("message") or f"Docket {entry_id} not found.",
            }

    # ------------------------------------------------------------------
    # 8. Invoice Payment Lookup & Recording (Both Cory and Deborah)
    # ------------------------------------------------------------------
    def _load_ar_invoice_snapshot(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            if self._cached_ar_snapshot is not None and not force_refresh:
                return list(self._cached_ar_snapshot)

            as_of_date = date.today().isoformat()
            report = self.repo.ar_aging_report(
                {
                    "asOfDate": as_of_date,
                    "query": "",
                    "groupBy": "client",
                }
            )
            if not report.get("ok"):
                return []

            try:
                matter_by_invoice = self.repo._payment_invoice_matter_contexts(as_of_date)
            except Exception:
                matter_by_invoice = {}

            excluded_statuses = {
                "void", "voided", "cancelled", "canceled",
                "reversed", "reversal", "superseded",
            }
            snapshot: List[Dict[str, Any]] = []
            seen_invoices: set[str] = set()
            for row in list(report.get("rows") or []):
                invoice = str(row.get("invoice") or "").strip()
                if not invoice:
                    continue
                status = str(row.get("status") or "Open").strip()
                if status.casefold() in excluded_statuses:
                    continue
                seen_invoices.add(invoice.casefold())
                client = str(row.get("client") or "").strip()
                billing_client = str(row.get("billingClient") or client).strip()
                work_client = str(row.get("workClient") or client).strip()
                invoice_total = float(self.repo._money_round(row.get("invoiceTotal")))
                paid = float(self.repo._money_round(row.get("paid")))
                credits = float(self.repo._money_round(row.get("credits")))
                balance = float(self.repo._money_round(row.get("balance")))
                matter = str(matter_by_invoice.get(invoice.casefold()) or row.get("matter") or "").strip()
                is_open = balance > 0.005 and status.casefold() not in {"paid", "closed"}
                snapshot.append(
                    {
                        "invoice": invoice,
                        "invoiceNumber": invoice,
                        "date": str(row.get("date") or ""),
                        "client": client,
                        "workClient": work_client,
                        "billingClient": billing_client,
                        "matter": matter,
                        "matterDescription": matter,
                        "status": "Open" if is_open else "Paid",
                        "isOpen": is_open,
                        "ageDays": int(row.get("ageDays") or 0),
                        "bucketLabel": str(row.get("bucketLabel") or ""),
                        "invoiceTotal": invoice_total,
                        "invoiceTotalFormatted": f"${invoice_total:,.2f}",
                        "paid": paid,
                        "paidFormatted": f"${paid:,.2f}",
                        "credits": credits,
                        "balance": balance,
                        "balanceFormatted": f"${balance:,.2f}",
                        "display": f"{invoice} | {work_client or billing_client} | Bal: ${balance:,.2f}",
                    }
                )

            # Also append settled/paid invoices from tblReceivables so 'include_paid=True' finds them
            try:
                for r in self.repo.list_receivables():
                    invoice = str(r.get("invoiceNum") or "").strip()
                    if not invoice or invoice.casefold() in seen_invoices:
                        continue
                    status = str(r.get("status") or "Paid").strip()
                    if status.casefold() in excluded_statuses:
                        continue
                    seen_invoices.add(invoice.casefold())
                    billing_client = str(r.get("client") or "").strip()
                    work_client = str(r.get("workClient") or billing_client).strip()
                    invoice_total = float(self.repo._money_round(r.get("totalInvoiced")))
                    paid = float(self.repo._money_round(r.get("amountPaid")))
                    credits = float(self.repo._money_round(r.get("writeOff")))
                    balance = float(self.repo._money_round(r.get("balanceDue")))
                    matter = str(matter_by_invoice.get(invoice.casefold()) or "").strip()
                    is_open = balance > 0.005 and status.casefold() not in {"paid", "closed"}
                    snapshot.append(
                        {
                            "invoice": invoice,
                            "invoiceNumber": invoice,
                            "date": str(r.get("invoiceDate") or ""),
                            "client": work_client or billing_client,
                            "workClient": work_client or billing_client,
                            "billingClient": billing_client or work_client,
                            "matter": matter,
                            "matterDescription": matter,
                            "status": "Open" if is_open else "Paid",
                            "isOpen": is_open,
                            "ageDays": 0,
                            "bucketLabel": "Paid" if not is_open else "0-30",
                            "invoiceTotal": invoice_total,
                            "invoiceTotalFormatted": f"${invoice_total:,.2f}",
                            "paid": paid,
                            "paidFormatted": f"${paid:,.2f}",
                            "credits": credits,
                            "balance": balance,
                            "balanceFormatted": f"${balance:,.2f}",
                            "display": f"{invoice} | {work_client or billing_client} | Bal: ${balance:,.2f}",
                        }
                    )
            except Exception:
                pass

            self._cached_ar_snapshot = snapshot
            return list(snapshot)

    def search_payment_invoices(
        self,
        user_id: str = "deborah",
        query: str = "",
        party_type: str = "",
        party_value: str = "",
        include_paid: bool = False,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Search invoices using CSPM's 4-way Payment Entry matcher:
        1. Dollar Amount (±5% tolerance on Balance Due OR Invoice Total)
        2. Client (workClient / client)
        3. Billing Client (billingClient)
        4. Invoice Number (e.g. 26-0042 or 26-0043-PC) & Matter Name
        """
        from repositories.excel_repo import _payment_invoice_matches_query, _parse_payment_amount_query

        all_rows = self._load_ar_invoice_snapshot(force_refresh=force_refresh)
        q_clean = str(query or "").strip()
        p_type = str(party_type or "").strip().casefold()
        p_val = str(party_value or "").strip().casefold()

        clients_set: set[str] = set()
        billing_clients_set: set[str] = set()
        matched: List[Dict[str, Any]] = []

        target_amt = _parse_payment_amount_query(q_clean) if q_clean else None

        for row in all_rows:
            if not include_paid and not row.get("isOpen"):
                continue
            wc = str(row.get("workClient") or row.get("client") or "").strip()
            bc = str(row.get("billingClient") or row.get("client") or "").strip()
            if wc:
                clients_set.add(wc)
            if bc:
                billing_clients_set.add(bc)

            if p_val:
                if p_type in {"billing", "billing_client", "billing client"}:
                    if bc.casefold() != p_val:
                        continue
                else:
                    if wc.casefold() != p_val and bc.casefold() != p_val:
                        continue

            if q_clean:
                matches_std = _payment_invoice_matches_query(row, q_clean)
                matches_total = False
                if not matches_std and target_amt is not None:
                    try:
                        from decimal import Decimal
                        inv_tot = Decimal(str(row.get("invoiceTotal") or 0))
                        if (target_amt * Decimal("0.95")) <= inv_tot <= (target_amt * Decimal("1.05")):
                            matches_total = True
                    except Exception:
                        pass
                if not (matches_std or matches_total):
                    continue

            matched.append(row)

        matched.sort(key=lambda r: (0 if r.get("isOpen") else 1, str(r.get("date") or ""), str(r.get("invoice") or "")), reverse=True)
        # Keep open invoices first, then newest first
        matched.sort(key=lambda r: (0 if r.get("isOpen") else 1, -int(str(r.get("date") or "0000-00-00").replace("-", "") or 0)))

        return {
            "ok": True,
            "invoices": matched[:100],
            "totalMatches": len(matched),
            "clients": sorted(clients_set, key=lambda s: s.casefold()),
            "billingClients": sorted(billing_clients_set, key=lambda s: s.casefold()),
        }

    def post_payment_entry(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Record a single-invoice payment/write-off or a multi-invoice Billing Client receipt."""
        data = dict(payload or {})
        payment_date = str(data.get("date") or data.get("paymentDate") or date.today().isoformat()).strip()
        method = str(data.get("method") or data.get("paymentMethod") or "e-Transfer").strip()
        deposit_acct_raw = str(data.get("depositAccount") or data.get("fromAccount") or "CIBC_PC_GENERAL").strip()
        meta = ACCOUNT_UI_META.get(deposit_acct_raw.upper(), {})
        deposit_account = meta.get("displayName") or deposit_acct_raw
        reference = str(data.get("reference") or "").strip()
        notes = str(data.get("notes") or "").strip()
        allocations = data.get("allocations")

        with self._lock:
            try:
                if isinstance(allocations, list) and len(allocations) > 1:
                    billing_client = str(data.get("billingClient") or data.get("client") or "").strip()
                    total_amount = round(sum(float(a.get("amount") or 0.0) for a in allocations), 2)
                    res = self.repo.post_billing_client_receipt(
                        {
                            "billingClient": billing_client,
                            "date": payment_date,
                            "totalAmount": total_amount,
                            "method": method,
                            "depositAccount": deposit_account,
                            "reference": reference,
                            "notes": notes,
                            "allocations": allocations,
                        }
                    )
                else:
                    if isinstance(allocations, list) and len(allocations) == 1:
                        inv_num = str(allocations[0].get("invoice") or "")
                        amt_val = float(allocations[0].get("amount") or data.get("amount") or 0.0)
                    else:
                        inv_num = str(data.get("invoice") or data.get("invoiceNumber") or "").strip()
                        amt_val = float(data.get("amount") or data.get("paymentAmount") or 0.0)
                    res = self.repo.post_invoice_payment(
                        {
                            "invoice": inv_num,
                            "date": payment_date,
                            "paymentAmount": amt_val,
                            "amount": amt_val,
                            "method": method,
                            "depositAccount": deposit_account,
                            "reference": reference,
                            "notes": notes,
                        }
                    )
                self._cached_ar_snapshot = None
                if res.get("ok"):
                    try:
                        uid = "cory" if self._is_cory(user_id) else "deborah"
                        self.session_tracker.record_event(
                            uid,
                            "INVOICE_ACTION",
                            f"Posted Payment: Inv #{inv_num} (${amt_val:,.2f}) into {deposit_account}",
                            item_data={"action": "PAYMENT_POSTED", "invoiceNumber": inv_num, "amount": amt_val, "account": deposit_account},
                        )
                    except Exception:
                        pass
                return res
            except Exception as exc:
                return {"ok": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # 9. Receipt Snapshots, Smart Auto-Read (OCR) & Tax-Ready Folder Filing
    # ------------------------------------------------------------------
    def _receipts_root_dir(self) -> Path:
        if not self._is_isolated_test():
            try:
                master_dir = self.paths.master_data_dir()
                if master_dir and master_dir.exists():
                    rdir = master_dir / "Receipts"
                    rdir.mkdir(parents=True, exist_ok=True)
                    return rdir
            except Exception:
                pass
            try:
                for od in sorted(Path.home().glob("OneDrive*")):
                    cand = od / "CSPM_Shared_Data"
                    if cand.is_dir():
                        rdir = cand / "Receipts"
                        rdir.mkdir(parents=True, exist_ok=True)
                        return rdir
            except Exception:
                pass
        local_rdir = self.paths.data_dir() / "Receipts"
        local_rdir.mkdir(parents=True, exist_ok=True)
        return local_rdir

    def _receipts_index_path(self) -> Path:
        return self._receipts_root_dir() / "receipts_index.json"

    def _read_receipts_index(self) -> Dict[str, Dict[str, Any]]:
        ipath = self._receipts_index_path()
        if not ipath.is_file():
            return {"byTxnId": {}, "byReceiptId": {}}
        try:
            raw = json.loads(ipath.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "byTxnId" in raw and "byReceiptId" in raw:
                return raw
        except Exception as exc:
            logger.warning("Could not read receipts_index.json: %s", exc)
        return {"byTxnId": {}, "byReceiptId": {}}

    def _write_receipts_index(self, idx: Dict[str, Dict[str, Any]]) -> None:
        ipath = self._receipts_index_path()
        try:
            ipath.parent.mkdir(parents=True, exist_ok=True)
            ipath.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write receipts_index.json: %s", exc)

    def _get_receipt_for_transaction(self, txn_id: str) -> Optional[Dict[str, Any]]:
        if not txn_id:
            return None
        idx = self._read_receipts_index()
        return idx.get("byTxnId", {}).get(str(txn_id))

    @staticmethod
    def _resolve_receipt_tax_folder(
        stream_id: str,
        category_code: str,
        txn_date: str,
    ) -> Tuple[str, str]:
        """Return (relative_subfolder, friendly_folder_label) under Receipts/<Year>/."""
        year_str = (str(txn_date or "")[:4] or str(date.today().year)).strip()
        if not re.match(r"^\d{4}$", year_str):
            year_str = str(date.today().year)
        ym_str = (str(txn_date or "")[:7] or date.today().strftime("%Y-%m")).strip()
        if not re.match(r"^\d{4}-\d{2}$", ym_str):
            ym_str = date.today().strftime("%Y-%m")

        sid = str(stream_id or "FAMILY").strip().upper()
        cat = str(category_code or "").strip().upper()

        if sid == "FAMILY":
            if cat in {
                "EXP_MEDICAL",
                "EXP_DENTAL",
                "EXP_VISION",
                "EXP_PHARMACY",
                "EXP_THERAPY",
                "EXP_HEALTH_INSURANCE",
            }:
                return (
                    f"{year_str}/01_Family_Tax_Credits/Medical_Dental_Pharmacy",
                    f"{year_str} › Family Tax Credits › Medical, Dental & Pharmacy",
                )
            if cat in {
                "EXP_CHILDCARE",
                "EXP_SCHOOL_TUITION",
                "EXP_KIDS_ACTIVITIES",
                "EXP_SCHOOL_SUPPLIES",
                "EXP_RESP_CONTRIBUTION",
            }:
                return (
                    f"{year_str}/01_Family_Tax_Credits/Childcare_and_Education",
                    f"{year_str} › Family Tax Credits › Childcare & Education",
                )
            if cat in {"EXP_DONATIONS", "EXP_CHARITY", "EXP_POLITICAL_CONTRIBUTION"}:
                return (
                    f"{year_str}/01_Family_Tax_Credits/Charitable_Donations",
                    f"{year_str} › Family Tax Credits › Charitable Donations",
                )
            if cat in {
                "EXP_HOME_IMPROVEMENT",
                "EXP_HOME_MAINTENANCE",
                "EXP_PROPERTY_TAX",
                "EXP_HOME_INSURANCE",
                "EXP_UTILITIES_HYDRO",
                "EXP_UTILITIES_GAS",
                "EXP_UTILITIES_WATER",
                "EXP_MORTGAGE_INTEREST",
            }:
                return (
                    f"{year_str}/02_Family_Home_and_Property",
                    f"{year_str} › Family Home & Property",
                )
            return (
                f"{year_str}/03_Family_Everyday/{ym_str}",
                f"{year_str} › Family Everyday › {ym_str}",
            )

        if sid == "DEBORAH_OT_PRIVATE":
            return (
                f"{year_str}/04_Deborah_OT_Private/{ym_str}",
                f"{year_str} › Deborah OT (Private) › {ym_str}",
            )
        if sid == "DEBORAH_OT_VHA":
            return (
                f"{year_str}/05_Deborah_OT_VHA/{ym_str}",
                f"{year_str} › Deborah OT (VHA) › {ym_str}",
            )
        if sid == "CORY_SOLE_PROP":
            return (
                f"{year_str}/06_Cory_Sole_Prop/{ym_str}",
                f"{year_str} › Cory Legal (Sole Prop) › {ym_str}",
            )
        if sid == "CORY_PC":
            return (
                f"{year_str}/07_Cory_PC/{ym_str}",
                f"{year_str} › Cory Law PC › {ym_str}",
            )
        return (
            f"{year_str}/03_Family_Everyday/{ym_str}",
            f"{year_str} › Family Everyday › {ym_str}",
        )

    def _run_windows_ocr_on_image(self, image_path: Path) -> str:
        """Run headless Windows 11 WinRT OcrEngine via Windows PowerShell 5.1 with CREATE_NO_WINDOW."""
        import subprocess
        import sys

        if sys.platform != "win32" or not image_path.is_file():
            return ""
        ps_exe = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        if not ps_exe.is_file():
            return ""

        escaped_path = str(image_path.resolve()).replace("'", "''")
        ps_script = (
            "$ErrorActionPreference = 'Stop'; "
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]; "
            "$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]; "
            "$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
            "$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and "
            "$_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*' })[0]; "
            "Function Await($WinRtTask, $ResultType) { "
            "$asTask = $asTaskGeneric.MakeGenericMethod($ResultType); "
            "$netTask = $asTask.Invoke($null, @($WinRtTask)); "
            "$netTask.Wait(-1) | Out-Null; $netTask.Result }; "
            f"$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{escaped_path}')) ([Windows.Storage.StorageFile]); "
            "$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream]); "
            "$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder]); "
            "$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]); "
            "$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); "
            "$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult]); "
            "$stream.Dispose(); "
            "foreach ($line in $result.Lines) { Write-Output $line.Text }"
        )
        creationflags = 0x08000000  # subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(
                [str(ps_exe), "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=creationflags,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout.strip()
        except Exception as exc:
            logger.warning("Windows OCR warning: %s", exc)
        return ""

    def _extract_text_from_receipt_file(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(str(file_path))
                text_parts: List[str] = []
                for i in range(min(2, len(doc))):
                    text_parts.append(doc[i].get_text("text") or "")
                combined = "\n".join(text_parts).strip()
                if len(combined) >= 20:
                    doc.close()
                    return combined
                # Scanned image PDF: render page 0 to temporary PNG and OCR
                if len(doc) > 0:
                    import tempfile

                    pix = doc[0].get_pixmap(dpi=200)
                    fd, tmp_png = tempfile.mkstemp(prefix="cspm_rcpt_", suffix=".png")
                    os.close(fd)
                    try:
                        pix.save(tmp_png)
                        doc.close()
                        return self._run_windows_ocr_on_image(Path(tmp_png))
                    finally:
                        try:
                            os.remove(tmp_png)
                        except OSError:
                            pass
                doc.close()
            except Exception as exc:
                logger.warning("PDF receipt text extraction warning: %s", exc)
            return ""
        return self._run_windows_ocr_on_image(file_path)

    def _parse_receipt_ocr_text(self, raw_text: str, user_id: str = "deborah") -> Dict[str, Any]:
        """Parse OCR text from a Canadian store/vendor receipt into structured pre-fill fields."""
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in str(raw_text or "").splitlines() if ln.strip()]
        full_text = "\n".join(lines)
        full_lower = full_text.lower()

        # 1. Merchant / Payee & Default Category / Stream Lookup
        merchant_rules = [
            (["costco wholesale", "costco"], "Costco Wholesale", "EXP_GROCERIES", "FAMILY"),
            (["shoppers drug mart", "shoppers drug", "pharmaprix"], "Shoppers Drug Mart", "EXP_PHARMACY", "FAMILY"),
            (["no frills", "nofrills"], "No Frills", "EXP_GROCERIES", "FAMILY"),
            (["loblaws", "loblaw"], "Loblaws", "EXP_GROCERIES", "FAMILY"),
            (["real canadian superstore", "superstore"], "Real Canadian Superstore", "EXP_GROCERIES", "FAMILY"),
            (["fortinos"], "Fortinos", "EXP_GROCERIES", "FAMILY"),
            (["metro"], "Metro", "EXP_GROCERIES", "FAMILY"),
            (["sobeys"], "Sobeys", "EXP_GROCERIES", "FAMILY"),
            (["farm boy", "farmboy"], "Farm Boy", "EXP_GROCERIES", "FAMILY"),
            (["longo's", "longos"], "Longo's", "EXP_GROCERIES", "FAMILY"),
            (["whole foods"], "Whole Foods Market", "EXP_GROCERIES", "FAMILY"),
            (["walmart", "wal-mart"], "Walmart", "EXP_HOUSEHOLD_SUPPLIES", "FAMILY"),
            (["canadian tire"], "Canadian Tire", "EXP_HOME_MAINTENANCE", "FAMILY"),
            (["home depot"], "The Home Depot", "EXP_HOME_MAINTENANCE", "FAMILY"),
            (["roni", "rona"], "RONA", "EXP_HOME_MAINTENANCE", "FAMILY"),
            (["ikea"], "IKEA", "EXP_HOME_IMPROVEMENT", "FAMILY"),
            (["dollarama"], "Dollarama", "EXP_HOUSEHOLD_SUPPLIES", "FAMILY"),
            (["winners", "homesense", "marshalls"], "Winners / HomeSense", "EXP_CLOTHING", "FAMILY"),
            (["indigo", "chapters"], "Indigo", "EXP_GIFTS", "FAMILY"),
            (["rexall"], "Rexall Pharmacy", "EXP_PHARMACY", "FAMILY"),
            (["lcbo"], "LCBO", "EXP_DINING_OUT", "FAMILY"),
            (["starbucks"], "Starbucks", "EXP_DINING_OUT", "FAMILY"),
            (["tim hortons"], "Tim Hortons", "EXP_DINING_OUT", "FAMILY"),
            (["mcdonald's", "mcdonalds"], "McDonald's", "EXP_DINING_OUT", "FAMILY"),
            (["uber eats", "ubereats"], "Uber Eats", "EXP_DINING_OUT", "FAMILY"),
            (["doordash"], "DoorDash", "EXP_DINING_OUT", "FAMILY"),
            (["skip the dishes", "skipthedishes"], "SkipTheDishes", "EXP_DINING_OUT", "FAMILY"),
            (["shell"], "Shell", "EXP_AUTO_FUEL", "FAMILY"),
            (["esso"], "Esso", "EXP_AUTO_FUEL", "FAMILY"),
            (["petro-canada", "petro canada"], "Petro-Canada", "EXP_AUTO_FUEL", "FAMILY"),
            (["pioneer"], "Pioneer Gas", "EXP_AUTO_FUEL", "FAMILY"),
            (["407 etr"], "407 ETR", "EXP_AUTO_PARKING_TOLLS", "FAMILY"),
            (["green p", "toronto parking"], "Green P Parking", "EXP_AUTO_PARKING_TOLLS", "FAMILY"),
            (["staples"], "Staples", "EXP_OFFICE_SUPPLIES", "CORY_PC" if self._is_cory(user_id) else "DEBORAH_OT_PRIVATE"),
            (["amazon.ca", "amazon"], "Amazon.ca", "EXP_HOUSEHOLD_SUPPLIES", "FAMILY"),
            (["apple.com", "apple store"], "Apple", "EXP_SOFTWARE_SUBSCRIPTIONS", "FAMILY"),
            (["law society of ontario", "lso"], "Law Society of Ontario", "EXP_LICENSES_FEES", "CORY_PC"),
            (["serviceontario", "ministry of public and business"], "ServiceOntario", "EXP_LICENSES_FEES", "CORY_PC"),
            (["dye & durham", "dye and durham", "teraview"], "Dye & Durham", "EXP_OFFICE_SUPPLIES", "CORY_PC"),
            (["canada post"], "Canada Post", "EXP_POSTAGE_COURIER", "CORY_PC" if self._is_cory(user_id) else "FAMILY"),
            (["fedex", "purolator", "ups"], "Courier (FedEx/UPS)", "EXP_POSTAGE_COURIER", "CORY_PC" if self._is_cory(user_id) else "FAMILY"),
        ]

        detected_payee = ""
        detected_category = ""
        detected_stream = ""
        for tokens, p_name, c_code, s_id in merchant_rules:
            if any(tok in full_lower for tok in tokens):
                detected_payee = p_name
                detected_category = c_code
                if not self._is_cory(user_id) and s_id in ("CORY_PC", "CORY_SOLE_PROP"):
                    detected_stream = "FAMILY"
                else:
                    detected_stream = s_id
                break

        if not detected_payee and lines:
            noise_re = re.compile(
                r"^(welcome|customer copy|merchant copy|transaction|receipt|tax invoice|invoice|tel|phone|www\.|http|\d+\s+[a-z]+|toronto|thornhill|vaughan|richmond hill|ontario)",
                re.IGNORECASE,
            )
            for ln in lines[:5]:
                clean_ln = re.sub(r"[^A-Za-z0-9\s&'\-\.]", "", ln).strip()
                if len(clean_ln) >= 3 and not noise_re.search(clean_ln) and not re.match(r"^[\d\W]+$", clean_ln):
                    detected_payee = clean_ln.title()
                    break

        # 2. Receipt Date Extraction
        detected_date = date.today().isoformat()
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        # Pattern A: YYYY-MM-DD or YYYY/MM/DD
        m_iso = re.search(r"\b(202\d)[-/\.](0[1-9]|1[0-2])[-/\.](0[1-9]|[12]\d|3[01])\b", full_text)
        if m_iso:
            detected_date = f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
        else:
            # Pattern B: Month DD, YYYY or DD Month YYYY (e.g. Oct 26, 2026 or 26-OCT-2026)
            m_txt = re.search(
                r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.,]+(\d{1,2})[\s\-\.,]+(202\d)\b",
                full_text,
                re.IGNORECASE,
            )
            if m_txt:
                mm = month_map[m_txt.group(1)[:3].lower()]
                dd = int(m_txt.group(2))
                yy = int(m_txt.group(3))
                detected_date = f"{yy:04d}-{mm:02d}-{dd:02d}"
            else:
                m_txt2 = re.search(
                    r"\b(\d{1,2})[\s\-\.](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\.,]+(202\d)\b",
                    full_text,
                    re.IGNORECASE,
                )
                if m_txt2:
                    dd = int(m_txt2.group(1))
                    mm = month_map[m_txt2.group(2)[:3].lower()]
                    yy = int(m_txt2.group(3))
                    detected_date = f"{yy:04d}-{mm:02d}-{dd:02d}"
                else:
                    # Pattern C: MM/DD/YYYY or DD/MM/YYYY
                    m_slash = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](202\d)\b", full_text)
                    if m_slash:
                        a, b, yy = int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3))
                        if a > 12 and 1 <= b <= 12:
                            dd, mm = a, b
                        else:
                            mm, dd = a, b
                        if 1 <= mm <= 12 and 1 <= dd <= 31:
                            detected_date = f"{yy:04d}-{mm:02d}-{dd:02d}"

        # 3. Total Paid ($) and Exact Printed HST ($) Extraction
        money_re = re.compile(r"(?:\$\s*)?(\d{1,5}(?:,\d{3})*\.\d{2})\b")
        total_candidates: List[float] = []
        subtotal_candidates: List[float] = []
        tax_candidates: List[float] = []
        all_amounts: List[float] = []

        for ln in lines:
            ln_low = ln.lower()
            nums = [float(x.replace(",", "")) for x in money_re.findall(ln)]
            if not nums:
                continue
            for n in nums:
                if n > 0:
                    all_amounts.append(n)

            if any(k in ln_low for k in ("subtotal", "sub-total", "sub total", "merchandise")):
                subtotal_candidates.extend(nums)
            elif any(k in ln_low for k in ("hst", "gst", "h.s.t", "g.s.t", "tax 13", "13%", "sales tax", "ont tax")):
                # Ignore "total with tax" or "total incl tax" when looking for tax amount
                if not any(t in ln_low for t in ("total incl", "total with", "after tax")):
                    tax_candidates.append(nums[-1])
            elif any(
                k in ln_low
                for k in ("total", "amount due", "balance due", "grand total", "visa", "mastercard", "debit", "amex", "cad$")
            ):
                if not any(
                    excl in ln_low
                    for excl in ("tax", "discount", "saving", "saved", "points", "change", "cash back", "items", "qty")
                ):
                    total_candidates.append(nums[-1])

        detected_total = 0.0
        if total_candidates:
            detected_total = max(total_candidates)
        elif all_amounts:
            detected_total = max(all_amounts)

        detected_hst = 0.0
        has_explicit_tax = False
        if tax_candidates:
            valid_taxes = [t for t in tax_candidates if 0.0 <= t < detected_total and t <= round(detected_total * 0.20, 2)]
            if valid_taxes:
                detected_hst = round(max(valid_taxes), 2)
                has_explicit_tax = True
        elif subtotal_candidates and detected_total > 0:
            sub = max(s for s in subtotal_candidates if s <= detected_total)
            diff = round(detected_total - sub, 2)
            if 0.0 <= diff <= round(detected_total * 0.16, 2):
                detected_hst = diff
                has_explicit_tax = True

        if has_explicit_tax and detected_total > 0:
            if detected_hst == 0.0:
                hst_mode = "zero"
            else:
                std_hst = round(detected_total * 13.0 / 113.0, 2)
                hst_mode = "auto" if abs(detected_hst - std_hst) <= 0.04 else "custom"
        else:
            if detected_category in {"EXP_GROCERIES", "EXP_MEDICAL", "EXP_DENTAL", "EXP_PHARMACY", "EXP_CHILDCARE", "EXP_DONATIONS"}:
                hst_mode = "zero"
                detected_hst = 0.0
            elif detected_total > 0:
                hst_mode = "auto"
                detected_hst = round(detected_total * 13.0 / 113.0, 2)
            else:
                hst_mode = "auto"
                detected_hst = 0.0

        # 4. Payment Card / Account Detection
        detected_account = ""
        if "mastercard" in full_lower or "triangle" in full_lower or "m/c" in full_lower:
            detected_account = "TRIANGLE_MASTERCARD"
        elif "visa" in full_lower or "simplii" in full_lower:
            detected_account = "SIMPLII_VISA"
        elif "debit" in full_lower or "interac" in full_lower or "chequing" in full_lower:
            detected_account = "CIBC_CHEQUING"

        return {
            "payee": detected_payee,
            "txnDate": detected_date,
            "amount": round(detected_total, 2) if detected_total > 0 else 0.0,
            "taxAmount": round(detected_hst, 2),
            "hstMode": hst_mode,
            "hasExplicitTax": has_explicit_tax,
            "fromAccount": detected_account,
            "categoryCode": detected_category,
            "streamId": detected_stream,
            "ocrLines": lines[:30],
            "rawText": full_text[:2000],
        }

    def scan_and_stage_receipt(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Accept a base64 receipt photo or PDF, save to _staging, run OCR, and return pre-fill fields."""
        import base64

        uid = "cory" if self._is_cory(user_id) else "deborah"
        data = dict(payload or {})
        raw_b64 = str(data.get("dataBase64") or data.get("base64Data") or data.get("dataUrl") or "").strip()
        filename = str(data.get("fileName") or "receipt.jpg").strip()
        mime_type = str(data.get("mimeType") or "").strip().lower()

        if not raw_b64:
            return {"ok": False, "message": "No receipt image or PDF data received."}

        if "," in raw_b64 and raw_b64.startswith("data:"):
            header, raw_b64 = raw_b64.split(",", 1)
            if not mime_type and ";" in header:
                mime_type = header.split(":", 1)[-1].split(";", 1)[0].strip().lower()

        try:
            file_bytes = base64.b64decode(raw_b64)
        except Exception as exc:
            return {"ok": False, "message": f"Invalid base64 receipt image: {exc}"}

        ext = Path(filename).suffix.lower()
        if not ext or ext not in {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".bmp"}:
            ext = ".pdf" if "pdf" in mime_type else (".png" if "png" in mime_type else ".jpg")
        if not mime_type:
            mime_type = "application/pdf" if ext == ".pdf" else ("image/png" if ext == ".png" else "image/jpeg")

        receipt_token = f"RCPT_{uuid4().hex[:12]}"
        staging_dir = self._receipts_root_dir() / "_staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_path = staging_dir / f"{receipt_token}{ext}"
        staged_path.write_bytes(file_bytes)

        ocr_text = self._extract_text_from_receipt_file(staged_path)
        parsed = self._parse_receipt_ocr_text(ocr_text, user_id=uid)

        # Also register staged receipt in receipts_index so preview works immediately
        idx = self._read_receipts_index()
        idx.setdefault("byReceiptId", {})[receipt_token] = {
            "receiptId": receipt_token,
            "transactionId": "",
            "fileName": staged_path.name,
            "relativePath": f"_staging/{staged_path.name}",
            "folderCategory": "Staged (Ready to File on Save)",
            "mimeType": mime_type,
            "fileSize": len(file_bytes),
            "ocrText": parsed.get("rawText", ""),
            "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._write_receipts_index(idx)

        msg_text = (
            f"📸 Scanned receipt: {parsed.get('payee') or 'Store'} · "
            f"${parsed.get('amount', 0.0):,.2f} (HST ${parsed.get('taxAmount', 0.0):,.2f})"
            if parsed.get("amount")
            else "📸 Receipt attached! Fill or confirm details below."
        )

        try:
            self.session_tracker.record_event(
                uid,
                "RECEIPT_OCR_SCAN",
                f"Scanned receipt: {filename} -> {parsed.get('payee') or 'Store'} (${parsed.get('amount', 0.0):,.2f})",
                item_data={
                    "fileName": filename,
                    "payee": parsed.get("payee"),
                    "amount": parsed.get("amount"),
                    "taxAmount": parsed.get("taxAmount"),
                    "txnDate": parsed.get("date"),
                    "receiptToken": receipt_token,
                },
            )
        except Exception:
            pass

        return {
            "ok": True,
            "receiptToken": receipt_token,
            "receiptUrl": f"/api/receipt/file?receiptId={receipt_token}&userId={uid}",
            "mimeType": mime_type,
            "fileSize": len(file_bytes),
            "parsed": parsed,
            "prefill": parsed,
            "summary": msg_text,
            "message": msg_text,
        }

    def _finalize_staged_receipt(
        self,
        receipt_token: str,
        transaction_id: str,
        stream_id: str,
        category_code: str,
        txn_date: str,
        payee: str,
        amount: float,
        tax_amount: float,
        matter_number: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Move a staged receipt into its permanent Tax-Ready folder in CSPM_Shared_Data/Receipts/<Year>/..."""
        import shutil

        root_dir = self._receipts_root_dir()
        idx = self._read_receipts_index()
        existing_meta = idx.get("byReceiptId", {}).get(receipt_token)

        staged_file: Optional[Path] = None
        if existing_meta and existing_meta.get("relativePath"):
            cand = root_dir / existing_meta["relativePath"]
            if cand.is_file():
                staged_file = cand
        if staged_file is None:
            staging_dir = root_dir / "_staging"
            if staging_dir.is_dir():
                matches = list(staging_dir.glob(f"{receipt_token}.*"))
                if matches:
                    staged_file = matches[0]
        if staged_file is None or not staged_file.is_file():
            return None

        ext = staged_file.suffix.lower() or ".jpg"
        rel_folder, friendly_folder = self._resolve_receipt_tax_folder(stream_id, category_code, txn_date)
        target_dir = root_dir / rel_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_payee = re.sub(r"[^A-Za-z0-9]+", "_", str(payee or "Receipt")).strip("_")[:28] or "Receipt"
        safe_cat = re.sub(r"[^A-Za-z0-9]+", "_", str(category_code or "EXP")).strip("_")[:22] or "EXP"
        short_id = re.sub(r"[^A-Za-z0-9]+", "", str(transaction_id or receipt_token))[-8:]
        clean_date = (str(txn_date or "")[:10] or date.today().isoformat()).strip()
        final_name = f"{clean_date}_{safe_payee}_${amount:.2f}_HST${tax_amount:.2f}_{safe_cat}_{short_id}{ext}"
        final_path = target_dir / final_name

        if staged_file.resolve() != final_path.resolve():
            shutil.copy2(str(staged_file), str(final_path))
            if "_staging" in str(staged_file):
                try:
                    staged_file.unlink()
                except OSError:
                    pass

        # If also billed to a Client Matter, copy into 08_Client_Disbursements/<MatterNumber>/
        if matter_number:
            year_str = clean_date[:4] if re.match(r"^\d{4}", clean_date) else str(date.today().year)
            safe_matter = re.sub(r"[^A-Za-z0-9_\-]+", "_", matter_number.strip()).strip("_")
            disb_dir = root_dir / year_str / "08_Client_Disbursements" / safe_matter
            disb_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(final_path), str(disb_dir / final_name))
            except Exception:
                pass

        rel_path = f"{rel_folder}/{final_name}"
        meta = {
            "receiptId": receipt_token,
            "transactionId": str(transaction_id),
            "fileName": final_name,
            "relativePath": rel_path,
            "folderCategory": friendly_folder,
            "mimeType": (existing_meta or {}).get("mimeType") or ("application/pdf" if ext == ".pdf" else "image/jpeg"),
            "fileSize": final_path.stat().st_size,
            "ocrText": (existing_meta or {}).get("ocrText", ""),
            "streamId": stream_id,
            "categoryCode": category_code,
            "txnDate": clean_date,
            "payee": payee,
            "amount": amount,
            "taxAmount": tax_amount,
            "matterNumber": matter_number,
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        idx.setdefault("byReceiptId", {})[receipt_token] = meta
        idx.setdefault("byTxnId", {})[str(transaction_id)] = meta
        self._write_receipts_index(idx)
        return meta

    def attach_receipt_to_entry(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Attach a scanned/uploaded receipt to an existing transaction entry."""
        uid = "cory" if self._is_cory(user_id) else "deborah"
        data = dict(payload or {})
        txn_id = str(data.get("transactionId") or "").strip()
        receipt_token = str(data.get("receiptToken") or "").strip()

        if not txn_id:
            return {"ok": False, "message": "Missing transactionId."}
        entry = self.get_entry(user_id=uid, transaction_id=txn_id)
        if not entry:
            return {"ok": False, "message": "Transaction not found."}

        if not receipt_token and (data.get("dataBase64") or data.get("base64Data") or data.get("dataUrl")):
            scan_res = self.scan_and_stage_receipt(user_id=uid, payload=data)
            if not scan_res.get("ok"):
                return scan_res
            receipt_token = str(scan_res.get("receiptToken") or "")

        if not receipt_token:
            return {"ok": False, "message": "Missing receiptToken."}

        meta = self._finalize_staged_receipt(
            receipt_token=receipt_token,
            transaction_id=txn_id,
            stream_id=str(entry.get("streamId") or "FAMILY"),
            category_code=str(entry.get("categoryCode") or "EXP_OTHER"),
            txn_date=str(entry.get("txnDate") or date.today().isoformat()),
            payee=str(entry.get("payee") or "Receipt"),
            amount=float(entry.get("amount") or 0.0),
            tax_amount=float(entry.get("taxAmount") or 0.0),
        )
        if not meta:
            return {"ok": False, "message": "Could not locate staged receipt file."}
        updated_entry = self.get_entry(user_id=uid, transaction_id=txn_id)
        return {
            "ok": True,
            "transactionId": txn_id,
            "receipt": meta,
            "entry": updated_entry,
            "message": f"🧾 Receipt attached & filed in {meta.get('folderCategory')}!",
        }

    def get_receipt_file_info(self, user_id: str, receipt_id: str = "", transaction_id: str = "") -> Optional[Tuple[Path, str, str]]:
        """Return (file_path, mime_type, file_name) for a receiptId or transactionId."""
        idx = self._read_receipts_index()
        meta = None
        if receipt_id:
            meta = idx.get("byReceiptId", {}).get(str(receipt_id))
        if not meta and transaction_id:
            meta = idx.get("byTxnId", {}).get(str(transaction_id))
        if not meta:
            return None
        f_path = self._receipts_root_dir() / str(meta.get("relativePath") or "")
        if not f_path.is_file():
            return None
        mime = str(meta.get("mimeType") or "image/jpeg")
        fname = str(meta.get("fileName") or f_path.name)
        return f_path, mime, fname

    def _record_expense_as_client_disbursement(
        self,
        matter_number: str,
        txn_date: str,
        payee: str,
        details: str,
        gross_amount: float,
        tax_amount: float,
        biller_entity: str = "SOLE_PROP",
    ) -> Dict[str, Any]:
        """Record a billable Client Disbursement in cspm.db (disbursements table) so it appears in WIP."""
        import sqlite3

        pre_tax = round(max(0.0, gross_amount - tax_amount), 2)
        disb_id = f"DISB_{uuid4().hex[:8].upper()}"
        desc_text = f"{payee} - {details}".strip(" -") if payee and details != payee else (details or payee)

        db_paths = self._all_sqlite_db_paths()
        if not db_paths:
            return {"ok": False, "message": "No SQLite database found."}

        matched_matter_id = ""
        matched_client_id = ""
        matched_matter_num = matter_number.strip()
        for db_p in db_paths:
            try:
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                cur.execute(
                    "SELECT matter_id, matter_number, client_id FROM matters WHERE lower(matter_number)=lower(?) OR lower(matter_id)=lower(?) LIMIT 1",
                    (matched_matter_num, matched_matter_num),
                )
                row = cur.fetchone()
                if row:
                    matched_matter_id = str(row[0] or "")
                    matched_matter_num = str(row[1] or matched_matter_num)
                    matched_client_id = str(row[2] or "")
                now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                cur.execute(
                    """
                    INSERT OR REPLACE INTO disbursements (
                        disb_id, entry_date, client_id, matter_id, description,
                        amount_cents, hst_cents, total_cents, is_billed, billed_invoice_id,
                        biller_entity, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?, ?)
                    """,
                    (
                        disb_id,
                        txn_date[:10],
                        matched_client_id,
                        matched_matter_id or matched_matter_num,
                        desc_text,
                        int(round(pre_tax * 100)),
                        int(round(tax_amount * 100)),
                        int(round(gross_amount * 100)),
                        biller_entity,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.warning("SQLite disbursement insert warning (%s): %s", db_p, exc)

        return {"ok": True, "disbId": disb_id, "matterNumber": matched_matter_num}

    # ------------------------------------------------------------------
    # 10. Universal Voice Command Parser & LPN CRA-Safe Docket Formatter
    # ------------------------------------------------------------------
    @staticmethod
    def _format_cra_safe_docket_narrative(raw_text: str) -> str:
        """Apply LPN Mandatory Docket Narrative Rules (Global Rule 3):
        - First names only (strip known partner/client surnames after first names)
        - Present tense verbs (drafted -> draft, reviewed -> review, called -> telephone call with, etc.)
        - Semicolon separators (;) between distinct tasks
        - No em-dashes (—)
        """
        s = str(raw_text or "").strip()
        if not s:
            return ""
        s = s.replace("—", "; ").replace("–", "; ")

        # Known full-name -> first-name replacements
        known_people = [
            (r"\bJames\s+Hutchinson\b", "James"),
            (r"\bScott\s+Braun\b", "Scott"),
            (r"\bMichael\s+Connor\b", "Michael"),
            (r"\bCory\s+Schneider\b", "Cory"),
            (r"\bDavid\s+Hurangan\b", "David"),
            (r"\bStephen\s+Tatrallyay\b", "Stephen"),
            (r"\bMark\s+Trek\b", "Mark"),
        ]
        for pat, repl in known_people:
            s = re.sub(pat, repl, s, flags=re.IGNORECASE)

        # Past-tense / conversational verb normalizations to CRA-safe present tense
        verb_rules = [
            (r"\b(?:had a |phone )?call(?:ed)? with\b", "telephone call with"),
            (r"\bcalled\b(?!\s+with)", "telephone call with"),
            (r"\btelephoned\b", "telephone call with"),
            (r"\bspoke (?:with|to)\b", "telephone call with"),
            (r"\btalked (?:with|to)\b", "telephone call with"),
            (r"\bmet with\b", "meeting with"),
            (r"\battended a meeting with\b", "meeting with"),
            (r"\battended\b", "attend"),
            (r"\bemailed\b", "email to"),
            (r"\bsent (?:an )?email to\b", "email to"),
            (r"\bcorresponded with\b", "email to"),
            (r"\bcorrespondence with\b", "email to"),
            (r"\bdrafted and revised\b", "draft and revise"),
            (r"\bdrafted\b", "draft"),
            (r"\bdrafting\b", "draft"),
            (r"\brevised\b", "revise"),
            (r"\brevising\b", "revise"),
            (r"\breviewed and revised\b", "review and revise"),
            (r"\breviewed\b", "review"),
            (r"\breviewing\b", "review"),
            (r"\bprepared\b", "prepare"),
            (r"\bpreparing\b", "prepare"),
            (r"\bresearched\b", "research"),
            (r"\bresearching\b", "research"),
            (r"\bupdated\b", "update"),
            (r"\bupdating\b", "update"),
            (r"\bfinalized\b", "finalize"),
            (r"\bfinalizing\b", "finalize"),
            (r"\banalyzed\b", "analyze"),
            (r"\bdiscussed\b", "discuss"),
        ]
        for pat, repl in verb_rules:
            s = re.sub(pat, repl, s, flags=re.IGNORECASE)

        # Convert task-boundary connectors into semicolons (;)
        s = re.sub(
            r"\s+(?:and then|then|followed by|also|and also|;\s*and)\s+",
            "; ",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            r",\s*(?:and\s+)?(?=(?:draft|revise|review|prepare|email to|telephone call with|meeting with|attend|research|update|finalize)\b)",
            "; ",
            s,
            flags=re.IGNORECASE,
        )
        # Also split " and <verb>" when preceded by a full clause (>18 chars)
        parts = re.split(
            r"(?<!\bdraft)(?<!\breview)\s+and\s+(?=(?:email to|telephone call with|meeting with|prepare|research|finalize|review|draft|revise|update|attend)\b)",
            s,
            flags=re.IGNORECASE,
        )
        s = "; ".join(p.strip(" ,;.") for p in parts if p.strip(" ,;."))
        s = re.sub(r"\s*;\s*", "; ", s).strip(" ;.")
        if s:
            s = s[0].lower() + s[1:]
        return s

    def parse_voice_command(
        self,
        user_id: str,
        transcript: str,
        current_mode: str = "Expense",
    ) -> Dict[str, Any]:
        """Parse natural speech into structured actions across Expense, Income, Pay Credit Card,
        Transfer, Docket, Record Payment, Mobile Invoice, WIP/A/R Lookup, and Call Timer."""
        uid = "cory" if self._is_cory(user_id) else "deborah"
        raw = str(transcript or "").strip()
        if not raw:
            return {"ok": False, "message": "No voice transcript detected. Try speaking again."}
        low = raw.lower()

        # 1. Timer Commands ("start timer for Scott Braun", "pause timer", "stop timer")
        if re.search(r"\b(start|begin|resume|pause|stop|end|reset)\s+(?:the\s+)?(?:call\s+|task\s+)?timer\b", low):
            cmd = "start"
            if "pause" in low:
                cmd = "pause"
            elif "stop" in low or "end" in low:
                cmd = "stop"
            elif "reset" in low:
                cmd = "reset"
            matter_match = None
            m_for = re.search(r"timer\s+(?:for|on)\s+(.+)$", raw, re.IGNORECASE)
            if m_for and self._is_cory(uid):
                q_m = m_for.group(1).strip(" .")
                res_m = self.list_docket_matters(user_id=uid, query=q_m)
                if res_m.get("matters"):
                    matter_match = res_m["matters"][0]
            msg = f"⏱️ Timer command: {cmd.upper()}" + (f" ({matter_match['clientName']})" if matter_match else "")
            return {
                "ok": True,
                "intent": "TIMER",
                "action": "timer",
                "timerAction": cmd,
                "timerCommand": cmd,
                "matter": matter_match,
                "transcript": raw,
                "summary": msg,
                "message": msg,
            }

        # 1b. Report / Budget Charts Commands ("show budget", "show charts", "show my entries")
        if re.search(r"\b(show|open|view|check)\b.*\b(budget|chart|charts|pie chart|bar graph|report|entries|spending)\b", low):
            rep_period = "this_year" if ("year" in low or "ytd" in low or "2026" in low) else ("today" if "today" in low else "this_month")
            msg = f"📊 Opening Budget & Cash-Flow Charts ({rep_period.replace('_', ' ').title()})"
            return {
                "ok": True,
                "intent": "REPORT",
                "action": "open_report",
                "reportPeriod": rep_period,
                "transcript": raw,
                "summary": msg,
                "message": msg,
            }

        # 2. Navigation / Lookup Commands ("show WIP", "show overdue A/R", "show tax snapshot")
        if re.search(r"\b(show|open|view|check|go to)\b.*\b(wip|unbilled|a/r|receivables|overdue|aging|tax|shareholder loan|hst)\b", low):
            if "tax" in low or "shareholder" in low or "hst" in low:
                msg = "🏛️ Opening Live Tax, HST & Shareholder Loan Snapshot"
                return {
                    "ok": True,
                    "intent": "WIP_AR",
                    "action": "navigate",
                    "targetMode": "WIP_AR",
                    "subTab": "TAX",
                    "wipSubTab": "tax",
                    "transcript": raw,
                    "summary": msg,
                    "message": msg,
                }
            if any(k in low for k in ("a/r", "receivable", "overdue", "aging", "unpaid")):
                bucket = "ALL"
                if "90" in low:
                    bucket = "90+"
                elif "60" in low:
                    bucket = "61-90"
                elif "30" in low:
                    bucket = "31-60"
                msg = f"🧾 Opening Open A/R ({bucket})"
                return {
                    "ok": True,
                    "intent": "WIP_AR",
                    "action": "navigate",
                    "targetMode": "WIP_AR",
                    "subTab": "AR",
                    "wipSubTab": "ar",
                    "arBucket": bucket,
                    "transcript": raw,
                    "summary": msg,
                    "message": msg,
                }
            m_wip_for = re.search(r"(?:wip|unbilled)\s+(?:for|on)\s+(.+)$", raw, re.IGNORECASE)
            msg = "💼 Opening Unbilled WIP Pipeline"
            return {
                "ok": True,
                "intent": "WIP_AR",
                "action": "navigate",
                "targetMode": "WIP_AR",
                "subTab": "WIP",
                "wipSubTab": "wip",
                "filterQuery": m_wip_for.group(1).strip(" .") if m_wip_for else "",
                "transcript": raw,
                "summary": msg,
                "message": msg,
            }

        # 3. Mobile Invoice Creation Commands ("create invoice for Michael Connor", "bill 88 Queen")
        if self._is_cory(uid) and re.search(r"\b(create invoice|generate invoice|preview invoice|bill matter|prepare invoice|bill\s+[a-z0-9])\b", low):
            m_inv_client = re.search(
                r"(?:invoice|bill(?:\s+matter)?)\s+(?:for|on|to)?\s*(.+)$",
                raw,
                re.IGNORECASE,
            )
            q_client = m_inv_client.group(1).strip(" .") if m_inv_client else ""
            wip_res = self.get_wip_and_ar_overview(user_id=uid)
            wip_matters = wip_res.get("wipMatters") or []
            matched_wip = None
            if q_client:
                q_cf = q_client.casefold()
                for wm in wip_matters:
                    if (
                        q_cf in str(wm.get("clientName") or "").casefold()
                        or q_cf in str(wm.get("matterName") or "").casefold()
                        or q_cf in str(wm.get("matterNumber") or "").casefold()
                    ):
                        matched_wip = wm
                        break
            if not matched_wip and wip_matters:
                matched_wip = wip_matters[0]
            if matched_wip:
                msg = f"🧾 Opening Invoice Preview for {matched_wip.get('clientName')} ({matched_wip.get('matterNumber')})"
                return {
                    "ok": True,
                    "intent": "INVOICE",
                    "action": "open_invoice_preview",
                    "targetMode": "WIP_AR",
                    "matter": matched_wip,
                    "transcript": raw,
                    "summary": msg,
                    "message": msg,
                }

        # 4. Record Payment Voice Commands ("record payment for invoice 26-0124", "payment from Michael Connor")
        if re.search(r"\b(record payment|client payment|payment for invoice|paid invoice)\b", low) or current_mode == "Record Payment":
            inv_match = re.search(r"\b(\d{2}-\d{4}(?:-PC)?)\b", raw, re.IGNORECASE)
            amt_match = re.search(r"\$?\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)", raw)
            q_search = inv_match.group(1) if inv_match else ""
            if not q_search:
                m_from = re.search(r"(?:from|for|client)\s+([A-Za-z0-9\s,\.&'-]+?)(?:\s+by|\s+for|\s+\$|$)", raw, re.IGNORECASE)
                if m_from:
                    q_search = m_from.group(1).strip()
            inv_res = self.search_payment_invoices(user_id=uid, query=q_search)
            matched_inv = (inv_res.get("invoices") or [None])[0]
            method = "e-Transfer"
            if "wire" in low:
                method = "Wire"
            elif "cheque" in low or "check" in low:
                method = "Cheque"
            elif "trust" in low:
                method = "Trust Transfer"
            amt_val = float(amt_match.group(1).replace(",", "")) if amt_match and not inv_match else (matched_inv.get("balance") if matched_inv else 0.0)
            msg = f"💵 Pre-filled Record Payment" + (f" for Invoice {matched_inv['invoice']}" if matched_inv else "")
            return {
                "ok": True,
                "intent": "PAYMENT",
                "action": "fill_payment",
                "targetMode": "Record Payment",
                "searchQuery": q_search,
                "query": q_search,
                "invoice": matched_inv,
                "amount": amt_val,
                "method": method,
                "transcript": raw,
                "summary": msg,
                "message": msg,
            }

        # 5. Docket Voice Commands (Cory: when in Docket mode OR when hours/docket keywords spoken)
        is_docket_intent = self._is_cory(uid) and (
            current_mode == "Docket"
            or bool(re.search(r"\b(docket|billable|hours?|hrs?|minutes?|mins?|\d\.\d\s*h)\b", low))
        )
        if is_docket_intent and not re.search(r"\b(costco|loblaws|shoppers|visa|mastercard|groceries|hst)\b", low):
            hours_val = 0.0
            work_text = raw

            # Spoken time phrases
            if "hour and a half" in low:
                hours_val = 1.5
                work_text = re.sub(r"\b(?:an?\s+)?hour and a half\b", "", work_text, flags=re.IGNORECASE)
            elif "half an hour" in low or "half hour" in low:
                hours_val = 0.5
                work_text = re.sub(r"\b(?:a\s+)?half(?:\s+an)?\s+hour\b", "", work_text, flags=re.IGNORECASE)
            else:
                m_min = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?)\b", work_text, re.IGNORECASE)
                if m_min:
                    mins = int(m_min.group(1))
                    hours_val = max(0.1, round((mins + 5) // 6 * 0.1, 1))
                    work_text = work_text[: m_min.start()] + " " + work_text[m_min.end() :]
                else:
                    m_hr = re.search(r"\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:hours?|hrs?|h)\b", work_text, re.IGNORECASE)
                    if m_hr:
                        hours_val = round(float(m_hr.group(1)), 1)
                        work_text = work_text[: m_hr.start()] + " " + work_text[m_hr.end() :]
                    else:
                        m_dec = re.search(r"\b(0\.\d|[1-9]\.\d)\b", work_text)
                        if m_dec:
                            hours_val = round(float(m_dec.group(1)), 1)
                            work_text = work_text[: m_dec.start()] + " " + work_text[m_dec.end() :]

            if hours_val <= 0:
                hours_val = 0.3

            # Match Client / Matter from list_docket_matters
            matters_res = self.list_docket_matters(user_id=uid)
            all_matters = matters_res.get("matters") or []
            matched_matter = None
            best_score = 0
            matched_tokens_to_strip: List[str] = []

            for m in all_matters:
                c_name = str(m.get("clientName") or "")
                m_name = str(m.get("matterName") or "")
                m_num = str(m.get("matterNumber") or "")
                # Check exact matter number first
                if m_num and m_num.lower() in low:
                    matched_matter = m
                    matched_tokens_to_strip = [m_num]
                    break
                # Check client name words (e.g. "Braun, Scott" -> ["braun", "scott"])
                words = [w for w in re.split(r"[^A-Za-z0-9]+", f"{c_name} {m_name}") if len(w) >= 3 and w.lower() not in {"inc", "ltd", "corp", "the", "and", "general", "matter", "trust", "family"}]
                hits = [w for w in words if re.search(rf"\b{re.escape(w)}\b", work_text, re.IGNORECASE)]
                if len(hits) > best_score:
                    best_score = len(hits)
                    matched_matter = m
                    matched_tokens_to_strip = hits

            # Strip leading "docket [for] <client>" prefix before narrative
            work_text = re.sub(r"^\s*(?:please\s+)?(?:docket|log|record)\s+(?:for\s+|on\s+)?", "", work_text, flags=re.IGNORECASE)
            if matched_matter:
                c_parts = [w for w in re.split(r"[^A-Za-z0-9]+", str(matched_matter.get("clientName") or "")) if len(w) >= 3]
                if c_parts:
                    pat_prefix = r"^\s*(?:for\s+|on\s+)?" + r"[\s,]+".join(re.escape(p) for p in c_parts) + r"\b[\s,:;-]*"
                    work_text = re.sub(pat_prefix, "", work_text, flags=re.IGNORECASE)
                    if len(c_parts) >= 2:
                        pat_rev = r"^\s*(?:for\s+|on\s+)?" + r"[\s,]+".join(re.escape(p) for p in reversed(c_parts)) + r"\b[\s,:;-]*"
                        work_text = re.sub(pat_rev, "", work_text, flags=re.IGNORECASE)

            docket_date = date.today().isoformat()
            if "yesterday" in low:
                docket_date = (date.today() - timedelta(days=1)).isoformat()
                work_text = re.sub(r"\byesterday\b", "", work_text, flags=re.IGNORECASE)
            elif "today" in low:
                work_text = re.sub(r"\btoday\b", "", work_text, flags=re.IGNORECASE)

            narrative = self._format_cra_safe_docket_narrative(work_text)
            msg = (
                f"⏱️ Pre-filled Docket ({hours_val:.1f}h"
                + (f" · {matched_matter['clientName']}" if matched_matter else "")
                + f"): “{narrative or work_text.strip()}”"
            )

            return {
                "ok": True,
                "intent": "DOCKET",
                "action": "fill_docket",
                "targetMode": "Docket",
                "matter": matched_matter,
                "hours": hours_val,
                "date": docket_date,
                "docketDate": docket_date,
                "description": narrative or work_text.strip(),
                "transcript": raw,
                "summary": msg,
                "message": msg,
            }

        # 6. Expense / Income / Pay Credit Card / Transfer Voice Commands
        txn_date = date.today().isoformat()
        if "yesterday" in low:
            txn_date = (date.today() - timedelta(days=1)).isoformat()

        # Detect Mode
        target_mode = "Expense"
        if re.search(r"\b(pay credit card|paid credit card|paid off|pay off)\b", low) or (
            "paid" in low and ("chequing" in low or "general" in low) and ("visa" in low or "mastercard" in low)
        ):
            target_mode = "Pay Credit Card"
        elif re.search(r"\b(received|income|deposit(?:ed)?|retainer|e-transfer from|paid by)\b", low):
            target_mode = "Income"
        elif re.search(r"\b(transfer(?:red)?|moved)\b.*\b(from|to)\b", low):
            target_mode = "Transfer"

        # Extract dollar amounts: look for explicit HST first ("with 8.14 HST" or "HST 8.14")
        explicit_hst: Optional[float] = None
        m_hst = re.search(
            r"(?:with\s+\$?(\d+(?:\.\d{1,2})?)\s*(?:in\s+)?(?:hst|tax)|(?:hst|tax)\s+(?:of\s+|is\s+)?\$?(\d+(?:\.\d{1,2})?))",
            low,
        )
        cleaned_for_amt = low
        if m_hst:
            hst_str = m_hst.group(1) or m_hst.group(2)
            explicit_hst = round(float(hst_str), 2)
            cleaned_for_amt = cleaned_for_amt[: m_hst.start()] + " " + cleaned_for_amt[m_hst.end() :]

        amt_matches = re.findall(r"\$?\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\b", cleaned_for_amt)
        nums = [float(a.replace(",", "")) for a in amt_matches if float(a.replace(",", "")) > 0 and float(a.replace(",", "")) != 13.0]
        amount_val = round(nums[0], 2) if nums else 0.0

        parsed_rcpt = self._parse_receipt_ocr_text(raw, user_id=uid)
        stream_id = parsed_rcpt.get("streamId") or "FAMILY"
        if "private ot" in low or "deborah private" in low:
            stream_id = "DEBORAH_OT_PRIVATE"
        elif "vha" in low:
            stream_id = "DEBORAH_OT_VHA"
        elif self._is_cory(uid) and ("sole prop" in low or "sole proprietorship" in low):
            stream_id = "CORY_SOLE_PROP"
        elif self._is_cory(uid) and ("professional corp" in low or "cory pc" in low or "law pc" in low or "business expense" in low):
            stream_id = "CORY_PC"

        from_acct = parsed_rcpt.get("fromAccount") or "SIMPLII_VISA"
        to_acct = ""
        if "triangle" in low or "mastercard" in low:
            from_acct = "TRIANGLE_MASTERCARD"
        elif "simplii" in low or "visa" in low:
            from_acct = "SIMPLII_VISA"
        elif "pc general" in low and self._is_cory(uid):
            from_acct = "CIBC_PC_GENERAL"
        elif "pc trust" in low and self._is_cory(uid):
            from_acct = "CIBC_PC_TRUST"
        elif "savings" in low:
            from_acct = "CIBC_SAVINGS"
        elif "chequing" in low or "checking" in low:
            from_acct = "CIBC_CHEQUING"

        if target_mode == "Pay Credit Card":
            from_acct = "CIBC_CHEQUING"
            to_acct = "TRIANGLE_MASTERCARD" if ("triangle" in low or "mastercard" in low) else "SIMPLII_VISA"

        if explicit_hst is not None:
            hst_mode = "zero" if explicit_hst == 0 else "custom"
            tax_val = explicit_hst
        elif "no hst" in low or "no tax" in low or "hst exempt" in low or "zero hst" in low:
            hst_mode = "zero"
            tax_val = 0.0
        else:
            hst_mode = parsed_rcpt.get("hstMode") or "auto"
            tax_val = round(amount_val * 13.0 / 113.0, 2) if hst_mode == "auto" and amount_val > 0 else 0.0

        payee_val = parsed_rcpt.get("payee") or ""
        if not payee_val:
            m_at = re.search(r"\b(?:at|from|to)\s+([A-Za-z0-9\s&'\-]+?)(?:\s+for|\s+on|\s+with|\s+\$|\s+\d|$)", raw, re.IGNORECASE)
            if m_at:
                payee_val = m_at.group(1).strip().title()

        msg = f"🎙️ Pre-filled {target_mode}: {payee_val or 'Entry'} · ${amount_val:,.2f} (HST ${tax_val:,.2f})"
        prefill_dict = {
            "mode": target_mode,
            "streamId": stream_id,
            "txnDate": txn_date,
            "amount": amount_val,
            "taxAmount": tax_val,
            "hstMode": hst_mode,
            "fromAccount": from_acct,
            "toAccount": to_acct,
            "payee": payee_val,
            "categoryCode": parsed_rcpt.get("categoryCode") or "",
            "notes": raw,
        }

        try:
            self.session_tracker.record_event(
                uid,
                "VOICE_COMMAND",
                f"Voice parsed: '{raw[:50]}' -> {target_mode} (${amount_val:,.2f})",
                item_data={"transcript": raw, "mode": target_mode, "amount": amount_val, "payee": payee_val},
            )
        except Exception:
            pass

        return {
            "ok": True,
            "intent": target_mode.upper().replace(" ", "_"),
            "action": "fill_expense",
            "targetMode": target_mode,
            "prefill": prefill_dict,
            "streamId": stream_id,
            "txnDate": txn_date,
            "amount": amount_val,
            "taxAmount": tax_val,
            "hstMode": hst_mode,
            "fromAccount": from_acct,
            "toAccount": to_acct,
            "payee": payee_val,
            "categoryCode": parsed_rcpt.get("categoryCode") or "",
            "notes": raw,
            "transcript": raw,
            "summary": msg,
            "message": msg,
        }

    # ------------------------------------------------------------------
    # 11. Mobile Invoicing, Quick New Matter Intake & Tax/SHL Snapshot
    # ------------------------------------------------------------------
    def _next_invoice_number(self, biller_entity: str = "SOLE_PROP", invoice_date: str = "") -> str:
        import sqlite3

        yr_prefix = (str(invoice_date or "")[:4] or str(date.today().year))[-2:]
        max_seq = 0
        for db_p in self._all_sqlite_db_paths():
            try:
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                for tbl, col in [("Invoice", "invoice_number"), ("Receivable", "invoice_id")]:
                    try:
                        cur.execute(f"SELECT {col} FROM {tbl}")
                        for (val,) in cur.fetchall():
                            m = re.match(rf"^{re.escape(yr_prefix)}-(\d{{4}})(?:-PC)?$", str(val or "").strip(), re.IGNORECASE)
                            if m:
                                max_seq = max(max_seq, int(m.group(1)))
                    except Exception:
                        pass
                conn.close()
            except Exception:
                pass
        next_seq = max_seq + 1
        suffix = "-PC" if str(biller_entity or "").upper() == "PC" else ""
        return f"{yr_prefix}-{next_seq:04d}{suffix}"

    def preview_mobile_invoice(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Build an instant formatted Concept_A2 HTML preview + totals for a matter's unbilled WIP."""
        import sqlite3
        from services.invoice_document_service import InvoiceDocumentService

        if not self._is_cory(user_id):
            return {"ok": False, "message": "Invoicing is restricted to Cory."}

        data = dict(payload or {})
        matter_ref = str(data.get("matterId") or data.get("matterNumber") or "").strip()
        invoice_date = str(data.get("invoiceDate") or date.today().isoformat())[:10]
        biller_entity = str(data.get("billerEntity") or ("PC" if invoice_date >= "2026-11-01" else "SOLE_PROP")).strip().upper()
        address_override = str(data.get("billerAddressOverride") or "").strip()
        selected_entry_ids = set(str(x) for x in (data.get("entryIds") or []) if x)

        db_path = self._resolve_sqlite_db_path()
        if not db_path or not db_path.is_file():
            return {"ok": False, "message": "SQLite database not found."}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT m.matter_id, m.matter_number, m.description AS matter_name, m.client_id,
                   c.name AS client_name, c.billing_name, c.address, c.city_prov_postal, c.hst_exempt
            FROM matters m
            LEFT JOIN clients c ON c.client_id = m.client_id
            WHERE lower(m.matter_id)=lower(?) OR lower(m.matter_number)=lower(?)
            LIMIT 1
            """,
            (matter_ref, matter_ref),
        )
        m_row = cur.fetchone()
        if not m_row:
            conn.close()
            return {"ok": False, "message": f"Matter '{matter_ref}' not found."}

        m_id = str(m_row["matter_id"] or "")
        m_num = str(m_row["matter_number"] or m_id)
        m_name = str(m_row["matter_name"] or "")
        c_id = str(m_row["client_id"] or "")
        c_name = str(m_row["client_name"] or c_id)
        bill_to = str(m_row["billing_name"] or c_name)
        hst_exempt = bool(m_row["hst_exempt"])

        cur.execute(
            """
            SELECT entry_id, entry_date, description, hours, rate_cents, fee_cents, hst_cents, total_cents
            FROM time_entries
            WHERE (matter_id=? OR lower(matter_id)=lower(?))
              AND COALESCE(is_billed, 0)=0
              AND lower(COALESCE(status, 'unbilled'))!='billed'
              AND COALESCE(billed_invoice_id, '')=''
            ORDER BY entry_date ASC, entry_id ASC
            """,
            (m_id, m_num),
        )
        t_rows = cur.fetchall()

        cur.execute(
            """
            SELECT disb_id, entry_date, description, amount_cents, hst_cents, total_cents
            FROM disbursements
            WHERE (matter_id=? OR lower(matter_id)=lower(?))
              AND COALESCE(is_billed, 0)=0
              AND COALESCE(billed_invoice_id, '')=''
            ORDER BY entry_date ASC, disb_id ASC
            """,
            (m_id, m_num),
        )
        d_rows = cur.fetchall()
        conn.close()

        time_items: List[Dict[str, Any]] = []
        total_hours = 0.0
        total_fees = 0.0
        total_hst = 0.0

        for r in t_rows:
            eid = str(r["entry_id"] or "")
            if selected_entry_ids and eid not in selected_entry_ids:
                continue
            hrs = round(float(r["hours"] or 0.0), 2)
            fee = round(float(r["fee_cents"] or 0) / 100.0, 2)
            rate = round(float(r["rate_cents"] or 0) / 100.0, 2) or (round(fee / hrs, 2) if hrs > 0 else 450.0)
            hst = 0.0 if hst_exempt else round(float(r["hst_cents"] or round(fee * 13.0)) / 100.0, 2)
            total_hours = round(total_hours + hrs, 2)
            total_fees = round(total_fees + fee, 2)
            total_hst = round(total_hst + hst, 2)
            time_items.append(
                {
                    "entryId": eid,
                    "date": str(r["entry_date"] or "")[:10],
                    "description": str(r["description"] or ""),
                    "hours": f"{hrs:.2f}",
                    "rate": f"${rate:,.2f}",
                    "amount": f"${fee:,.2f}",
                    "rawHours": hrs,
                    "rawFee": fee,
                    "rawHst": hst,
                }
            )

        disb_items: List[Dict[str, Any]] = []
        total_disb = 0.0
        for d in d_rows:
            amt = round(float(d["amount_cents"] or 0) / 100.0, 2)
            hst = 0.0 if hst_exempt else round(float(d["hst_cents"] or 0) / 100.0, 2)
            total_disb = round(total_disb + amt, 2)
            total_hst = round(total_hst + hst, 2)
            disb_items.append(
                {
                    "disbId": str(d["disb_id"] or ""),
                    "date": str(d["entry_date"] or "")[:10],
                    "description": str(d["description"] or ""),
                    "amount": f"${amt:,.2f}",
                    "rawAmount": amt,
                    "rawHst": hst,
                }
            )

        if not time_items and not disb_items:
            return {"ok": False, "message": "No unbilled WIP entries found for this matter."}

        grand_total = round(total_fees + total_disb + total_hst, 2)
        inv_num = str(data.get("invoiceNumber") or "").strip() or self._next_invoice_number(biller_entity, invoice_date)

        is_pc = biller_entity == "PC"
        default_addr = (
            "7 Saint Thomas Street, Suite 307, Toronto, ON M5S 2B7"
            if is_pc
            else "14 Parsons Court, Thornhill, ON L4K 6Z4"
        )
        biller_addr = address_override or default_addr
        hst_reg = "PENDING RT0001" if is_pc else "78621 8222 RT0001"
        payable_to = "Cory Schneider Law Professional Corporation" if is_pc else "CORY SCHNEIDER"
        footer_disc = (
            "Cory Schneider Law Office is a registered business name of Cory Schneider Law Professional Corporation."
            if is_pc
            else ""
        )

        doc_payload = {
            "invoice_number": inv_num,
            "invoice_date": invoice_date,
            "is_draft": False,
            "client_name": c_name,
            "billing_client_name": bill_to,
            "client_address": str(m_row["address"] or ""),
            "client_city_prov_postal": str(m_row["city_prov_postal"] or ""),
            "matter_number": m_num,
            "matter_description": m_name,
            "biller_entity": biller_entity,
            "biller_legal_name": payable_to,
            "biller_practice_name": "Cory Schneider Law Office",
            "biller_address_line": biller_addr,
            "biller_hst_number": hst_reg,
            "payable_to_name": payable_to,
            "etransfer_email": "cory@coryschneiderlaw.ca",
            "footer_disclosure_text": footer_disc,
            "time_entries": time_items,
            "disbursements": disb_items,
            "total_hours": f"{total_hours:.2f}",
            "gross_professional_fees": f"${total_fees:,.2f}",
            "net_professional_fees": f"${total_fees:,.2f}",
            "disbursement_total": f"${total_disb:,.2f}",
            "total_tax": f"${total_hst:,.2f}",
            "total_due": f"${grand_total:,.2f}",
        }

        try:
            doc_svc = InvoiceDocumentService()
            html_preview = doc_svc.generate_html("Concept_A2", doc_payload)
        except Exception:
            html_preview = ""

        return {
            "ok": True,
            "invoiceNumber": inv_num,
            "invoiceDate": invoice_date,
            "billerEntity": biller_entity,
            "billerAddress": biller_addr,
            "hstNumber": hst_reg,
            "payableTo": payable_to,
            "matterId": m_id,
            "matterNumber": m_num,
            "matterName": m_name,
            "clientId": c_id,
            "clientName": c_name,
            "billingClientName": bill_to,
            "docketCount": len(time_items),
            "feeCount": len(time_items),
            "disbCount": len(disb_items),
            "totalHours": total_hours,
            "feesPreTax": total_fees,
            "totalFees": total_fees,
            "totalFeesFormatted": f"${total_fees:,.2f}",
            "disbPreTax": total_disb,
            "totalDisbursements": total_disb,
            "totalDisbursementsFormatted": f"${total_disb:,.2f}",
            "totalTax": total_hst,
            "totalHst": total_hst,
            "totalHstFormatted": f"${total_hst:,.2f}",
            "grandTotal": grand_total,
            "grandTotalFormatted": f"${grand_total:,.2f}",
            "timeEntries": time_items,
            "disbursements": disb_items,
            "htmlPreview": html_preview,
        }

    def finalize_mobile_invoice(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize an invoice from the phone: update cspm.db immediately, render PDF in __RECEIVABLE,
        and synchronize CSPM.xlsm + Dockets.xlsm in the background."""
        import sqlite3
        import subprocess
        import sys
        import tempfile

        if not self._is_cory(user_id):
            return {"ok": False, "message": "Invoicing is restricted to Cory."}

        prev = self.preview_mobile_invoice(user_id=user_id, payload=payload)
        if not prev.get("ok"):
            return prev

        inv_num = str(prev["invoiceNumber"])
        inv_date = str(prev["invoiceDate"])
        biller_entity = str(prev["billerEntity"])
        biller_addr = str(prev["billerAddress"])
        c_id = str(prev["clientId"])
        c_name = str(prev["clientName"])
        bill_to = str(prev["billingClientName"])
        m_id = str(prev["matterId"])
        m_num = str(prev["matterNumber"])
        m_name = str(prev["matterName"])
        fees = float(prev["totalFees"])
        disb = float(prev["totalDisbursements"])
        hst = float(prev["totalHst"])
        total = float(prev["grandTotal"])
        time_ids = [str(t["entryId"]) for t in prev.get("timeEntries", []) if t.get("entryId")]
        disb_ids = [str(d["disbId"]) for d in prev.get("disbursements", []) if d.get("disbId")]
        html_content = str(prev.get("htmlPreview") or "")

        # 1. Render PDF to OneDrive - LPN/__Invoices (1)/__RECEIVABLE/
        pdf_path_str = ""
        try:
            od_root = next(
                (p for p in sorted(Path.home().glob("OneDrive*")) if (p / "__Invoices (1)").is_dir()),
                Path.home() / "OneDrive - LPN",
            )
            receivable_dir = od_root / "__Invoices (1)" / "__RECEIVABLE"
            receivable_dir.mkdir(parents=True, exist_ok=True)
            dt_obj = datetime.strptime(inv_date[:10], "%Y-%m-%d")
            date_tag = dt_obj.strftime("%d%b%Y").upper()
            pdf_out = receivable_dir / f"C - INV {inv_num} - {c_name} - {date_tag}.pdf"

            edge_candidates = [
                Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            ]
            edge_exe = next((p for p in edge_candidates if p.is_file()), None)
            if edge_exe and html_content:
                fd_h, tmp_html = tempfile.mkstemp(prefix="cspm_mob_inv_", suffix=".html")
                os.close(fd_h)
                try:
                    Path(tmp_html).write_text(html_content, encoding="utf-8")
                    creationflags = 0x08000000 if sys.platform == "win32" else 0
                    subprocess.run(
                        [
                            str(edge_exe),
                            "--headless",
                            "--disable-gpu",
                            f"--print-to-pdf={pdf_out}",
                            "--no-pdf-header-footer",
                            Path(tmp_html).as_uri(),
                        ],
                        check=True,
                        creationflags=creationflags,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                    if pdf_out.is_file():
                        pdf_path_str = str(pdf_out)
                finally:
                    try:
                        os.remove(tmp_html)
                    except OSError:
                        pass
        except Exception as exc:
            logger.warning("Mobile invoice PDF render warning: %s", exc)

        # 2. Update all SQLite databases (cspm.db) immediately
        now_utc = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        for db_p in self._all_sqlite_db_paths():
            try:
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                for eid in time_ids:
                    cur.execute(
                        "UPDATE TimeEntry SET status='Billed', is_billed=1, billed_invoice_id=?, updated_at=? WHERE time_id=?",
                        (inv_num, now_utc, eid),
                    )
                    cur.execute(
                        "UPDATE time_entries SET status='Billed', is_billed=1, billed_invoice_id=?, updated_at=? WHERE entry_id=?",
                        (inv_num, now_utc, eid),
                    )
                for did in disb_ids:
                    cur.execute(
                        "UPDATE disbursements SET is_billed=1, billed_invoice_id=?, updated_at=? WHERE disb_id=?",
                        (inv_num, now_utc, did),
                    )
                cur.execute("DELETE FROM Invoice WHERE invoice_id=? OR invoice_number=?", (inv_num, inv_num))
                cur.execute(
                    """
                    INSERT INTO Invoice (
                        invoice_id, invoice_number, client_id, client_name, parent_id, parent_name,
                        matter_id, matter_name, invoice_date, due_date, status,
                        fees, fees_cents, disbursements, disbursements_cents,
                        hst, hst_cents, total, total_cents,
                        paid_amount, paid_amount_cents, file_path,
                        biller_entity, biller_address_override, biller_hst_override
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        inv_num, inv_num, c_id, c_name, "", bill_to,
                        m_id, m_name, inv_date, inv_date, "Unpaid",
                        fees, int(round(fees * 100)), disb, int(round(disb * 100)),
                        hst, int(round(hst * 100)), total, int(round(total * 100)),
                        0.0, 0, pdf_path_str,
                        biller_entity, biller_addr, "",
                    ),
                )
                cur.execute("DELETE FROM Receivable WHERE receivable_id=? OR invoice_id=?", (inv_num, inv_num))
                cur.execute(
                    """
                    INSERT INTO Receivable (
                        receivable_id, invoice_id, client_id, client_name, parent_id, parent_name,
                        invoice_date, due_date, original_amount, original_amount_cents,
                        paid_amount, paid_amount_cents, balance, balance_cents,
                        status, biller_entity, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        inv_num, inv_num, c_id, bill_to, "", c_name,
                        inv_date, inv_date, total, int(round(total * 100)),
                        0.0, 0, total, int(round(total * 100)),
                        "Unpaid", biller_entity, now_utc,
                    ),
                )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.warning("SQLite finalize invoice warning (%s): %s", db_p, exc)

        self._cached_ar_snapshot = None

        # 3. Also trigger background workbook sync via manage_invoice.py if available
        if not self._is_isolated_test() and time_ids:
            dates = sorted(str(t.get("date") or inv_date) for t in prev.get("timeEntries", []))
            from_d = dates[0] if dates else inv_date
            to_d = dates[-1] if dates else inv_date
            threading.Thread(
                target=self._background_sync_invoice_workbooks,
                args=(c_name, from_d, to_d, inv_date, inv_num, fees, disb, hst, total, bill_to),
                name=f"SyncInvoice_{inv_num}",
                daemon=True,
            ).start()

        try:
            self.session_tracker.record_event(
                "cory",
                "INVOICE_ACTION",
                f"Finalized Invoice #{inv_num} ({c_name}): ${total:,.2f}",
                item_data={"action": "FINALIZED", "invoiceNumber": inv_num, "client": c_name, "amount": total},
            )
        except Exception:
            pass

        return {
            "ok": True,
            "invoiceNumber": inv_num,
            "invoiceDate": inv_date,
            "clientName": c_name,
            "billingClientName": bill_to,
            "matterNumber": m_num,
            "grandTotal": total,
            "grandTotalFormatted": f"${total:,.2f}",
            "pdfUrl": f"/api/invoice/pdf?invoice={inv_num}&userId=cory",
            "pdfPath": pdf_path_str,
            "message": f"🧾 Finalized Invoice {inv_num} ({f'${total:,.2f}'})!",
        }

    def _background_sync_invoice_workbooks(
        self,
        client_name: str,
        from_date: str,
        to_date: str,
        invoice_date: str,
        invoice_num: str,
        fees: float,
        disb: float,
        hst: float,
        total: float,
        bill_to_client: str,
    ) -> None:
        try:
            script_path = Path.home() / ".gemini" / "config" / "skills" / "cspm-invoice" / "scripts" / "manage_invoice.py"
            if script_path.is_file():
                import importlib.util

                spec = importlib.util.spec_from_file_location("manage_invoice_mod", str(script_path))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    paths = mod.discover_paths()
                    mod.finalize_in_dockets_xlsm(
                        paths,
                        invoice_num=invoice_num,
                        client_query=client_name,
                        from_date=from_date,
                        to_date=to_date,
                        invoice_date=invoice_date,
                        fees=fees,
                        disb=disb,
                        hst=hst,
                        total=total,
                        bill_to_client=bill_to_client,
                        sub_client=client_name if bill_to_client.casefold() != client_name.casefold() else "",
                    )
        except Exception as exc:
            logger.debug("Background workbook invoice sync note: %s", exc)

    def reverse_mobile_invoice(self, user_id: str, invoice_number: str) -> Dict[str, Any]:
        """Reverse/void an invoice from the phone, unlocking its dockets back to Unbilled WIP."""
        import sqlite3

        if not self._is_cory(user_id):
            return {"ok": False, "message": "Reversing invoices is restricted to Cory."}
        inv_num = str(invoice_number or "").strip()
        if not inv_num:
            return {"ok": False, "message": "Please specify an invoice number to reverse."}

        now_utc = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        unlocked_count = 0
        for db_p in self._all_sqlite_db_paths():
            try:
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                cur.execute(
                    "UPDATE TimeEntry SET status='Unbilled', is_billed=0, billed_invoice_id='', updated_at=? WHERE lower(COALESCE(billed_invoice_id,''))=lower(?)",
                    (now_utc, inv_num),
                )
                cur.execute(
                    "UPDATE time_entries SET status='Unbilled', is_billed=0, billed_invoice_id='', updated_at=? WHERE lower(COALESCE(billed_invoice_id,''))=lower(?)",
                    (now_utc, inv_num),
                )
                unlocked_count = max(unlocked_count, cur.rowcount or 0)
                cur.execute(
                    "UPDATE disbursements SET is_billed=0, billed_invoice_id='', updated_at=? WHERE lower(COALESCE(billed_invoice_id,''))=lower(?)",
                    (now_utc, inv_num),
                )
                cur.execute("DELETE FROM Invoice WHERE lower(invoice_id)=lower(?) OR lower(invoice_number)=lower(?)", (inv_num, inv_num))
                cur.execute("DELETE FROM Receivable WHERE lower(receivable_id)=lower(?) OR lower(invoice_id)=lower(?)", (inv_num, inv_num))
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.warning("SQLite reverse invoice warning (%s): %s", db_p, exc)

        self._cached_ar_snapshot = None
        try:
            self.session_tracker.record_event(
                "cory",
                "INVOICE_ACTION",
                f"Reversed Invoice #{inv_num}",
                item_data={"action": "REVERSED", "invoiceNumber": inv_num},
            )
        except Exception:
            pass

        return {
            "ok": True,
            "invoiceNumber": inv_num,
            "unlockedEntries": unlocked_count,
            "message": f"↩️ Reversed Invoice {inv_num} and unlocked dockets back to Unbilled WIP.",
        }

    def resolve_invoice_pdf(self, user_id: str, invoice_number: str) -> Optional[Tuple[Path, str]]:
        """Locate or render the PDF for any invoice number in __RECEIVABLE, __Invoices (1), or Clients (CS)."""
        import sqlite3

        inv_num = str(invoice_number or "").strip()
        if not inv_num:
            return None

        # 1. Check file_path in cspm.db
        db_path = self._resolve_sqlite_db_path()
        if db_path and db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                cur.execute(
                    "SELECT file_path FROM Invoice WHERE lower(invoice_number)=lower(?) OR lower(invoice_id)=lower(?) LIMIT 1",
                    (inv_num, inv_num),
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    cand = Path(str(row[0]))
                    if cand.is_file() and cand.suffix.lower() == ".pdf":
                        return cand, cand.name
            except Exception:
                pass

        # 2. Search OneDrive - LPN/__Invoices (1)/__RECEIVABLE and __Invoices (1)
        for od in sorted(Path.home().glob("OneDrive*")):
            inv_root = od / "__Invoices (1)"
            if not inv_root.is_dir():
                continue
            for folder in (inv_root / "__RECEIVABLE", inv_root):
                if not folder.is_dir():
                    continue
                matches = [
                    f for f in sorted(folder.glob(f"*{inv_num}*.pdf"))
                    if f.is_file()
                ]
                if matches:
                    # Prefer clean "INV ..." or "C - INV ..."
                    best = matches[0]
                    return best, best.name

        return None

    def create_quick_matter(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Quickly create a new Client & Matter from the phone in cspm.db so Cory can docket immediately."""
        import sqlite3

        if not self._is_cory(user_id):
            return {"ok": False, "message": "Creating matters is restricted to Cory."}

        data = dict(payload or {})
        client_name = str(data.get("clientName") or "").strip()
        matter_name = str(data.get("matterName") or data.get("description") or "General Legal Services").strip()
        matter_type = str(data.get("matterType") or "General").strip()
        rate = float(data.get("rate") or data.get("defaultRate") or 475.0)
        biller_entity = str(data.get("billerEntity") or ("PC" if date.today().isoformat() >= "2026-11-01" else "SOLE_PROP")).strip().upper()

        if not client_name:
            return {"ok": False, "message": "Please enter the Client Name."}

        clean_tok = re.sub(r"[^A-Za-z0-9]+", "", client_name.upper())[:4].ljust(4, "X")
        type_tok = re.sub(r"[^A-Za-z]+", "", matter_type.upper())[:3] or "GEN"
        seq_num = datetime.now().strftime("%m%d")
        matter_number = str(data.get("matterNumber") or f"{clean_tok}-{seq_num}-{type_tok}").strip().upper()
        client_id = f"C_{clean_tok}_{uuid4().hex[:4].upper()}"
        matter_id = f"M_{matter_number.replace('-', '_')}"
        now_iso = datetime.now().strftime("%Y-%m-%d")

        for db_p in self._all_sqlite_db_paths():
            try:
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                cur.execute(
                    "SELECT client_id, name FROM clients WHERE lower(name)=lower(?) LIMIT 1",
                    (client_name,),
                )
                existing_c = cur.fetchone()
                if existing_c:
                    client_id = str(existing_c[0])
                else:
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO clients (
                            client_id, name, billing_name, default_rate_cents, hst_exempt, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, 'Active', ?, ?)
                        """,
                        (client_id, client_name, client_name, int(round(rate * 100)), now_iso, now_iso),
                    )
                cur.execute(
                    """
                    INSERT OR REPLACE INTO matters (
                        matter_id, matter_number, client_id, description, matter_type,
                        status, open_date, default_rate_cents, default_biller_entity, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?)
                    """,
                    (
                        matter_id,
                        matter_number,
                        client_id,
                        matter_name,
                        matter_type,
                        now_iso,
                        int(round(rate * 100)),
                        biller_entity,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.warning("create_quick_matter SQLite warning (%s): %s", db_p, exc)

        return {
            "ok": True,
            "matter": {
                "matterId": matter_id,
                "matterNumber": matter_number,
                "matterName": matter_name,
                "clientId": client_id,
                "clientName": client_name,
                "defaultRate": rate,
                "defaultBillerEntity": biller_entity,
                "displayLabel": f"{client_name} — {matter_name} ({matter_number})",
            },
            "message": f"➕ Created Matter {matter_number} ({client_name} — {matter_name})!",
        }

    def get_tax_and_shl_snapshot(self, user_id: str = "cory") -> Dict[str, Any]:
        """Return live Dual HST (RT0001 for SOLE_PROP & PC), Shareholder Loan (GIFI 2781),
        and Family / OT Tax Credit & Deduction buckets for 2026."""
        import sqlite3

        if not self._is_cory(user_id):
            return {"ok": False, "message": "Tax & Shareholder Loan snapshot is restricted to Cory."}

        # 1. Shareholder Loan (GIFI 2781) — Verified Oct 17, 2026 Opening + PC Personal Outlays
        shl_entries = [
            {
                "entryId": "SHL-2026-0001",
                "date": "2026-10-17",
                "vendor": "Advanced Consulting & Engineering Inc. (GetNuans.com)",
                "description": "Ontario NUANS corporate name search report",
                "preTax": 39.95,
                "hstItc": 0.00,
                "gross": 39.95,
                "delta": 39.95,
                "runningBalance": 39.95,
            },
            {
                "entryId": "SHL-2026-0002",
                "date": "2026-10-17",
                "vendor": "ServiceOntario (OCN 1001781977)",
                "description": "Statutory Articles of Incorporation filing fee",
                "preTax": 300.00,
                "hstItc": 0.00,
                "gross": 300.00,
                "delta": 300.00,
                "runningBalance": 339.95,
            },
            {
                "entryId": "SHL-2026-0003",
                "date": "2026-10-17",
                "vendor": "ServiceOntario (BIN 1001782016)",
                "description": "Statutory Business Name Registration fee",
                "preTax": 60.00,
                "hstItc": 0.00,
                "gross": 60.00,
                "delta": 60.00,
                "runningBalance": 399.95,
            },
            {
                "entryId": "SHL-2026-0004",
                "date": "2026-10-17",
                "vendor": "Law Society of Ontario (App #534837)",
                "description": "2026 Certificate of Authorization application fee",
                "preTax": 350.00,
                "hstItc": 45.50,
                "gross": 395.50,
                "delta": 395.50,
                "runningBalance": 795.45,
            },
            {
                "entryId": "SHL-2026-0005",
                "date": "2026-10-17",
                "vendor": "Cory Schneider Law PC (Treasury)",
                "description": "OBCA s. 23(3) Set-off for 100 Class 1 Common Shares ($1.00)",
                "preTax": 0.00,
                "hstItc": 0.00,
                "gross": 1.00,
                "delta": -1.00,
                "runningBalance": 794.45,
            },
        ]
        shl_balance = 794.45
        shl_pre_tax_total = 749.95
        shl_itc_total = 45.50

        # Also check any CORY_PC expenses paid via personal cards/accounts in 2026
        ytd_entries = self.list_entries(user_id="cory", period="ytd")
        personal_cards = {"SIMPLII_VISA", "TRIANGLE_MASTERCARD", "CIBC_CHEQUING", "CIBC_SAVINGS", "CORY_PERSONAL"}

        sp_itcs = 0.0
        sp_expenses_pre_tax = 0.0
        pc_itcs = 45.50
        pc_expenses_pre_tax = 749.95

        family_tax_buckets = {
            "medical": {"label": "🏥 Medical, Dental & Pharmacy", "total": 0.0, "count": 0},
            "childcare": {"label": "🎒 Childcare, Tuition & Kids", "total": 0.0, "count": 0},
            "donations": {"label": "💝 Charitable Donations", "total": 0.0, "count": 0},
            "deborahPrivate": {"label": "👩‍⚕️ Deborah OT (Private) Net", "income": 0.0, "expense": 0.0, "hstItc": 0.0},
            "deborahVha": {"label": "🏥 Deborah OT (VHA) Net", "income": 0.0, "expense": 0.0, "hstItc": 0.0},
        }

        for e in ytd_entries:
            sid = str(e.get("streamId") or "")
            cat = str(e.get("categoryCode") or "").upper()
            amt = float(e.get("amount") or 0.0)
            hst = float(e.get("taxAmount") or 0.0)
            pre = round(max(0.0, amt - hst), 2)

            if e.get("mode") == "Expense":
                if sid == "CORY_SOLE_PROP":
                    sp_expenses_pre_tax = round(sp_expenses_pre_tax + pre, 2)
                    sp_itcs = round(sp_itcs + hst, 2)
                elif sid == "CORY_PC":
                    pc_expenses_pre_tax = round(pc_expenses_pre_tax + pre, 2)
                    pc_itcs = round(pc_itcs + hst, 2)
                    if str(e.get("fromAccount") or "") in personal_cards:
                        shl_balance = round(shl_balance + amt, 2)
                        shl_pre_tax_total = round(shl_pre_tax_total + pre, 2)
                        shl_itc_total = round(shl_itc_total + hst, 2)
                        shl_entries.append(
                            {
                                "entryId": str(e.get("transactionId") or ""),
                                "date": str(e.get("txnDate") or ""),
                                "vendor": str(e.get("payee") or ""),
                                "description": str(e.get("categoryName") or ""),
                                "preTax": pre,
                                "hstItc": hst,
                                "gross": amt,
                                "delta": amt,
                                "runningBalance": shl_balance,
                            }
                        )
                elif sid == "DEBORAH_OT_PRIVATE":
                    family_tax_buckets["deborahPrivate"]["expense"] = round(
                        family_tax_buckets["deborahPrivate"]["expense"] + pre, 2
                    )
                    family_tax_buckets["deborahPrivate"]["hstItc"] = round(
                        family_tax_buckets["deborahPrivate"]["hstItc"] + hst, 2
                    )
                elif sid == "DEBORAH_OT_VHA":
                    family_tax_buckets["deborahVha"]["expense"] = round(
                        family_tax_buckets["deborahVha"]["expense"] + pre, 2
                    )
                    family_tax_buckets["deborahVha"]["hstItc"] = round(
                        family_tax_buckets["deborahVha"]["hstItc"] + hst, 2
                    )
                elif sid == "FAMILY":
                    if cat in {"EXP_MEDICAL", "EXP_DENTAL", "EXP_VISION", "EXP_PHARMACY", "EXP_THERAPY", "EXP_HEALTH_INSURANCE"}:
                        family_tax_buckets["medical"]["total"] = round(family_tax_buckets["medical"]["total"] + amt, 2)
                        family_tax_buckets["medical"]["count"] += 1
                    elif cat in {"EXP_CHILDCARE", "EXP_SCHOOL_TUITION", "EXP_KIDS_ACTIVITIES", "EXP_SCHOOL_SUPPLIES"}:
                        family_tax_buckets["childcare"]["total"] = round(family_tax_buckets["childcare"]["total"] + amt, 2)
                        family_tax_buckets["childcare"]["count"] += 1
                    elif cat in {"EXP_DONATIONS", "EXP_CHARITY"}:
                        family_tax_buckets["donations"]["total"] = round(family_tax_buckets["donations"]["total"] + amt, 2)
                        family_tax_buckets["donations"]["count"] += 1
            elif e.get("mode") == "Income":
                if sid == "DEBORAH_OT_PRIVATE":
                    family_tax_buckets["deborahPrivate"]["income"] = round(
                        family_tax_buckets["deborahPrivate"]["income"] + amt, 2
                    )
                elif sid == "DEBORAH_OT_VHA":
                    family_tax_buckets["deborahVha"]["income"] = round(
                        family_tax_buckets["deborahVha"]["income"] + amt, 2
                    )

        # 2. Query 2026 Billed Revenue & HST Collected from cspm.db (SOLE_PROP vs PC)
        sp_rev = 0.0
        sp_hst_collected = 0.0
        pc_rev = 0.0
        pc_hst_collected = 0.0
        db_path = self._resolve_sqlite_db_path()
        if db_path and db_path.is_file():
            try:
                conn = sqlite3.connect(str(db_path))
                cur = conn.cursor()
                inv_cols = {c[1] for c in cur.execute("PRAGMA table_info(Invoice)").fetchall()}
                dt_col = "date" if "date" in inv_cols else "invoice_date"
                fees_col = "total_fees" if "total_fees" in inv_cols else "fees"
                disb_col = "total_disbursements" if "total_disbursements" in inv_cols else "disbursements"
                hst_col = "tax_amount" if "tax_amount" in inv_cols else "hst"
                cur.execute(
                    f"""
                    SELECT COALESCE(biller_entity, 'SOLE_PROP'),
                           SUM(COALESCE({fees_col}, 0) + COALESCE({disb_col}, 0)),
                           SUM(COALESCE({hst_col}, 0))
                    FROM Invoice
                    WHERE substr(COALESCE({dt_col}, ''), 1, 4) = '2026'
                      AND lower(COALESCE(status, '')) NOT IN ('void', 'voided', 'reversed', 'cancelled')
                    GROUP BY COALESCE(biller_entity, 'SOLE_PROP')
                    """
                )
                for b_ent, rev_sum, hst_sum in cur.fetchall():
                    if str(b_ent or "").upper() == "PC":
                        pc_rev = round(float(rev_sum or 0.0), 2)
                        pc_hst_collected = round(float(hst_sum or 0.0), 2)
                    else:
                        sp_rev = round(float(rev_sum or 0.0), 2)
                        sp_hst_collected = round(float(hst_sum or 0.0), 2)
                conn.close()
            except Exception as exc:
                logger.debug("Tax snapshot invoice query note: %s", exc)

        sp_net_hst = round(sp_hst_collected - sp_itcs, 2)
        pc_net_hst = round(pc_hst_collected - pc_itcs, 2)

        idx = self._read_receipts_index()
        receipts_count = len(idx.get("byTxnId", {}))

        sp_hst_dict = {
            "billerCode": "SOLE_PROP",
            "label": "Cory Schneider (Sole Prop — T2125)",
            "hstNumber": "78621 8222 RT0001",
            "line101Sales": sp_rev,
            "line101Revenue": sp_rev,
            "line101Formatted": f"${sp_rev:,.2f}",
            "line103HstCollected": sp_hst_collected,
            "line103Formatted": f"${sp_hst_collected:,.2f}",
            "line106Itcs": sp_itcs,
            "line108Itcs": sp_itcs,
            "line108Formatted": f"${sp_itcs:,.2f}",
            "line109NetTax": sp_net_hst,
            "line109Formatted": f"${sp_net_hst:,.2f}",
        }
        pc_hst_dict = {
            "billerCode": "PC",
            "label": "Cory Schneider Law PC (T2 — Nov 1+)",
            "hstNumber": "PENDING RT0001",
            "line101Sales": pc_rev,
            "line101Revenue": pc_rev,
            "line101Formatted": f"${pc_rev:,.2f}",
            "line103HstCollected": pc_hst_collected,
            "line103Formatted": f"${pc_hst_collected:,.2f}",
            "line106Itcs": pc_itcs,
            "line108Itcs": pc_itcs,
            "line108Formatted": f"${pc_itcs:,.2f}",
            "line109NetTax": pc_net_hst,
            "line109Formatted": (
                f"-${abs(pc_net_hst):,.2f} (Refund)" if pc_net_hst < 0 else f"${pc_net_hst:,.2f}"
            ),
        }

        streams_ytd = [
            {
                "streamId": "CORY_SOLE_PROP",
                "icon": "⚖️",
                "label": "Cory Legal (Sole Prop — T2125)",
                "incomePreTax": sp_rev,
                "expensePreTax": sp_expenses_pre_tax,
                "hstCollected": sp_hst_collected,
                "hstItc": sp_itcs,
            },
            {
                "streamId": "CORY_PC",
                "icon": "🏛️",
                "label": "Cory Schneider Law PC (T2)",
                "incomePreTax": pc_rev,
                "expensePreTax": pc_expenses_pre_tax,
                "hstCollected": pc_hst_collected,
                "hstItc": pc_itcs,
            },
            {
                "streamId": "DEBORAH_OT_PRIVATE",
                "icon": "👩‍⚕️",
                "label": "Deborah OT (Private — T2125)",
                "incomePreTax": family_tax_buckets["deborahPrivate"]["income"],
                "expensePreTax": family_tax_buckets["deborahPrivate"]["expense"],
                "hstCollected": 0.0,
                "hstItc": family_tax_buckets["deborahPrivate"]["hstItc"],
            },
            {
                "streamId": "DEBORAH_OT_VHA",
                "icon": "🏥",
                "label": "Deborah OT (VHA — T2125)",
                "incomePreTax": family_tax_buckets["deborahVha"]["income"],
                "expensePreTax": family_tax_buckets["deborahVha"]["expense"],
                "hstCollected": 0.0,
                "hstItc": family_tax_buckets["deborahVha"]["hstItc"],
            },
        ]

        return {
            "ok": True,
            "year": date.today().year,
            "asOfDate": date.today().isoformat(),
            "receiptsCount": receipts_count,
            "shareholderLoan": {
                "gifiCode": "2781",
                "entityName": "Cory Schneider Law Professional Corporation",
                "holder": "Cory Adam Schneider",
                "balance": shl_balance,
                "closingBalance": shl_balance,
                "balanceFormatted": f"${shl_balance:,.2f}",
                "runningBalanceFormatted": f"${shl_balance:,.2f}",
                "preTaxCorporateExpense": shl_pre_tax_total,
                "preTaxCorporateExpenseFormatted": f"${shl_pre_tax_total:,.2f}",
                "claimablePcItc": shl_itc_total,
                "claimablePcItcFormatted": f"${shl_itc_total:,.2f}",
                "entryCount": len(shl_entries),
                "note": f"Includes Oct 17, 2026 incorporation outlays ($749.95 pre-tax + $45.50 HST ITC − $1.00 OBCA s. 23(3) share set-off)",
                "entries": shl_entries,
            },
            "hst": {
                "SOLE_PROP": sp_hst_dict,
                "soleProp": sp_hst_dict,
                "PC": pc_hst_dict,
                "pc": pc_hst_dict,
            },
            "streamsYtd": streams_ytd,
            "familyTaxBuckets": family_tax_buckets,
        }

    # ------------------------------------------------------------------
    # 12. Session Management & Old-School Batch Reporting (v16)
    # ------------------------------------------------------------------
    def format_old_school_session_report(self, session_data: Dict[str, Any]) -> Tuple[str, str]:
        from services.quick_expense_session import format_old_school_session_report as _fmt
        return _fmt(session_data)

    def complete_session(
        self,
        user_id: str,
        reason: str = "Operator Finished Session",
        force_send: bool = False,
        client_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.session_tracker.complete_session(
            user_id=user_id,
            reason=reason,
            force_send=force_send,
            client_meta=client_meta,
        )

    def check_and_complete_idle_sessions(self, idle_seconds: int = 600) -> List[Dict[str, Any]]:
        return self.session_tracker.check_and_complete_idle_sessions(idle_seconds=idle_seconds)

    def get_active_session(
        self, user_id: str, client_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self.session_tracker.get_or_create_active_session(user_id=user_id, client_meta=client_meta)


