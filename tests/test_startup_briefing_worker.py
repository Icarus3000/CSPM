"""Regression coverage for the crash-isolated Practice Briefing worker."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from backend.app_controller import _startup_briefing_worker_command  # noqa: E402
from backend import startup_briefing_worker  # noqa: E402


def test_worker_persists_a_success_payload_without_qt_or_gui(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps({"filters": {"readyToBillMode": "ready_only"}}), encoding="utf-8")
    monkeypatch.setattr(
        startup_briefing_worker,
        "collect_startup_briefing",
        lambda request: {"ok": True, "summary": {"activeClientCount": 1}, "filters": request["filters"]},
    )

    assert startup_briefing_worker.run(request_path, result_path) == 0
    assert json.loads(result_path.read_text(encoding="utf-8"))["payload"]["summary"]["activeClientCount"] == 1


def test_worker_command_bypasses_normal_application_startup(tmp_path):
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"

    source_command = _startup_briefing_worker_command(
        request_path,
        result_path,
        executable="python.exe",
        frozen=False,
    )
    packaged_command = _startup_briefing_worker_command(
        request_path,
        result_path,
        executable="CSPM.exe",
        frozen=True,
    )

    assert source_command[0] == "python.exe"
    assert source_command[1].endswith("src\\python\\main.py")
    assert packaged_command == ["CSPM.exe", "--startup-briefing-worker", str(request_path), str(result_path)]
