import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "python"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.append(str(SOURCE_ROOT))


from backend.app_controller import (  # noqa: E402
    _powershell_wait_and_launch_script,
    _restart_command,
)


def test_source_restart_command_keeps_the_python_entrypoint_and_arguments():
    command = _restart_command(
        executable=r"C:\Python\python.exe",
        argv=[r"C:\Projects\__CSPM\src\python\main.py", "--tray-only"],
        frozen=False,
    )

    assert command == [
        r"C:\Python\python.exe",
        r"C:\Projects\__CSPM\src\python\main.py",
        "--tray-only",
    ]


def test_packaged_restart_command_does_not_pass_the_exe_to_itself():
    command = _restart_command(
        executable=r"C:\Projects\__CSPM\dist\CSPM\CSPM.exe",
        argv=[r"C:\Projects\__CSPM\dist\CSPM\CSPM.exe", "--tray-only"],
        frozen=True,
    )

    assert command == [r"C:\Projects\__CSPM\dist\CSPM\CSPM.exe", "--tray-only"]


def test_delayed_windows_restart_waits_for_current_single_instance_to_exit():
    script = _powershell_wait_and_launch_script(
        4321,
        [r"C:\Projects\__CSPM\dist\CSPM\CSPM.exe", "--tray-only"],
        r"C:\Projects\__CSPM\dist\CSPM",
    )

    assert "Wait-Process -Id 4321" in script
    assert "Start-Process -FilePath 'C:\\Projects\\__CSPM\\dist\\CSPM\\CSPM.exe'" in script
    assert "-ArgumentList @('--tray-only')" in script


def test_native_splash_progress_clock_starts_after_visible_paint():
    source = (SOURCE_ROOT / "main.py").read_text(encoding="utf-8")

    assert "def _start_progress_after_visible_paint(self):" in source
    assert "self._progress_clock.invalidate()" in source
    assert "self._start_progress_after_visible_paint()" in source
