from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from repositories.excel_repo import ExcelRepo
from services.paths import AppPaths

logger = logging.getLogger("cspm.leap_intake")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Extracted from OffexExpress.Client.Common.Utils.TotpGenerator..ctor
LEAP_TOTP_BASE32_SECRET = "LZ5HOLRRFBREIQBPF5ETK33WNRCCUNBXKZXXEMSSGJJC6Q3DHISA"
LEAP_APP_ID = "34PUII2XII3HFVY8"
LEAP_APP_VERSION = "2.5.548.0"
LEAP_USER_AGENT = "ClientComponent/7.6.9.500 (7.6.9 S)"
LEAP_QUERY_URL = "https://offexserver.leapaws.ca/QueryService.svc/query"
LEAP_COMMAND_URL = "https://offexserver.leapaws.ca/CommandService.svc/command"
LEAP_DEFAULT_FIRM_ID = "dc2857d8-e04c-4a73-9964-6ad7a17e677d"
LEAP_DEFAULT_TRUST_ACCOUNT_GUID = "6ee4f87a-3722-443a-9c32-c5b9fdefbc80"
LEAP_HASH_SALT = "4B8E3632-64E0-460B-AF3F-A00C821AA5D0"

# Canonical LPN Staff Directory (from Data\Staff\*.xml)
LPN_STAFF: List[Dict[str, str]] = [
    {
        "initials": "CS",
        "name": "Cory Schneider",
        "role": "Partner / Lawyer",
        "staffId": "c41cb3ae-503c-4015-8588-967c633d4327",
        "userId": "e1e7f03d-0561-4ffa-a0b8-c4d02635298a",
    },
    {
        "initials": "AT",
        "name": "Alejandra Talbot",
        "role": "Law Clerk / Assistant",
        "staffId": "2d74fefc-3232-45db-b916-5024550dd55e",
        "userId": "1a24568f-9448-4e46-af53-6f4c28b64f24",
    },
    {
        "initials": "JH",
        "name": "James Hutchinson",
        "role": "Partner / Lawyer",
        "staffId": "87f1c87b-e2e2-4294-ac55-e5ee0775ea89",
        "userId": "45dd7068-f560-4c3a-8fc2-cbd38b4ed649",
    },
    {
        "initials": "KT",
        "name": "Karen Tuschak",
        "role": "Staff",
        "staffId": "b0e6e4b9-2b40-45cf-875a-54b26efd684d",
        "userId": "1fdd9dc8-b5d0-4e2b-9833-9f247db5abb2",
    },
]

PINNED_FAVORITE_MATTER_TYPE_IDS: Tuple[str, ...] = (
    "d621425a-5945-4950-a051-ac74ad2dc74f",  # General Advice - Business
    "cdcc586e-4828-42a8-920e-7f263e77b890",  # Tax
    "f0dfa3f6-15fb-4fbe-b580-8c0bce5a949b",  # Trust
    "b8ca867a-b735-44cf-96d3-6e9ac3a2d95a",  # Will & Power of Attorney
)

BUILTIN_ONTARIO_MATTER_TYPES_FALLBACK: List[Dict[str, Any]] = [
    {
        "matterTypeId": "d621425a-5945-4950-a051-ac74ad2dc74f",
        "name": "General Advice - Business",
        "category": "Commercial / Corporate",
        "state": "ON",
        "isFavorite": True,
        "isTimeRecorded": True,
        "description": "For legal advice related to business law",
        "substitution": {"Client": "3", "OtherSide": "7", "OtherSideSolicitor": "4", "OtherSideInsurer": "0"},
        "title": {
            "Client": "Business Consultation",
            "ClientPrefix": "false",
            "ClientSuffix": "false",
            "Other": "- Business",
            "OtherPrefix": "true",
            "OtherSuffix": "false",
        },
        "defaultCards": ["3", "7", "4", "733"],
        "definableTables": [],
        "relations": [],
    },
    {
        "matterTypeId": "cdcc586e-4828-42a8-920e-7f263e77b890",
        "name": "Tax",
        "category": "Tax",
        "state": "ON",
        "isFavorite": True,
        "isTimeRecorded": True,
        "description": "For matters related to general tax advice or tax disputes in Ontario",
        "substitution": {
            "Client": "e247361c-c91b-4b42-a2d2-f7850f05bd4a",
            "OtherSide": "2b9fbf54-b7a3-4212-866d-322cc32429a0",
            "OtherSideSolicitor": "032bda4b-86c6-45d5-85f5-0de564fd485b",
            "OtherSideInsurer": "0",
        },
        "title": {
            "Client": "Tax",
            "ClientPrefix": "false",
            "ClientSuffix": "false",
            "Other": "- Tax",
            "OtherPrefix": "true",
            "OtherSuffix": "false",
        },
        "defaultCards": ["3", "7", "4", "733"],
        "definableTables": [],
        "relations": [],
    },
    {
        "matterTypeId": "f0dfa3f6-15fb-4fbe-b580-8c0bce5a949b",
        "name": "Trust",
        "category": "Estates & Trusts",
        "state": "ON",
        "isFavorite": True,
        "isTimeRecorded": True,
        "description": "For trust creation, administration, and variation matters in Ontario",
        "substitution": {"Client": "3", "OtherSide": "0", "OtherSideSolicitor": "0", "OtherSideInsurer": "0"},
        "title": {
            "Client": "Trust",
            "ClientPrefix": "false",
            "ClientSuffix": "false",
            "Other": "- Trust",
            "OtherPrefix": "true",
            "OtherSuffix": "false",
        },
        "defaultCards": ["3", "733"],
        "definableTables": [],
        "relations": [],
    },
    {
        "matterTypeId": "b8ca867a-b735-44cf-96d3-6e9ac3a2d95a",
        "name": "Will & Power of Attorney",
        "category": "Wills & Estates",
        "state": "ON",
        "isFavorite": True,
        "isTimeRecorded": True,
        "description": "For Wills and Powers of Attorney in Ontario",
        "substitution": {"Client": "3", "OtherSide": "0", "OtherSideSolicitor": "0", "OtherSideInsurer": "0"},
        "title": {
            "Client": "Will & Power of Attorney",
            "ClientPrefix": "false",
            "ClientSuffix": "false",
            "Other": "- Will & Power of Attorney",
            "OtherPrefix": "true",
            "OtherSuffix": "false",
        },
        "defaultCards": ["3", "733"],
        "definableTables": [],
        "relations": [],
    },
]


def generate_leap_totp(timestamp: Optional[float] = None) -> str:
    """Pure-Python HMAC-SHA256 6-digit TOTP matching OffexExpress.Client.Common.Utils.TotpGenerator."""
    ts = time.time() if timestamp is None else float(timestamp)
    padded = LEAP_TOTP_BASE32_SECRET + "=" * ((8 - len(LEAP_TOTP_BASE32_SECRET) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = int(ts // 30)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def _now_leap_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _norm_name(value: str) -> str:
    txt = str(value or "").strip().lower()
    txt = re.sub(r"\b(inc|incorporated|corp|corporation|ltd|limited|lp|llp|ulc)\b\.?", lambda m: m.group(1), txt)
    txt = re.sub(r"[^a-z0-9]+", " ", txt).strip()
    return txt


def _clean_folder_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "New Client"


def _xml_esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _split_street_address(line1: str) -> Tuple[str, str]:
    s = str(line1 or "").strip()
    if not s:
        return "", ""
    m = re.match(r"^(\d+[A-Za-z0-9\-/]*)\s+(.+)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", s


def _parse_person_name(raw_name: str, first_hint: str = "", last_hint: str = "") -> Tuple[str, str]:
    f = str(first_hint or "").strip()
    l = str(last_hint or "").strip()
    if f and l:
        return f, l
    raw = str(raw_name or "").strip()
    if not raw:
        return f or "Client", l or ""
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        return (parts[1] or f), (parts[0] or l)
    tokens = raw.split()
    if len(tokens) == 1:
        return tokens[0], ""
    return " ".join(tokens[:-1]), tokens[-1]


def _jwt_exp_epoch(jwt_token: str) -> int:
    try:
        parts = str(jwt_token or "").split(".")
        if len(parts) < 2:
            return 0
        b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")).decode("utf-8"))
        return int(payload.get("exp") or 0)
    except Exception:
        return 0


def _resolve_onedrive_lpn_root() -> Optional[Path]:
    home = Path.home()
    candidates = [
        home / "OneDrive - LPN",
        Path(os.environ.get("OneDriveCommercial", "")) if os.environ.get("OneDriveCommercial") else None,
        Path(os.environ.get("OneDrive", "")) if os.environ.get("OneDrive") else None,
    ]
    for c in candidates:
        if c and c.is_dir() and (c / "__Admin").is_dir():
            return c
    for c in sorted(home.glob("OneDrive*")):
        if c.is_dir() and ((c / "__Admin").is_dir() or (c / "LPN").is_dir()):
            return c
    return None


def _resolve_default_cspm_paths() -> AppPaths:
    default_paths = AppPaths(root=AppPaths.project_root())
    if not os.environ.get("PYTEST_CURRENT_TEST", "").strip():
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
    return default_paths


class LeapIntakeService:
    """Unified Client ('Card' + 'Person') & Matter intake engine bridging CSPM, LEAP Cloud/Desktop,
    Quick Expense PWA (:24820), OneDrive - LPN, and LeapSync."""

    def __init__(self, paths: Optional[AppPaths] = None, repo: Optional[ExcelRepo] = None):
        self.paths = paths or _resolve_default_cspm_paths()
        self.repo = repo or ExcelRepo(self.paths)
        self.onedrive_root = _resolve_onedrive_lpn_root()
        self.shared_state_dir = (
            (self.onedrive_root / "__Admin" / "Antigravity_Customizations" / "shared_state")
            if self.onedrive_root
            else (self.paths.data_dir() / "shared_state")
        )
        self.clients_lpn_root = (
            (self.onedrive_root / "LPN" / "Clients (LPN)")
            if self.onedrive_root and (self.onedrive_root / "LPN" / "Clients (LPN)").is_dir()
            else ((self.onedrive_root / "Clients (LPN)") if self.onedrive_root else (Path.home() / "Clients (LPN)"))
        )

    # ------------------------------------------------------------------
    # Paths, Auth & Shared-State Mirroring
    # ------------------------------------------------------------------
    def _matter_map_path(self) -> Path:
        self.shared_state_dir.mkdir(parents=True, exist_ok=True)
        return self.shared_state_dir / "cspm_leap_matter_map.json"

    def _matter_types_cache_path(self) -> Path:
        self.shared_state_dir.mkdir(parents=True, exist_ok=True)
        return self.shared_state_dir / "leap_ontario_matter_types.json"

    def _leap_cards_cache_path(self) -> Path:
        self.shared_state_dir.mkdir(parents=True, exist_ok=True)
        return self.shared_state_dir / "leap_cards_matters_cache.json"

    def _leap_auth_shared_path(self) -> Path:
        self.shared_state_dir.mkdir(parents=True, exist_ok=True)
        return self.shared_state_dir / "leap_auth_shared.json"

    def _find_leap_auth_helper(self) -> Optional[Path]:
        if os.name != "nt":
            return None
        candidates = [
            Path(os.path.expandvars(r"%LOCALAPPDATA%\LPN\LeapSync\LeapAuthHelper.exe")),
            (self.onedrive_root / "__Admin" / "LeapSync" / "LeapAuthHelper.exe") if self.onedrive_root else None,
        ]
        for c in candidates:
            if c and c.is_file():
                return c
        return None

    def _resolve_leap_user_data_dir(self) -> Optional[Path]:
        if os.name != "nt":
            return None
        dat_path = Path(r"C:\ProgramData\LEAP Office\Cloud\Net Client\last.dat")
        if dat_path.is_file():
            try:
                root = ET.parse(dat_path).getroot()
                dp = (root.findtext("DataPath") or "").strip()
                if dp and Path(dp).is_dir():
                    data_sub = Path(dp) / "Data"
                    return data_sub if data_sub.is_dir() else Path(dp)
                ig = (root.findtext("InstanceGuid") or "").strip()
                if ig:
                    cand = Path(os.path.expandvars(r"%LOCALAPPDATA%\LEAP Desktop\User")) / ig / "Data"
                    if cand.is_dir():
                        return cand
            except Exception:
                pass
        base = Path(os.path.expandvars(r"%LOCALAPPDATA%\LEAP Desktop\User"))
        if base.is_dir():
            dirs = sorted(
                (d / "Data" for d in base.iterdir() if d.is_dir() and (d / "Data" / "Matters").is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if dirs:
                return dirs[0]
        return None

    def _ensure_leap_sync_importable(self) -> bool:
        candidates = [
            Path(r"Y:\Projects\LeapSync\src"),
            Path(r"C:\Projects\LeapSync\src"),
            Path.home() / "Projects" / "LeapSync" / "src",
            Path.home() / "LeapSync" / "src",
        ]
        for c in candidates:
            if (c / "leap_sync" / "core.py").is_file():
                if str(c) not in sys.path:
                    sys.path.insert(0, str(c))
                return True
        return False

    def get_leap_auth_context(self, refresh_if_needed: bool = True) -> Dict[str, str]:
        """Resolve FirmId, InstanceGuid, UserId, and valid JWT across Windows and Linux."""
        ctx: Dict[str, str] = {
            "firmId": LEAP_DEFAULT_FIRM_ID,
            "instanceGuid": "f8e8815f-72f3-4e5f-8f81-38d960dbe379",
            "userId": "e1e7f03d-0561-4ffa-a0b8-c4d02635298a",
            "staffId": "c41cb3ae-503c-4015-8588-967c633d4327",
            "jwt": "",
        }
        if os.name == "nt":
            dat_path = Path(r"C:\ProgramData\LEAP Office\Cloud\Net Client\last.dat")
            if dat_path.is_file():
                try:
                    dat_el = ET.parse(dat_path).getroot()
                    ctx["firmId"] = (dat_el.findtext("FirmId") or ctx["firmId"]).strip()
                    ctx["instanceGuid"] = (dat_el.findtext("InstanceGuid") or ctx["instanceGuid"]).strip()
                    ctx["userId"] = (dat_el.findtext("UserId") or ctx["userId"]).strip()
                    for st in LPN_STAFF:
                        if st["userId"].lower() == ctx["userId"].lower():
                            ctx["staffId"] = st["staffId"]
                            break
                except Exception:
                    pass

            helper = self._find_leap_auth_helper()
            if helper:
                for attempt in range(2):
                    try:
                        r = subprocess.run(
                            [str(helper), "read"],
                            capture_output=True,
                            text=True,
                            timeout=12,
                            creationflags=CREATE_NO_WINDOW,
                        )
                        if r.returncode == 0 and "<Token>" in r.stdout:
                            auth_el = ET.fromstring(r.stdout.strip())
                            tok = (auth_el.findtext("Token") or "").strip()
                            exp = _jwt_exp_epoch(tok)
                            if tok and (not refresh_if_needed or exp == 0 or exp - time.time() > 300 or attempt == 1):
                                ctx["jwt"] = tok
                                break
                    except Exception:
                        pass
                    if refresh_if_needed and attempt == 0 and self._ensure_leap_sync_importable():
                        try:
                            from leap_sync.core import ensure_leap_authenticated

                            ensure_leap_authenticated(force_refresh=True)
                            time.sleep(0.8)
                        except Exception:
                            break

            if ctx["jwt"]:
                try:
                    self._leap_auth_shared_path().write_text(
                        json.dumps(
                            {
                                "firmId": ctx["firmId"],
                                "instanceGuid": ctx["instanceGuid"],
                                "userId": ctx["userId"],
                                "staffId": ctx["staffId"],
                                "jwt": ctx["jwt"],
                                "exp": _jwt_exp_epoch(ctx["jwt"]),
                                "updatedAt": _now_leap_iso(),
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

        if not ctx["jwt"]:
            shared_p = self._leap_auth_shared_path()
            if shared_p.is_file():
                try:
                    cached = json.loads(shared_p.read_text(encoding="utf-8"))
                    ctx["firmId"] = str(cached.get("firmId") or ctx["firmId"])
                    ctx["instanceGuid"] = str(cached.get("instanceGuid") or ctx["instanceGuid"])
                    ctx["userId"] = str(cached.get("userId") or ctx["userId"])
                    ctx["staffId"] = str(cached.get("staffId") or ctx["staffId"])
                    ctx["jwt"] = str(cached.get("jwt") or "")
                except Exception:
                    pass
        return ctx

    # ------------------------------------------------------------------
    # WCF SOAP 1.1 Pure-Python Client + LeapAuthHelper.exe Dual Transport
    # ------------------------------------------------------------------
    def query_data_soap(self, sync_type: str, record_guid: str, auth_ctx: Optional[Dict[str, str]] = None) -> str:
        """Pure-Python HTTPS WCF SOAP 1.1 QueryData call (works on Windows & Linux)."""
        ctx = auth_ctx or self.get_leap_auth_context()
        jwt = ctx.get("jwt") or ""
        if not jwt:
            raise RuntimeError("LEAP OAuth JWT is unavailable. Open LEAP Desktop or sync shared_state/leap_auth_shared.json.")
        totp = generate_leap_totp()
        envelope = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body>"
            '<QueryData xmlns="http://officeexpress.leap.com.au/svc" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
            '<token xmlns:a="http://schemas.datacontract.org/2004/07/OfficeExpress.Contracts.DataContracts">'
            f"<a:AppVersion>{_xml_esc(LEAP_APP_VERSION)}</a:AppVersion>"
            f"<a:FirmId>{_xml_esc(ctx['firmId'])}</a:FirmId>"
            f"<a:InstanceId>{_xml_esc(ctx['instanceGuid'])}</a:InstanceId>"
            '<a:MetaInfoXml i:nil="true"/>'
            f"<a:Token>{_xml_esc(jwt)}</a:Token>"
            f"<a:UserId>{_xml_esc(ctx['userId'])}</a:UserId>"
            "</token>"
            f"<dataType>{_xml_esc(sync_type)}</dataType>"
            f'<key xmlns:ser="http://schemas.microsoft.com/2003/10/Serialization/" i:type="ser:guid">{_xml_esc(record_guid)}</key>'
            "</QueryData>"
            "</s:Body>"
            "</s:Envelope>"
        ).encode("utf-8")
        req = urllib.request.Request(
            LEAP_QUERY_URL,
            data=envelope,
            method="POST",
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": '"http://officeexpress.leap.com.au/svc/IQueryService/QueryData"',
                "User-Agent": LEAP_USER_AGENT,
                "Authorization": f"Bearer {jwt}",
                "x-LEAPData-Version": "1",
                "x-LEAPData-Type": totp,
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_xml = resp.read().decode("utf-8", errors="replace")
        root = ET.fromstring(raw_xml)
        for el in root.iter():
            if el.tag.endswith("SyncXml"):
                return el.text or ""
        return ""

    def save_user_data_soap(self, sync_type: str, record_guid: str, sync_xml: str, auth_ctx: Optional[Dict[str, str]] = None) -> str:
        """Pure-Python HTTPS WCF SOAP 1.1 SaveUserData call (works on Windows & Linux)."""
        ctx = auth_ctx or self.get_leap_auth_context()
        jwt = ctx.get("jwt") or ""
        if not jwt:
            raise RuntimeError("LEAP OAuth JWT is unavailable.")
        totp = generate_leap_totp()
        req_id = str(uuid4())
        envelope = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body>"
            '<SaveUserData xmlns="http://officeexpress.leap.com.au/svc" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
            '<token xmlns:a="http://schemas.datacontract.org/2004/07/OfficeExpress.Contracts.DataContracts">'
            f"<a:AppVersion>{_xml_esc(LEAP_APP_VERSION)}</a:AppVersion>"
            f"<a:FirmId>{_xml_esc(ctx['firmId'])}</a:FirmId>"
            f"<a:InstanceId>{_xml_esc(ctx['instanceGuid'])}</a:InstanceId>"
            '<a:MetaInfoXml i:nil="true"/>'
            f"<a:Token>{_xml_esc(jwt)}</a:Token>"
            f"<a:UserId>{_xml_esc(ctx['userId'])}</a:UserId>"
            "</token>"
            f"<requestId>{req_id}</requestId>"
            '<data xmlns:d="http://officeexpress.leap.com.au/data">'
            f"<d:Id>{_xml_esc(record_guid)}</d:Id>"
            f"<d:Type>{_xml_esc(sync_type)}</d:Type>"
            f"<d:SyncXml>{_xml_esc(sync_xml)}</d:SyncXml>"
            "</data>"
            "</SaveUserData>"
            "</s:Body>"
            "</s:Envelope>"
        ).encode("utf-8")
        req = urllib.request.Request(
            LEAP_COMMAND_URL,
            data=envelope,
            method="POST",
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": '"http://officeexpress.leap.com.au/svc/ICommandService/SaveUserData"',
                "User-Agent": LEAP_USER_AGENT,
                "Authorization": f"Bearer {jwt}",
                "x-LEAPData-Version": "1",
                "x-LEAPData-Type": totp,
            },
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            _ = resp.read()
        return req_id

    def query_leap_record(self, sync_type: str, record_guid: str) -> str:
        helper = self._find_leap_auth_helper()
        if helper:
            r = subprocess.run(
                [str(helper), "query-record", sync_type, record_guid],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
                creationflags=CREATE_NO_WINDOW,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        return self.query_data_soap(sync_type, record_guid)

    def save_leap_record(self, sync_type: str, record_guid: str, xml_content: str) -> Tuple[bool, str, str]:
        """Push record to LEAP Cloud and verify persistence via QueryData.
        Returns (ok, status_msg, verified_server_xml)."""
        ET.fromstring(xml_content)  # Strict pre-flight XML syntax check
        helper = self._find_leap_auth_helper()
        if helper:
            with tempfile.TemporaryDirectory(prefix="leap_intake_") as tmpd:
                in_p = Path(tmpd) / f"{record_guid}_in.xml"
                out_p = Path(tmpd) / f"{record_guid}_srv.xml"
                in_p.write_text(xml_content, encoding="utf-8")
                r = subprocess.run(
                    [str(helper), "save-record", sync_type, record_guid, str(in_p), str(out_p)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=35,
                    creationflags=CREATE_NO_WINDOW,
                )
                if r.returncode == 0:
                    srv_xml = out_p.read_text(encoding="utf-8") if out_p.is_file() else ""
                    return True, r.stdout.strip(), srv_xml or xml_content
                logger.warning("LeapAuthHelper save-record fallback to SOAP (%s): %s", r.returncode, r.stderr)

        ctx = self.get_leap_auth_context(refresh_if_needed=True)
        req_id = self.save_user_data_soap(sync_type, record_guid, xml_content, auth_ctx=ctx)
        srv_xml = ""
        for attempt in range(5):
            time.sleep(0.4 if attempt == 0 else 0.65)
            try:
                srv_xml = self.query_data_soap(sync_type, record_guid, auth_ctx=ctx)
                if srv_xml:
                    break
            except Exception:
                pass
        return True, f"OK Saved={record_guid} RequestId={req_id} Verified={bool(srv_xml)}", srv_xml or xml_content

    # ------------------------------------------------------------------
    # Ontario MatterTypes, Existing LEAP Cards & Matters Discovery
    # ------------------------------------------------------------------
    def list_ontario_matter_types(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        cache_p = self._matter_types_cache_path()
        data_dir = self._resolve_leap_user_data_dir()
        if not force_refresh and cache_p.is_file():
            try:
                cached = json.loads(cache_p.read_text(encoding="utf-8"))
                items = cached.get("matterTypes") or []
                if items and (data_dir is None or len(items) >= 10):
                    return items
            except Exception:
                pass

        if data_dir and (data_dir / "MatterTypes").is_dir():
            mt_dir = data_dir / "MatterTypes"
            parsed_items: List[Dict[str, Any]] = []
            fav_rank = {gid: idx for idx, gid in enumerate(PINNED_FAVORITE_MATTER_TYPE_IDS)}
            for entry in os.scandir(mt_dir):
                if not entry.is_file() or not entry.name.endswith(".xml") or entry.name.lower() == "mattertypelist.xml":
                    continue
                try:
                    root = ET.parse(entry.path).getroot()
                    if (root.findtext("DeleteCode") or "0").strip() != "0":
                        continue
                    if (root.findtext("Type") or "").strip() != "MatterType":
                        continue
                    states_el = root.find("States")
                    states = [s.text.strip().upper() for s in (states_el.findall("State") if states_el is not None else []) if s.text]
                    if states and "ON" not in states:
                        continue
                    mt_id = (root.findtext("MatterTypeId") or Path(entry.name).stem).strip().lower()
                    name = (root.findtext("Name") or "").strip()
                    if not name:
                        continue

                    sub_map = {"Client": "3", "OtherSide": "7", "OtherSideSolicitor": "4", "OtherSideInsurer": "0"}
                    st_el = root.find("SubstitutionTables")
                    if st_el is not None:
                        for role_tag in ("Client", "OtherSide", "OtherSideSolicitor", "OtherSideInsurer"):
                            role_el = st_el.find(role_tag)
                            if role_el is not None:
                                chosen = None
                                for tid_el in role_el.findall("TableId"):
                                    if (tid_el.attrib.get("Default") or "").lower() == "true" and (tid_el.text or "").strip():
                                        chosen = tid_el.text.strip()
                                        break
                                if chosen is not None:
                                    sub_map[role_tag] = chosen
                                elif not role_el.findall("TableId"):
                                    sub_map[role_tag] = "0"

                    title_map = {
                        "Client": name,
                        "ClientPrefix": "false",
                        "ClientSuffix": "false",
                        "Other": f"- {name}",
                        "OtherPrefix": "true",
                        "OtherSuffix": "false",
                    }
                    t_el = root.find("Title")
                    if t_el is not None:
                        for k in list(title_map.keys()):
                            v = t_el.findtext(k)
                            if v is not None:
                                title_map[k] = v.strip()

                    default_cards: List[Dict[str, str]] = []
                    cards_el = root.find("Cards")
                    if cards_el is not None:
                        for idx_c, c_el in enumerate(cards_el.findall("Card"), start=1):
                            if (c_el.findtext("Default") or "").strip().lower() == "true":
                                tid = (c_el.findtext("Table_TableId") or "").strip()
                                ord_raw = (c_el.findtext("Order") or str(idx_c)).strip()
                                try:
                                    ord_num = int(ord_raw) * 1000000 if int(ord_raw) < 1000 else int(ord_raw)
                                except Exception:
                                    ord_num = idx_c * 1000000
                                if tid:
                                    default_cards.append({"tableId": tid, "order": str(ord_num)})

                    definable_tables: List[Dict[str, str]] = []
                    dt_el = root.find("DefinableTables")
                    if dt_el is not None:
                        for idx_d, d_el in enumerate(dt_el.findall("DefinableTable"), start=1):
                            if (d_el.findtext("Default") or "").strip().lower() == "true":
                                dt_id = (d_el.findtext("DefinableTableId") or d_el.findtext("Table_TableId") or "").strip()
                                ord_raw = (d_el.findtext("Order") or str(idx_d)).strip()
                                try:
                                    ord_num = int(ord_raw) * 1000000 if int(ord_raw) < 1000 else int(ord_raw)
                                except Exception:
                                    ord_num = idx_d * 1000000
                                if dt_id:
                                    definable_tables.append({"definableTableId": dt_id, "order": str(ord_num)})

                    relations: List[Dict[str, str]] = []
                    rel_el = root.find("Relations")
                    if rel_el is not None:
                        for r_el in rel_el.findall("Relation"):
                            relations.append(
                                {
                                    "parentTableId": (r_el.findtext("ParentTableId") or "").strip(),
                                    "childTableId": (r_el.findtext("ChildTableId") or "").strip(),
                                    "order": (r_el.findtext("Order") or "1").strip(),
                                    "singleton": (r_el.findtext("Singleton") or "false").strip(),
                                    "active": (r_el.findtext("Active") or "false").strip(),
                                }
                            )

                    parsed_items.append(
                        {
                            "matterTypeId": mt_id,
                            "name": name,
                            "state": "ON",
                            "isFavorite": mt_id in fav_rank,
                            "favoriteRank": fav_rank.get(mt_id, 999),
                            "isTimeRecorded": (root.findtext("IsTimeRecorded") or "true").strip().lower() != "false",
                            "description": (root.findtext("Description") or "").strip(),
                            "substitution": sub_map,
                            "title": title_map,
                            "defaultCards": default_cards,
                            "definableTables": definable_tables,
                            "relations": relations,
                        }
                    )
                except Exception:
                    continue

            if parsed_items:
                parsed_items.sort(key=lambda x: (int(x.get("favoriteRank", 999)), x["name"].lower()))
                try:
                    cache_p.write_text(
                        json.dumps({"updatedAt": _now_leap_iso(), "count": len(parsed_items), "matterTypes": parsed_items}, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                return parsed_items

        return list(BUILTIN_ONTARIO_MATTER_TYPES_FALLBACK)

    def resolve_matter_type(self, matter_type_ref: str) -> Dict[str, Any]:
        all_types = self.list_ontario_matter_types()
        ref = str(matter_type_ref or "").strip()
        ref_low = ref.lower()
        for mt in all_types:
            if mt["matterTypeId"].lower() == ref_low or mt["name"].lower() == ref_low:
                return mt
        # Heuristic mapping from CSPM practice areas / tokens
        if any(k in ref_low for k in ("tax", "-tax-", "cra", "hst", "gst")):
            target_id = "cdcc586e-4828-42a8-920e-7f263e77b890"
        elif any(k in ref_low for k in ("trust", "-trt-")):
            target_id = "f0dfa3f6-15fb-4fbe-b580-8c0bce5a949b"
        elif any(k in ref_low for k in ("will", "estate", "poa", "probate", "-est-")):
            target_id = "b8ca867a-b735-44cf-96d3-6e9ac3a2d95a"
        else:
            target_id = "d621425a-5945-4950-a051-ac74ad2dc74f"
        for mt in all_types:
            if mt["matterTypeId"].lower() == target_id:
                return mt
        for mt in all_types:
            if ref_low and ref_low in mt["name"].lower():
                return mt
        return all_types[0]

    def resolve_staff(self, ref: str, fallback_initials: str = "CS") -> Dict[str, str]:
        q = str(ref or "").strip().lower()
        for s in LPN_STAFF:
            if q in (s["initials"].lower(), s["staffId"].lower(), s["userId"].lower(), s["name"].lower()):
                return s
        for s in LPN_STAFF:
            if q and q in s["name"].lower():
                return s
        for s in LPN_STAFF:
            if s["initials"].upper() == fallback_initials.upper():
                return s
        return LPN_STAFF[0]

    def load_cspm_leap_map(self) -> Dict[str, Any]:
        p = self._matter_map_path()
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("matters", {})
                    data.setdefault("clients", {})
                    return data
            except Exception:
                pass
        return {"version": 1, "updatedAt": _now_leap_iso(), "matters": {}, "clients": {}}

    def save_cspm_leap_map(self, data: Dict[str, Any]) -> None:
        data["updatedAt"] = _now_leap_iso()
        self._matter_map_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list_existing_leap_cards_and_matters(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        data_dir = self._resolve_leap_user_data_dir()
        cards: List[Dict[str, Any]] = []
        matters: List[Dict[str, Any]] = []

        if data_dir:
            cl_path = data_dir / "Cards" / "CardList.xml"
            if cl_path.is_file():
                try:
                    root = ET.parse(cl_path).getroot()
                    for c_el in root.findall("Card"):
                        if (c_el.findtext("DeleteCode") or "0").strip() != "0":
                            continue
                        guid = (c_el.attrib.get("guid") or c_el.findtext("InstanceGuid") or "").strip().lower()
                        full_name = (c_el.findtext("FullName") or c_el.findtext("CompanyName") or c_el.findtext("ShortName") or "").strip()
                        short_name = (c_el.findtext("ShortName") or full_name).strip()
                        ctype = (c_el.findtext("Type") or "Company").strip()
                        if guid and full_name:
                            cards.append(
                                {
                                    "cardGuid": guid,
                                    "fullName": full_name,
                                    "shortName": short_name,
                                    "type": ctype,
                                    "normName": _norm_name(full_name),
                                }
                            )
                except Exception as exc:
                    logger.warning("CardList.xml parse warning: %s", exc)

            ml_path = data_dir / "Matters" / "MatterList.xml"
            if ml_path.is_file():
                try:
                    root = ET.parse(ml_path).getroot()
                    for m_el in root.findall("Matter"):
                        if (m_el.findtext("DeleteCode") or "0").strip() != "0":
                            continue
                        guid = (m_el.attrib.get("guid") or "").strip().lower()
                        fno = (m_el.findtext("FileNumber") or "").strip()
                        mtype = (m_el.findtext("Type") or "").strip()
                        desc_el = m_el.find("Description")
                        client_first = (desc_el.findtext("FirstLong") or desc_el.findtext("First") or "").strip() if desc_el is not None else ""
                        custom_desc = (m_el.findtext("CustomDescription") or mtype).strip()
                        card_ids = [
                            (ce.findtext("RecordId") or "").strip().lower()
                            for ce in m_el.findall("./Cards/Card")
                            if (ce.findtext("RecordId") or "").strip()
                        ]
                        matters.append(
                            {
                                "matterGuid": guid,
                                "fileNumber": fno,
                                "type": mtype,
                                "clientName": client_first,
                                "description": custom_desc,
                                "status": (m_el.findtext("Status") or "In progress").strip(),
                                "staff": (m_el.findtext("Staff") or "").strip(),
                                "cardGuids": card_ids,
                                "normClient": _norm_name(client_first),
                            }
                        )
                except Exception as exc:
                    logger.warning("MatterList.xml parse warning: %s", exc)

            if cards or matters:
                try:
                    self._leap_cards_cache_path().write_text(
                        json.dumps({"updatedAt": _now_leap_iso(), "cards": cards, "matters": matters}, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                return cards, matters

        cache_p = self._leap_cards_cache_path()
        if cache_p.is_file():
            try:
                cached = json.loads(cache_p.read_text(encoding="utf-8"))
                return cached.get("cards") or [], cached.get("matters") or []
            except Exception:
                pass
        return cards, matters

    def compute_next_leap_file_number(self, existing_matters: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, int]:
        _, matters = (None, existing_matters) if existing_matters is not None else self.list_existing_leap_cards_and_matters()
        max_num = 100
        for m in matters or []:
            fno = str(m.get("fileNumber") or "").strip()
            if fno.isdigit():
                val = int(fno)
                if 100 <= val < 90000 and val > max_num:
                    max_num = val
        fmap = self.load_cspm_leap_map()
        for info in (fmap.get("matters") or {}).values():
            fno = str((info or {}).get("leapFileNumber") or "").strip()
            if fno.isdigit():
                val = int(fno)
                if 100 <= val < 90000 and val > max_num:
                    max_num = val
        next_seq = max_num + 1
        return f"{next_seq:04d}", next_seq

    def find_matching_leap_card(
        self,
        client_name: str,
        first_name: str = "",
        last_name: str = "",
        existing_cards: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        cards = existing_cards if existing_cards is not None else self.list_existing_leap_cards_and_matters()[0]
        candidates = set()
        if client_name:
            candidates.add(_norm_name(client_name))
            if "," in client_name:
                f, l = _parse_person_name(client_name)
                candidates.add(_norm_name(f"{f} {l}"))
        if first_name or last_name:
            candidates.add(_norm_name(f"{first_name} {last_name}"))
            candidates.add(_norm_name(f"{last_name} {first_name}"))
        candidates.discard("")
        for c in cards:
            if c.get("normName") in candidates:
                return c
        return None

    # ------------------------------------------------------------------
    # CSPM Client & Matter Inventory + "Not Yet in LEAP" Reconciliation
    # ------------------------------------------------------------------
    def _all_sqlite_db_paths(self) -> List[Path]:
        out: List[Path] = []
        seen: set[str] = set()
        for d in (self.paths.master_data_dir(), self.paths.data_dir()):
            if d and (d / "cspm.db").is_file():
                k = str((d / "cspm.db").resolve()).casefold()
                if k not in seen:
                    seen.add(k)
                    out.append(d / "cspm.db")
        for od in sorted(Path.home().glob("OneDrive*")):
            cand = od / "CSPM_Shared_Data" / "cspm.db"
            if cand.is_file():
                k = str(cand.resolve()).casefold()
                if k not in seen:
                    seen.add(k)
                    out.append(cand)
        return out

    def list_cspm_clients_and_matters_with_leap_status(self) -> Dict[str, Any]:
        leap_cards, leap_matters = self.list_existing_leap_cards_and_matters()
        fmap = self.load_cspm_leap_map()
        mapped_matters = fmap.get("matters") or {}
        mapped_clients = fmap.get("clients") or {}

        leap_by_fno = {str(m["fileNumber"]).strip(): m for m in leap_matters if m.get("fileNumber")}
        leap_matters_by_client: Dict[str, List[Dict[str, Any]]] = {}
        for m in leap_matters:
            nc = m.get("normClient") or ""
            if nc:
                leap_matters_by_client.setdefault(nc, []).append(m)

        cspm_clients: List[Dict[str, Any]] = []
        cspm_matters: List[Dict[str, Any]] = []
        seen_client_ids: set[str] = set()
        seen_matter_keys: set[str] = set()

        try:
            for c in self.repo.list_client_directory() or []:
                cid = str(c.get("clientId") or "").strip()
                cname = str(c.get("displayName") or c.get("clientName") or c.get("legalName") or "").strip()
                if not cname:
                    continue
                key = (cid or cname).upper()
                if key in seen_client_ids:
                    continue
                seen_client_ids.add(key)
                matched_card = None
                if cid in mapped_clients:
                    cg = mapped_clients[cid].get("cardGuid", "")
                    matched_card = next((x for x in leap_cards if x["cardGuid"] == cg), None)
                if not matched_card:
                    matched_card = self.find_matching_leap_card(
                        cname,
                        first_name=str(c.get("firstName") or ""),
                        last_name=str(c.get("lastName") or ""),
                        existing_cards=leap_cards,
                    )
                cspm_clients.append(
                    {
                        "clientId": cid,
                        "clientName": cname,
                        "entityType": str(c.get("entityType") or ""),
                        "primaryEmail": str(c.get("primaryEmail") or ""),
                        "primaryPhone": str(c.get("primaryPhone") or ""),
                        "status": str(c.get("status") or "Active"),
                        "inLeapCard": bool(matched_card),
                        "leapCardGuid": matched_card["cardGuid"] if matched_card else "",
                        "leapCardName": matched_card["fullName"] if matched_card else "",
                        "leapCardType": matched_card["type"] if matched_card else "",
                    }
                )
        except Exception as exc:
            logger.debug("repo.list_client_directory warning: %s", exc)

        def _register_cspm_matter(raw: Dict[str, Any]) -> None:
            mid = str(raw.get("matterId") or raw.get("matter_id") or "").strip()
            mnum = str(raw.get("matterNumber") or raw.get("matter_number") or mid).strip()
            mname = str(raw.get("matterName") or raw.get("matter_name") or raw.get("displayName") or raw.get("display_name") or "").strip()
            cid = str(raw.get("clientId") or raw.get("client_id") or "").strip()
            cname = str(raw.get("clientName") or raw.get("client_name") or "").strip()
            status = str(raw.get("status") or "Open").strip()
            if status in ("Closed", "Archived", "Deleted"):
                return
            if mid.upper() == "MAT-DEFAULT" or mnum.upper() == "MAT-DEFAULT" or not cname:
                return
            dedup_k = (mnum or mid).upper()
            if not dedup_k or dedup_k in seen_matter_keys:
                return
            seen_matter_keys.add(dedup_k)

            matched_leap_matter = None
            map_entry = mapped_matters.get(mid) or mapped_matters.get(mnum)
            if map_entry:
                mg = str(map_entry.get("matterGuid") or "").lower()
                fno = str(map_entry.get("leapFileNumber") or "")
                matched_leap_matter = next((m for m in leap_matters if m["matterGuid"] == mg), None) or leap_by_fno.get(fno)
                if not matched_leap_matter and mg:
                    matched_leap_matter = {"matterGuid": mg, "fileNumber": fno, "type": map_entry.get("matterType", "")}

            if not matched_leap_matter:
                # Match explicit 4-digit LEAP number if embedded or equal
                if mnum in leap_by_fno:
                    matched_leap_matter = leap_by_fno[mnum]
                else:
                    nc = _norm_name(cname)
                    if "," in cname and not leap_matters_by_client.get(nc):
                        f_p, l_p = _parse_person_name(cname)
                        nc = _norm_name(f"{f_p} {l_p}")
                    c_matters = leap_matters_by_client.get(nc) or []
                    if len(c_matters) == 1:
                        matched_leap_matter = c_matters[0]
                    elif len(c_matters) > 1:
                        nm = _norm_name(mname)
                        for cand_m in c_matters:
                            if nm and (nm in _norm_name(cand_m.get("description", "")) or _norm_name(cand_m.get("type", "")) in nm):
                                matched_leap_matter = cand_m
                                break

            matched_card = self.find_matching_leap_card(cname, existing_cards=leap_cards)
            cspm_matters.append(
                {
                    "matterId": mid or mnum,
                    "matterNumber": mnum,
                    "matterName": mname,
                    "clientId": cid,
                    "clientName": cname,
                    "matterType": str(raw.get("matterType") or raw.get("matter_type") or raw.get("practiceArea") or ""),
                    "status": status,
                    "inLeap": bool(matched_leap_matter),
                    "leapMatterGuid": matched_leap_matter.get("matterGuid", "") if matched_leap_matter else "",
                    "leapFileNumber": matched_leap_matter.get("fileNumber", "") if matched_leap_matter else "",
                    "inLeapCard": bool(matched_card),
                    "leapCardGuid": matched_card["cardGuid"] if matched_card else "",
                    "leapCardName": matched_card["fullName"] if matched_card else "",
                    "label": f"{cname} - {mname} ({mnum})" if mname else f"{cname} ({mnum})",
                }
            )

        try:
            for m in self.repo.list_matter_directory() or []:
                _register_cspm_matter(m)
        except Exception as exc:
            logger.debug("repo.list_matter_directory warning: %s", exc)

        dbs = self._all_sqlite_db_paths()
        if dbs:
            try:
                conn = sqlite3.connect(str(dbs[0]))
                cur = conn.cursor()
                for tbl_sql in (
                    "SELECT matter_id, matter_number, matter_name, display_name, client_id, client_name, status, practice_area AS matter_type FROM Matter",
                    "SELECT matter_id, matter_number, description AS matter_name, description AS display_name, client_id, '' AS client_name, status, matter_type FROM matters",
                ):
                    try:
                        cur.execute(tbl_sql)
                        cols = [d[0] for d in cur.description]
                        for row in cur.fetchall():
                            _register_cspm_matter(dict(zip(cols, row)))
                    except Exception:
                        continue
                conn.close()
            except Exception:
                pass

        cspm_matters.sort(key=lambda x: (bool(x["inLeap"]), (x["clientName"] or "").lower(), (x["matterNumber"] or "").lower()))
        return {
            "cspmClients": cspm_clients,
            "cspmMatters": cspm_matters,
            "leapCardsCount": len(leap_cards),
            "leapMattersCount": len(leap_matters),
        }

    def suggest_onedrive_client_folder(self, client_name: str) -> str:
        clean = _clean_folder_name(client_name)
        if "," in clean:
            f_p, l_p = _parse_person_name(clean)
            alt = _clean_folder_name(f"{f_p} {l_p}")
        else:
            alt = clean
        if self.clients_lpn_root.is_dir():
            norm_targets = {_norm_name(clean), _norm_name(alt)}
            norm_targets.discard("")
            try:
                for entry in os.scandir(self.clients_lpn_root):
                    if entry.is_dir() and _norm_name(entry.name) in norm_targets:
                        return str(Path(entry.path))
            except Exception:
                pass
        return str(self.clients_lpn_root / clean)

    def get_leap_intake_bootstrap(self) -> Dict[str, Any]:
        inv = self.list_cspm_clients_and_matters_with_leap_status()
        next_fno, next_seq = self.compute_next_leap_file_number()
        mtypes = self.list_ontario_matter_types()
        compact_types = [
            {
                "matterTypeId": m["matterTypeId"],
                "name": m["name"],
                "isFavorite": bool(m.get("isFavorite")),
                "description": m.get("description", ""),
            }
            for m in mtypes
        ]
        return {
            "ok": True,
            "firmId": LEAP_DEFAULT_FIRM_ID,
            "nextLeapFileNumber": next_fno,
            "nextLeapSequence": next_seq,
            "staff": LPN_STAFF,
            "defaultStaff": {
                "credit": "CS",
                "responsible": "CS",
                "acting": "CS",
                "assisting": "AT",
            },
            "cardTypes": [
                {"code": "Company", "label": "🏢 Company / Corporation", "cspmEntityType": "Corporation"},
                {"code": "People", "label": "👤 Individual (Person)", "cspmEntityType": "Individual"},
                {"code": "Business", "label": "🤝 Partnership / LP / Business", "cspmEntityType": "Partnership"},
                {"code": "Trust", "label": "🛡️ Trust / Estate", "cspmEntityType": "Trust"},
            ],
            "matterTypes": compact_types,
            "clientsLpnRoot": str(self.clients_lpn_root),
            "cspmMatters": inv["cspmMatters"],
            "cspmClients": inv["cspmClients"],
            "leapCardsCount": inv["leapCardsCount"],
            "leapMattersCount": inv["leapMattersCount"],
        }

    def build_cspm_to_leap_prefill(self, matter_key: str = "", client_key: str = "") -> Dict[str, Any]:
        """Pull full ClientProfile + MatterProfile from CSPM to pre-fill LEAP Card + Matter creation."""
        m_prof: Dict[str, Any] = {}
        c_prof: Dict[str, Any] = {}

        if matter_key:
            try:
                res_m = self.repo.get_matter_profile(matter_key) or {}
                m_prof = dict(res_m.get("matter") or res_m or {})
            except Exception:
                m_prof = {}
            if not m_prof.get("clientName"):
                dbs = self._all_sqlite_db_paths()
                if dbs:
                    try:
                        conn = sqlite3.connect(str(dbs[0]))
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT * FROM Matter WHERE upper(matter_id)=upper(?) OR upper(matter_number)=upper(?) LIMIT 1",
                            (matter_key, matter_key),
                        )
                        row = cur.fetchone()
                        if row:
                            cols = [d[0] for d in cur.description]
                            d = dict(zip(cols, row))
                            m_prof = {
                                "matterId": d.get("matter_id") or matter_key,
                                "matterNumber": d.get("matter_number") or matter_key,
                                "matterName": d.get("matter_name") or d.get("display_name") or "",
                                "clientId": d.get("client_id") or "",
                                "clientName": d.get("client_name") or "",
                                "practiceArea": d.get("practice_area") or "",
                                "matterType": d.get("matter_type") or "",
                                "billingEmail": d.get("billing_email") or "",
                                "defaultRate": d.get("default_rate") or 475.0,
                                "description": d.get("description") or d.get("matter_name") or "",
                            }
                        conn.close()
                    except Exception:
                        pass

        resolved_client_key = str(client_key or m_prof.get("clientId") or m_prof.get("clientName") or "").strip()
        if resolved_client_key:
            try:
                res_c = self.repo.get_client_profile(resolved_client_key) or {}
                c_prof = dict(res_c.get("client") or res_c or {})
            except Exception:
                c_prof = {}

        client_name = str(
            c_prof.get("legalName")
            or c_prof.get("displayName")
            or c_prof.get("clientName")
            or m_prof.get("clientName")
            or resolved_client_key
        ).strip()
        if not client_name:
            return {"ok": False, "message": f"Could not find CSPM matter/client '{matter_key or client_key}'."}

        ent = str(c_prof.get("entityType") or "").strip().lower()
        name_low = client_name.lower()
        if "trust" in ent or "trust" in name_low or "estate of" in name_low:
            card_type = "Trust"
        elif "partner" in ent or re.search(r"\b(lp|llp|limited partnership|general partnership)\b", name_low):
            card_type = "Business"
        elif "indiv" in ent or "person" in ent:
            card_type = "People"
        elif "corp" in ent or "comp" in ent or re.search(r"\b(inc|corp|ltd|limited|incorporated|ulc|holdings|corporation|enterprises|group|pc)\b", name_low):
            card_type = "Company"
        else:
            card_type = "People" if ("," in client_name or len(client_name.split()) == 2) else "Company"

        first_name, last_name = "", ""
        contact_first, contact_last = "", ""
        if card_type == "People":
            first_name, last_name = _parse_person_name(
                client_name,
                first_hint=str(c_prof.get("firstName") or ""),
                last_hint=str(c_prof.get("lastName") or ""),
            )
        else:
            principal = str(c_prof.get("principalName") or m_prof.get("billingContact") or "").strip()
            if principal:
                contact_first, contact_last = _parse_person_name(principal)

        raw_type_hint = " ".join(
            [
                str(m_prof.get("practiceArea") or ""),
                str(m_prof.get("matterType") or ""),
                str(m_prof.get("matterNumber") or ""),
                str(m_prof.get("matterName") or ""),
            ]
        )
        mt = self.resolve_matter_type(raw_type_hint)
        existing_card = self.find_matching_leap_card(client_name, first_name=first_name, last_name=last_name)

        resp_lawyer = str(m_prof.get("responsibleLawyer") or "CS")
        staff_init = "JH" if "james" in resp_lawyer.lower() or resp_lawyer.strip().upper() == "JH" else "CS"

        parties = m_prof.get("parties") or []
        joint_clients: List[str] = []
        if isinstance(parties, list) and len(parties) > 1:
            for pt in parties:
                pname = str((pt or {}).get("clientName") or (pt or {}).get("partyName") or "").strip()
                if pname and _norm_name(pname) != _norm_name(client_name):
                    joint_clients.append(pname)

        prefill = {
            "sourceMode": "CSPM_EXISTING",
            "cspmMatterId": str(m_prof.get("matterId") or ""),
            "cspmMatterNumber": str(m_prof.get("matterNumber") or ""),
            "cspmClientId": str(c_prof.get("clientId") or m_prof.get("clientId") or ""),
            "cardType": card_type,
            "clientName": f"{first_name} {last_name}".strip() if card_type == "People" and first_name else client_name,
            "shortName": f"{last_name}, {first_name}".strip(", ") if card_type == "People" and last_name else client_name,
            "firstName": first_name,
            "lastName": last_name,
            "contactFirstName": contact_first,
            "contactLastName": contact_last,
            "email": str(m_prof.get("billingEmail") or c_prof.get("primaryEmail") or c_prof.get("billingEmail") or "").strip(),
            "phone": str(c_prof.get("primaryPhone") or "").strip(),
            "website": str(c_prof.get("website") or "").strip(),
            "addressLine1": str(c_prof.get("addressLine1") or "").strip(),
            "city": str(c_prof.get("city") or "Toronto").strip(),
            "stateProvince": str(c_prof.get("stateProvince") or "ON").strip(),
            "postalCode": str(c_prof.get("postalCode") or "").strip(),
            "country": str(c_prof.get("country") or "Canada").strip(),
            "taxId": str(c_prof.get("taxId") or "").strip(),
            "createMatter": bool(matter_key or m_prof.get("matterName")),
            "matterTypeId": mt["matterTypeId"],
            "matterTypeName": mt["name"],
            "matterDescription": str(m_prof.get("matterName") or m_prof.get("description") or mt["name"]).strip(),
            "otherRefs": str(m_prof.get("matterNumber") or "").strip(),
            "rate": float(m_prof.get("defaultRate") or 475.0),
            "creditStaff": staff_init,
            "responsibleStaff": staff_init,
            "actingStaff": staff_init,
            "assistingStaff": "AT",
            "jointClientNames": joint_clients,
            "existingLeapCard": existing_card,
            "oneDriveFolder": self.suggest_onedrive_client_folder(client_name),
            "linkLeapSync": True,
        }
        return {"ok": True, "prefill": prefill}

    # ------------------------------------------------------------------
    # Exact LEAP Wire & Local Cache XML Builders
    # ------------------------------------------------------------------
    def build_person_xml(
        self,
        person_guid: str,
        first_name: str,
        last_name: str,
        email: str = "",
        phone: str = "",
        website: str = "",
        auth_ctx: Optional[Dict[str, str]] = None,
    ) -> str:
        ctx = auth_ctx or self.get_leap_auth_context(refresh_if_needed=False)
        now_s = _now_leap_iso()
        return (
            "<Person>\n"
            "  <Version>\n"
            "    <BaseVersion>1</BaseVersion>\n"
            f"    <RecordId>{_xml_esc(person_guid)}</RecordId>\n"
            f"    <UserId>{_xml_esc(ctx['userId'])}</UserId>\n"
            f"    <FirmId>{_xml_esc(ctx['firmId'])}</FirmId>\n"
            f"    <StaffId>{_xml_esc(ctx['staffId'])}</StaffId>\n"
            f"    <LastUpdate>{_xml_esc(now_s)}</LastUpdate>\n"
            "    <Status>Current</Status>\n"
            f"    <InstanceGuid>{_xml_esc(ctx['instanceGuid'])}</InstanceGuid>\n"
            f"    <ModifiedUserId>{_xml_esc(ctx['userId'])}</ModifiedUserId>\n"
            f"    <ModifiedStaffId>{_xml_esc(ctx['staffId'])}</ModifiedStaffId>\n"
            f"    <CreatedByAppId>{LEAP_APP_ID}</CreatedByAppId>\n"
            f"    <ModifiedByAppId>{LEAP_APP_ID}</ModifiedByAppId>\n"
            "  </Version>\n"
            "  <PersonId>0</PersonId>\n"
            "  <DeleteCode>0</DeleteCode>\n"
            "  <Gender>Unknown</Gender>\n"
            f"  <FirstName>{_xml_esc(first_name)}</FirstName>\n"
            f"  <LastName>{_xml_esc(last_name)}</LastName>\n"
            "  <EmailType1>1</EmailType1>\n"
            "  <EmailType2>2</EmailType2>\n"
            "  <PhoneType1>1</PhoneType1>\n"
            "  <PhoneType2>2</PhoneType2>\n"
            "  <PhoneType3>3</PhoneType3>\n"
            "  <WebAddresses>\n"
            f"    <WebAddress><Type>Email</Type><Value>{_xml_esc(email)}</Value></WebAddress>\n"
            f"    <WebAddress><Type>Web</Type><Value>{_xml_esc(website)}</Value></WebAddress>\n"
            "    <WebAddress><Type>Email2</Type><Value /></WebAddress>\n"
            "    <WebAddress><Type>Web2</Type><Value /></WebAddress>\n"
            "  </WebAddresses>\n"
            "  <PhoneNumbers>\n"
            f"    <PhoneNumber><Type>Phone</Type><Value>{_xml_esc(phone)}</Value></PhoneNumber>\n"
            "  </PhoneNumbers>\n"
            "</Person>"
        )

    def build_card_xml(
        self,
        card_guid: str,
        card_type: str,
        full_name: str,
        short_name: str = "",
        person_guids: Optional[List[str]] = None,
        email: str = "",
        phone: str = "",
        website: str = "",
        address_line1: str = "",
        city: str = "",
        state_prov: str = "ON",
        postal_code: str = "",
        country: str = "Canada",
        trustees_title: str = "",
        settlor_name: str = "",
        include_persons_inline: bool = True,
        auth_ctx: Optional[Dict[str, str]] = None,
    ) -> str:
        ctx = auth_ctx or self.get_leap_auth_context(refresh_if_needed=False)
        now_s = _now_leap_iso()
        ctype = card_type if card_type in ("People", "Company", "Business", "Trust") else "Company"
        sname = short_name or full_name
        title_val = trustees_title or full_name
        salutation = sname.split(",")[0].strip() if ctype == "People" else "Sir/Madam"
        street_no, street_name = _split_street_address(address_line1)

        company_tags = ""
        if ctype in ("Company", "Business"):
            company_tags = (
                f"  <CompanyName>{_xml_esc(full_name)}</CompanyName>\n"
                f"  <TradingName>{_xml_esc(full_name)}</TradingName>\n"
            )
        elif ctype == "Trust":
            company_tags = (
                f"  <TradingName>{_xml_esc(full_name)}</TradingName>\n"
                "  <TrustStatus>as trustees for</TrustStatus>\n"
            )

        addr_children = ["      <Type>Street</Type>"]
        if street_no:
            addr_children.append(f"      <Number>{_xml_esc(street_no)}</Number>")
        if street_name:
            addr_children.append(f"      <Street>{_xml_esc(street_name)}</Street>")
        if city:
            addr_children.append(f"      <Suburb>{_xml_esc(city)}</Suburb>")
        if state_prov:
            addr_children.append(f"      <State>{_xml_esc(state_prov)}</State>")
        if postal_code:
            addr_children.append(f"      <Postcode>{_xml_esc(postal_code)}</Postcode>")
        if country and (street_name or city or postal_code):
            addr_children.append(f"      <Country>{_xml_esc(country)}</Country>")
        addr_children.extend(
            [
                "      <PostCodeType>Zip</PostCodeType>",
                "      <StateType />",
                "      <StreetDirection />",
                "      <Municipality />",
            ]
        )

        persons_block = ""
        if include_persons_inline:
            p_list = [p for p in (person_guids or []) if p]
            if p_list:
                inner = "".join(f"    <Person><RecordId>{_xml_esc(pg)}</RecordId></Person>\n" for pg in p_list)
                persons_block = f"  <Persons>\n{inner}  </Persons>\n"
            else:
                persons_block = "  <Persons />\n"

        return (
            "<Card>\n"
            "  <Version>\n"
            "    <BaseVersion>1</BaseVersion>\n"
            f"    <RecordId>{_xml_esc(card_guid)}</RecordId>\n"
            f"    <UserId>{_xml_esc(ctx['userId'])}</UserId>\n"
            f"    <FirmId>{_xml_esc(ctx['firmId'])}</FirmId>\n"
            f"    <StaffId>{_xml_esc(ctx['staffId'])}</StaffId>\n"
            f"    <LastUpdate>{_xml_esc(now_s)}</LastUpdate>\n"
            "    <Status>Current</Status>\n"
            f"    <InstanceGuid>{_xml_esc(ctx['instanceGuid'])}</InstanceGuid>\n"
            f"    <ModifiedUserId>{_xml_esc(ctx['userId'])}</ModifiedUserId>\n"
            f"    <ModifiedStaffId>{_xml_esc(ctx['staffId'])}</ModifiedStaffId>\n"
            f"    <CreatedByAppId>{LEAP_APP_ID}</CreatedByAppId>\n"
            f"    <ModifiedByAppId>{LEAP_APP_ID}</ModifiedByAppId>\n"
            "  </Version>\n"
            "  <CardId>0</CardId>\n"
            "  <DeleteCode>0</DeleteCode>\n"
            "  <Fields />\n"
            f"  <ShortName>{_xml_esc(sname)}</ShortName>\n"
            f"  <FullName>{_xml_esc(full_name)}</FullName>\n"
            f"  <Type>{_xml_esc(ctype)}</Type>\n"
            "  <IsSupplier>False</IsSupplier>\n"
            "  <TitleType>Default</TitleType>\n"
            f"  <Title>{_xml_esc(title_val)}</Title>\n"
            "  <SalutationTitleType>DefaultFormal</SalutationTitleType>\n"
            f"  <SalutationTitle>{_xml_esc(salutation)}</SalutationTitle>\n"
            f"  <Description>{_xml_esc(full_name)}</Description>\n"
            f"{company_tags}"
            "  <SoleDirector>False</SoleDirector>\n"
            "  <EmailType1>1</EmailType1>\n"
            "  <EmailType2>2</EmailType2>\n"
            "  <PhoneType1>1</PhoneType1>\n"
            "  <PhoneType2>2</PhoneType2>\n"
            "  <PhoneType3>3</PhoneType3>\n"
            "  <MarketingConsent>False</MarketingConsent>\n"
            "  <RegOffice>\n"
            "    <SameAsStreetAddress>False</SameAsStreetAddress>\n"
            "    <StreetDirection />\n"
            "    <Municipality />\n"
            "  </RegOffice>\n"
            "  <BankAccount>\n"
            "    <BSB />\n"
            "    <AccountName />\n"
            "    <AccountNumber />\n"
            "    <VerifiedBy />\n"
            "    <DateVerified />\n"
            "  </BankAccount>\n"
            "  <Trust>\n"
            "    <TrustPurpose />\n"
            f"    <SettlorName>{_xml_esc(settlor_name)}</SettlorName>\n"
            "  </Trust>\n"
            "  <Addresses>\n"
            "    <DefaultAddress>Street</DefaultAddress>\n"
            "    <Address>\n"
            + "\n".join(addr_children)
            + "\n    </Address>\n"
            "    <Address>\n"
            "      <Type>POBox</Type>\n"
            "      <POBoxType>PO Box</POBoxType>\n"
            "      <StationInfo />\n"
            "      <StateType />\n"
            "      <Municipality />\n"
            "    </Address>\n"
            "    <Address>\n"
            "      <Type>DX</Type>\n"
            "    </Address>\n"
            "  </Addresses>\n"
            "  <FutureAddresses>\n"
            "    <Hide>true</Hide>\n"
            "    <DefaultAddress>Street</DefaultAddress>\n"
            "    <StartDate />\n"
            "    <EndDate />\n"
            "    <Address><Type>Street</Type><PostCodeType /><StateType /><StreetDirection /><Municipality /></Address>\n"
            "    <Address><Type>POBox</Type><StationInfo /><StateType /><Municipality /></Address>\n"
            "    <Address><Type>DX</Type></Address>\n"
            "  </FutureAddresses>\n"
            "  <WebAddresses>\n"
            f"    <WebAddress><Type>Email</Type><Value>{_xml_esc(email)}</Value></WebAddress>\n"
            f"    <WebAddress><Type>Web</Type><Value>{_xml_esc(website)}</Value></WebAddress>\n"
            "    <WebAddress><Type>Email2</Type><Value /></WebAddress>\n"
            "    <WebAddress><Type>Web2</Type><Value /></WebAddress>\n"
            "  </WebAddresses>\n"
            "  <PhoneNumbers>\n"
            f"    <PhoneNumber><Type>Phone</Type><Value>{_xml_esc(phone)}</Value></PhoneNumber>\n"
            "  </PhoneNumbers>\n"
            "  <Trustees />\n"
            "  <DocList />\n"
            f"{persons_block}"
            "</Card>"
        )

    def build_matter_xml(
        self,
        matter_guid: str,
        file_number: str,
        sequence_num: int,
        matter_type: Dict[str, Any],
        client_card_guids: List[str],
        client_display_name: str,
        custom_description: str,
        other_refs: str = "",
        credit_staff: Optional[Dict[str, str]] = None,
        responsible_staff: Optional[Dict[str, str]] = None,
        acting_staff: Optional[Dict[str, str]] = None,
        assisting_staff: Optional[Dict[str, str]] = None,
        include_cards_inline: bool = True,
        auth_ctx: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """Returns (matter_xml, standalone_card_list_xml)."""
        ctx = auth_ctx or self.get_leap_auth_context(refresh_if_needed=False)
        now_s = _now_leap_iso()
        s_credit = credit_staff or self.resolve_staff("CS")
        s_resp = responsible_staff or self.resolve_staff("CS")
        s_acting = acting_staff or self.resolve_staff("CS")
        s_assist = assisting_staff or self.resolve_staff("AT")

        primary_card = client_card_guids[0]
        sub = matter_type.get("substitution") or {"Client": "3", "OtherSide": "7", "OtherSideSolicitor": "4", "OtherSideInsurer": "0"}
        ttl = matter_type.get("title") or {
            "Client": matter_type["name"],
            "ClientPrefix": "false",
            "ClientSuffix": "false",
            "Other": f"- {matter_type['name']}",
            "OtherPrefix": "true",
            "OtherSuffix": "false",
        }
        auto_desc = "true" if not custom_description or custom_description.strip().lower() == matter_type["name"].lower() else "false"
        desc_text = custom_description.strip() or matter_type["name"]

        # DefinableTables
        dt_entries = matter_type.get("definableTables") or []
        if dt_entries:
            dt_xml_inner = "\n".join(
                "    <DefinableTable>\n"
                f"      <DefinableTableId>{_xml_esc(dt['definableTableId'])}</DefinableTableId>\n"
                f"      <Order>{_xml_esc(dt['order'])}</Order>\n"
                "      <Default>true</Default>\n"
                "      <CalcFieldId />\n"
                "      <DisplaySequence>1</DisplaySequence>\n"
                "      <Description />\n"
                "      <Fields />\n"
                "      <RecordId />\n"
                "    </DefinableTable>"
                for dt in dt_entries
            )
            dt_block = f"  <DefinableTables>\n{dt_xml_inner}\n  </DefinableTables>\n"
        else:
            dt_block = "  <DefinableTables />\n"

        # Relations
        rel_entries = matter_type.get("relations") or []
        if rel_entries:
            rel_inner = "\n".join(
                "    <Relation>\n"
                f"      <ParentTableId>{_xml_esc(r['parentTableId'])}</ParentTableId>\n"
                f"      <ChildTableId>{_xml_esc(r['childTableId'])}</ChildTableId>\n"
                f"      <Order>{_xml_esc(r.get('order', '1'))}</Order>\n"
                f"      <Singleton>{_xml_esc(r.get('singleton', 'false'))}</Singleton>\n"
                f"      <Active>{_xml_esc(r.get('active', 'false'))}</Active>\n"
                "      <CalcFieldId />\n"
                "    </Relation>"
                for r in rel_entries
            )
            rel_block = f"  <Relations>\n{rel_inner}\n  </Relations>\n"
        else:
            rel_block = "  <Relations />\n"

        # Cards binding: bind all represented client_card_guids to TableId=3 and primary debtor to TableId=733
        card_nodes: List[str] = []
        raw_def_cards = matter_type.get("defaultCards") or []
        norm_def_cards: List[Dict[str, str]] = []
        for idx_c, item in enumerate(raw_def_cards, start=1):
            if isinstance(item, dict):
                norm_def_cards.append(item)
            else:
                norm_def_cards.append({"tableId": str(item), "order": str(idx_c * 1000000 + 1000)})

        seen_t3 = False
        seen_t733 = False
        for dc in norm_def_cards:
            tid = dc["tableId"]
            order_s = dc["order"]
            if tid == "3":
                seen_t3 = True
                for seq_i, cg in enumerate(client_card_guids, start=1):
                    mc_id = str(uuid4())
                    ord_val = int(order_s) + (seq_i - 1) * 1000 if order_s.isdigit() else 1000000 + seq_i * 1000
                    card_nodes.append(
                        "    <Card>\n"
                        "      <Table_TableId>3</Table_TableId>\n"
                        f"      <Order>{ord_val}</Order>\n"
                        f"      <Default>{'true' if seq_i == 1 else 'false'}</Default>\n"
                        "      <CalcFieldId />\n"
                        f"      <RecordId>{_xml_esc(cg)}</RecordId>\n"
                        f"      <DisplaySequence>{seq_i}</DisplaySequence>\n"
                        "      <Reference />\n"
                        f"      <MatterCardId>{mc_id}</MatterCardId>\n"
                        "    </Card>"
                    )
            elif tid == "733":
                seen_t733 = True
                mc_id = str(uuid4())
                card_nodes.append(
                    "    <Card>\n"
                    "      <Table_TableId>733</Table_TableId>\n"
                    f"      <Order>{_xml_esc(order_s)}</Order>\n"
                    "      <Default>true</Default>\n"
                    "      <CalcFieldId />\n"
                    f"      <RecordId>{_xml_esc(primary_card)}</RecordId>\n"
                    "      <DisplaySequence>1</DisplaySequence>\n"
                    "      <Reference />\n"
                    f"      <MatterCardId>{mc_id}</MatterCardId>\n"
                    "    </Card>"
                )
            else:
                card_nodes.append(
                    "    <Card>\n"
                    f"      <Table_TableId>{_xml_esc(tid)}</Table_TableId>\n"
                    f"      <Order>{_xml_esc(order_s)}</Order>\n"
                    "      <Default>true</Default>\n"
                    "      <CalcFieldId />\n"
                    "      <RecordId />\n"
                    "      <DisplaySequence>1</DisplaySequence>\n"
                    "    </Card>"
                )

        if not seen_t3:
            for seq_i, cg in enumerate(client_card_guids, start=1):
                card_nodes.insert(
                    seq_i - 1,
                    "    <Card>\n"
                    "      <Table_TableId>3</Table_TableId>\n"
                    f"      <Order>{1000000 + seq_i * 1000}</Order>\n"
                    f"      <Default>{'true' if seq_i == 1 else 'false'}</Default>\n"
                    "      <CalcFieldId />\n"
                    f"      <RecordId>{_xml_esc(cg)}</RecordId>\n"
                    f"      <DisplaySequence>{seq_i}</DisplaySequence>\n"
                    "      <Reference />\n"
                    f"      <MatterCardId>{uuid4()}</MatterCardId>\n"
                    "    </Card>",
                )
        if not seen_t733:
            card_nodes.append(
                "    <Card>\n"
                "      <Table_TableId>733</Table_TableId>\n"
                "      <Order>17001000</Order>\n"
                "      <Default>true</Default>\n"
                "      <CalcFieldId />\n"
                f"      <RecordId>{_xml_esc(primary_card)}</RecordId>\n"
                "      <DisplaySequence>1</DisplaySequence>\n"
                "      <Reference />\n"
                f"      <MatterCardId>{uuid4()}</MatterCardId>\n"
                "    </Card>"
            )

        cards_inner = "\n".join(card_nodes)
        inline_cards_block = f"  <Cards>\n{cards_inner}\n  </Cards>\n" if include_cards_inline else ""
        standalone_card_list = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Cards ModifiedUserId="{_xml_esc(ctx["userId"])}" InstanceGuid="{_xml_esc(matter_guid)}">\n'
            f"{cards_inner}\n"
            "</Cards>"
        )

        is_time_rec = "True" if matter_type.get("isTimeRecorded", True) else "False"
        matter_xml = (
            "<Matter>\n"
            "  <Version>\n"
            "    <BaseVersion>1</BaseVersion>\n"
            f"    <RecordId>{_xml_esc(matter_guid)}</RecordId>\n"
            f"    <UserId>{_xml_esc(ctx['userId'])}</UserId>\n"
            f"    <FirmId>{_xml_esc(ctx['firmId'])}</FirmId>\n"
            f"    <StaffId>{_xml_esc(ctx['staffId'])}</StaffId>\n"
            f"    <LastUpdate>{_xml_esc(now_s)}</LastUpdate>\n"
            "    <Status>Current</Status>\n"
            f"    <InstanceGuid>{_xml_esc(ctx['instanceGuid'])}</InstanceGuid>\n"
            f"    <ModifiedUserId>{_xml_esc(ctx['userId'])}</ModifiedUserId>\n"
            f"    <ModifiedStaffId>{_xml_esc(ctx['staffId'])}</ModifiedStaffId>\n"
            f"    <CreatedByAppId>{LEAP_APP_ID}</CreatedByAppId>\n"
            f"    <ModifiedByAppId>{LEAP_APP_ID}</ModifiedByAppId>\n"
            "  </Version>\n"
            f"{dt_block}"
            "  <Comments />\n"
            "  <File>\n"
            f"    <Number>{_xml_esc(file_number)}</Number>\n"
            f"    <OtherRefs>{_xml_esc(other_refs)}</OtherRefs>\n"
            f"    <Sequence>{int(sequence_num)}</Sequence>\n"
            "  </File>\n"
            f"  <MatterType_MatterTypeId>{_xml_esc(matter_type['matterTypeId'])}</MatterType_MatterTypeId>\n"
            "  <DeleteCode>0</DeleteCode>\n"
            "  <NoFileCreated>false</NoFileCreated>\n"
            "  <Financial>\n"
            "    <EstimateWarning>0</EstimateWarning>\n"
            f"    <TimeRecordedMatter>{is_time_rec}</TimeRecordedMatter>\n"
            "    <CostsEstimate>0</CostsEstimate>\n"
            "    <CostsEstimateGST>0</CostsEstimateGST>\n"
            "    <DisbursementsEstimate>0</DisbursementsEstimate>\n"
            "    <DisbursementsEstimateGST>0</DisbursementsEstimateGST>\n"
            "    <CostAgreement><Required>False</Required><Received /></CostAgreement>\n"
            "    <EstimateWarningAction />\n"
            "    <AutoAllocateFees>False</AutoAllocateFees>\n"
            "    <OmitFromOverdueInvoices>False</OmitFromOverdueInvoices>\n"
            "    <TaxCodes><IncomeGST /><ExpenseGST /><GST /></TaxCodes>\n"
            "    <MinimumCreditBalance>0</MinimumCreditBalance>\n"
            "    <CreditBalanceWarning>0</CreditBalanceWarning>\n"
            "    <MinimumTrustRetainerBalance>0</MinimumTrustRetainerBalance>\n"
            f"    <DefaultTrustAccountGuid>{LEAP_DEFAULT_TRUST_ACCOUNT_GUID}</DefaultTrustAccountGuid>\n"
            "    <GLReportingGroupBranchGuid />\n"
            "  </Financial>\n"
            f"  <DataVersion>{LEAP_APP_VERSION}</DataVersion>\n"
            "  <IsCurrent>True</IsCurrent>\n"
            f"  <Type>{_xml_esc(matter_type['name'])}</Type>\n"
            "  <State>ON</State>\n"
            "  <Substitution>\n"
            f"    <Client>{_xml_esc(sub.get('Client', '3'))}</Client>\n"
            f"    <OtherSide>{_xml_esc(sub.get('OtherSide', '7'))}</OtherSide>\n"
            f"    <OtherSideSolicitor>{_xml_esc(sub.get('OtherSideSolicitor', '4'))}</OtherSideSolicitor>\n"
            f"    <OtherSideInsurer>{_xml_esc(sub.get('OtherSideInsurer', '0'))}</OtherSideInsurer>\n"
            "  </Substitution>\n"
            f"  <CustomDescription>{_xml_esc(desc_text)}</CustomDescription>\n"
            f"  <AutoCustomDescription>{auto_desc}</AutoCustomDescription>\n"
            "  <Title>\n"
            f"    <Client>{_xml_esc(ttl.get('Client', matter_type['name']))}</Client>\n"
            f"    <ClientPrefix>{_xml_esc(ttl.get('ClientPrefix', 'false'))}</ClientPrefix>\n"
            f"    <ClientSuffix>{_xml_esc(ttl.get('ClientSuffix', 'false'))}</ClientSuffix>\n"
            f"    <Other>{_xml_esc(ttl.get('Other', '- ' + matter_type['name']))}</Other>\n"
            f"    <OtherPrefix>{_xml_esc(ttl.get('OtherPrefix', 'true'))}</OtherPrefix>\n"
            f"    <OtherSuffix>{_xml_esc(ttl.get('OtherSuffix', 'false'))}</OtherSuffix>\n"
            "    <ClientDefault>true</ClientDefault>\n"
            "    <OtherDefault>true</OtherDefault>\n"
            "  </Title>\n"
            "  <CriticalDates>\n"
            "    <CriticalDate>\n"
            "      <CriticalDateId>2</CriticalDateId>\n"
            "      <Name>Instruction date</Name>\n"
            "      <DisplayName>File opened date</DisplayName>\n"
            "      <IsConfirmable>false</IsConfirmable>\n"
            "      <Status>In progress</Status>\n"
            "      <ConfirmStatus />\n"
            "      <CompPercent>0</CompPercent>\n"
            "      <Order>1</Order>\n"
            "      <JSName>instructionDate</JSName>\n"
            f"      <Value>{_xml_esc(now_s)}</Value>\n"
            "      <Confirmed>false</Confirmed>\n"
            "      <CalculationFieldId />\n"
            "      <CalculationTableId />\n"
            "      <AutoCalc>false</AutoCalc>\n"
            "    </CriticalDate>\n"
            "    <CriticalDate>\n"
            "      <CriticalDateId>-2</CriticalDateId>\n"
            "      <Name>File complete date</Name>\n"
            "      <DisplayName>File closed date</DisplayName>\n"
            "      <IsConfirmable>true</IsConfirmable>\n"
            "      <Status>To be completed</Status>\n"
            "      <ConfirmStatus>Complete</ConfirmStatus>\n"
            "      <CompPercent>0</CompPercent>\n"
            "      <Order>4</Order>\n"
            "      <JSName>fileCompleteDate</JSName>\n"
            "      <Value />\n"
            "      <Confirmed>false</Confirmed>\n"
            "      <CalculationFieldId />\n"
            "      <CalculationTableId />\n"
            "      <AutoCalc>false</AutoCalc>\n"
            "    </CriticalDate>\n"
            "  </CriticalDates>\n"
            '  <Status AIStatus="false">In progress</Status>\n'
            f"{rel_block}"
            "  <Staff>\n"
            f'    <Credit Access="0">{_xml_esc(s_credit["staffId"])}</Credit>\n'
            f'    <Responsible Access="0">{_xml_esc(s_resp["staffId"])}</Responsible>\n'
            f'    <Acting Access="0">{_xml_esc(s_acting["staffId"])}</Acting>\n'
            f'    <Assisting Access="0">{_xml_esc(s_assist["staffId"])}</Assisting>\n'
            f'    <Initials>{_xml_esc(s_resp["initials"])}</Initials>\n'
            "  </Staff>\n"
            "  <Referrer />\n"
            "  <WorkObtained />\n"
            "  <InvoiceFixed>False</InvoiceFixed>\n"
            "  <InvoiceFixedAmount>0</InvoiceFixedAmount>\n"
            "  <FilemanStatus />\n"
            "  <ReferrerCard><CardGUID /><PersonGUID /></ReferrerCard>\n"
            "  <DebtorNote />\n"
            "  <TaxFree>False</TaxFree>\n"
            "  <ReportingGroupId />\n"
            "  <BillingCategoryId />\n"
            '  <ACL Enabled="false" />\n'
            "  <Title2><ClientDefault>true</ClientDefault><OtherDefault>true</OtherDefault></Title2>\n"
            "  <CustomFields />\n"
            "  <MatterId>0</MatterId>\n"
            "  <Description>\n"
            f"    <First>{_xml_esc(client_display_name)}</First>\n"
            "    <Second />\n"
            f"    <FirstLong>{_xml_esc(client_display_name)}</FirstLong>\n"
            "  </Description>\n"
            f"  <DebtorCard>{_xml_esc(primary_card)}</DebtorCard>\n"
            "  <DocList_RequestTimeStamp />\n"
            "  <Calculations />\n"
            f"{inline_cards_block}"
            "</Matter>"
        )
        return matter_xml, standalone_card_list

    # ------------------------------------------------------------------
    # Local LEAP Desktop Cache Persistence (Windows Instant UI Visibility)
    # ------------------------------------------------------------------
    def _write_local_leap_desktop_cache(
        self,
        person_records: List[Tuple[str, str]],
        card_records: List[Dict[str, Any]],
        matter_record: Optional[Dict[str, Any]],
        auth_ctx: Dict[str, str],
    ) -> None:
        data_dir = self._resolve_leap_user_data_dir()
        if not data_dir:
            return
        try:
            persons_dir = data_dir / "Persons"
            cards_dir = data_dir / "Cards"
            matters_dir = data_dir / "Matters"
            persons_dir.mkdir(parents=True, exist_ok=True)
            cards_dir.mkdir(parents=True, exist_ok=True)
            matters_dir.mkdir(parents=True, exist_ok=True)

            for p_guid, p_xml in person_records:
                (persons_dir / f"{p_guid}.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n' + p_xml, encoding="utf-8")

            cl_path = cards_dir / "CardList.xml"
            cl_tree = ET.parse(cl_path) if cl_path.is_file() else ET.ElementTree(ET.Element("Cards"))
            cl_root = cl_tree.getroot()
            existing_c_guids = {(el.attrib.get("guid") or "").lower() for el in cl_root.findall("Card")}

            for cr in card_records:
                c_guid = cr["cardGuid"]
                local_c_xml = cr["localCardXml"]
                p_guids = cr.get("personGuids") or []
                (cards_dir / f"{c_guid}.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n' + local_c_xml, encoding="utf-8")
                if p_guids:
                    plist_inner = "\n".join(
                        f"  <Person><Order>{i}</Order><RecordId>{_xml_esc(pg)}</RecordId></Person>"
                        for i, pg in enumerate(p_guids, start=1)
                    )
                    plist_xml = (
                        '<?xml version="1.0" encoding="utf-8"?>\n'
                        f'<Persons ModifiedUserId="{_xml_esc(auth_ctx["userId"])}" InstanceGuid="{_xml_esc(c_guid)}">\n'
                        f"{plist_inner}\n"
                        "</Persons>"
                    )
                    (cards_dir / f"{c_guid}_PersonList.xml").write_text(plist_xml, encoding="utf-8")
                if c_guid.lower() not in existing_c_guids:
                    c_node = ET.SubElement(cl_root, "Card", {"guid": c_guid, "ver": "1"})
                    ET.SubElement(c_node, "CardId").text = "0"
                    ET.SubElement(c_node, "DeleteCode").text = "0"
                    ET.SubElement(c_node, "Type").text = cr["cardType"]
                    if cr["cardType"] in ("Company", "Business"):
                        ET.SubElement(c_node, "CompanyName").text = cr["fullName"]
                    ET.SubElement(c_node, "TradingName").text = cr["fullName"] if cr["cardType"] != "People" else ""
                    ET.SubElement(c_node, "IsSupplier").text = "False"
                    ET.SubElement(c_node, "PropertySuburb").text = cr.get("city") or ""
                    ET.SubElement(c_node, "ShortName").text = cr["shortName"]
                    ET.SubElement(c_node, "FullName").text = cr["fullName"]
                    ET.SubElement(c_node, "Tables")
                    p_sub = ET.SubElement(c_node, "Persons")
                    for pg in p_guids:
                        ET.SubElement(p_sub, "RecordId").text = pg
                    ET.SubElement(c_node, "InstanceGuid").text = auth_ctx["instanceGuid"]
            if card_records:
                cl_tree.write(cl_path, encoding="utf-8", xml_declaration=True)

            if matter_record:
                m_guid = matter_record["matterGuid"]
                srv_xml = matter_record["serverMatterXml"]
                # Split <Cards> out for local LEAP Desktop cache format
                m_root = ET.fromstring(srv_xml)
                inline_cards = m_root.find("Cards")
                if inline_cards is not None:
                    m_root.remove(inline_cards)
                (matters_dir / f"{m_guid}.xml").write_text(
                    '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(m_root, encoding="unicode"),
                    encoding="utf-8",
                )
                (matters_dir / f"{m_guid}_CardList.xml").write_text(matter_record["cardListXml"], encoding="utf-8")

                ml_path = matters_dir / "MatterList.xml"
                ml_tree = ET.parse(ml_path) if ml_path.is_file() else ET.ElementTree(ET.Element("Matters"))
                ml_root = ml_tree.getroot()
                existing_m_guids = {(el.attrib.get("guid") or "").lower() for el in ml_root.findall("Matter")}
                if m_guid.lower() not in existing_m_guids:
                    now_s = _now_leap_iso()
                    mn = ET.SubElement(ml_root, "Matter", {"guid": m_guid, "ver": "1"})
                    ET.SubElement(mn, "Type").text = matter_record["matterTypeName"]
                    ET.SubElement(mn, "State").text = "ON"
                    ET.SubElement(mn, "DeleteCode").text = "0"
                    ET.SubElement(mn, "LastUpdate").text = now_s
                    ET.SubElement(mn, "FileNumber").text = matter_record["fileNumber"]
                    ET.SubElement(mn, "Status").text = "In progress"
                    ET.SubElement(mn, "Staff").text = matter_record["staffInitials"]
                    resp_el = ET.SubElement(mn, "Responsible", {"Access": "0"})
                    resp_el.text = matter_record["responsibleStaffId"]
                    d_el = ET.SubElement(mn, "Description")
                    ET.SubElement(d_el, "First").text = matter_record["clientDisplayName"]
                    ET.SubElement(d_el, "FirstLong").text = matter_record["clientDisplayName"]
                    ET.SubElement(mn, "CustomDescription").text = matter_record["customDescription"]
                    sub_el = ET.SubElement(mn, "Substitution")
                    for k_sub, v_sub in (matter_record.get("substitution") or {}).items():
                        ET.SubElement(sub_el, k_sub).text = str(v_sub)
                    cs_el = ET.SubElement(mn, "Cards")
                    for cg in matter_record["clientCardGuids"]:
                        ce = ET.SubElement(cs_el, "Card")
                        ET.SubElement(ce, "RecordId").text = cg
                        ET.SubElement(ce, "TableId").text = "3"
                    ce_deb = ET.SubElement(cs_el, "Card")
                    ET.SubElement(ce_deb, "RecordId").text = matter_record["clientCardGuids"][0]
                    ET.SubElement(ce_deb, "TableId").text = "733"
                    ET.SubElement(mn, "InstructionDate").text = now_s
                    ml_tree.write(ml_path, encoding="utf-8", xml_declaration=True)
        except Exception as exc:
            logger.warning("Local LEAP Desktop cache write warning: %s", exc)

    # ------------------------------------------------------------------
    # Core Intake Orchestration (Push to LEAP + Unified CSPM + LeapSync)
    # ------------------------------------------------------------------
    def push_to_leap(self, payload: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Create or reuse LEAP Card (+ Person) and optionally create LEAP Matter + OneDrive LeapSync link."""
        data = dict(payload or {})
        dry_run = bool(dry_run or data.get("dryRun", False))
        create_matter = bool(data.get("createMatter", True))
        force_new_card = bool(data.get("forceNewCard", False))
        link_folder = bool(data.get("linkLeapSync", data.get("linkFolder", False)))

        card_type = str(data.get("cardType") or "Company").strip()
        if card_type not in ("Company", "People", "Business", "Trust"):
            card_type = "Company"

        first_name = str(data.get("firstName") or "").strip()
        last_name = str(data.get("lastName") or "").strip()
        raw_client_name = str(data.get("clientName") or "").strip()
        if card_type == "People":
            if not (first_name and last_name) and raw_client_name:
                first_name, last_name = _parse_person_name(raw_client_name, first_name, last_name)
            full_name = f"{first_name} {last_name}".strip() or raw_client_name
            short_name = str(data.get("shortName") or (f"{last_name}, {first_name}".strip(", ") if last_name else full_name)).strip()
        else:
            full_name = raw_client_name or f"{first_name} {last_name}".strip()
            short_name = str(data.get("shortName") or full_name).strip()

        if not full_name:
            return {"ok": False, "message": "Client / Card name is required."}

        contact_first = str(data.get("contactFirstName") or "").strip()
        contact_last = str(data.get("contactLastName") or "").strip()
        email = str(data.get("email") or "").strip()
        phone = str(data.get("phone") or "").strip()
        website = str(data.get("website") or "").strip()
        addr1 = str(data.get("addressLine1") or "").strip()
        city = str(data.get("city") or "").strip()
        state_prov = str(data.get("stateProvince") or "ON").strip()
        postal = str(data.get("postalCode") or "").strip()
        country = str(data.get("country") or "Canada").strip()

        auth_ctx = self.get_leap_auth_context(refresh_if_needed=not dry_run)
        existing_cards, existing_matters = self.list_existing_leap_cards_and_matters()

        explicit_card_guid = str(data.get("existingCardGuid") or "").strip().lower()
        matched_card = None
        if explicit_card_guid and not force_new_card:
            matched_card = next((c for c in existing_cards if c["cardGuid"] == explicit_card_guid), None)
            if not matched_card:
                matched_card = {"cardGuid": explicit_card_guid, "fullName": full_name, "type": card_type}
        elif not force_new_card:
            matched_card = self.find_matching_leap_card(full_name, first_name=first_name, last_name=last_name, existing_cards=existing_cards)

        person_records_to_create: List[Tuple[str, str]] = []
        card_records_to_create: List[Dict[str, Any]] = []
        client_card_guids: List[str] = []

        if matched_card:
            primary_card_guid = matched_card["cardGuid"]
            card_action = "reuse_existing"
            wire_card_xml = ""
        else:
            primary_card_guid = str(uuid4())
            card_action = "create_new"
            p_guids: List[str] = []
            if card_type == "People":
                pg = str(uuid4())
                p_xml = self.build_person_xml(pg, first_name or full_name, last_name, email=email, phone=phone, website=website, auth_ctx=auth_ctx)
                ET.fromstring(p_xml)
                person_records_to_create.append((pg, p_xml))
                p_guids.append(pg)
            elif contact_first or contact_last:
                pg = str(uuid4())
                p_xml = self.build_person_xml(pg, contact_first, contact_last, email=email, phone=phone, website=website, auth_ctx=auth_ctx)
                ET.fromstring(p_xml)
                person_records_to_create.append((pg, p_xml))
                p_guids.append(pg)

            wire_card_xml = self.build_card_xml(
                card_guid=primary_card_guid,
                card_type=card_type,
                full_name=full_name,
                short_name=short_name,
                person_guids=p_guids,
                email=email,
                phone=phone,
                website=website,
                address_line1=addr1,
                city=city,
                state_prov=state_prov,
                postal_code=postal,
                country=country,
                include_persons_inline=True,
                auth_ctx=auth_ctx,
            )
            local_card_xml = self.build_card_xml(
                card_guid=primary_card_guid,
                card_type=card_type,
                full_name=full_name,
                short_name=short_name,
                person_guids=p_guids,
                email=email,
                phone=phone,
                website=website,
                address_line1=addr1,
                city=city,
                state_prov=state_prov,
                postal_code=postal,
                country=country,
                include_persons_inline=False,
                auth_ctx=auth_ctx,
            )
            ET.fromstring(wire_card_xml)
            card_records_to_create.append(
                {
                    "cardGuid": primary_card_guid,
                    "cardType": card_type,
                    "fullName": full_name,
                    "shortName": short_name,
                    "city": city,
                    "personGuids": p_guids,
                    "wireCardXml": wire_card_xml,
                    "localCardXml": local_card_xml,
                }
            )
        client_card_guids.append(primary_card_guid)

        # Optional Joint Clients
        joint_names = [str(x).strip() for x in (data.get("jointClientNames") or []) if str(x).strip()]
        for jname in joint_names:
            j_match = self.find_matching_leap_card(jname, existing_cards=existing_cards)
            if j_match:
                client_card_guids.append(j_match["cardGuid"])
            else:
                jg = str(uuid4())
                j_is_person = "," in jname or not re.search(r"\b(inc|corp|ltd|lp|trust|holdings)\b", jname.lower())
                j_pguids: List[str] = []
                if j_is_person:
                    jf, jl = _parse_person_name(jname)
                    jpg = str(uuid4())
                    jp_xml = self.build_person_xml(jpg, jf, jl, auth_ctx=auth_ctx)
                    person_records_to_create.append((jpg, jp_xml))
                    j_pguids.append(jpg)
                    j_full = f"{jf} {jl}".strip()
                    j_short = f"{jl}, {jf}".strip(", ")
                    j_type = "People"
                else:
                    j_full = jname
                    j_short = jname
                    j_type = "Company"
                jw_xml = self.build_card_xml(jg, j_type, j_full, j_short, person_guids=j_pguids, include_persons_inline=True, auth_ctx=auth_ctx)
                jl_xml = self.build_card_xml(jg, j_type, j_full, j_short, person_guids=j_pguids, include_persons_inline=False, auth_ctx=auth_ctx)
                card_records_to_create.append(
                    {
                        "cardGuid": jg,
                        "cardType": j_type,
                        "fullName": j_full,
                        "shortName": j_short,
                        "city": "",
                        "personGuids": j_pguids,
                        "wireCardXml": jw_xml,
                        "localCardXml": jl_xml,
                    }
                )
                client_card_guids.append(jg)

        matter_guid = ""
        file_number = ""
        seq_num = 0
        mt_obj: Dict[str, Any] = {}
        wire_matter_xml = ""
        card_list_xml = ""
        custom_desc = ""
        s_credit = self.resolve_staff(str(data.get("creditStaff") or "CS"), "CS")
        s_resp = self.resolve_staff(str(data.get("responsibleStaff") or "CS"), "CS")
        s_acting = self.resolve_staff(str(data.get("actingStaff") or "CS"), "CS")
        s_assist = self.resolve_staff(str(data.get("assistingStaff") or "AT"), "AT")

        if create_matter:
            matter_guid = str(uuid4())
            req_fno = str(data.get("leapFileNumber") or "").strip()
            if req_fno and req_fno.isdigit():
                seq_num = int(req_fno)
                file_number = f"{seq_num:04d}"
            else:
                file_number, seq_num = self.compute_next_leap_file_number(existing_matters=existing_matters)
            mt_obj = self.resolve_matter_type(str(data.get("matterTypeId") or data.get("matterTypeName") or data.get("matterType") or ""))
            custom_desc = str(data.get("matterDescription") or data.get("description") or mt_obj["name"]).strip()
            other_refs = str(data.get("otherRefs") or data.get("cspmMatterNumber") or "").strip()
            wire_matter_xml, card_list_xml = self.build_matter_xml(
                matter_guid=matter_guid,
                file_number=file_number,
                sequence_num=seq_num,
                matter_type=mt_obj,
                client_card_guids=client_card_guids,
                client_display_name=full_name,
                custom_description=custom_desc,
                other_refs=other_refs,
                credit_staff=s_credit,
                responsible_staff=s_resp,
                acting_staff=s_acting,
                assisting_staff=s_assist,
                include_cards_inline=True,
                auth_ctx=auth_ctx,
            )
            ET.fromstring(wire_matter_xml)
            ET.fromstring(card_list_xml)

        target_folder = str(data.get("oneDriveFolder") or "").strip() or self.suggest_onedrive_client_folder(full_name)

        if dry_run:
            return {
                "ok": True,
                "dryRun": True,
                "cardAction": card_action,
                "cardGuid": primary_card_guid,
                "cardType": card_type,
                "clientName": full_name,
                "personsToCreate": len(person_records_to_create),
                "cardsToCreate": len(card_records_to_create),
                "createMatter": create_matter,
                "matterGuid": matter_guid,
                "allocatedFileNumber": file_number,
                "matterTypeId": mt_obj.get("matterTypeId", ""),
                "matterTypeName": mt_obj.get("name", ""),
                "matterDescription": custom_desc,
                "staff": {
                    "credit": f"{s_credit['name']} ({s_credit['initials']})",
                    "responsible": f"{s_resp['name']} ({s_resp['initials']})",
                    "acting": f"{s_acting['name']} ({s_acting['initials']})",
                    "assisting": f"{s_assist['name']} ({s_assist['initials']})",
                },
                "oneDriveFolder": target_folder,
                "willLinkLeapSync": link_folder,
                "xmlSizes": {
                    "personBytes": sum(len(x[1].encode("utf-8")) for x in person_records_to_create),
                    "cardBytes": len(wire_card_xml.encode("utf-8")),
                    "matterBytes": len(wire_matter_xml.encode("utf-8")),
                },
                "message": (
                    f"[DRY RUN] Validated LEAP XMLs: Card '{full_name}' ({'REUSE ' + primary_card_guid[:8] if card_action == 'reuse_existing' else 'NEW ' + card_type})"
                    + (f" -> Matter #{file_number} ({mt_obj.get('name')} - {custom_desc})" if create_matter else "")
                ),
            }

        # LIVE PUSH TO LEAP CLOUD (Person -> Card -> Matter)
        sync_log: List[str] = []
        for p_guid, p_xml in person_records_to_create:
            ok_p, msg_p, _ = self.save_leap_record("Person", p_guid, p_xml)
            sync_log.append(f"Person {p_guid}: {msg_p}")

        for cr in card_records_to_create:
            ok_c, msg_c, srv_c_xml = self.save_leap_record("Card", cr["cardGuid"], cr["wireCardXml"])
            sync_log.append(f"Card {cr['cardGuid']} ({cr['fullName']}): {msg_c}")

        matter_cache_rec: Optional[Dict[str, Any]] = None
        if create_matter:
            ok_m, msg_m, srv_m_xml = self.save_leap_record("Matter", matter_guid, wire_matter_xml)
            sync_log.append(f"Matter {matter_guid}: {msg_m}")
            try:
                srv_m_root = ET.fromstring(srv_m_xml)
                srv_fno = (srv_m_root.findtext("./File/Number") or "").strip()
                if srv_fno:
                    file_number = srv_fno
            except Exception:
                pass
            matter_cache_rec = {
                "matterGuid": matter_guid,
                "fileNumber": file_number,
                "matterTypeName": mt_obj["name"],
                "staffInitials": s_resp["initials"],
                "responsibleStaffId": s_resp["staffId"],
                "clientDisplayName": full_name,
                "customDescription": custom_desc,
                "substitution": mt_obj.get("substitution") or {},
                "clientCardGuids": client_card_guids,
                "serverMatterXml": srv_m_xml,
                "cardListXml": card_list_xml,
            }

        self._write_local_leap_desktop_cache(
            person_records=person_records_to_create,
            card_records=card_records_to_create,
            matter_record=matter_cache_rec,
            auth_ctx=auth_ctx,
        )
        # Refresh shared_state cache
        self.list_existing_leap_cards_and_matters()

        # Persist CSPM <-> LEAP mapping
        fmap = self.load_cspm_leap_map()
        cspm_cid = str(data.get("cspmClientId") or "").strip()
        if cspm_cid:
            fmap["clients"][cspm_cid] = {
                "cardGuid": primary_card_guid,
                "clientName": full_name,
                "cardType": card_type,
                "updatedAt": _now_leap_iso(),
            }
        cspm_mid = str(data.get("cspmMatterId") or "").strip()
        cspm_mnum = str(data.get("cspmMatterNumber") or "").strip()
        if create_matter:
            entry_val = {
                "matterGuid": matter_guid,
                "leapFileNumber": file_number,
                "cardGuid": primary_card_guid,
                "clientName": full_name,
                "matterType": mt_obj["name"],
                "description": custom_desc,
                "cspmMatterId": cspm_mid,
                "cspmMatterNumber": cspm_mnum,
                "oneDriveFolder": target_folder if link_folder else "",
                "updatedAt": _now_leap_iso(),
            }
            if cspm_mid:
                fmap["matters"][cspm_mid] = entry_val
            if cspm_mnum:
                fmap["matters"][cspm_mnum] = entry_val
            fmap["matters"][file_number] = entry_val
        self.save_cspm_leap_map(fmap)

        leap_sync_status = ""
        if create_matter and link_folder and target_folder:
            folder_p = Path(target_folder)
            folder_p.mkdir(parents=True, exist_ok=True)
            if self._ensure_leap_sync_importable():
                try:
                    from leap_sync.core import link_matter

                    ok_ls, msg_ls = link_matter(
                        identifier=matter_guid,
                        folder_path=folder_p,
                        preserve_local_layout=True,
                    )
                    leap_sync_status = msg_ls
                except Exception as exc:
                    leap_sync_status = f"Folder created ({folder_p}), LeapSync link warning: {exc}"
            else:
                leap_sync_status = f"Folder created ({folder_p}); LeapSync module not on path."

        return {
            "ok": True,
            "dryRun": False,
            "cardAction": card_action,
            "cardGuid": primary_card_guid,
            "cardType": card_type,
            "clientName": full_name,
            "createMatter": create_matter,
            "matterGuid": matter_guid,
            "leapFileNumber": file_number,
            "matterTypeName": mt_obj.get("name", "") if create_matter else "",
            "matterDescription": custom_desc,
            "oneDriveFolder": target_folder if link_folder else "",
            "leapSyncStatus": leap_sync_status,
            "syncLog": sync_log,
            "message": (
                f"Pushed to LEAP: {full_name}"
                + (f" -> Matter #{file_number} ({mt_obj.get('name')} - {custom_desc})" if create_matter else " (Card Only)")
                + (" + Linked LeapSync!" if leap_sync_status else "")
            ),
        }

    def _ensure_cspm_records(self, payload: Dict[str, Any], allocated_leap_fno: str = "") -> Dict[str, Any]:
        """Create/update Client & Matter in CSPM (ExcelRepo if writeable, plus SQLite cspm.db)."""
        data = dict(payload or {})
        card_type = str(data.get("cardType") or "Company").strip()
        entity_map = {
            "People": "Individual",
            "Company": "Corporation",
            "Business": "Partnership",
            "Trust": "Trust",
        }
        entity_type = entity_map.get(card_type, "Corporation")
        first_name = str(data.get("firstName") or "").strip()
        last_name = str(data.get("lastName") or "").strip()
        client_name = str(data.get("clientName") or f"{first_name} {last_name}".strip()).strip()
        email = str(data.get("email") or "").strip()
        phone = str(data.get("phone") or "").strip()
        rate = float(data.get("rate") or 475.0)
        biller_entity = str(
            data.get("billerEntity") or ("PC" if date.today().isoformat() >= "2026-11-01" else "SOLE_PROP")
        ).strip().upper()

        mt_obj = self.resolve_matter_type(str(data.get("matterTypeId") or data.get("matterTypeName") or data.get("matterType") or ""))
        matter_desc = str(data.get("matterDescription") or data.get("description") or mt_obj["name"]).strip()

        clean_tok = re.sub(r"[^A-Za-z0-9]+", "", (last_name or client_name).upper())[:4].ljust(4, "X")
        if "tax" in mt_obj["name"].lower():
            type_tok, prac_area = "TAX", "Tax"
        elif "trust" in mt_obj["name"].lower():
            type_tok, prac_area = "TRT", "Trusts & Estates"
        elif "will" in mt_obj["name"].lower():
            type_tok, prac_area = "EST", "Trusts & Estates"
        else:
            type_tok, prac_area = "CRP", "Corporate / Commercial"

        yr_tok = date.today().strftime("%y")
        seq_part = allocated_leap_fno or datetime.now().strftime("%m%d")
        matter_number = str(data.get("cspmMatterNumber") or data.get("matterNumber") or f"{clean_tok}-LEVI-{type_tok}-{yr_tok}-{seq_part}").strip().upper()
        client_id = str(data.get("cspmClientId") or f"C_{clean_tok}_{uuid4().hex[:4].upper()}").strip()
        matter_id = str(data.get("cspmMatterId") or f"M_{matter_number.replace('-', '_')}").strip()
        today_iso = date.today().isoformat()

        # Try full ExcelRepo save first when workbook is unlocked; fall back cleanly to SQLite
        saved_via_repo = False
        try:
            c_res = self.repo.save_client_profile(
                {
                    "clientId": data.get("cspmClientId") or "",
                    "clientName": client_name,
                    "displayName": client_name,
                    "legalName": client_name,
                    "firstName": first_name,
                    "lastName": last_name,
                    "entityType": entity_type,
                    "principalName": f"{data.get('contactFirstName', '')} {data.get('contactLastName', '')}".strip(),
                    "primaryEmail": email,
                    "billingEmail": email,
                    "primaryPhone": phone,
                    "website": str(data.get("website") or ""),
                    "addressLine1": str(data.get("addressLine1") or ""),
                    "city": str(data.get("city") or ""),
                    "stateProvince": str(data.get("stateProvince") or "ON"),
                    "postalCode": str(data.get("postalCode") or ""),
                    "country": str(data.get("country") or "Canada"),
                    "taxId": str(data.get("taxId") or ""),
                    "status": "Active",
                }
            )
            if c_res and c_res.get("ok"):
                client_id = str(c_res.get("clientId") or client_id)
                if bool(data.get("createMatter", True)):
                    m_res = self.repo.save_matter_profile(
                        {
                            "matterId": data.get("cspmMatterId") or "",
                            "matterNumber": matter_number,
                            "matterName": matter_desc,
                            "displayName": matter_desc,
                            "clientId": client_id,
                            "clientName": client_name,
                            "matterType": prac_area,
                            "practiceArea": prac_area,
                            "status": "Open",
                            "responsibleLawyer": "Cory Schneider",
                            "billingArrangement": "Hourly",
                            "billingEmail": email,
                            "defaultRate": rate,
                            "defaultSharePct": 100.0,
                            "dateOpened": today_iso,
                            "description": matter_desc,
                            "defaultBiller": biller_entity,
                        }
                    )
                    if m_res and m_res.get("ok"):
                        matter_id = str(m_res.get("matterId") or matter_id)
                        matter_number = str(m_res.get("matterNumber") or matter_number)
                        saved_via_repo = True
                else:
                    saved_via_repo = True
        except Exception as exc:
            logger.debug("ExcelRepo intake save skipped (using SQLite direct): %s", exc)

        if not saved_via_repo:
            for db_p in self._all_sqlite_db_paths():
                try:
                    conn = sqlite3.connect(str(db_p))
                    cur = conn.cursor()
                    # Table set 1: QuickExpense lowercase tables if present
                    try:
                        cur.execute("SELECT client_id FROM clients WHERE lower(name)=lower(?) LIMIT 1", (client_name,))
                        row_c = cur.fetchone()
                        if row_c:
                            client_id = str(row_c[0])
                        else:
                            cur.execute(
                                "INSERT OR IGNORE INTO clients (client_id, name, billing_name, default_rate_cents, hst_exempt, status, created_at, updated_at) VALUES (?, ?, ?, ?, 0, 'Active', ?, ?)",
                                (client_id, client_name, client_name, int(round(rate * 100)), today_iso, today_iso),
                            )
                        if bool(data.get("createMatter", True)):
                            cur.execute(
                                "INSERT OR REPLACE INTO matters (matter_id, matter_number, client_id, description, matter_type, status, open_date, default_rate_cents, default_biller_entity, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?)",
                                (matter_id, matter_number, client_id, matter_desc, prac_area, today_iso, int(round(rate * 100)), biller_entity, today_iso, today_iso),
                            )
                    except Exception:
                        pass
                    # Table set 2: Canonical CSPM PascalCase tables if present
                    try:
                        cur.execute("SELECT client_id FROM Client WHERE lower(client_name)=lower(?) OR lower(display_name)=lower(?) LIMIT 1", (client_name, client_name))
                        row_pc = cur.fetchone()
                        if row_pc:
                            client_id = str(row_pc[0])
                        else:
                            cur.execute(
                                "INSERT OR IGNORE INTO Client (client_id, client_name, display_name, legal_name, entity_type, primary_email, primary_phone, status, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', 1, ?, ?)",
                                (client_id, client_name, client_name, client_name, entity_type, email, phone, today_iso, today_iso),
                            )
                        if bool(data.get("createMatter", True)):
                            cur.execute(
                                "INSERT OR REPLACE INTO Matter (matter_id, matter_number, matter_name, display_name, client_id, client_name, matter_type, practice_area, status, default_rate, default_share_pct, default_biller_entity, date_opened, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, 100.0, ?, ?, ?, ?)",
                                (matter_id, matter_number, matter_desc, matter_desc, client_id, client_name, prac_area, prac_area, rate, biller_entity, today_iso, today_iso, today_iso),
                            )
                    except Exception:
                        pass
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    logger.warning("SQLite intake save warning (%s): %s", db_p, exc)

        return {
            "cspmClientId": client_id,
            "cspmMatterId": matter_id,
            "cspmMatterNumber": matter_number,
            "clientName": client_name,
            "matterName": matter_desc,
            "savedViaExcelRepo": saved_via_repo,
        }

    def submit_unified_intake(self, payload: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        """Unified entry point for Quick Expense PWA, CSPM Desktop, and leap-intake CLI.
        Supports:
          - sourceMode == 'CSPM_EXISTING': Pull existing CSPM matter/client and push to LEAP (+ optional folder/LeapSync).
          - sourceMode == 'NEW_INTAKE': Create in CSPM + push to LEAP + scaffold OneDrive folder + link LeapSync."""
        data = dict(payload or {})
        dry_run = bool(dry_run or data.get("dryRun", False))
        source_mode = str(data.get("sourceMode") or "NEW_INTAKE").strip().upper()
        push_to_leap_flag = bool(data.get("pushToLeap", True))

        if source_mode == "CSPM_EXISTING":
            m_ref = str(data.get("cspmMatterId") or data.get("cspmMatterNumber") or data.get("matterKey") or "").strip()
            c_ref = str(data.get("cspmClientId") or data.get("clientKey") or "").strip()
            if (m_ref or c_ref) and not data.get("clientName"):
                pre = self.build_cspm_to_leap_prefill(matter_key=m_ref, client_key=c_ref)
                if not pre.get("ok"):
                    return pre
                merged = dict(pre["prefill"])
                merged.update({k: v for k, v in data.items() if v not in (None, "")})
                data = merged
            return self.push_to_leap(data, dry_run=dry_run)

        # Brand-New Unified Intake
        allocated_fno = ""
        if push_to_leap_flag and bool(data.get("createMatter", True)):
            allocated_fno, _ = self.compute_next_leap_file_number()

        if dry_run:
            leap_preview = self.push_to_leap(data, dry_run=True) if push_to_leap_flag else {"ok": True, "dryRun": True}
            leap_preview["willSaveToCspm"] = True
            return leap_preview

        cspm_res = self._ensure_cspm_records(data, allocated_leap_fno=allocated_fno)
        data["cspmClientId"] = cspm_res["cspmClientId"]
        data["cspmMatterId"] = cspm_res["cspmMatterId"]
        data["cspmMatterNumber"] = cspm_res["cspmMatterNumber"]

        if not push_to_leap_flag:
            return {
                "ok": True,
                "cspm": cspm_res,
                "message": f"Created in CSPM: {cspm_res['clientName']} - {cspm_res['matterName']} ({cspm_res['cspmMatterNumber']})",
            }

        leap_res = self.push_to_leap(data, dry_run=False)
        leap_res["cspm"] = cspm_res
        if leap_res.get("ok"):
            leap_res["message"] = (
                f"Created in CSPM ({cspm_res['cspmMatterNumber']}) & LEAP "
                + (f"(Matter #{leap_res.get('leapFileNumber')})" if leap_res.get("createMatter") else "(Card)")
                + (" + Linked LeapSync!" if leap_res.get("leapSyncStatus") else "!")
            )
        return leap_res


def cli_main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LeapIntake — Unified CSPM <-> LEAP Cloud/Desktop Client & Matter Intake")
    parser.add_argument("--bootstrap", action="store_true", help="Output full LEAP intake bootstrap JSON")
    parser.add_argument("--list-unlinked-cspm", action="store_true", help="List CSPM matters and their LEAP status")
    parser.add_argument("--prefill-cspm", metavar="MATTER_OR_CLIENT", help="Preview pre-filled LEAP payload from an existing CSPM matter/client")
    parser.add_argument("--push-cspm-matter", metavar="MATTER_KEY", help="Pull an existing CSPM matter and push it to LEAP")
    parser.add_argument("--create", action="store_true", help="Create a new Client (Card) and/or Matter")
    parser.add_argument("--full-intake", action="store_true", help="Also create Client & Matter in CSPM (unified intake)")
    parser.add_argument("--card-only", action="store_true", help="Create LEAP Card only (no Matter)")
    parser.add_argument("--card-type", default="Company", choices=["Company", "People", "Business", "Trust"])
    parser.add_argument("--client-name", default="", help="Company/Trust/Business name or full individual name")
    parser.add_argument("--first-name", default="", help="Individual first name (for People card)")
    parser.add_argument("--last-name", default="", help="Individual last name (for People card)")
    parser.add_argument("--contact-first", default="", help="Primary contact first name (for Company card)")
    parser.add_argument("--contact-last", default="", help="Primary contact last name (for Company card)")
    parser.add_argument("--email", default="", help="Primary / billing email")
    parser.add_argument("--phone", default="", help="Primary phone")
    parser.add_argument("--address", default="", help="Street address line 1")
    parser.add_argument("--city", default="Toronto")
    parser.add_argument("--province", default="ON")
    parser.add_argument("--postal-code", default="")
    parser.add_argument("--matter-type", default="General Advice - Business", help="Ontario LEAP MatterType name or GUID")
    parser.add_argument("--description", default="", help="Matter description")
    parser.add_argument("--rate", type=float, default=475.0, help="CSPM hourly rate")
    parser.add_argument("--credit", default="CS", help="Credit lawyer initials (CS, JH, AT, KT)")
    parser.add_argument("--responsible", default="CS", help="Responsible lawyer initials")
    parser.add_argument("--acting", default="CS", help="Acting lawyer initials")
    parser.add_argument("--assisting", default="AT", help="Assisting clerk initials")
    parser.add_argument("--folder", default="", help="Explicit OneDrive folder path")
    parser.add_argument("--link-folder", action="store_true", help="Create OneDrive folder and link via LeapSync")
    parser.add_argument("--force-new-card", action="store_true", help="Do not reuse matching existing LEAP Card")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview XMLs without writing to LEAP Cloud")

    args = parser.parse_args(argv)
    svc = LeapIntakeService()

    if args.bootstrap:
        print(json.dumps(svc.get_leap_intake_bootstrap(), indent=2, ensure_ascii=False))
        return 0

    if args.list_unlinked_cspm:
        inv = svc.list_cspm_clients_and_matters_with_leap_status()
        unlinked = [m for m in inv["cspmMatters"] if not m["inLeap"]]
        linked = [m for m in inv["cspmMatters"] if m["inLeap"]]
        print(
            json.dumps(
                {
                    "ok": True,
                    "unlinkedCount": len(unlinked),
                    "linkedCount": len(linked),
                    "leapCardsCount": inv["leapCardsCount"],
                    "leapMattersCount": inv["leapMattersCount"],
                    "unlinkedMatters": unlinked,
                    "linkedMatters": linked,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.prefill_cspm:
        res = svc.build_cspm_to_leap_prefill(matter_key=args.prefill_cspm)
        if not res.get("ok"):
            res = svc.build_cspm_to_leap_prefill(client_key=args.prefill_cspm)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 1

    if args.push_cspm_matter:
        pre = svc.build_cspm_to_leap_prefill(matter_key=args.push_cspm_matter)
        if not pre.get("ok"):
            print(json.dumps(pre, indent=2, ensure_ascii=False))
            return 1
        payload = pre["prefill"]
        if args.folder:
            payload["oneDriveFolder"] = args.folder
        payload["linkLeapSync"] = bool(args.link_folder)
        payload["forceNewCard"] = bool(args.force_new_card)
        res = svc.push_to_leap(payload, dry_run=args.dry_run)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 1

    if args.create:
        payload = {
            "sourceMode": "NEW_INTAKE" if args.full_intake else "LEAP_ONLY",
            "cardType": args.card_type,
            "clientName": args.client_name,
            "firstName": args.first_name,
            "lastName": args.last_name,
            "contactFirstName": args.contact_first,
            "contactLastName": args.contact_last,
            "email": args.email,
            "phone": args.phone,
            "addressLine1": args.address,
            "city": args.city,
            "stateProvince": args.province,
            "postalCode": args.postal_code,
            "createMatter": not args.card_only,
            "matterType": args.matter_type,
            "matterDescription": args.description,
            "rate": args.rate,
            "creditStaff": args.credit,
            "responsibleStaff": args.responsible,
            "actingStaff": args.acting,
            "assistingStaff": args.assisting,
            "oneDriveFolder": args.folder,
            "linkLeapSync": bool(args.link_folder),
            "forceNewCard": bool(args.force_new_card),
            "pushToLeap": True,
        }
        if args.full_intake:
            res = svc.submit_unified_intake(payload, dry_run=args.dry_run)
        else:
            res = svc.push_to_leap(payload, dry_run=args.dry_run)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("ok") else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
