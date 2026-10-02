import os
from pathlib import Path
import subprocess
import sys


def test_calendar_selection_reaches_workbench_and_filters_actual_rows():
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
    result = subprocess.run([sys.executable, str(root / 'tests/wip_calendar_probe.py')],
                            cwd=root, env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"calendarSelectionAndRangeFiltering": true' in result.stdout
