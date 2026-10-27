#!/usr/bin/env python3
"""Headless Watchdog for the CSPM Quick Expense Server (Port 24820).

Complies with Global Rule 12:
- Checks if TCP port 24820 is already listening via socket before spawning anything.
- Spawns `pythonw.exe` with `CREATE_NO_WINDOW` (0x08000000) so zero console windows ever flash.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PORT = 24820
REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = REPO_ROOT / "src" / "python" / "quick_expense_server.py"


def is_port_listening(port: int = PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def find_pythonw() -> str:
    # Prefer repo venv pythonw.exe if available, else system pythonw.exe
    for venv_dir in sorted(REPO_ROOT.glob(".venv*")):
        pw = venv_dir / "Scripts" / "pythonw.exe"
        if pw.exists():
            return str(pw)
    cur = Path(sys.executable)
    pw_sys = cur.with_name("pythonw.exe")
    if pw_sys.exists():
        return str(pw_sys)
    return str(cur)


def main() -> int:
    if is_port_listening(PORT):
        return 0
    import time

    pythonw = find_pythonw()
    subprocess.Popen(
        [pythonw, str(SERVER_SCRIPT), "--port", str(PORT)],
        cwd=str(REPO_ROOT),
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )
    for _ in range(30):
        if is_port_listening(PORT):
            break
        time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
