"""Exercise a frozen CSPM package using a caller-prepared read-only profile.

Windows desktop smoke only. No cursor input, workbook copies, settings edits,
source injection, or automatic process termination. Failed runs retain their
owned process and private evidence so the caller can inspect the failure.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WORKBOOKS = ("CSPM.xlsm", "Dockets.xlsm")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def pair_identity(hashes: dict[str, str]) -> str:
    return hashlib.sha256("|".join(hashes[name] for name in WORKBOOKS).encode("ascii")).hexdigest()[:12].upper()


def optional_hash(path: Path) -> str | None:
    return sha256(path) if path.is_file() else None


def prepared_profile(profile: Path, package: Path) -> tuple[dict, Path, Path, dict]:
    if profile == package or profile.is_relative_to(package):
        raise ValueError("The runtime profile must be outside the package.")
    settings = json.loads((profile / "user_settings.json").read_text(encoding="utf-8"))
    if settings.get("readOnlyVerification") is not True:
        raise ValueError("The externally prepared profile must enable readOnlyVerification.")
    if not Path(settings["localDataDir"]).is_absolute() or not Path(settings["masterDataDir"]).is_absolute():
        raise ValueError("The prepared profile must use absolute local and governed source paths.")
    if settings.get("mainWindowLayout", {}).get("maximized") is True:
        raise ValueError("Prepare the profile with a restored mainWindowLayout before this smoke.")
    local = Path(settings["localDataDir"]).resolve()
    master = Path(settings["masterDataDir"]).resolve()
    if not settings.get("masterDataDir") or local == master or master in local.parents or local in master.parents:
        raise ValueError("A configured governed source and separate local replica are required.")
    local_hashes = {name: sha256(local / name) for name in WORKBOOKS}
    master_hashes = {name: sha256(master / name) for name in WORKBOOKS}
    if local_hashes != master_hashes:
        raise ValueError("The prepared replica does not match the configured governed pair.")
    observation = dict(localHashes=local_hashes, governedHashes=master_hashes,
                       datasetIdentity=pair_identity(local_hashes),
                       checkoutMarker=optional_hash(master / ".cspm_checkout.json"),
                       syncState=optional_hash(profile / "sync_state.json"))
    return settings, local, master, observation


def isolated_environment(profile: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith(("CSPM_", "QT_", "QSG_", "QML_", "QTWEBENGINE")) or key in {
            "PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX",
        }:
            environment.pop(key)
    for directory in ("local", "roaming", "temp", "logs", "exports"):
        (profile / directory).mkdir(exist_ok=True)
    environment.update(
        LOCALAPPDATA=str(profile / "local"), APPDATA=str(profile / "roaming"),
        TEMP=str(profile / "temp"), TMP=str(profile / "temp"),
        CSPM_RUNTIME_DIR=str(profile), CSPM_DATA_DIR=str(profile),
        CSPM_EXECUTABLE_ROOT=str(profile), CSPM_LOG_DIR=str(profile / "logs"),
        CSPM_EXPORT_DIR=str(profile / "exports"), CSPM_MACHINE_ID_FILE=str(profile / "machine.json"),
        CSPM_VERIFY_DATA_READ_ONLY="1", PYTHONDONTWRITEBYTECODE="1",
    )
    return environment


def powershell_script(hwnd: int, action: str) -> str:
    if action not in {"status", "toggle", "close", "search"}:
        raise ValueError("Unsupported accessibility action")
    return r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$cspmRoot = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]WINDOW_HANDLE)
$cspmElements = @($cspmRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition))
$cspmAction = 'ACTION_VALUE'
if ($cspmAction -eq 'status') {
    $labels = @($cspmElements | Where-Object { -not $_.Current.IsOffscreen -and $_.Current.Name -like '*Governed source*' } | ForEach-Object { $_.Current.Name } | Select-Object -Unique)
    $controls = @($cspmElements | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $_.Current.Name -in @([string][char]0xE922, [string][char]0xE923) -and $_.Current.IsEnabled -and -not $_.Current.IsOffscreen })
    @{ labels=$labels; automationId=$cspmRoot.Current.AutomationId; enabled=$cspmRoot.Current.IsEnabled; controlsReady=($controls.Count -eq 1) } | ConvertTo-Json -Compress
    exit 0
}
if ($cspmAction -eq 'search') {
    $edits = @($cspmElements | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Edit -and $_.Current.IsEnabled -and -not $_.Current.IsOffscreen } | Sort-Object { $_.Current.BoundingRectangle.Top } | Select-Object -First 1)
    if ($edits.Count -ne 1) { throw 'No accessible header search input' }
    $edits[0].GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue('matters list')
    $edits[0].SetFocus()
    @{ searchValue='matters list'; focused=$edits[0].Current.HasKeyboardFocus } | ConvertTo-Json -Compress
    exit 0
}
$glyphs = if ($cspmAction -eq 'close') { @([string][char]0xE8BB) } else { @([string][char]0xE922, [string][char]0xE923) }
$buttons = @($cspmElements | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $_.Current.Name -in $glyphs -and $_.Current.IsEnabled -and -not $_.Current.IsOffscreen })
if ($buttons.Count -ne 1) { throw "Expected one accessible $cspmAction control; found $($buttons.Count)" }
$glyph = [int][char]$buttons[0].Current.Name
$buttons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
@{ invoked=$cspmAction; glyph=$glyph } | ConvertTo-Json -Compress
'''.replace("WINDOW_HANDLE", str(int(hwnd))).replace("ACTION_VALUE", action)


class WindowsDesktop:
    def __init__(self, process_id: int):
        self.process_id = process_id
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user.EnumWindows.argtypes = [self.callback_type, wintypes.LPARAM]
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        for name in ("IsWindowVisible", "IsWindowEnabled"):
            getattr(self.user, name).argtypes = [wintypes.HWND]
        self.user.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        self.user.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    def windows(self) -> list[dict]:
        results = []
        @self.callback_type
        def visit(hwnd, _):
            pid = wintypes.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.process_id:
                title = ctypes.create_unicode_buffer(512)
                self.user.GetWindowTextW(hwnd, title, len(title))
                results.append(dict(hwnd=int(hwnd), title=title.value,
                                    visible=bool(self.user.IsWindowVisible(hwnd))))
            return True
        self.user.EnumWindows(visit, 0)
        return results

    def main_handle(self) -> int | None:
        return next((window["hwnd"] for window in self.windows()
                     if window["visible"] and window["title"] == "CSPM - Main Menu"), None)

    def rectangle(self, hwnd: int) -> list[int]:
        rect = wintypes.RECT()
        if not self.user.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top]

    def input_ready(self, hwnd: int) -> bool:
        return bool(self.user.IsWindowVisible(hwnd) and self.user.IsWindowEnabled(hwnd))

    def uia(self, hwnd: int, action: str) -> dict:
        script = powershell_script(hwnd, action)
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        executable = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        result = subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError("Accessibility action failed: " + result.stderr.strip())
        return json.loads(result.stdout.lstrip("\ufeff").strip())

    def submit_search(self, hwnd: int) -> None:
        # Only the HWND owned by the launched package receives Enter. The
        # physical cursor/keyboard and unrelated windows are not manipulated.
        self.user.PostMessageW(hwnd, 0x100, 0x0D, 0x001C0001)
        self.user.PostMessageW(hwnd, 0x101, 0x0D, 0xC01C0001)


def wait_for(predicate, process, *, timeout: float, label: str, allow_exit=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        if process.poll() is not None and not allow_exit:
            raise RuntimeError(f"Package exited during {label}: {process.returncode}")
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for " + label)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--cycles", type=int, choices=(1, 5), default=1, help="Maximize/restore pairs")
    parser.add_argument("--startup-timeout", type=float, default=120)
    parser.add_argument("--search-navigation", action="store_true", help="Exercise accessible search and Matters navigation")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    options = arguments(argv)
    if sys.platform != "win32":
        raise RuntimeError("Frozen lifecycle smoke requires a real Windows desktop")
    package, profile = options.package.resolve(), options.profile.resolve()
    executable = package / "CSPM.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    _, local, master, before = prepared_profile(profile, package)
    result_path = profile / "packaged-lifecycle-result.private.json"
    if result_path.exists():
        raise FileExistsError("Use a fresh prepared profile; previous evidence is preserved")
    environment = isolated_environment(profile)
    log_path = profile / "logs/cspm.log"
    log_offset = log_path.stat().st_size if log_path.exists() else 0
    def log():
        if not log_path.exists():
            return ""
        with log_path.open("rb") as stream:
            stream.seek(log_offset)
            return stream.read().decode("utf-8", errors="replace")
    started = time.monotonic()
    report = dict(ok=False, package=str(package), profile=str(profile), checks=[], failures=[],
                  before=before, cycles=options.cycles, executableSha256=sha256(executable),
                  cloudServerFreshnessVerified=False, forcedTermination=False)
    stdout = (profile / "packaged-stdout.private.log").open("x", encoding="utf-8")
    stderr = (profile / "packaged-stderr.private.log").open("x", encoding="utf-8")
    process = subprocess.Popen([str(executable), "--verify-data-read-only"], cwd=package, env=environment,
                               stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    report["processId"] = process.pid
    desktop = WindowsDesktop(process.pid)
    try:
        hwnd = wait_for(lambda: desktop.main_handle() if "startup-input-ready" in log() else None,
                        process, timeout=options.startup_timeout, label="visible input-ready main window")
        report["windowHandle"] = hwnd
        report["startupSeconds"] = round(time.monotonic() - started, 3)
        def accessible_source_ready():
            status = desktop.uia(hwnd, "status")
            labels = status.get("labels", [])
            verified = any("Governed source" in label and "read-only verification" in label
                           and "cloud freshness unverified" in label and before["datasetIdentity"] in label for label in labels)
            return status if verified and status.get("enabled") and status.get("controlsReady") else None
        status = wait_for(accessible_source_ready, process, timeout=20,
                          label="visible accessible governed dataset banner and title-bar controls")
        labels = status.get("labels", [])
        report["dataStatus"] = labels
        initial = desktop.rectangle(hwnd)
        report["normalRectangle"] = initial
        report["checks"].append("frozen startup and accessible governed read-only status")
        for toggle in range(options.cycles * 2):
            previous = len(log().splitlines())
            desktop.uia(hwnd, "toggle")
            def completed():
                fresh = log().splitlines()[previous:]
                returned = [line for line in fresh if "motion live-return" in line]
                expected = desktop.rectangle(hwnd) == initial if toggle % 2 else desktop.rectangle(hwnd)[2] > initial[2]
                overlay = any(window["visible"] and window["title"] == "CSPM window transition" for window in desktop.windows())
                return returned[-1] if returned and expected and desktop.input_ready(hwnd) and not overlay else None
            outcome = wait_for(completed, process, timeout=25, label=f"motion live-return {toggle + 1}")
            if "recovery=passed" not in outcome:
                raise AssertionError("Motion failed to restore live input/visibility")
            report["checks"].append(dict(toggle=toggle + 1, rectangle=desktop.rectangle(hwnd), outcome=outcome))
        if options.search_navigation:
            previous = len(log().splitlines())
            search = desktop.uia(hwnd, "search")
            if not search.get("focused"):
                raise AssertionError("Accessible header search did not receive focus")
            desktop.submit_search(hwnd)
            wait_for(lambda: any("node=A09" in line for line in log().splitlines()[previous:]),
                     process, timeout=25, label="search navigation to Matters")
            report["checks"].append("accessible search focus, value and Matters navigation")
        desktop.uia(hwnd, "close")
        wait_for(lambda: process.poll() is not None, process, timeout=35,
                 label="normal title-bar X process exit", allow_exit=True)
        report["processExitCode"] = process.returncode
        final_log = log()
        report["closeStarts"] = final_log.count("[PERF] start key=window.transition.close")
        report["closeEnds"] = final_log.count("[PERF] end key=window.transition.close")
        report["trayReleaseEvents"] = final_log.count("tray resources released; owned timers stopped")
        if process.returncode != 0 or report["closeStarts"] != 1 or report["closeEnds"] != 1 or report["trayReleaseEvents"] != 1:
            raise AssertionError("Title-bar X did not produce one close transaction and orderly exit/tray teardown")
        if desktop.windows():
            raise AssertionError("Owned native windows remained after process exit")
        report["checks"].append("one title-bar close animation; process exits zero; tray resources released")
        report["ok"] = True
    except Exception as exc:
        report["failures"].append(repr(exc))
    finally:
        report["processStillRunning"] = process.poll() is None
        report["elapsedSeconds"] = round(time.monotonic() - started, 3)
        try:
            report["after"] = dict(localHashes={name: sha256(local / name) for name in WORKBOOKS},
                                   governedHashes={name: sha256(master / name) for name in WORKBOOKS},
                                   checkoutMarker=optional_hash(master / ".cspm_checkout.json"),
                                   syncState=optional_hash(profile / "sync_state.json"))
            if any(report["after"][key] != before[key] for key in report["after"]):
                report["ok"] = False
                report["failures"].append("Workbook hashes, checkout marker or sync state changed")
        except Exception as exc:
            report["ok"] = False
            report["failures"].append("Final data audit failed: " + repr(exc))
        stdout.close()
        stderr.close()
        result_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": report["ok"], "result": str(result_path), "processId": process.pid,
                          "processStillRunning": report["processStillRunning"], "failures": report["failures"]}), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
