from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        "sortOrder": 11,
        "isCreditCard": True,
    },
    "CIBC_CHEQUING": {
        "icon": "🏦",
        "displayName": "CIBC Personal Chequing",
        "shortName": "CIBC Personal Cheq",
        "group": "Personal & Family Bank Accounts",
        "sortOrder": 20,
        "isBank": True,
    },
    "CIBC_SAVINGS": {
        "icon": "🐷",
        "displayName": "CIBC Personal Savings",
        "shortName": "CIBC Savings",
        "group": "Personal & Family Bank Accounts",
        "sortOrder": 21,
        "isBank": True,
    },
    "SIMPLII_CHEQUING": {
        "icon": "🏦",
        "displayName": "Simplii Chequing",
        "shortName": "Simplii Chequing",
        "group": "Personal & Family Bank Accounts",
        "sortOrder": 22,
        "isBank": True,
    },
    "CIBC_PC_GENERAL": {
        "icon": "🏛️",
        "displayName": "CIBC PC General",
        "shortName": "CIBC PC General",
        "group": "Cory PC Business Accounts",
        "sortOrder": 30,
        "isBank": True,
        "isCorpGeneral": True,
    },
    "CIBC_PC_TRUST": {
        "icon": "⚖️",
        "displayName": "CIBC PC Trust (Client Money In / Out to General Only)",
        "shortName": "CIBC PC Trust",
        "group": "Cory PC Business Accounts",
        "sortOrder": 31,
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
        "sortOrder": 40,
        "isCash": True,
    },
    "CASH_CORY": {
        "icon": "💵",
        "displayName": "Cash - Cory",
        "shortName": "Cash (Cory)",
        "group": "Cash",
        "sortOrder": 41,
        "isCash": True,
    },
    "CIBC_MORTGAGE": {
        "icon": "🏠",
        "displayName": "CIBC Mortgage Account",
        "shortName": "CIBC Mortgage",
        "group": "Mortgages",
        "sortOrder": 50,
        "isDebt": True,
    },
    "HOME_TRUST_MORTGAGE": {
        "icon": "🏡",
        "displayName": "Home Trust Mortgage Account",
        "shortName": "Home Trust Mortgage",
        "group": "Mortgages",
        "sortOrder": 51,
        "isDebt": True,
    },
    # Cory-Only Accounts (Filtered out on backend for Deborah):
    "KOHO": {
        "icon": "🔒",
        "displayName": "Koho",
        "shortName": "Koho",
        "group": "Cory Private Accounts",
        "sortOrder": 60,
        "coryOnly": True,
    },
    "EQ_ACCOUNT": {
        "icon": "🔒",
        "displayName": "EQ Account",
        "shortName": "EQ Account",
        "group": "Cory Private Accounts",
        "sortOrder": 61,
        "coryOnly": True,
        "isBank": True,
    },
    "EQ_CARD": {
        "icon": "🔒",
        "displayName": "EQ Card",
        "shortName": "EQ Card",
        "group": "Cory Private Accounts",
        "sortOrder": 62,
        "coryOnly": True,
    },
    "WEALTHSIMPLE": {
        "icon": "📈",
        "displayName": "Wealthsimple",
        "shortName": "Wealthsimple",
        "group": "Cory Private Accounts",
        "sortOrder": 63,
        "coryOnly": True,
    },
    "CIBC_LOC": {
        "icon": "🏦",
        "displayName": "CIBC Line of Credit (LOC)",
        "shortName": "CIBC LOC",
        "group": "Cory Private Accounts",
        "sortOrder": 64,
        "coryOnly": True,
        "isDebt": True,
    },
    "CORY_PERSONAL": {
        "icon": "💳",
        "displayName": "Cory Personal Card / Account",
        "shortName": "Cory Personal",
        "group": "Cory Private Accounts",
        "sortOrder": 65,
        "coryOnly": True,
        "isCreditCard": True,
    },
    "SHAREHOLDER_LOAN": {
        "icon": "📒",
        "displayName": "Due to Shareholder (GIFI 2781)",
        "shortName": "Shareholder Loan",
        "group": "Cory Private Accounts",
        "sortOrder": 66,
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
    (Chromebook PWA + Windows/Fedora/macOS Native Desktop Dialog).
    Enforces:
      1. User Login (`deborah` vs. `cory`)
      2. Hard Server-Side Account & Transaction Firewall for Deborah
         (NEVER exposes Koho, Wealthsimple, EQ, or CIBC LOC)
      3. Strict CIBC PC Trust Account Guardrail
         (Visible to Deborah, but blocked for Expenses/Card Payments; only
          allowed for Money In from Clients or Transfer Out to CIBC PC General)
      4. Separate CIBC Mortgage & Home Trust Mortgage categories
      5. Next / Previous Card-Deck navigation and 1-Click Period Review Reports
    """

    def __init__(self, paths: Optional[AppPaths] = None, repo: Optional[ExcelRepo] = None):
        self.paths = paths or AppPaths()
        self.repo = repo or ExcelRepo(self.paths)
        self.finance_repo = FinanceRepo(self.repo)

    # ------------------------------------------------------------------
    # 1. Authentication & User Profiles
    # ------------------------------------------------------------------
    def authenticate(self, username: str, pin: str = "") -> Dict[str, Any]:
        user_key = str(username or "").strip().lower()
        entered_pin = str(pin or "").strip()

        if user_key in ("deborah", "deb"):
            expected_deb_pin = os.environ.get("CSPM_DEBORAH_PIN", "").strip()
            if expected_deb_pin and entered_pin != expected_deb_pin:
                return {"ok": False, "message": "Incorrect PIN for Deborah."}
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
            # Internal AP / legacy alias replaced by CIBC_PC_GENERAL in quick UI
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

        # Also check text fields so no mention of Koho, Wealthsimple, EQ, or CIBC LOC leaks
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
        uid = "cory" if self._is_cory(user_id) else "deborah"

        # 1. Filtered Accounts
        raw_accounts = self.finance_repo.list_transaction_accounts(include_inactive=False)
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
        accounts.sort(key=lambda a: (a["sortOrder"], a["accountName"]))

        # 2. Enriched Categories
        raw_categories = self.finance_repo.list_transaction_categories(include_inactive=False)
        categories: List[Dict[str, Any]] = []
        for cat in raw_categories:
            code = str(cat.get("categoryCode") or "").strip().upper()
            if not uid == "cory" and code in {"DEBT_LOC_PRINCIPAL_CIBC"}:
                # Hide CIBC LOC principal category from Deborah
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
    # 5. Save / Update Entry (with CIBC PC Trust & Privacy Guardrails)
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
                # Money In from Clients -> Deposit into CIBC_PC_TRUST
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

        # Tag who entered it inside Notes if not already tagged, while keeping Notes clean
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

            # Determine TaxFlag from category metadata
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

        repo_payload = {
            "transactionId": str(data.get("transactionId") or "").strip(),
            "txnDate": txn_date,
            "class": txn_class,
            "businessUnit": business_unit,
            "type": txn_type,
            "fromAccount": from_account,
            "toAccount": to_account,
            "payee": payee,
            "categoryCode": category_code,
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
        }

        try:
            result = self.finance_repo.save_transaction(repo_payload)
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

        if not result.get("ok"):
            return {"ok": False, "message": result.get("message") or "Could not save entry."}

        saved_id = str(result.get("transactionId") or "")
        enriched = self.get_entry(user_id=uid, transaction_id=saved_id)
        return {
            "ok": True,
            "transactionId": saved_id,
            "entry": enriched,
            "message": "Saved to CSPM!",
        }

    # ------------------------------------------------------------------
    # 6. Delete Entry
    # ------------------------------------------------------------------
    def delete_entry(self, user_id: str, transaction_id: str) -> Dict[str, Any]:
        uid = "cory" if self._is_cory(user_id) else "deborah"
        existing = self.get_entry(user_id=uid, transaction_id=transaction_id)
        if not existing:
            return {"ok": False, "message": "Entry not found or not accessible."}
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
        all_rows = self.finance_repo.list_transactions({})
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

        raw_rows = self.finance_repo.list_transactions(filters)
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
