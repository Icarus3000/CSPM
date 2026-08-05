# scripts\74_fix_tiles_consistency.ps1
# Fixes:
# 1) "Enter Time" tile frame different: set primary:false (so it matches others)
# 2) Icon paths resolving under /components/: wrap with Qt.resolvedUrl("assets/icons/..")

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
    if (Test-Path -LiteralPath (Join-Path $candidate "src\qml\Main.qml")) { return $candidate }

    $cwd = (Get-Location).Path
    if (Test-Path -LiteralPath (Join-Path $cwd "src\qml\Main.qml")) { return $cwd }

    throw "Could not resolve ProjectRoot. Pass -ProjectRoot pointing to __CSPM (must contain src\qml\Main.qml)."
}

$root = Resolve-ProjectRoot -MaybeRoot $ProjectRoot
$backupRoot = Join-Path $root "scripts\_patch_backups\74_fix_tiles_consistency"
Ensure-Dir -Path $backupRoot

$mainQmlPath = Join-Path $root "src\qml\Main.qml"
if (-not (Test-Path -LiteralPath $mainQmlPath)) {
    throw "Missing: $mainQmlPath"
}

Backup-File -Path $mainQmlPath -BackupRoot $backupRoot
$txt = Get-Content -LiteralPath $mainQmlPath -Raw -Encoding UTF8

# ----------------------------------------
# 1) Make Enter Time tile not "primary:true"
#    We target the first TileCard containing text "Enter Time"
# ----------------------------------------
$txt = [regex]::Replace(
    $txt,
    '(?s)(TileCard\s*\{.*?text\s*:\s*"(?:Enter\s+Time|Enter\s+Time\s*)".*?)(\bprimary\s*:\s*)true(\s*;?)',
    '$1$2false$4',
    1
)

# If primary wasn't present in that block, we insert primary:false right after the text line.
$txt = [regex]::Replace(
    $txt,
    '(?s)(TileCard\s*\{.*?text\s*:\s*"(?:Enter\s+Time|Enter\s+Time\s*)"\s*;?\s*\n)(?!.*?\bprimary\s*:)',
    '$1        primary: false' + "`n",
    1
)

# ----------------------------------------
# 2) Fix iconSource paths: use Qt.resolvedUrl("assets/icons/..")
#    Replace ONLY plain string iconSource: "assets/icons/..."
#    Leave already-resolved ones alone.
# ----------------------------------------
$txt = [regex]::Replace(
    $txt,
    '(?m)^\s*iconSource\s*:\s*"(assets/icons/[^"]+)"\s*$',
    '            iconSource: Qt.resolvedUrl("$1")'
)

# Also handle single quotes just in case
$txt = [regex]::Replace(
    $txt,
    "(?m)^\s*iconSource\s*:\s*'(assets/icons/[^']+)'\s*$",
    '            iconSource: Qt.resolvedUrl("$1")'
)

Write-Utf8NoBom -Path $mainQmlPath -Content $txt

Write-Host "PATCHED: src\qml\Main.qml" -ForegroundColor Green
Write-Host "Backups saved to: $backupRoot" -ForegroundColor DarkGray
Write-Host "Done." -ForegroundColor Cyan