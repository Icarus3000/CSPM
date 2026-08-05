<#
CSPM_TearAway_Hotfix.ps1

Fixes QML runtime ReferenceError(s) introduced by the tear-away patch:
  - Main.qml: appCloseWarning popup references panel2Color/accentColor/textColor without qualifying scope.
    In QML, child objects don't automatically resolve parent properties by bare name in all bindings.
    Fix: qualify as appCloseWarning.panel2Color (etc).

Also improves Python runner detection:
  - Uses .venv if present AND functional.
  - Otherwise uses $env:CSPM_PY if set.
  - Otherwise uses 'py' launcher if available.
  - Otherwise uses 'python' on PATH.

Run from repo root:
  .\scripts\CSPM_TearAway_Hotfix.ps1

This script:
  1) creates timestamped backups of modified files
  2) applies deterministic text edits
  3) runs the app
#>

$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
    $here = Get-Location
    if (Test-Path (Join-Path $here 'src\qml\Main.qml')) { return $here.Path }

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $candidate = Split-Path -Parent $scriptDir
    if (Test-Path (Join-Path $candidate 'src\qml\Main.qml')) { return $candidate }

    if (Test-Path (Join-Path $scriptDir 'src\qml\Main.qml')) { return $scriptDir }

    throw "Repo root not found. Run from repo root (where src\qml\Main.qml exists) or keep this script in repo\scripts."
}

function New-BackupFolder([string]$root) {
    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    $b = Join-Path $root (Join-Path 'backups' (Join-Path 'patches' $ts))
    New-Item -ItemType Directory -Force -Path $b | Out-Null
    return $b
}

function Backup-File([string]$root, [string]$backupRoot, [string]$relPath) {
    $src = Join-Path $root $relPath
    if (!(Test-Path $src)) {
        throw "Expected file missing: $relPath"
    }
    $dst = Join-Path $backupRoot $relPath
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    Copy-Item -Force $src $dst
}

function Write-Utf8NoBom([string]$path, [string]$content) {
    $dir = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
}

function Test-PythonExe([string]$exePath) {
    if (!(Test-Path $exePath)) { return $false }
    try {
        $p = Start-Process -FilePath $exePath -ArgumentList @('-c','import sys; print(sys.executable)') -NoNewWindow -PassThru -Wait
        return ($p.ExitCode -eq 0)
    } catch {
        return $false
    }
}

function Get-PythonCommand([string]$root) {
    $venvPy = Join-Path $root '.venv\Scripts\python.exe'
    if (Test-PythonExe $venvPy) {
        return @{ Kind='exe'; Value=$venvPy }
    }

    if ($env:CSPM_PY -and (Test-Path $env:CSPM_PY)) {
        if (Test-PythonExe $env:CSPM_PY) {
            return @{ Kind='exe'; Value=$env:CSPM_PY }
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{ Kind='launcher'; Value=$pyLauncher.Source }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{ Kind='exe'; Value=$pythonCmd.Source }
    }

    throw "Could not locate a working Python. Fix .venv, or set CSPM_PY to your python.exe path, or install/enable the 'py' launcher."
}

function Apply-MainQml-Hotfix([string]$text) {
    $orig = $text

    # Scope-fix for appCloseWarning popup.
    # These were referenced without qualification, causing ReferenceError at runtime.
    $text = $text -replace 'color:\s*panel2Color\b', 'color: appCloseWarning.panel2Color'
    $text = $text -replace 'border\.color:\s*accentColor\b', 'border.color: appCloseWarning.accentColor'
    $text = $text -replace 'Qt\.rgba\(accentColor\.r', 'Qt.rgba(appCloseWarning.accentColor.r'
    $text = $text -replace 'Qt\.rgba\(accentColor\.r,\s*accentColor\.g,\s*accentColor\.b', 'Qt.rgba(appCloseWarning.accentColor.r, appCloseWarning.accentColor.g, appCloseWarning.accentColor.b'

    # Text color references
    $text = $text -replace 'color:\s*textColor\b', 'color: appCloseWarning.textColor'

    # If we accidentally replaced other popups (unlikely), ensure we only keep changes where appCloseWarning exists.
    if ($text -notmatch 'id:\s*appCloseWarning') {
        throw 'Sanity check failed: appCloseWarning id not found in Main.qml; refusing to apply scope fix.'
    }

    # Ensure we actually changed something
    if ($text -eq $orig) {
        Write-Host '[HOTFIX] No changes detected in Main.qml (already fixed?)' -ForegroundColor Yellow
    }

    return $text
}

$root = Resolve-RepoRoot
$backup = New-BackupFolder $root

$mainRel = 'src\qml\Main.qml'
Backup-File $root $backup $mainRel
Write-Host "[HOTFIX] Backed up: $mainRel -> $backup" -ForegroundColor Green

$mainPath = Join-Path $root $mainRel
$mainText = Get-Content -Raw -LiteralPath $mainPath
$fixed = Apply-MainQml-Hotfix $mainText
Write-Utf8NoBom $mainPath $fixed
Write-Host "[HOTFIX] Patched: $mainRel" -ForegroundColor Green

# Run the app
$pyInfo = Get-PythonCommand $root
Write-Host "[RUN] Python: $($pyInfo.Kind) => $($pyInfo.Value)" -ForegroundColor Cyan

Push-Location $root
try {
    if ($pyInfo.Kind -eq 'launcher') {
        # Prefer 3.14 if installed, otherwise default
        & $pyInfo.Value -3.14 'src\python\main.py'
        if ($LASTEXITCODE -ne 0) {
            & $pyInfo.Value 'src\python\main.py'
        }
    } else {
        & $pyInfo.Value 'src\python\main.py'
    }
} finally {
    Pop-Location
}
