"""Headless background supervisor for the CSPM Quick Expense server (LAN + Tailscale only, zero third-party relays)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PYTHON = REPO_ROOT / "src" / "python"
if str(SRC_PYTHON) not in sys.path:
    sys.path.insert(0, str(SRC_PYTHON))

LOG_DIR = REPO_ROOT / "logs"
SERVER_LOG = LOG_DIR / "quick_expense_server.log"
CRASH_LOG = LOG_DIR / "supervisor_crash.log"
PID_FILE = LOG_DIR / "quick_expense_supervisor.pid"
TAILSCALE_INFO_FILE = LOG_DIR / "tailscale_info.json"
TAILSCALE_EXE = Path(r"C:\Program Files\Tailscale\tailscale.exe")


def _configure_tailscale_if_ready(configured_flag: list[bool]) -> None:
    if not TAILSCALE_EXE.exists():
        return
    try:
        out = subprocess.check_output(
            [str(TAILSCALE_EXE), "status", "--json"],
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=5,
        )
        data = json.loads(out)
        state = data.get("BackendState")
        ips = data.get("TailscaleIPs") or []
        dns_name = (data.get("Self") or {}).get("DNSName", "").rstrip(".")
        if state == "Running" and ips:
            if not configured_flag[0]:
                # Enable unattended mode and configure tailscale serve on port 80/443 -> 127.0.0.1:24820
                subprocess.run(
                    [str(TAILSCALE_EXE), "set", "--unattended"],
                    creationflags=CREATE_NO_WINDOW,
                    timeout=5,
                )
                subprocess.run(
                    [str(TAILSCALE_EXE), "funnel", "--bg", "24820"],
                    creationflags=CREATE_NO_WINDOW,
                    timeout=8,
                )
                subprocess.run(
                    [str(TAILSCALE_EXE), "serve", "--bg", "--tcp", "80", "tcp://127.0.0.1:24820"],
                    creationflags=CREATE_NO_WINDOW,
                    timeout=8,
                )
                configured_flag[0] = True
            TAILSCALE_INFO_FILE.write_text(
                json.dumps(
                    {
                        "state": state,
                        "ips": ips,
                        "dnsName": dns_name,
                        "httpUrl": f"http://{ips[0]}",
                        "httpsUrl": f"https://{dns_name}" if dns_name else "",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    except Exception:
        pass


def main() -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        server_log_fh = open(SERVER_LOG, "w", encoding="utf-8", buffering=1)
        sys.stdout = server_log_fh
        sys.stderr = server_log_fh

        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

        from quick_expense_server import QuickExpenseServerDaemon, is_port_listening
        from services.quick_expense_service import QuickExpenseService

        service = QuickExpenseService()
        daemon = QuickExpenseServerDaemon(service=service, port=24820)
        info = daemon.ensure_running()
        print(f"Quick Expense server listening on {info['localUrl']} and {info['lanUrl']}")
        threading.Thread(target=lambda: service.get_bootstrap_data("deborah"), daemon=True).start()

        ts_configured = [False]
        while True:
            if not is_port_listening(24820):
                try:
                    daemon.ensure_running()
                except Exception:
                    pass
            _configure_tailscale_if_ready(ts_configured)
            time.sleep(4)
    except BaseException:
        with open(CRASH_LOG, "a", encoding="utf-8") as fh:
            fh.write("=== SUPERVISOR CRASH ===\n")
            fh.write(traceback.format_exc() + "\n")


if __name__ == "__main__":
    main()
