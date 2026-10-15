"""Wait for Linux instance ownership to end before launching its replacement."""
from __future__ import annotations

import os
import subprocess
import time


def run_from_argv(argv: list[str]) -> int:
    index = argv.index("--restart-after-pid")
    parent_pid = int(argv[index + 1])
    if argv[index + 2] != "--" or not argv[index + 3:]:
        raise ValueError("A restart requires an explicit executable and arguments.")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            os.kill(parent_pid, 0)
        except ProcessLookupError:
            subprocess.Popen(argv[index + 3:], close_fds=True, start_new_session=True)
            return 0
        time.sleep(0.1)
    return 1
