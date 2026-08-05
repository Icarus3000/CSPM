# scripts\67c_fix_lastclick_monitor0.ps1
# Fix: ensure AppController initializes _last_click, and monitor0 never dereferences _last_click directly.
# Idempotent. Creates backup under scripts\_patch_backups\67c_fix_lastclick_monitor0\

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
        Copy-Item -LiteralPath $Path -Destination (Join-Path $BackupRoot ($stamp + "_" + $name)) -Force
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

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\67c_fix_lastclick_monitor0"
Ensure-Dir -Path $backupRoot

$path = Join-Path $root "src\python\backend\app_controller.py"
if (-not (Test-Path -LiteralPath $path)) { throw "Missing: $path" }

Backup-File -Path $path -BackupRoot $backupRoot
$txt = Get-Content -LiteralPath $path -Raw -Encoding UTF8

# 1) Ensure QCursor import exists (do not try to be clever; just ensure it's present somewhere)
if ($txt -notmatch '(?m)\bQCursor\b') {
    # Insert after QtCore import if possible
    $txt = [regex]::Replace(
        $txt,
        '(?m)^(from\s+PySide6\.QtCore\s+import\s+.+)$',
        '$1' + "`nfrom PySide6.QtGui import QCursor",
        1
    )
}

# 2) Ensure _last_click initialized in __init__ after super().__init__()
if ($txt -notmatch '(?m)self\._last_click\s*=') {
    $txt = [regex]::Replace(
        $txt,
        '(?m)^\s*super\(\)\.__init__\(\)\s*$',
        '$0' + "`n        self._last_click = QCursor.pos()`n",
        1
    )
}

# 3) Make monitor0 safe: replace direct self._last_click usage with getattr fallback.
# Replace the exact pattern: _screen_for_point(self._last_click)
$txt = $txt -replace '(_screen_for_point\s*\()\s*self\._last_click\s*(\))', '$1getattr(self, "_last_click", QCursor.pos())$2'

Write-Utf8NoBom -Path $path -Content $txt

Write-Host "PATCHED: $path" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray
Write-Host "Done." -ForegroundColor Cyan