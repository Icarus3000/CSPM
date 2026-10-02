"""Run a packaged candidate on disposable data; exercise real title-bar buttons.

Windows desktop validation, not a smoothness or mixed-DPI acceptance test.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exe', type=Path, default=ROOT/'dist/CSPM/CSPM.exe')
parser.add_argument('--startup-timeout', type=float, default=60,
                    help='Seconds allowed for cold packaged startup (default: 60)')
parser.add_argument('--transitions', action='store_true',
                    help='Also click controls; requires permission to move the actual desktop cursor')
parser.add_argument('--uia-controls', action='store_true',
                    help='Invoke title-bar controls through Windows accessibility without moving the desktop cursor')
args = parser.parse_args()
audit = ROOT/'logs/packaged_window_candidate'
audit.mkdir(parents=True, exist_ok=True)
profile = audit/'profile'
profile.mkdir(exist_ok=True)
for name in ('local', 'master'):
    target = profile/name
    target.mkdir(exist_ok=True)
    for workbook in ('CSPM.xlsm', 'Dockets.xlsm'):
        shutil.copy2(Path(os.environ['LOCALAPPDATA'])/'CSPM/data'/workbook, target/workbook)
settings = json.loads((Path(os.environ['LOCALAPPDATA'])/'CSPM/user_settings.json').read_text())
settings.update(localDataDir=str(profile/'local'), masterDataDir=str(profile/'master'),
                appStyle='Professional', keepTrayAlive=False, runAtStartup=False,
                mainWindowLayout=dict(maximized=False, hasExactRect=True, x=320, y=140,
                    width=1100, height=760, workAreaX=0, workAreaY=0,
                    workAreaWidth=1920, workAreaHeight=1040))
(profile/'user_settings.json').write_text(json.dumps(settings), encoding='utf-8')
runtime = audit/time.strftime('runtime_%Y%m%d_%H%M%S')
env = os.environ.copy()
env.update(CSPM_RUNTIME_DIR=str(profile), CSPM_DATA_DIR=str(profile), CSPM_LOG_DIR=str(runtime))
user = ctypes.windll.user32
user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user.IsWindowVisible.argtypes = [wintypes.HWND]
user.SetForegroundWindow.argtypes = [wintypes.HWND]
user.WindowFromPoint.argtypes = [wintypes.POINT]
user.WindowFromPoint.restype = wintypes.HWND
user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user.EnumWindows.argtypes = [enum_type, wintypes.LPARAM]
cursor = wintypes.POINT()
user.GetCursorPos(ctypes.byref(cursor))
if args.transitions and not args.uia_controls:
    user.SetCursorPos(960, 520)
process = subprocess.Popen([str(args.exe.resolve())], env=env,
                           creationflags=subprocess.CREATE_NO_WINDOW)
started = time.monotonic()
report = {'exe':str(args.exe.resolve()), 'ok':False, 'checks':[], 'runtime':str(runtime)}

def main_handle(expected_title='CSPM - Main Menu'):
    found = []
    @enum_type
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, 256)
        if pid.value == process.pid and title.value == expected_title:
            found.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    return found[0] if found else None

def logs():
    path = runtime/'cspm.log'
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''

def wait_for(predicate, timeout=60):
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Candidate exited early: {process.returncode}')
        if predicate(): return
        time.sleep(.1)
    raise TimeoutError('Candidate check timed out; inspect runtime log')

def rectangle(hwnd):
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)): raise ctypes.WinError()
    return [rect.left, rect.top, rect.right-rect.left, rect.bottom-rect.top]

def click_maximize(hwnd):
    # 32 px controls + 16 px inset; restored canvas has 11 px exterior pad.
    rect = rectangle(hwnd)
    pad = 11 if rect[2] < 1500 else 0
    if args.uia_controls:
        script = '''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]HWND_VALUE)
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$buttons = @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition) | Where-Object { $_.Current.Name -eq [string][char]0xE922 -or $_.Current.Name -eq [string][char]0xE923 })
if ($buttons.Count -ne 1) { throw 'Expected exactly one maximize/restore control' }
$pattern = $buttons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
$pattern.Invoke()
'''.replace('HWND_VALUE', str(hwnd))
        return subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    user.SetForegroundWindow(hwnd)
    positioned = user.SetCursorPos(rect[0]+rect[2]-pad-66, rect[1]+36+pad)
    actual = wintypes.POINT()
    user.GetCursorPos(ctypes.byref(actual))
    print('INPUT', hwnd, 'visible',user.IsWindowVisible(hwnd), 'positioned',positioned,
          'cursor',actual.x,actual.y,'hit',user.WindowFromPoint(actual),flush=True)
    if not positioned:
        raise RuntimeError('Desktop cursor positioning denied; packaged transition input not validated')
    time.sleep(.1)
    user.mouse_event(0x2,0,0,0,0)
    time.sleep(.05)
    user.mouse_event(0x4,0,0,0,0)

try:
    wait_for(lambda: ('startup-input-ready' in logs()
                     or '[STARTUP-FIRST-INPUT-READY]' in logs()) and main_handle(),
             timeout=args.startup_timeout)
    hwnd = main_handle()
    assert user.IsWindowVisible(hwnd)
    initial = rectangle(hwnd)
    report['ready_seconds'] = round(time.monotonic()-started,2)
    report['checks'].append({'label':'ready', 'rect':initial})
    time.sleep(2)  # Allow the opening surface/input shield to retire.
    for cycle in range(4 if args.transitions or args.uia_controls else 0):
        observed = {'surface':False}
        invoked = click_maximize(hwnd)
        def settled():
            surface = main_handle('CSPM window transition')
            visible = bool(surface and user.IsWindowVisible(surface))
            observed['surface'] |= visible
            rect = rectangle(hwnd)
            expected = (rect == initial if cycle % 2 else
                        rect[2] > initial[2] and rect[3] > initial[3])
            return observed['surface'] and not visible and expected
        # Normal packaged builds do not persist QML debug completion messages.
        # Observe the real transition HWND appearing and retiring instead.
        wait_for(settled, timeout=15)
        if invoked:
            _, stderr = invoked.communicate(timeout=15)
            if invoked.returncode:
                raise RuntimeError('Accessibility control invocation failed: '+stderr)
        rect = rectangle(hwnd)
        style = user.GetWindowLongPtrW(hwnd,-16)
        assert style & 0x00C00000 == 0, 'Native caption style appeared'
        if cycle % 2:
            assert rect == initial, rect
        else:
            assert rect[2] > initial[2] and rect[3] > initial[3], rect
        report['checks'].append({'label':f'toggle {cycle}', 'rect':rect, 'style':hex(style),
                                'observed_transition_surface':observed['surface']})
    report['ok'] = True
except Exception as exc:
    report['error'] = repr(exc)
finally:
    hwnd = main_handle()
    if hwnd: user.PostMessageW(hwnd,0x10,0,0)
    try: process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.terminate()  # Only the disposable candidate process started here.
        process.wait(timeout=10)
    if args.transitions and not args.uia_controls:
        user.SetCursorPos(cursor.x,cursor.y)
    (audit/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)
raise SystemExit(0 if report['ok'] else 1)
