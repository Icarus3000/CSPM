"""
xero_sync_service.py: Built-in Lawyers In-House (LIH) Xero Projects (!6x!pP) Auto-Sync & 4-Way Reconciliation
Service for CSPM (Desktop UI, Mobile Quick Expense/Docket PWA, and Background Daemons).

Features:
  1. Pure-Python Headless OIDC PKCE Silent Token Refresh:
     - Reads/writes rolling session cookies and OIDC tokens in
       <OneDrive - LPN>/__Admin/Antigravity_Customizations/shared_state/xero_lih_auth.json
       so OFFICENEW, OMNIBOOK, and imac Fedora share one seamless authenticated session.
  2. Real-Time Non-Blocking Auto-Sync on Docket Create / Update / Delete:
     - `trigger_async_xero_sync_entry(entry_id, paths=None)`: Spawns a background daemon thread
       whenever any docket is saved/edited in CSPM (Desktop or Mobile Phone App). If the docket
       belongs to an LIH matter (`parent_id == 'LIHD'` or James Bittner), it immediately creates (`POST`)
       or updates (`PUT`) the corresponding time entry in Xero Projects and stores `xero_time_entry_id`
       in `cspm.db` (`TimeEntry` and `time_entries`).
     - `trigger_async_xero_delete_entry(entry_id, xero_time_entry_id=None, xero_project_id=None, paths=None)`:
       Deletes (`DELETE`) the time entry in Xero Projects when an unbilled LIH docket is deleted in CSPM.
  3. Dynamic New-Client / New-Matter Auto-Discovery:
     - When a brand-new LIH client/matter is added in CSPM, queries live Xero Projects (`status=INPROGRESS`),
       matches `contactName` / `name`, selects the active lawyer task (`General (Cory Schneider)` /
       `As of Feb 2026` / `General`), and persists the mapping to `shared_state/xero_lih_mappings.json`
       and `Matter` in `cspm.db`.
  4. 4-Way Reconciliation Engine (`get_reconciliation_data`):
     - Reconciles any calendar month (`YYYY-MM`), Month-to-Date (`MTD`), or custom date range across:
       (1) `cspm.db` (`TimeEntry`), (2) `CSPM.xlsm` (`TimeEntries`), (3) `Dockets.xlsm` (`Dockets`), and
       (4) live `Xero Projects` (`!6x!pP`).
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import os
import pathlib
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import openpyxl
import requests

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

XERO_SHORTCODE = "!6x!pP"
XERO_TENANT_ID = "28c5cc37-0749-4193-a623-1af229a56315"
XERO_USER_ID = "26ac926a-d0aa-41c3-9d7a-5f258c5bc5be"
XERO_CLIENT_ID = "xero_business_go"
XERO_SCOPE = "openid profile email xero_frontend-apis xero_frontend-platform-apis"
XERO_TZ = ZoneInfo("America/New_York")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"
)

_SYNC_LOCK = threading.Lock()

DEFAULT_CLIENT_PROJECT_TASK_MAP: Dict[str, Dict[str, Any]] = {
    "ABDI": {
        "client_label": "A2B Directcare Inc.",
        "projectId": "5c6cc12b-a64d-448d-a5bc-fa8e96f36d4c",
        "projectName": "General Corporate",
        "taskId": "373454cd-438f-420a-bf9b-70fb0a8ea0f7",
        "taskName": "General - As of February 2026",
    },
    "PLCG": {
        "client_label": "PLC Group Inc.",
        "projectId": "0d258bbd-f9cd-447f-963e-96a46a87493f",
        "projectName": "Corporate/Commercial",
        "taskId": "fed55d1d-b4e1-4684-b28f-5733dfe2bcbd",
        "taskName": "General - As of Feb 2026",
    },
    "JBIT": {
        "client_label": "James Bittner",
        "projectId": "a71ae482-2db1-43e5-90ce-adbb23ea1b47",
        "projectName": "General Legal Services",
        "taskId": "573fcc3f-a6c5-4051-8221-fdd4d7adb36e",
        "taskName": "General (Cory Schneider)",
        "expected_share_pct": 100.0,
    },
    "NEXT": {
        "client_label": "Next Millennium Farms Inc. (dba Entomo Farms)",
        "projectId": "4e8d1906-eb3e-4006-865f-04fb8b49e6a0",
        "projectName": "General Legal Services",
        "taskId": "94dd9a6a-1cf0-407e-8045-9b3a8d0d8299",
        "taskName": "General - As of Feb 2026",
    },
    "FINA": {
        "client_label": "Finavator Inc.",
        "projectId": "3f3a1689-67ac-4432-b33b-07a62cb25170",
        "projectName": "General Legal Services",
        "taskId": "24bf120f-5dcc-42fc-b725-0ede6f0becd1",
        "taskName": "General - As of Feb 2026",
    },
    "C_3f94496218": {
        "client_label": "Brick Labs Inc.",
        "projectId": "3ed42ce8-229c-472d-a77a-302b57a660b1",
        "projectName": "General Legal Services",
        "taskId": "e90cad91-9e63-4f19-9f25-c01a1c781ab7",
        "taskName": "General - As of Feb 2026",
    },
    "CANA": {
        "client_label": "14876881 Canada Inc (dba Carnegie Capital)",
        "projectId": "c8a8d039-4804-44d5-be9d-af779f3b4b77",
        "projectName": "General Legal Services",
        "taskId": "8265a4d4-a12c-4245-a913-a08c3e65ce84",
        "taskName": "General Legal Services",
    },
    "C_8e33fb4f21": {
        "client_label": "17976704 Canada Ltd.",
        "projectId": "68a2dad3-3b1d-4c6b-a52a-9fe5daef0850",
        "projectName": "General Legal Services",
        "taskId": "98915dfd-8e4c-4765-a616-3e57be9b0bd9",
        "taskName": "Canadian Corporation Share Transfer",
    },
    "BOU": {
        "client_label": "Abound Business Solutions, LLC",
        "projectId": "bea01578-b719-430a-9d91-27e017fa9842",
        "projectName": "General Legal Services",
        "taskId": "9ac644da-64d4-474a-8494-128f28694720",
        "taskName": "General",
    },
    "AFRI": {
        "client_label": "African Bronze Honey Company Limited",
        "projectId": "0ebb6356-edf8-4b42-ac2a-873df0e0a7b5",
        "projectName": "General Legal Services",
        "taskId": "fa02c59c-a2cc-4246-bf8b-b43e2b868587",
        "taskName": "General - As of February 2026",
    },
    "CONS": {
        "client_label": "Constance Terrevina Ince",
        "projectId": "9aeecb5c-f41f-487c-84c1-8b4bab36ce1f",
        "projectName": "Estate Planning",
        "taskId": "80929255-ad65-4cbb-b49a-4ab90ce75ba2",
        "taskName": "Flat Fee",
    },
    "JAME": {
        "client_label": "James A. Hutchinson Private Client",
        "projectId": "12e914cf-bb27-4d44-9d45-8d9276b9e675",
        "projectName": "General Legal Services",
        "taskId": "3c9e962d-5790-4505-9d88-7df1f650b5e4",
        "taskName": "General - As of Feb 2026",
    },
    "OSAM": {
        "client_label": "Osama Khan",
        "projectId": "3f432b84-98d3-45ac-a1fa-742ddf3e6002",
        "projectName": "Osama Khan",
        "taskId": "54431230-6d6b-4e5b-984d-c41175597f35",
        "taskName": "General - As of Feb 2026",
    },
    "BHAR": {
        "client_label": "Shiva Bhardwaj",
        "projectId": "34431c75-b92b-43fd-9caa-857f8c14f6d9",
        "projectName": "Corporate Legal Advisory Services",
        "taskId": "68589188-c1a1-4b8e-9018-45405cb89bf4",
        "taskName": "General",
    },
}


def resolve_xero_runtime_paths(app_paths: Any = None) -> Dict[str, Any]:
    """Resolve OneDrive and local CSPM paths across Windows (OFFICENEW, OMNIBOOK) and Linux (imac Fedora)."""
    home = pathlib.Path.home()
    onedrive_candidates = [
        home / "OneDrive - LPN",
        home / "OneDrive",
        pathlib.Path(os.environ.get("OneDriveCommercial", "")) if os.environ.get("OneDriveCommercial") else None,
        pathlib.Path(os.environ.get("OneDrive", "")) if os.environ.get("OneDrive") else None,
    ]
    onedrive_root = next((p for p in onedrive_candidates if p and p.is_dir()), home / "OneDrive - LPN")

    shared_dir = onedrive_root / "CSPM_Shared_Data"
    primary_dockets = onedrive_root / "__Invoices (1)" / "Dockets.xlsm"
    shared_dockets = shared_dir / "Dockets.xlsm"
    shared_db = shared_dir / "cspm.db"
    shared_xlsm = shared_dir / "CSPM.xlsm"
    shared_state_dir = onedrive_root / "__Admin" / "Antigravity_Customizations" / "shared_state"

    local_data_dir = (
        pathlib.Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))) / "CSPM" / "data"
        if sys.platform == "win32"
        else home / ".cspm_data" / "data"
    )
    local_app_dir = local_data_dir.parent

    if app_paths is not None:
        try:
            if hasattr(app_paths, "master_data_dir"):
                md = app_paths.master_data_dir()
                if md and pathlib.Path(md).is_dir():
                    shared_dir = pathlib.Path(md)
                    if (shared_dir / "cspm.db").is_file():
                        shared_db = shared_dir / "cspm.db"
                    if (shared_dir / "CSPM.xlsm").is_file():
                        shared_xlsm = shared_dir / "CSPM.xlsm"
            if hasattr(app_paths, "data_dir"):
                dd = app_paths.data_dir()
                if dd and pathlib.Path(dd).is_dir():
                    local_data_dir = pathlib.Path(dd)
                    if not shared_db.is_file() and (local_data_dir / "cspm.db").is_file():
                        shared_db = local_data_dir / "cspm.db"
        except Exception:
            pass

    return {
        "onedrive_root": onedrive_root,
        "shared_dir": shared_dir,
        "db_path": shared_db if shared_db.is_file() else (local_data_dir / "cspm.db"),
        "cspm_xlsm_path": shared_xlsm if shared_xlsm.is_file() else (local_data_dir / "CSPM.xlsm"),
        "primary_dockets_xlsm_path": primary_dockets if primary_dockets.is_file() else shared_dockets,
        "shared_dockets_xlsm_path": shared_dockets,
        "local_data_dir": local_data_dir,
        "local_app_dir": local_app_dir,
        "shared_state_dir": shared_state_dir,
    }


def load_merged_client_mappings(shared_state_dir: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    merged = {k: dict(v) for k, v in DEFAULT_CLIENT_PROJECT_TASK_MAP.items()}
    custom_file = shared_state_dir / "xero_lih_mappings.json"
    if custom_file.exists():
        try:
            custom_data = json.loads(custom_file.read_text(encoding="utf-8"))
            if isinstance(custom_data, dict):
                for k, v in custom_data.items():
                    if isinstance(v, dict) and v.get("projectId") and v.get("taskId"):
                        merged[k] = v
        except Exception:
            pass
    return merged


def save_custom_client_mapping(shared_state_dir: pathlib.Path, client_code: str, mapping: Dict[str, Any]) -> None:
    custom_file = shared_state_dir / "xero_lih_mappings.json"
    data: Dict[str, Any] = {}
    if custom_file.exists():
        try:
            data = json.loads(custom_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[client_code] = mapping
    custom_file.parent.mkdir(parents=True, exist_ok=True)
    custom_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm_date(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()[:10]


def flt(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return round(float(val), 4)
    s = str(val).strip().replace("$", "").replace(",", "")
    try:
        return round(float(s), 4)
    except Exception:
        return 0.0


def norm_desc(text: Any) -> str:
    s = " ".join(str(text or "").strip().lower().split())
    if s.startswith("next task: "):
        s = s[len("next task: "):].strip()
    return s


def norm_company_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(inc|incorporated|ltd|limited|corp|corporation|llc|llp|ulc|co|company|the)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def date_to_xero_utc(date_str: str) -> str:
    y, m, d = map(int, date_str[:10].split("-"))
    local_dt = datetime.datetime(y, m, d, 0, 0, 0, tzinfo=XERO_TZ)
    utc_dt = local_dt.astimezone(datetime.timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def xero_utc_to_date(date_utc: str) -> str:
    if not date_utc:
        return ""
    try:
        s = date_utc.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        local_dt = dt.astimezone(XERO_TZ)
        return local_dt.strftime("%Y-%m-%d")
    except Exception:
        return date_utc[:10]


def resolve_client_code(
    client_id: str,
    client_name: str,
    matter_id: str,
    mappings: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    mp = mappings or DEFAULT_CLIENT_PROJECT_TASK_MAP
    cid = (client_id or "").strip()
    if cid in mp:
        return cid
    cname = (client_name or "").lower()
    mid = (matter_id or "").upper()
    if "a2b" in cname or mid.startswith("ABDI") or mid.startswith("A2B"):
        return "ABDI"
    if "plc" in cname or mid.startswith("PLCG") or mid.startswith("GRO"):
        return "PLCG"
    if "bittner" in cname or mid.startswith("JBIT") or mid.startswith("JAM"):
        return "JBIT"
    if "entomo" in cname or "next millennium" in cname or mid.startswith("NEXT") or mid.startswith("NEX"):
        return "NEXT"
    if "finavator" in cname or mid.startswith("FIN"):
        return "FINA"
    if "brick labs" in cname or mid.startswith("BRIC") or mid.startswith("BRI1"):
        return "C_3f94496218"
    if "14876881" in cname or "carnegie" in cname or mid.startswith("CANA") or mid.startswith("1481"):
        return "CANA"
    if "17976704" in cname or mid.startswith("1797"):
        return "C_8e33fb4f21"
    if "abound" in cname or mid.startswith("ABOU"):
        return "BOU"
    if "african bronze" in cname or mid.startswith("AFRI"):
        return "AFRI"
    if "constance" in cname or mid.startswith("CONS") or mid.startswith("CON1"):
        return "CONS"
    if "osama" in cname or mid.startswith("OSA"):
        return "OSAM"
    if "bhardwaj" in cname or "shiva" in cname or mid.startswith("BHA"):
        return "BHAR"
    norm_c = norm_company_name(client_name)
    if norm_c:
        for k, v in mp.items():
            if norm_company_name(v.get("client_label", "")) == norm_c:
                return k
    return cid or cname


def is_lih_entry_or_matter(
    parent_id: str,
    matter_id: str,
    matter_number: str,
    client_id: str,
    client_name: str,
    matter_row: Optional[Dict[str, Any]] = None,
) -> bool:
    pid = str(parent_id or (matter_row or {}).get("parent_id") or "").upper()
    mid = str(matter_id or "").upper()
    mnum = str(matter_number or (matter_row or {}).get("matter_number") or "").upper()
    cid = str(client_id or (matter_row or {}).get("client_id") or "").upper()
    cname = str(client_name or (matter_row or {}).get("client_name") or "").lower()
    if pid == "LIHD" or "LIHD" in mid or "LIHD" in mnum:
        return True
    if cid == "JBIT" or "bittner" in cname or mnum.startswith("JAME-COM-26-0065") or mid.startswith("JAME-COM-26-0065"):
        return True
    if (matter_row or {}).get("xero_project_id"):
        return True
    return False


def ensure_xero_schema(conn: sqlite3.Connection, shared_state_dir: Optional[pathlib.Path] = None) -> None:
    cur = conn.cursor()
    for tbl in ("TimeEntry", "time_entries"):
        cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'")
        if not cur.fetchone():
            continue
        existing_cols = {r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()}
        for col_name, col_def in [
            ("xero_time_entry_id", "TEXT DEFAULT ''"),
            ("xero_project_id", "TEXT DEFAULT ''"),
            ("xero_task_id", "TEXT DEFAULT ''"),
            ("xero_sync_status", "TEXT DEFAULT ''"),
            ("xero_synced_at", "TEXT DEFAULT ''"),
        ]:
            if col_name not in existing_cols:
                try:
                    cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Matter'")
    if cur.fetchone():
        m_cols = {r[1] for r in cur.execute("PRAGMA table_info(Matter)").fetchall()}
        for col_name, col_def in [
            ("xero_project_id", "TEXT DEFAULT ''"),
            ("xero_task_id", "TEXT DEFAULT ''"),
        ]:
            if col_name not in m_cols:
                try:
                    cur.execute(f"ALTER TABLE Matter ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError:
                    pass

        mappings = load_merged_client_mappings(shared_state_dir) if shared_state_dir else DEFAULT_CLIENT_PROJECT_TASK_MAP
        rows = cur.execute("SELECT matter_id, matter_number, client_id, client_name, parent_id, xero_project_id, xero_task_id FROM Matter").fetchall()
        for r in rows:
            mid, mnum, cid, cname, pid, xpid, xtid = r
            if xpid and xtid:
                continue
            if is_lih_entry_or_matter(pid, mid, mnum, cid, cname):
                ccode = resolve_client_code(str(cid or ""), str(cname or ""), str(mnum or mid or ""), mappings)
                mp = mappings.get(ccode)
                if mp and mp.get("projectId") and mp.get("taskId"):
                    cur.execute(
                        "UPDATE Matter SET xero_project_id = ?, xero_task_id = ? WHERE matter_id = ?",
                        (mp["projectId"], mp["taskId"], mid),
                    )
    conn.commit()


class XeroProjectsClient:
    """Cross-workstation headless Xero Projects API client using shared_state/xero_lih_auth.json."""

    def __init__(self, shared_state_dir: pathlib.Path):
        self.shared_state_dir = shared_state_dir
        self.auth_path = shared_state_dir / "xero_lih_auth.json"
        self.catalog_path = shared_state_dir / "xero_lih_catalog.json"
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.expires_at: int = 0
        self._load_auth()

    def _load_auth(self) -> None:
        if not self.auth_path.exists():
            raise RuntimeError(
                f"Xero auth file not found at {self.auth_path}. Click 'Re-Authenticate Xero' to log in."
            )
        data = json.loads(self.auth_path.read_text(encoding="utf-8"))
        for c in data.get("cookies", []):
            self.session.cookies.set(
                c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/")
            )
        oidc_raw = data.get("sessionStorage", {}).get(
            f"oidc.user:https://identity.xero.com:{XERO_CLIENT_ID}", "{}"
        )
        if isinstance(oidc_raw, str):
            try:
                oidc = json.loads(oidc_raw)
            except Exception:
                oidc = {}
        else:
            oidc = oidc_raw or {}
        self.access_token = oidc.get("access_token")
        self.expires_at = int(oidc.get("expires_at") or 0)

    def _save_auth(self, new_oidc: Optional[Dict[str, Any]] = None) -> None:
        try:
            existing = json.loads(self.auth_path.read_text(encoding="utf-8")) if self.auth_path.exists() else {}
        except Exception:
            existing = {}

        cookie_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for c in existing.get("cookies", []):
            key = (c.get("domain", ""), c.get("path", "/"), c.get("name", ""))
            cookie_map[key] = c
        for c in self.session.cookies:
            key = (c.domain or "", c.path or "/", c.name)
            entry = cookie_map.get(key, {}).copy()
            entry.update({
                "name": c.name,
                "value": c.value,
                "domain": c.domain or "",
                "path": c.path or "/",
                "secure": bool(c.secure),
            })
            if c.expires:
                entry["expires"] = c.expires
            cookie_map[key] = entry

        existing["cookies"] = list(cookie_map.values())
        if new_oidc is not None:
            existing.setdefault("sessionStorage", {})[
                f"oidc.user:https://identity.xero.com:{XERO_CLIENT_ID}"
            ] = json.dumps(new_oidc)
        existing["updated_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        existing["updated_by_host"] = os.environ.get("COMPUTERNAME") or (os.uname().nodename if hasattr(os, "uname") else "unknown")
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def ensure_valid_token(self, force_refresh: bool = False) -> str:
        now_ts = int(time.time())
        if not force_refresh and self.access_token and self.expires_at > now_ts + 90:
            return self.access_token
        return self.refresh_oidc_token_headless()

    def refresh_oidc_token_headless(self) -> str:
        code_verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        state = secrets.token_hex(16)

        authorize_url = (
            "https://login.xero.com/identity/connect/authorize?"
            + urllib.parse.urlencode({
                "client_id": XERO_CLIENT_ID,
                "redirect_uri": "https://go.xero.com/oidc/silent.html",
                "response_type": "code",
                "scope": XERO_SCOPE,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "none",
                "response_mode": "query",
            })
        )
        r1 = self.session.get(
            authorize_url,
            headers={"User-Agent": USER_AGENT, "Referer": "https://go.xero.com/"},
            allow_redirects=False,
            timeout=15,
        )
        loc = r1.headers.get("Location", "")
        hops = 0
        while r1.status_code in (301, 302, 303, 307, 308) and "oidc/silent.html" not in loc and hops < 8:
            hops += 1
            r1 = self.session.get(
                loc,
                headers={"User-Agent": USER_AGENT, "Referer": "https://go.xero.com/"},
                allow_redirects=False,
                timeout=15,
            )
            loc = r1.headers.get("Location", "")

        parsed = urllib.parse.urlparse(loc)
        qs = urllib.parse.parse_qs(parsed.query)
        if "error" in qs:
            err = qs["error"][0]
            raise RuntimeError(
                f"Xero silent OIDC refresh returned '{err}'. Session cookie expired; click 'Re-Authenticate Xero' to log in."
            )
        code = qs.get("code", [None])[0]
        if not code:
            raise RuntimeError(
                f"Could not obtain authorization code from Xero silent refresh (status={r1.status_code}). Click 'Re-Authenticate Xero'."
            )

        r_tok = self.session.post(
            "https://identity.xero.com/connect/token",
            data={
                "client_id": XERO_CLIENT_ID,
                "code": code,
                "redirect_uri": "https://go.xero.com/oidc/silent.html",
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
            },
            headers={
                "User-Agent": USER_AGENT,
                "Origin": "https://go.xero.com",
                "Referer": "https://go.xero.com/",
            },
            timeout=15,
        )
        if r_tok.status_code != 200:
            raise RuntimeError(f"Xero token exchange failed ({r_tok.status_code}): {r_tok.text[:300]}")
        tok_data = r_tok.json()
        self.access_token = tok_data["access_token"]
        self.expires_at = int(time.time()) + int(tok_data.get("expires_in", 720))
        tok_data["expires_at"] = self.expires_at
        self._save_auth(new_oidc=tok_data)
        return self.access_token

    def _headers(self) -> Dict[str, str]:
        token = self.ensure_valid_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Xero-Tenant-Shortcode": XERO_SHORTCODE,
            "Xero-Tenant-Id": XERO_TENANT_ID,
            "User-Agent": USER_AGENT,
        }

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Any:
        url = f"https://go.xero.com{path}" if path.startswith("/") else path
        r = self.session.request(method, url, params=params, json=json_body, headers=self._headers(), timeout=20)
        if r.status_code == 401:
            self._load_auth()
            self.ensure_valid_token(force_refresh=True)
            r = self.session.request(method, url, params=params, json=json_body, headers=self._headers(), timeout=20)
        if not r.ok:
            raise RuntimeError(f"Xero API {method} {url} failed ({r.status_code}): {r.text[:400]}")
        if r.status_code == 204 or not r.text.strip():
            return {}
        return r.json()

    def get_projects(self, status: str = "INPROGRESS") -> List[Dict[str, Any]]:
        data = self.request(
            "GET",
            "/api/projects/projects",
            params={
                "assigned": "any",
                "includeSummary": "true",
                "itemsPerPage": 100,
                "order": "asc",
                "page": 1,
                "search": "",
                "sort": "contact",
                "status": status,
            },
        )
        return data.get("items", [])

    def get_project_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        data = self.request(
            "GET",
            f"/api/projects/projects/{project_id}/tasks",
            params={"pageSize": 100},
        )
        return data.get("items", [])

    def get_time_entries(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        dt_start = datetime.date.fromisoformat(start_date[:10]) - datetime.timedelta(days=1)
        dt_end = datetime.date.fromisoformat(end_date[:10]) + datetime.timedelta(days=2)
        after_utc = f"{dt_start.isoformat()}T00:00:00Z"
        before_utc = f"{dt_end.isoformat()}T00:00:00Z"

        all_items: List[Dict[str, Any]] = []
        for page_num in range(1, 10):
            data = self.request(
                "GET",
                "/api/projects/time",
                params={
                    "userId": XERO_USER_ID,
                    "dateAfterUtc": after_utc,
                    "dateBeforeUtc": before_utc,
                    "page": page_num,
                    "pageSize": 100,
                },
            )
            items = data.get("items", [])
            all_items.extend(items)
            if len(items) < 100:
                break

        filtered = []
        for it in all_items:
            local_d = xero_utc_to_date(it.get("dateUtc", ""))
            it["_local_date"] = local_d
            if start_date <= local_d <= end_date:
                filtered.append(it)
        return filtered

    def create_time_entry(
        self,
        project_id: str,
        task_id: str,
        date_str: str,
        duration_minutes: int,
        description: str,
    ) -> Dict[str, Any]:
        payload = {
            "taskId": task_id,
            "userId": XERO_USER_ID,
            "duration": int(duration_minutes),
            "startMinutesFromMidnight": None,
            "dateUtc": date_to_xero_utc(date_str),
            "description": description.strip(),
            "timeEntryType": "duration",
        }
        return self.request("POST", f"/api/projects/projects/{project_id}/time", json_body=payload)

    def update_time_entry(
        self,
        project_id: str,
        time_entry_id: str,
        task_id: str,
        date_str: str,
        duration_minutes: int,
        description: str,
    ) -> Dict[str, Any]:
        payload = {
            "projectId": project_id,
            "taskId": task_id,
            "duration": int(duration_minutes),
            "startMinutesFromMidnight": None,
            "dateUtc": date_to_xero_utc(date_str),
            "description": description.strip(),
        }
        return self.request("PUT", f"/api/projects/projects/{project_id}/time/{time_entry_id}", json_body=payload)

    def delete_time_entry(self, project_id: str, time_entry_id: str) -> Dict[str, Any]:
        return self.request("DELETE", f"/api/projects/projects/{project_id}/time/{time_entry_id}")

    def discover_mapping_for_client(self, client_name: str, matter_name: str = "") -> Optional[Dict[str, Any]]:
        projects = self.get_projects("INPROGRESS")
        norm_c = norm_company_name(client_name)
        norm_m = norm_company_name(matter_name)
        if not norm_c and not norm_m:
            return None

        best_proj = None
        for p in projects:
            c_contact = norm_company_name(p.get("contactName", ""))
            c_pname = norm_company_name(p.get("name", ""))
            if norm_c and (norm_c == c_contact or norm_c in c_contact or c_contact in norm_c):
                best_proj = p
                break
            if norm_m and c_contact and (c_contact in norm_m or norm_m in c_pname):
                best_proj = p

        if not best_proj:
            return None

        pid = best_proj["projectId"]
        tasks = self.get_project_tasks(pid)
        if not tasks:
            return None

        def _task_score(t: Dict[str, Any]) -> Tuple[int, float]:
            tname = (t.get("name") or "").lower()
            rtype = (t.get("rateType") or "HOURLY").upper()
            rate_val = flt((t.get("rate") or {}).get("value") if isinstance(t.get("rate"), dict) else t.get("rate"))
            is_hourly = 1 if rtype != "FIXED" and "flat fee" not in tname else 0
            if "cory" in tname or "schneider" in tname:
                prio = 100
            elif "as of feb" in tname or "2026" in tname:
                prio = 90
            elif tname in ("general", "general legal services", "general corporate"):
                prio = 80
            elif "general" in tname:
                prio = 70
            else:
                prio = 50
            return (is_hourly * 1000 + prio, rate_val)

        best_task = sorted(tasks, key=_task_score, reverse=True)[0]
        return {
            "client_label": best_proj.get("contactName") or client_name,
            "projectId": pid,
            "projectName": best_proj.get("name", ""),
            "taskId": best_task["taskId"],
            "taskName": best_task.get("name", ""),
        }


def _update_entry_xero_status_in_dbs(
    paths: Dict[str, Any],
    entry_id: str,
    xero_id: str,
    project_id: str,
    task_id: str,
    status: str,
) -> None:
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_candidates = [paths.get("db_path")]
    local_data_dir = paths.get("local_data_dir")
    local_app_dir = paths.get("local_app_dir")
    if local_data_dir:
        db_candidates.append(pathlib.Path(local_data_dir) / "cspm.db")
    if local_app_dir:
        db_candidates.append(pathlib.Path(local_app_dir) / "data" / "cspm.db")
        db_candidates.append(pathlib.Path(local_app_dir) / "working" / "data" / "cspm.db")

    seen = set()
    for db_p in db_candidates:
        if not db_p:
            continue
        p = pathlib.Path(db_p)
        if not p.is_file():
            continue
        norm_p = os.path.normcase(str(p.resolve()))
        if norm_p in seen:
            continue
        seen.add(norm_p)
        try:
            conn = sqlite3.connect(str(p), timeout=10)
            ensure_xero_schema(conn, paths.get("shared_state_dir"))
            conn.execute(
                """
                UPDATE TimeEntry
                SET xero_time_entry_id = ?, xero_project_id = ?, xero_task_id = ?, xero_sync_status = ?, xero_synced_at = ?
                WHERE time_id = ?
                """,
                (xero_id, project_id, task_id, status, now_utc, entry_id),
            )
            conn.execute(
                """
                UPDATE time_entries
                SET xero_time_entry_id = ?, xero_project_id = ?, xero_task_id = ?, xero_sync_status = ?, xero_synced_at = ?
                WHERE entry_id = ? OR time_id = ?
                """,
                (xero_id, project_id, task_id, status, now_utc, entry_id, entry_id),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass


def sync_single_entry_from_db(entry_id: str, paths: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _SYNC_LOCK:
        paths = paths or resolve_xero_runtime_paths()
        db_path = paths["db_path"]
        shared_state_dir = paths["shared_state_dir"]
        if not db_path or not pathlib.Path(db_path).is_file():
            return {"status": "NO_DB", "entry_id": entry_id}

        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        ensure_xero_schema(conn, shared_state_dir)

        row_obj = conn.execute("SELECT * FROM TimeEntry WHERE time_id = ?", (entry_id,)).fetchone()
        if not row_obj:
            row_obj = conn.execute("SELECT * FROM time_entries WHERE entry_id = ? OR time_id = ?", (entry_id, entry_id)).fetchone()
        if not row_obj:
            conn.close()
            return {"status": "NOT_FOUND", "entry_id": entry_id}

        row = dict(row_obj)
        if str(row.get("entry_status") or "SAVED").upper() in ("RUNNING", "PAUSED"):
            conn.close()
            return {"status": "SKIPPED_ACTIVE_TIMER", "entry_id": entry_id}

        mid = str(row.get("matter_id") or "")
        m_obj = conn.execute("SELECT * FROM Matter WHERE matter_id = ? OR matter_number = ?", (mid, mid)).fetchone()
        matter_row = dict(m_obj) if m_obj else {}

        if not is_lih_entry_or_matter(
            row.get("parent_id", ""),
            mid,
            row.get("matter_name", ""),
            row.get("client_id", ""),
            row.get("client_name", ""),
            matter_row,
        ):
            conn.close()
            return {"status": "SKIPPED_NON_LIH", "entry_id": entry_id}

        hours = flt(row.get("hours"))
        minutes = int(round(hours * 60))
        if minutes <= 0:
            conn.close()
            _update_entry_xero_status_in_dbs(paths, entry_id, "", "", "", "FLAT_FEE")
            return {"status": "FLAT_FEE", "entry_id": entry_id}

        mappings = load_merged_client_mappings(shared_state_dir)
        ccode = resolve_client_code(
            str(row.get("client_id") or matter_row.get("client_id") or ""),
            str(row.get("client_name") or matter_row.get("client_name") or ""),
            str(matter_row.get("matter_number") or mid),
            mappings,
        )

        project_id = str(row.get("xero_project_id") or matter_row.get("xero_project_id") or mappings.get(ccode, {}).get("projectId") or "")
        task_id = str(row.get("xero_task_id") or matter_row.get("xero_task_id") or mappings.get(ccode, {}).get("taskId") or "")

        xero = XeroProjectsClient(shared_state_dir)

        if not (project_id and task_id):
            discovered = xero.discover_mapping_for_client(
                str(row.get("client_name") or matter_row.get("client_name") or ""),
                str(matter_row.get("matter_name") or row.get("matter_name") or ""),
            )
            if discovered:
                project_id = discovered["projectId"]
                task_id = discovered["taskId"]
                save_key = str(row.get("client_id") or matter_row.get("client_id") or ccode)
                save_custom_client_mapping(shared_state_dir, save_key, discovered)
                if matter_row.get("matter_id"):
                    conn.execute(
                        "UPDATE Matter SET xero_project_id = ?, xero_task_id = ? WHERE matter_id = ?",
                        (project_id, task_id, matter_row["matter_id"]),
                    )
                    conn.commit()
            else:
                conn.close()
                _update_entry_xero_status_in_dbs(paths, entry_id, "", "", "", "UNMAPPED_CLIENT")
                return {"status": "UNMAPPED_CLIENT", "entry_id": entry_id, "client_code": ccode}

        conn.close()

        date_str = norm_date(row.get("date"))
        description = str(row.get("description") or "").strip()
        existing_xero_id = str(row.get("xero_time_entry_id") or "").strip()

        day_entries = xero.get_time_entries(date_str, date_str)
        if not existing_xero_id:
            desc_n = norm_desc(description)
            for xe in day_entries:
                if xe.get("projectId") == project_id and (
                    norm_desc(xe.get("description"))[:35] == desc_n[:35]
                    or (int(xe.get("duration") or 0) == minutes and desc_n[:20] in norm_desc(xe.get("description")))
                ):
                    existing_xero_id = str(xe.get("timeEntryId") or "")
                    break

        if existing_xero_id:
            matched_xe = next((xe for xe in day_entries if xe.get("timeEntryId") == existing_xero_id), None)
            if matched_xe and matched_xe.get("status") == "INVOICED":
                _update_entry_xero_status_in_dbs(paths, entry_id, existing_xero_id, project_id, task_id, "SYNCED_INVOICED")
                return {"status": "ALREADY_INVOICED", "entry_id": entry_id, "xero_time_entry_id": existing_xero_id}

            if (
                matched_xe
                and int(matched_xe.get("duration") or 0) == minutes
                and norm_desc(matched_xe.get("description")) == norm_desc(description)
                and matched_xe.get("_local_date") == date_str
            ):
                _update_entry_xero_status_in_dbs(paths, entry_id, existing_xero_id, project_id, task_id, "SYNCED")
                return {"status": "ALREADY_SYNCED", "entry_id": entry_id, "xero_time_entry_id": existing_xero_id}

            try:
                xero.update_time_entry(
                    project_id=project_id,
                    time_entry_id=existing_xero_id,
                    task_id=task_id,
                    date_str=date_str,
                    duration_minutes=minutes,
                    description=description,
                )
                _update_entry_xero_status_in_dbs(paths, entry_id, existing_xero_id, project_id, task_id, "SYNCED")
                return {"status": "UPDATED", "entry_id": entry_id, "xero_time_entry_id": existing_xero_id}
            except Exception:
                pass

        resp = xero.create_time_entry(
            project_id=project_id,
            task_id=task_id,
            date_str=date_str,
            duration_minutes=minutes,
            description=description,
        )
        new_xero_id = str(resp.get("timeEntryId") or "")
        _update_entry_xero_status_in_dbs(paths, entry_id, new_xero_id, project_id, task_id, "SYNCED")
        return {
            "status": "CREATED",
            "entry_id": entry_id,
            "xero_time_entry_id": new_xero_id,
            "project_id": project_id,
            "task_id": task_id,
            "minutes": minutes,
        }


def delete_single_entry_from_xero(
    entry_id: str,
    xero_time_entry_id: Optional[str] = None,
    xero_project_id: Optional[str] = None,
    paths: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with _SYNC_LOCK:
        paths = paths or resolve_xero_runtime_paths()
        db_path = paths["db_path"]
        shared_state_dir = paths["shared_state_dir"]

        if not (xero_time_entry_id and xero_project_id) and db_path and pathlib.Path(db_path).is_file():
            try:
                conn = sqlite3.connect(str(db_path), timeout=5)
                conn.row_factory = sqlite3.Row
                ensure_xero_schema(conn, shared_state_dir)
                r = conn.execute("SELECT xero_time_entry_id, xero_project_id FROM TimeEntry WHERE time_id = ?", (entry_id,)).fetchone()
                if r:
                    xero_time_entry_id = xero_time_entry_id or r["xero_time_entry_id"]
                    xero_project_id = xero_project_id or r["xero_project_id"]
                conn.close()
            except Exception:
                pass

        if not xero_time_entry_id or not xero_project_id:
            return {"status": "NO_XERO_ID", "entry_id": entry_id}

        try:
            xero = XeroProjectsClient(shared_state_dir)
            xero.delete_time_entry(xero_project_id, xero_time_entry_id)
            return {"status": "DELETED_IN_XERO", "entry_id": entry_id, "xero_time_entry_id": xero_time_entry_id}
        except Exception as e:
            return {"status": "DELETE_FAILED", "entry_id": entry_id, "error": str(e)}


def trigger_async_xero_sync_entry(entry_id: str, app_paths: Any = None) -> None:
    """Non-blocking background thread trigger to sync a single docket entry to Xero Projects."""
    clean_id = str(entry_id or "").strip()
    if not clean_id or clean_id.lower().startswith("draft:"):
        return

    def _worker() -> None:
        try:
            paths = resolve_xero_runtime_paths(app_paths)
            res = sync_single_entry_from_db(clean_id, paths=paths)
            if res.get("status") in ("CREATED", "UPDATED"):
                logger.info("[xero_sync] %s LIH docket %s -> Xero %s", res.get("status"), clean_id, res.get("xero_time_entry_id"))
        except Exception as exc:
            logger.debug("[xero_sync] Background sync warning for %s: %s", clean_id, exc)

    threading.Thread(target=_worker, name=f"XeroAutoSync-{clean_id}", daemon=True).start()


def trigger_async_xero_delete_entry(
    entry_id: str,
    xero_time_entry_id: Optional[str] = None,
    xero_project_id: Optional[str] = None,
    app_paths: Any = None,
) -> None:
    """Non-blocking background thread trigger to delete an unbilled LIH docket entry from Xero Projects."""
    clean_id = str(entry_id or "").strip()
    if not clean_id or clean_id.lower().startswith("draft:"):
        return

    def _worker() -> None:
        try:
            paths = resolve_xero_runtime_paths(app_paths)
            delete_single_entry_from_xero(
                clean_id,
                xero_time_entry_id=xero_time_entry_id,
                xero_project_id=xero_project_id,
                paths=paths,
            )
        except Exception as exc:
            logger.debug("[xero_sync] Background delete warning for %s: %s", clean_id, exc)

    threading.Thread(target=_worker, name=f"XeroAutoDelete-{clean_id}", daemon=True).start()


def read_sheet(wb: openpyxl.Workbook, name: str) -> List[Dict[str, Any]]:
    if name not in wb.sheetnames:
        return []
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    out = []
    for idx, r in enumerate(rows[1:], start=2):
        if any(x is not None and str(x).strip() != "" for x in r):
            d = dict(zip(headers, r))
            d["_row"] = idx
            out.append(d)
    return out


def load_local_lih_data(paths: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
    mappings = load_merged_client_mappings(paths["shared_state_dir"])
    conn = sqlite3.connect(str(paths["db_path"]), timeout=10)
    conn.row_factory = sqlite3.Row
    ensure_xero_schema(conn, paths["shared_state_dir"])

    matters_all = [dict(r) for r in conn.execute("SELECT * FROM Matter").fetchall()]
    matter_by_id = {str(m["matter_id"]): m for m in matters_all}
    matter_by_num = {str(m["matter_number"]): m for m in matters_all if m.get("matter_number")}

    lih_matter_ids = set()
    lih_matter_nums = set()
    for m in matters_all:
        if is_lih_entry_or_matter(
            m.get("parent_id", ""),
            m.get("matter_id", ""),
            m.get("matter_number", ""),
            m.get("client_id", ""),
            m.get("client_name", ""),
            m,
        ):
            lih_matter_ids.add(str(m["matter_id"]))
            if m.get("matter_number"):
                lih_matter_nums.add(str(m["matter_number"]))

    db_rows_raw = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM TimeEntry WHERE date >= ? AND date <= ? ORDER BY date ASC, created_at ASC",
            (start_date, end_date),
        ).fetchall()
    ]
    conn.close()

    db_lih = []
    for r in db_rows_raw:
        mid = str(r.get("matter_id") or "")
        pid = str(r.get("parent_id") or "").upper()
        m_info = matter_by_id.get(mid) or matter_by_num.get(mid) or {}
        if pid == "LIHD" or mid in lih_matter_ids or mid in lih_matter_nums or is_lih_entry_or_matter(pid, mid, r.get("matter_name", ""), r.get("client_id", ""), r.get("client_name", ""), m_info):
            ccode = resolve_client_code(
                str(r.get("client_id") or m_info.get("client_id") or ""),
                str(r.get("client_name") or m_info.get("client_name") or ""),
                mid,
                mappings,
            )
            r["_client_code"] = ccode
            r["_matter_number"] = m_info.get("matter_number") or mid
            r["_minutes"] = int(round(flt(r.get("hours")) * 60))
            db_lih.append(r)

    cspm_xl_lih = []
    if paths.get("cspm_xlsm_path") and pathlib.Path(paths["cspm_xlsm_path"]).is_file():
        wb_cspm = openpyxl.load_workbook(paths["cspm_xlsm_path"], data_only=True, read_only=True)
        xl_cspm_all = read_sheet(wb_cspm, "TimeEntries")
        wb_cspm.close()
        for r in xl_cspm_all:
            d_str = norm_date(r.get("Date"))
            if not (start_date <= d_str <= end_date):
                continue
            mid = str(r.get("MatterID") or "")
            pid = str(r.get("ParentID") or "").upper()
            m_info = matter_by_id.get(mid) or matter_by_num.get(mid) or {}
            if pid == "LIHD" or mid in lih_matter_ids or mid in lih_matter_nums:
                ccode = resolve_client_code(
                    str(r.get("ClientID") or m_info.get("client_id") or ""),
                    str(m_info.get("client_name") or ""),
                    mid,
                    mappings,
                )
                r["_date"] = d_str
                r["_client_code"] = ccode
                r["_hours"] = flt(r.get("Hours"))
                r["_minutes"] = int(round(flt(r.get("Hours")) * 60))
                cspm_xl_lih.append(r)

    dock_lih = []
    if paths.get("primary_dockets_xlsm_path") and pathlib.Path(paths["primary_dockets_xlsm_path"]).is_file():
        wb_dock = openpyxl.load_workbook(paths["primary_dockets_xlsm_path"], data_only=True, read_only=True)
        dock_all = read_sheet(wb_dock, "Dockets")
        wb_dock.close()
        for r in dock_all:
            d_str = norm_date(r.get("Date"))
            if not (start_date <= d_str <= end_date):
                continue
            mid = str(r.get("Matter_ID") or "")
            client = str(r.get("Client") or "")
            sub2 = str(r.get("Sub-Client2") or "")
            pct = flt(r.get("Percentage"))
            ccode = resolve_client_code("", client, mid, mappings)
            is_lih = (
                mid in lih_matter_nums
                or mid in lih_matter_ids
                or "LIHD" in mid.upper()
                or "lih" in client.lower()
                or "lih" in sub2.lower()
                or (0 < pct < 1.0)
                or ccode in mappings
            )
            if is_lih:
                raw_hrs = r.get("Time (in hrs)")
                is_flat = isinstance(raw_hrs, str) and "flat" in raw_hrs.lower()
                hrs = 0.0 if is_flat else flt(raw_hrs)
                r["_date"] = d_str
                r["_client_code"] = ccode
                r["_hours"] = hrs
                r["_minutes"] = int(round(hrs * 60))
                r["_is_flat_fee"] = is_flat
                dock_lih.append(r)

    return {
        "db_lih": db_lih,
        "cspm_xl_lih": cspm_xl_lih,
        "dock_lih": dock_lih,
        "matter_by_id": matter_by_id,
        "matter_by_num": matter_by_num,
        "mappings": mappings,
    }


def get_reconciliation_data(
    start_date: str,
    end_date: str,
    period_label: str = "",
    do_sync: bool = False,
    update_mismatches: bool = False,
    include_clients: Optional[List[str]] = None,
    exclude_clients: Optional[List[str]] = None,
    report_out: Optional[pathlib.Path] = None,
    app_paths: Any = None,
) -> Dict[str, Any]:
    paths = resolve_xero_runtime_paths(app_paths)
    if not period_label:
        period_label = f"{start_date} to {end_date}"
    xero = XeroProjectsClient(paths["shared_state_dir"])

    xero_entries = xero.get_time_entries(start_date, end_date)
    local_data = load_local_lih_data(paths, start_date, end_date)

    db_lih = local_data["db_lih"]
    cspm_xl_lih = local_data["cspm_xl_lih"]
    dock_lih = local_data["dock_lih"]
    mappings = local_data["mappings"]

    proj_to_client_code = {v["projectId"]: k for k, v in mappings.items() if v.get("projectId")}
    for xe in xero_entries:
        xe["_client_code"] = proj_to_client_code.get(xe.get("projectId", ""), xe.get("contactName", "UNKNOWN"))

    if include_clients:
        inc = {c.upper() for c in include_clients}
        db_lih = [r for r in db_lih if r["_client_code"].upper() in inc]
        cspm_xl_lih = [r for r in cspm_xl_lih if r["_client_code"].upper() in inc]
        dock_lih = [r for r in dock_lih if r["_client_code"].upper() in inc]
        xero_entries = [r for r in xero_entries if r["_client_code"].upper() in inc]

    if exclude_clients:
        exc = {c.upper() for c in exclude_clients}
        db_lih = [r for r in db_lih if r["_client_code"].upper() not in exc]
        cspm_xl_lih = [r for r in cspm_xl_lih if r["_client_code"].upper() not in exc]
        dock_lih = [r for r in dock_lih if r["_client_code"].upper() not in exc]
        xero_entries = [r for r in xero_entries if r["_client_code"].upper() not in exc]

    unmatched_xero = list(xero_entries)
    matched_pairs: List[Tuple[Dict[str, Any], Dict[str, Any], str]] = []
    missing_in_xero: List[Dict[str, Any]] = []
    flat_fee_entries: List[Dict[str, Any]] = []

    for db_row in db_lih:
        if db_row["_minutes"] == 0:
            flat_fee_entries.append(db_row)
            continue
        c_code = db_row["_client_code"]
        d_str = norm_date(db_row.get("date"))
        mins = db_row["_minutes"]
        desc_n = norm_desc(db_row.get("description"))
        existing_xid = str(db_row.get("xero_time_entry_id") or "").strip()

        if existing_xid:
            cand0 = next((xe for xe in unmatched_xero if xe.get("timeEntryId") == existing_xid), None)
            if cand0:
                unmatched_xero.remove(cand0)
                st0 = "EXACT" if int(cand0.get("duration") or 0) == mins and norm_desc(cand0.get("description"))[:35] == desc_n[:35] else (
                    "DURATION_MISMATCH" if int(cand0.get("duration") or 0) != mins else "DESC_DIFF"
                )
                matched_pairs.append((db_row, cand0, st0))
                continue

        cand = next(
            (
                xe for xe in unmatched_xero
                if xe["_client_code"] == c_code
                and xe["_local_date"] == d_str
                and int(xe.get("duration") or 0) == mins
                and (norm_desc(xe.get("description"))[:35] == desc_n[:35] or desc_n[:25] in norm_desc(xe.get("description")))
            ),
            None,
        )
        if cand:
            unmatched_xero.remove(cand)
            matched_pairs.append((db_row, cand, "EXACT"))
            if not existing_xid:
                _update_entry_xero_status_in_dbs(
                    paths,
                    str(db_row.get("time_id") or ""),
                    str(cand.get("timeEntryId") or ""),
                    str(cand.get("projectId") or ""),
                    str(cand.get("taskId") or ""),
                    "SYNCED",
                )
            continue

        cand2 = next(
            (
                xe for xe in unmatched_xero
                if xe["_client_code"] == c_code
                and xe["_local_date"] == d_str
                and int(xe.get("duration") or 0) == mins
            ),
            None,
        )
        if cand2:
            unmatched_xero.remove(cand2)
            matched_pairs.append((db_row, cand2, "DESC_DIFF"))
            continue

        cand3 = next(
            (
                xe for xe in unmatched_xero
                if xe["_client_code"] == c_code
                and xe["_local_date"] == d_str
                and norm_desc(xe.get("description"))[:30] == desc_n[:30]
            ),
            None,
        )
        if cand3:
            unmatched_xero.remove(cand3)
            matched_pairs.append((db_row, cand3, "DURATION_MISMATCH"))
            continue

        missing_in_xero.append(db_row)

    synced_count = 0
    updated_count = 0
    if do_sync and (missing_in_xero or (update_mismatches and any(st != "EXACT" for _, _, st in matched_pairs))):
        for db_row in missing_in_xero:
            tid = str(db_row.get("time_id") or "")
            res = sync_single_entry_from_db(tid, paths=paths)
            if res.get("status") in ("CREATED", "UPDATED", "ALREADY_SYNCED"):
                synced_count += 1

        if update_mismatches:
            for db_row, xe, st in matched_pairs:
                if st in ("DURATION_MISMATCH", "DESC_DIFF"):
                    d_str = norm_date(db_row.get("date"))
                    mins = db_row["_minutes"]
                    desc = str(db_row.get("description") or "").strip()
                    xero.update_time_entry(
                        project_id=xe["projectId"],
                        time_entry_id=xe["timeEntryId"],
                        task_id=xe["taskId"],
                        date_str=d_str,
                        duration_minutes=mins,
                        description=desc,
                    )
                    _update_entry_xero_status_in_dbs(
                        paths,
                        str(db_row.get("time_id") or ""),
                        str(xe.get("timeEntryId") or ""),
                        str(xe.get("projectId") or ""),
                        str(xe.get("taskId") or ""),
                        "SYNCED",
                    )
                    updated_count += 1

        res_after = get_reconciliation_data(
            start_date=start_date,
            end_date=end_date,
            period_label=f"{period_label} [POST-SYNC VERIFIED]",
            do_sync=False,
            include_clients=include_clients,
            exclude_clients=exclude_clients,
            report_out=report_out,
            app_paths=app_paths,
        )
        res_after["synced_count"] = synced_count
        res_after["updated_count"] = updated_count
        return res_after

    all_client_codes = sorted(
        set(r["_client_code"] for r in db_lih)
        | set(r["_client_code"] for r in cspm_xl_lih)
        | set(r["_client_code"] for r in dock_lih)
        | set(r["_client_code"] for r in xero_entries)
    )

    lines: List[str] = []
    def out(s: str = "") -> None:
        lines.append(s)

    out("=" * 108)
    out(f"LAWYERS IN-HOUSE (LIH) 4-WAY XERO RECONCILIATION REPORT - {period_label} ({start_date} to {end_date})")
    out("=" * 108)
    out(f"Xero Org / Tenant : LawyersInHouse.com (Shortcode: {XERO_SHORTCODE} | Tenant: {XERO_TENANT_ID})")
    out(f"Xero User         : Cory Schneider ({XERO_USER_ID})")
    out("-" * 108)
    out(f"{'Client':34s} | {'cspm.db':10s} | {'CSPM.xlsm':10s} | {'Dockets.xl':10s} | {'Xero Proj':12s} | {'Diff (DB-Xero)':14s} | {'Status'}")
    out("-" * 108)

    tot_db_min = 0
    tot_xl_min = 0
    tot_dk_min = 0
    tot_xe_min = 0
    client_rollup: List[Dict[str, Any]] = []

    for ccode in all_client_codes:
        mp = mappings.get(ccode, {})
        label = mp.get("client_label", ccode)[:34]
        c_db = [r for r in db_lih if r["_client_code"] == ccode]
        c_xl = [r for r in cspm_xl_lih if r["_client_code"] == ccode]
        c_dk = [r for r in dock_lih if r["_client_code"] == ccode]
        c_xe = [r for r in xero_entries if r["_client_code"] == ccode]

        db_m = sum(r["_minutes"] for r in c_db)
        xl_m = sum(r["_minutes"] for r in c_xl)
        dk_m = sum(r["_minutes"] for r in c_dk)
        xe_m = sum(int(r.get("duration") or 0) for r in c_xe)

        tot_db_min += db_m
        tot_xl_min += xl_m
        tot_dk_min += dk_m
        tot_xe_min += xe_m

        diff_m = db_m - xe_m
        if db_m == xl_m == dk_m == xe_m:
            st = "OK (4-WAY MATCH)" if db_m > 0 else "OK (FLAT FEE / 0h)"
        elif diff_m > 0:
            st = f"MISSING IN XERO ({diff_m/60:+.2f}h)"
        elif diff_m < 0:
            st = f"EXTRA IN XERO ({diff_m/60:+.2f}h)"
        else:
            st = "LOCAL REPLICA DRIFT"

        client_rollup.append({
            "client_code": ccode,
            "client_label": mp.get("client_label", ccode),
            "project_name": mp.get("projectName", ""),
            "task_name": mp.get("taskName", ""),
            "db_hours": round(db_m / 60.0, 2),
            "db_count": len(c_db),
            "cspm_xl_hours": round(xl_m / 60.0, 2),
            "cspm_xl_count": len(c_xl),
            "dockets_xl_hours": round(dk_m / 60.0, 2),
            "dockets_xl_count": len(c_dk),
            "xero_hours": round(xe_m / 60.0, 2),
            "xero_count": len(c_xe),
            "diff_hours": round(diff_m / 60.0, 2),
            "diff_minutes": diff_m,
            "status": st,
        })

        out(
            f"{label:34s} | {db_m/60:6.2f}h ({len(c_db):2d}) | {xl_m/60:6.2f}h ({len(c_xl):2d}) | "
            f"{dk_m/60:6.2f}h ({len(c_dk):2d}) | {xe_m/60:6.2f}h ({len(c_xe):2d})   | "
            f"{diff_m/60:+6.2f}h ({diff_m:+4d}m) | {st}"
        )

    out("-" * 108)
    tot_diff_m = tot_db_min - tot_xe_min
    is_reconciled = (tot_diff_m == 0 and not missing_in_xero and not unmatched_xero and tot_db_min == tot_xl_min == tot_dk_min)
    out(
        f"{'TOTAL':34s} | {tot_db_min/60:6.2f}h ({len(db_lih):2d}) | {tot_xl_min/60:6.2f}h ({len(cspm_xl_lih):2d}) | "
        f"{tot_dk_min/60:6.2f}h ({len(dock_lih):2d}) | {tot_xe_min/60:6.2f}h ({len(xero_entries):2d})   | "
        f"{tot_diff_m/60:+6.2f}h ({tot_diff_m:+4d}m) | {'100% RECONCILED' if is_reconciled else 'ACTION NEEDED'}"
    )
    out("=" * 108)

    out(f"\n1. MATCHED IN BOTH CSPM & XERO ({len(matched_pairs)} entries)")
    matched_list: List[Dict[str, Any]] = []
    for db_row, xe, st in matched_pairs:
        label = mappings.get(db_row["_client_code"], {}).get("client_label", db_row["_client_code"])
        d_str = norm_date(db_row.get("date"))
        mins = db_row["_minutes"]
        x_mins = int(xe.get("duration") or 0)
        x_status = str(xe.get("status") or "")
        tag = "[OK]" if st == "EXACT" else f"[{st}]"
        out(f"  {tag:18s} {d_str} | {label[:28]:28s} | CSPM={mins/60:.2f}h ({mins:3d}m) vs Xero={x_mins/60:.2f}h ({x_mins:3d}m) [{x_status:8s}] | {str(db_row.get('description') or '')[:50]}")
        matched_list.append({
            "time_id": str(db_row.get("time_id") or ""),
            "xero_id": str(xe.get("timeEntryId") or ""),
            "date": d_str,
            "client_label": label,
            "db_hours": round(mins / 60.0, 2),
            "xero_hours": round(x_mins / 60.0, 2),
            "xero_status": x_status,
            "match_type": st,
            "share_pct": flt(db_row.get("share_pct")),
            "description": str(db_row.get("description") or ""),
        })

    out(f"\n2. LOGGED IN CSPM/DOCKETS BUT MISSING IN XERO ({len(missing_in_xero)} entries)")
    if not missing_in_xero:
        out("  [None - 0 missing entries in Xero]")
    missing_list: List[Dict[str, Any]] = []
    for db_row in missing_in_xero:
        ccode = db_row["_client_code"]
        mp = mappings.get(ccode, {})
        label = mp.get("client_label", ccode)
        task_label = mp.get("taskName", "Auto-Discover on Sync")
        d_str = norm_date(db_row.get("date"))
        mins = db_row["_minutes"]
        pct = flt(db_row.get("share_pct"))
        out(
            f"  [MISSING_IN_XERO]  {d_str} | {label[:28]:28s} | {mins/60:5.2f}h ({mins:3d}m) | Split={pct:5.1f}% | Target Task: {task_label[:24]:24s} | {str(db_row.get('description') or '')[:48]}"
        )
        missing_list.append({
            "time_id": str(db_row.get("time_id") or ""),
            "date": d_str,
            "client_label": label,
            "hours": round(mins / 60.0, 2),
            "minutes": mins,
            "share_pct": pct,
            "target_task": task_label,
            "description": str(db_row.get("description") or ""),
        })

    out(f"\n3. LOGGED IN XERO ONLY / UNMATCHED IN CSPM ({len(unmatched_xero)} entries)")
    if not unmatched_xero:
        out("  [None - 0 orphaned entries in Xero]")
    xero_only_list: List[Dict[str, Any]] = []
    for xe in unmatched_xero:
        d_str = xe["_local_date"]
        x_mins = int(xe.get("duration") or 0)
        cname = str(xe.get("contactName") or "")
        out(
            f"  [XERO_ONLY]        {d_str} | {cname[:28]:28s} | {x_mins/60:5.2f}h ({x_mins:3d}m) | Status={xe.get('status')} | {str(xe.get('description') or '')[:55]}"
        )
        xero_only_list.append({
            "xero_id": str(xe.get("timeEntryId") or ""),
            "date": d_str,
            "client_label": cname,
            "xero_hours": round(x_mins / 60.0, 2),
            "xero_status": str(xe.get("status") or ""),
            "description": str(xe.get("description") or ""),
        })

    warnings: List[str] = []
    for db_row in flat_fee_entries:
        label = mappings.get(db_row["_client_code"], {}).get("client_label", db_row["_client_code"])
        warnings.append(
            f"  [FLAT_FEE_INFO]    {norm_date(db_row.get('date'))} | {label} ({db_row['_matter_number']}): 0.00h Flat Fee row in CSPM/Dockets (${flt(db_row.get('rate')):.2f} @ {flt(db_row.get('share_pct')):.0f}%). Xero Project uses Fixed Price task (not hourly time entry)."
        )
    for db_row in db_lih:
        pct = flt(db_row.get("share_pct"))
        ccode = db_row["_client_code"]
        expected_pct = float(mappings.get(ccode, {}).get("expected_share_pct", 70.0))
        if db_row["_minutes"] > 0 and abs(pct - expected_pct) > 0.01:
            label = mappings.get(ccode, {}).get("client_label", ccode)
            warnings.append(
                f"  [SHARE_PCT_CHECK]  {norm_date(db_row.get('date'))} | {label} ({db_row['_matter_number']}) | {db_row['_minutes']/60:.2f}h: Logged with share_pct={pct:.1f}% (expected {expected_pct:.1f}%) in cspm.db/Dockets.xlsm."
            )

    out(f"\n4. BILLING & SPLIT AUDIT NOTES ({len(warnings)} items)")
    if not warnings:
        out("  [None]")
    for w in warnings:
        out(w)

    report_text = "\n".join(lines)
    if report_out:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        md_content = f"# LIH Xero Reconciliation Report - {period_label} ({start_date} to {end_date})\n\n```text\n" + report_text + "\n```\n"
        report_out.write_text(md_content, encoding="utf-8")

    return {
        "ok": True,
        "period_label": period_label,
        "start_date": start_date,
        "end_date": end_date,
        "is_reconciled": is_reconciled,
        "synced_count": synced_count,
        "updated_count": updated_count,
        "totals": {
            "db_hours": round(tot_db_min / 60.0, 2),
            "db_count": len(db_lih),
            "cspm_xl_hours": round(tot_xl_min / 60.0, 2),
            "cspm_xl_count": len(cspm_xl_lih),
            "dockets_xl_hours": round(tot_dk_min / 60.0, 2),
            "dockets_xl_count": len(dock_lih),
            "xero_hours": round(tot_xe_min / 60.0, 2),
            "xero_count": len(xero_entries),
            "diff_hours": round(tot_diff_m / 60.0, 2),
            "diff_minutes": tot_diff_m,
        },
        "client_rollup": client_rollup,
        "matched_entries": matched_list,
        "missing_in_xero": missing_list,
        "xero_only": xero_only_list,
        "warnings": [w.strip() for w in warnings],
        "report_text": report_text,
        "saved_report_path": str(report_out) if report_out else "",
    }
