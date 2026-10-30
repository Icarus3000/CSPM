"""Headless background supervisor for the CSPM Quick Expense server (LAN + Tailscale + Auto-Git-Pull & Hot-Reload)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
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

WATCHED_BACKEND_FILES = [
    Path(__file__).resolve(),
    SRC_PYTHON / "quick_expense_server.py",
    SRC_PYTHON / "services" / "quick_expense_service.py",
    SRC_PYTHON / "services" / "quick_expense_display.py",
]


def _backend_sig() -> tuple:
    out = []
    for p in WATCHED_BACKEND_FILES:
        try:
            st = p.stat()
            out.append((str(p), st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((str(p), 0, 0))
    return tuple(out)


def _auto_git_pull_if_updated() -> bool:
    """Silently check origin/main every 45s; if a new commit was pushed, pull with --autostash."""
    if not (REPO_ROOT / ".git").exists():
        return False
    try:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "fetch", "origin", "main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=15,
        )
        head = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=5,
        ).strip()
        remote = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "origin/main"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=5,
        ).strip()
        if head and remote and head != remote:
            anc = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor", remote, head],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=5,
            )
            if anc.returncode != 0:
                r_pull = subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "pull", "--rebase", "--autostash", "origin", "main"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=30,
                )
                print(f"[AutoUpdate] Pulled origin/main ({head[:7]} -> {remote[:7]}): rc={r_pull.returncode}")
                return r_pull.returncode == 0
    except Exception as exc:
        print(f"[AutoUpdate] Git check note: {exc}")
    return False


def _configure_tailscale_if_ready(configured_flag: list[bool]) -> None:
    if os.name != "nt" or not TAILSCALE_EXE.exists():
        return
    import socket

    if socket.gethostname().strip().lower() != "officenew" and os.environ.get("CSPM_ENABLE_FUNNEL") != "1":
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
                subprocess.run([str(TAILSCALE_EXE), "set", "--unattended"], creationflags=CREATE_NO_WINDOW, timeout=5)
                subprocess.run([str(TAILSCALE_EXE), "funnel", "--bg", "24820"], creationflags=CREATE_NO_WINDOW, timeout=8)
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
        server_log_fh = open(SERVER_LOG, "a", encoding="utf-8", buffering=1)
        sys.stdout = server_log_fh
        sys.stderr = server_log_fh

        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        boot_sig = _backend_sig()

        from quick_expense_server import QuickExpenseServerDaemon, is_port_listening
        from services.quick_expense_service import QuickExpenseService

        service = QuickExpenseService()
        daemon = QuickExpenseServerDaemon(service=service, port=24820)
        info = daemon.ensure_running()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Quick Expense server listening on {info['localUrl']} and {info['lanUrl']}")
        threading.Thread(target=lambda: service.get_bootstrap_data("deborah"), daemon=True).start()

        ts_configured = [False]
        last_git_check = time.time()
        while True:
            if not is_port_listening(24820):
                try:
                    daemon.ensure_running()
                except Exception:
                    pass
            _configure_tailscale_if_ready(ts_configured)

            now = time.time()
            if now - last_git_check >= 45.0:
                last_git_check = now
                _auto_git_pull_if_updated()

            # Hot-reload supervisor if any Python backend file changed on disk
            if _backend_sig() != boot_sig:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Backend Python update detected; hot-restarting Quick Expense server...")
                daemon.stop()
                time.sleep(0.35)
                subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve())],
                    cwd=str(REPO_ROOT),
                    creationflags=CREATE_NO_WINDOW,
                    close_fds=True,
                )
                os._exit(0)

            time.sleep(4)
    except BaseException:
        with open(CRASH_LOG, "a", encoding="utf-8") as fh:
            fh.write("=== SUPERVISOR CRASH ===\n")
            fh.write(traceback.format_exc() + "\n")


if __name__ == "__main__":
    main()
