from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_productivity_inline_and_zen_share_the_wheel_policy():
    source = (PROJECT_ROOT / "src/qml/components/ProductivityReportPanel.qml").read_text(
        encoding="utf-8"
    )
    assert source.count("root.adjustTrendMonths(wheel.angleDelta.y)") == 1
    assert source.count("root.adjustTrendDays(wheel.angleDelta.y)") == 1
    assert "root.adjustTrendMonths(delta)" in source
    assert "root.adjustTrendDays(delta)" in source
    generate = source.split("function generateReport()", 1)[1].split(
        "function adjustTrendMonths", 1
    )[0]
    assert "root.syncZenPanel()" in generate


def test_productivity_zen_wheel_updates_the_rendered_report():
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tests/productivity_wheel_probe.py")],
        cwd=PROJECT_ROOT, env=environment, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"realWheelDelivery": true' in result.stdout
