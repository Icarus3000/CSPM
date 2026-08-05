# scripts\67_fix_appcontroller_lastclick.ps1
# Fix AppController: ensure _last_click exists and expose monitor0/ordered monitors for QML.
# Idempotent patch. Creates backups under scripts\_patch_backups\67_fix_appcontroller_lastclick\

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Backup-File {
    param([string]$Path, [string]$BackupRoot)
    if (Test-Path -LiteralPath $Path) {
        Ensure-Dir -Path $BackupRoot
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $name = Split-Path -Leaf $Path
        $dest = Join-Path $BackupRoot ($stamp + "_" + $name)
        Copy-Item -LiteralPath $Path -Destination $dest -Force
        Write-Host "BACKUP: $Path -> $dest" -ForegroundColor DarkGray
    }
}

function Resolve-ProjectRoot {
    param([string]$MaybeRoot)

    if ($MaybeRoot -and $MaybeRoot.Trim() -ne "") {
        return (Resolve-Path -LiteralPath $MaybeRoot).Path
    }

    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

    $candidate = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
    if (Test-Path -LiteralPath (Join-Path $candidate "src\python\backend\app_controller.py")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\python\backend\app_controller.py")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM (must contain src\python\backend\app_controller.py)."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
Write-Host "ProjectRoot: $root" -ForegroundColor Cyan

$backupRoot = Join-Path $root "scripts\_patch_backups\67_fix_appcontroller_lastclick"
Ensure-Dir -Path $backupRoot

$path = Join-Path $root "src\python\backend\app_controller.py"
if (-not (Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
}

Backup-File -Path $path -BackupRoot $backupRoot

$txt = Get-Content -LiteralPath $path -Raw -Encoding UTF8

# ---------------------------
# 1) Ensure QtCore import includes QPoint
# ---------------------------
$txt = [regex]::Replace(
    $txt,
    '(?m)^from\s+PySide6\.QtCore\s+import\s+(.+)$',
    {
        param($m)
        $imports = $m.Groups[1].Value
        if ($imports -match '\bQPoint\b') { return $m.Value }
        return "from PySide6.QtCore import " + $imports.TrimEnd() + ", QPoint"
    },
    1
)

# ---------------------------
# 2) Ensure QtGui imports: QCursor, QGuiApplication
# ---------------------------
if ($txt -notmatch '(?m)^from\s+PySide6\.QtGui\s+import\s+') {
    # Insert after QtCore import line
    $txt = [regex]::Replace(
        $txt,
        '(?m)^(from\s+PySide6\.QtCore\s+import\s+.+)$',
        '$1' + "`nfrom PySide6.QtGui import QCursor, QGuiApplication",
        1
    )
} else {
    # If QtGui import exists but missing names, extend it (simple approach)
    if ($txt -notmatch '\bQCursor\b') {
        $txt = [regex]::Replace($txt, '(?m)^from\s+PySide6\.QtGui\s+import\s+(.+)$', { param($m) "from PySide6.QtGui import " + $m.Groups[1].Value.Trim() + ", QCursor" }, 1)
    }
    if ($txt -notmatch '\bQGuiApplication\b') {
        $txt = [regex]::Replace($txt, '(?m)^from\s+PySide6\.QtGui\s+import\s+(.+)$', { param($m) "from PySide6.QtGui import " + $m.Groups[1].Value.Trim() + ", QGuiApplication" }, 1)
    }
}

# ---------------------------
# 3) Ensure monitorChanged signal exists
# ---------------------------
if ($txt -notmatch '(?m)^\s*monitorChanged\s*=\s*Signal\(\s*\)\s*$') {
    $txt = [regex]::Replace(
        $txt,
        '(?m)^\s*listsChanged\s*=\s*Signal\(\s*\)\s*$',
        '$0' + "`n    monitorChanged = Signal()`n",
        1
    )
}

# ---------------------------
# 4) Ensure self._last_click is initialized in __init__
# ---------------------------
if ($txt -notmatch '(?m)self\._last_click\s*=') {
    # Insert right after super().__init__()
    $txt = [regex]::Replace(
        $txt,
        '(?m)^\s*super\(\)\.__init__\(\)\s*$',
        '$0' + "`n        self._last_click = QCursor.pos()`n",
        1
    )
}

# ---------------------------
# 5) Inject helper methods + properties + slot once
# ---------------------------
if ($txt -notmatch '(?m)def\s+_screens_ltr\s*\(') {
$appendBlock = @"

    # ---- Monitor helpers (0 = last click, 1..N = left-to-right) ----
    def _screens_ltr(self):
        screens = list(QGuiApplication.screens() or [])
        screens.sort(key=lambda s: int(s.geometry().x()))
        return screens

    def _screen_for_point(self, pt: QPoint):
        try:
            s = QGuiApplication.screenAt(pt)
            if s is not None:
                return s
        except Exception:
            pass
        for s in self._screens_ltr():
            try:
                if s.geometry().contains(pt):
                    return s
            except Exception:
                continue
        try:
            return QGuiApplication.primaryScreen()
        except Exception:
            return None

    def _rect_to_map(self, r):
        return {"x": int(r.x()), "y": int(r.y()), "w": int(r.width()), "h": int(r.height())}

    @Property("QVariantMap", notify=monitorChanged)
    def lastClick(self):
        p = self._last_click
        return {"x": int(p.x()), "y": int(p.y())}

    @Property("QVariantMap", notify=monitorChanged)
    def monitor0(self):
        s = self._screen_for_point(self._last_click)
        if s is None:
            return {"index": 1, "name": "Screen 1", "geometry": {"x":0,"y":0,"w":0,"h":0}, "available": {"x":0,"y":0,"w":0,"h":0}}
        screens = self._screens_ltr()
        ix = 1
        try:
            ix = screens.index(s) + 1
        except Exception:
            ix = 1
        return {
            "index": int(ix),
            "name": str(s.name() or f"Screen {ix}"),
            "geometry": self._rect_to_map(s.geometry()),
            "available": self._rect_to_map(s.availableGeometry()),
        }

    @Property("QVariantList", notify=monitorChanged)
    def monitorsOrdered(self):
        out = []
        for ix, s in enumerate(self._screens_ltr(), start=1):
            out.append({
                "index": int(ix),
                "name": str(s.name() or f"Screen {ix}"),
                "geometry": self._rect_to_map(s.geometry()),
                "available": self._rect_to_map(s.availableGeometry()),
            })
        return out

    @Slot(int, int)
    def setLastClick(self, x: int, y: int):
        self._last_click = QPoint(int(x), int(y))
        self.monitorChanged.emit()

"@
    $txt = $txt.TrimEnd() + $appendBlock
}

Write-Utf8NoBom -Path $path -Content $txt
Write-Host "PATCHED: src\python\backend\app_controller.py (initialized _last_click + monitor0 API)" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray
Write-Host "`nDone." -ForegroundColor Cyan