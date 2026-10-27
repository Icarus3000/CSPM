#!/usr/bin/env python3
"""1-Command Workstation Failover & Disaster Recovery Installer for CSPM & Quick Expense Mini-App.

If OFFICENEW ever breaks or is offline, run this script on OMNIBOOK (or any replacement
Windows computer signed into OneDrive - LPN, Git, and Tailscale):

    python scripts/setup_workstation_failover.py --activate

What this script does automatically (100% Headless per Global Rule 12):
1. Verifies that OneDrive - LPN has synced all live CSPM data:
   - `OneDrive - LPN/CSPM_Shared_Data/cspm.db`
   - `OneDrive - LPN/CSPM_Shared_Data/CSPM.xlsm`
   - `OneDrive - LPN/CSPM_Shared_Data/QuickExpense_Sync/inbox.json`
   - `OneDrive - LPN/CSPM_Shared_Data/Receipts/`
   - `OneDrive - LPN/__Invoices (1)/Dockets.xlsm`
2. Locates the machine's `pythonw.exe` (windowless GUI subsystem — zero console flashes).
3. Creates the headless Windows Startup launcher (`Start_CSPM_Quick_Expense_Server.vbs`)
   and registers the headless Scheduled Task (`CSPM_QuickExpense_Server_Watchdog`).
4. Starts the Quick Expense Server on port 24820 in the background (`CREATE_NO_WINDOW`).
5. Enables `tailscale serve --bg 24820` so Cory and Deborah's phones/Chromebooks can
   immediately connect to this computer over HTTPS.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
REPO_ROOT = Path(__file__).resolve().parents[1]
PORT = 24820


def _find_onedrive_root() -> Path:
    candidates = [
        Path.home() / "OneDrive - LPN",
        Path("C:/Users/cschn/OneDrive - LPN"),
    ]
    env_od = os.environ.get("OneDriveCommercial") or os.environ.get("OneDrive")
    if env_od:
        candidates.insert(0, Path(env_od))
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _find_pythonw() -> Path:
    exe = Path(sys.executable)
    pw = exe.with_name("pythonw.exe")
    if pw.exists():
        return pw
    for venv_dir in sorted(REPO_ROOT.glob(".venv*")):
        cand = venv_dir / "Scripts" / "pythonw.exe"
        if cand.exists():
            return cand
    return exe


def _is_port_listening(port: int = PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def verify_onedrive_data() -> dict:
    od_root = _find_onedrive_root()
    shared_dir = od_root / "CSPM_Shared_Data"
    inv_dir = od_root / "__Invoices (1)"
    checks = {
        "onedrive_root": str(od_root),
        "cspm_db": (shared_dir / "cspm.db").exists(),
        "cspm_xlsm": (shared_dir / "CSPM.xlsm").exists(),
        "quick_expense_inbox": (shared_dir / "QuickExpense_Sync" / "inbox.json").exists(),
        "receipts_dir": (shared_dir / "Receipts").exists(),
        "legacy_dockets_xlsm": (inv_dir / "Dockets.xlsm").exists(),
    }
    return checks


def install_headless_startup_and_watchdog() -> dict:
    pythonw = _find_pythonw()
    watchdog_py = REPO_ROOT / "scripts" / "ensure_quick_expense_server.py"
    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    vbs_path = startup_dir / "Start_CSPM_Quick_Expense_Server.vbs"

    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.Run """{pythonw}"" ""{watchdog_py}""", 0, False\n'
    )
    if startup_dir.exists():
        vbs_path.write_text(vbs_content, encoding="utf-8")

    # Register Windows Scheduled Task using wscript.exe (0 console flash)
    task_name = "CSPM_QuickExpense_Server_Watchdog"
    if vbs_path.exists():
        subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                task_name,
                "/TR",
                f'wscript.exe //B //NoLogo "{vbs_path}"',
                "/SC",
                "MINUTE",
                "/MO",
                "5",
                "/F",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )

    # Launch server now if not already listening
    if not _is_port_listening(PORT):
        subprocess.Popen(
            [str(pythonw), str(watchdog_py)],
            cwd=str(REPO_ROOT),
            creationflags=CREATE_NO_WINDOW,
            close_fds=True,
        )
        time.sleep(1.8)

    return {
        "pythonw": str(pythonw),
        "startup_vbs": str(vbs_path),
        "scheduled_task": task_name,
        "port_listening": _is_port_listening(PORT),
    }


def configure_tailscale_https() -> dict:
    ts_candidates = [
        Path("C:/Program Files/Tailscale/tailscale.exe"),
        Path("tailscale"),
    ]
    ts_exe = next((str(p) for p in ts_candidates if p.exists()), "tailscale")
    hostname_url = ""
    try:
        res_status = subprocess.run(
            [ts_exe, "status", "--json"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=6,
            check=False,
        )
        if res_status.returncode == 0 and res_status.stdout:
            data = json.loads(res_status.stdout)
            dns_name = ((data.get("Self") or {}).get("DNSName") or "").rstrip(".")
            if dns_name:
                hostname_url = f"https://{dns_name}"
        subprocess.run(
            [ts_exe, "serve", "--bg", str(PORT)],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
    except Exception:
        pass
    return {
        "tailscale_https_url": hostname_url or f"http://{socket.gethostname().lower()}:{PORT}",
        "local_url": f"http://localhost:{PORT}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CSPM Workstation Failover & Recovery Utility")
    parser.add_argument("--activate", action="store_true", help="Activate this workstation as the live Quick Expense & CSPM server")
    parser.add_argument("--check-only", action="store_true", help="Only verify OneDrive data sync status without starting services")
    args = parser.parse_args()

    report = {
        "workstation": socket.gethostname(),
        "data_verification": verify_onedrive_data(),
    }
    if args.activate or not args.check_only:
        report["service_setup"] = install_headless_startup_and_watchdog()
        report["network_urls"] = configure_tailscale_https()

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
