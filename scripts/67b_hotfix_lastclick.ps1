# scripts\67b_hotfix_lastclick.ps1
# Hotfix: guarantee AppController has _last_click and lastClick never crashes.
# Creates backup under scripts\_patch_backups\67b_hotfix_lastclick\

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

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\67b_hotfix_lastclick"
Ensure-Dir -Path $backupRoot

$path = Join-Path $root "src\python\backend\app_controller.py"
if (-not (Test-Path -LiteralPath $path)) { throw "Missing: $path" }

Backup-File -Path $path -BackupRoot $backupRoot
$txt = Get-Content -LiteralPath $path -Raw -Encoding UTF8

# 1) Ensure import for QCursor
if ($txt -notmatch '(?m)^from\s+PySide6\.QtGui\s+import\s+') {
    $txt = [regex]::Replace(
        $txt,
        '(?m)^(from\s+PySide6\.QtCore\s+import\s+.+)$',
        '$1' + "`nfrom PySide6.QtGui import QCursor",
        1
    )
} elseif ($txt -notmatch '\bQCursor\b') {
    $txt = [regex]::Replace(
        $txt,
        '(?m)^from\s+PySide6\.QtGui\s+import\s+(.+)$',
        { param($m) "from PySide6.QtGui import " + $m.Groups[1].Value.Trim() + ", QCursor" },
        1
    )
}

# 2) Ensure _last_click initialized in __init__ right after super().__init__()
if ($txt -notmatch '(?m)self\._last_click\s*=') {
    $txt = [regex]::Replace(
        $txt,
        '(?m)^\s*super\(\)\.__init__\(\)\s*$',
        '$0' + "`n        self._last_click = QCursor.pos()`n",
        1
    )
}

# 3) Harden lastClick property getter if present
# Replace: p = self._last_click  => p = getattr(self, "_last_click", QCursor.pos())
$txt = [regex]::Replace(
    $txt,
    '(?m)^\s*p\s*=\s*self\._last_click\s*$',
    '        p = getattr(self, "_last_click", QCursor.pos())',
    1
)

Write-Utf8NoBom -Path $path -Content $txt

Write-Host "PATCHED: $path" -ForegroundColor Green
Write-Host "Backups: $backupRoot" -ForegroundColor DarkGray