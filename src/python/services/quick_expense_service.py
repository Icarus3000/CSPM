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
            return {
                "ok": True,
                "user": {
                    "userId": "deborah",
                    "displayName": "Deborah",
                    "icon": "👩‍⚕️",
                    "role": "Family, Deborah OT & Legal Practice Entry",
                    "isCory": False,
                },
            }

        if user_key == "cory":
            expected_cory_pin = os.environ.get("CSPM_CORY_PIN", "1977").strip()
            if entered_pin and entered_pin != expected_cory_pin:
                return {"ok": False, "message": "Incorrect PIN for Cory."}
            if not entered_pin and expected_cory_pin:
                return {"ok": False, "requiresPin": True, "message": "Please enter Cory's PIN."}
            return {
                "ok": True,
                "user": {
                    "userId": "cory",
                    "displayName": "Cory",
                    "icon": "⚖️",
                    "role": "Full Access (All Accounts & Entities)",
                    "isCory": True,
                },
            }

        return {"ok": False, "message": "Please choose Deborah or Cory to sign in."}

    # ------------------------------------------------------------------
    # 2. Hard Privacy Firewall Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_cory(user_id: str) -> bool:
        return str(user_id or "").strip().lower() == "cory"

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
            self.flush_pending_inbox()

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

        try:
            self.flush_pending_inbox()
            result = self.finance_repo.save_transaction(repo_payload)
            if result.get("ok"):
                saved_id = str(result.get("transactionId") or "")
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

        # Fallback: If CSPM.xlsm is currently open/locked in Excel, queue safely into
        # OneDrive/CSPM_Shared_Data/QuickExpense_Sync/inbox.json so there is ZERO conflict!
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
        enriched = self._enrich_row(repo_payload)
        return {
            "ok": True,
            "transactionId": txn_id,
            "entry": enriched,
            "queuedToOneDriveInbox": True,
            "message": "Saved to OneDrive Sync Queue (will merge into CSPM.xlsm automatically)!",
        }

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

        return {
            "transactionId": str(row.get("transactionId") or ""),
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
            start = today - timedelta(days=today.weekday())
            return start.isoformat(), today.isoformat(), f"This Week ({start.isoformat()} to {today.isoformat()})"
        if p in ("this_month", "month"):
            start = today.replace(day=1)
            return start.isoformat(), today.isoformat(), f"This Month ({today.strftime('%B %Y')})"
        if p == "last_month":
            first_this = today.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            first_prev = last_prev.replace(day=1)
            return first_prev.isoformat(), last_prev.isoformat(), f"Last Month ({last_prev.strftime('%B %Y')})"
        if p in ("this_year", "year"):
            start = today.replace(month=1, day=1)
            return start.isoformat(), today.isoformat(), f"This Year ({today.year})"
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
        }

        for e in entries:
            amt = float(e.get("amount") or 0.0)
            hst = float(e.get("taxAmount") or 0.0)
            sid = e.get("streamId") or "FAMILY"
            bucket = by_stream.get(sid)
            if bucket:
                bucket["count"] += 1

            if e["mode"] == "Expense":
                expense_total = round(expense_total + amt, 2)
                expense_hst = round(expense_hst + hst, 2)
                if bucket:
                    bucket["expenseTotal"] = round(bucket["expenseTotal"] + amt, 2)
                    bucket["hstTotal"] = round(bucket["hstTotal"] + hst, 2)
            elif e["mode"] == "Income":
                income_total = round(income_total + amt, 2)
                if bucket:
                    bucket["incomeTotal"] = round(bucket["incomeTotal"] + amt, 2)
            else:
                transfer_total = round(transfer_total + amt, 2)

        for b in by_stream.values():
            b["expenseFormatted"] = f"${b['expenseTotal']:,.2f}"
            b["hstFormatted"] = f"${b['hstTotal']:,.2f}"
            b["incomeFormatted"] = f"${b['incomeTotal']:,.2f}"

        return {
            "ok": True,
            "userId": uid,
            "period": period,
            "periodLabel": period_label,
            "dateFrom": d_from,
            "dateTo": d_to,
            "entryCount": len(entries),
            "expensePreTaxTotal": round(max(0.0, expense_total - expense_hst), 2),
            "expensePreTaxFormatted": f"${max(0.0, expense_total - expense_hst):,.2f}",
            "expenseHstTotal": expense_hst,
            "expenseHstFormatted": f"${expense_hst:,.2f}",
            "expenseGrandTotal": expense_total,
            "expenseGrandFormatted": f"${expense_total:,.2f}",
            "incomeTotal": income_total,
            "incomeFormatted": f"${income_total:,.2f}",
            "transferTotal": transfer_total,
            "transferFormatted": f"${transfer_total:,.2f}",
            "byStream": list(by_stream.values()),
            "entries": entries,
        }

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
            d_span = max(1.0, float(b_stat.get("daysSpan") or 1.0))
            b_stat["avgHoursPerDay"] = round(float(b_stat.get("hours") or 0.0) / d_span, 1)
            b_stat["avgFeePerDay"] = round(float(b_stat.get("feePreTax") or 0.0) / d_span, 2)
            if key_b == "ytd":
                b_stat["avgHoursPerMonth"] = round(float(b_stat.get("hours") or 0.0) / ytd_months_elapsed, 1)
                b_stat["avgFeePerMonth"] = round(float(b_stat.get("feePreTax") or 0.0) / ytd_months_elapsed, 2)

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
                return res
            except Exception as exc:
                return {"ok": False, "message": str(exc)}
