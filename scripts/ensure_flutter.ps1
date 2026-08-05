param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$InstallIfMissing,
    [switch]$EnableWindowsDesktop,
    [switch]$PassThruFlutter
)

$ErrorActionPreference = "Stop"

function Resolve-FlutterExecutable {
    $pathFlutter = Get-Command flutter -ErrorAction SilentlyContinue
    if ($pathFlutter -and $pathFlutter.Source) {
        return $pathFlutter.Source
    }

    $localRoot = Join-Path $env:LOCALAPPDATA "CSPM\flutter\flutter"
    $localFlutter = Join-Path $localRoot "bin\flutter.bat"
    if (Test-Path -LiteralPath $localFlutter) {
        return $localFlutter
    }

    return $null
}

function Install-LocalFlutter {
    $installParent = Join-Path $env:LOCALAPPDATA "CSPM\flutter"
    $installRoot = Join-Path $installParent "flutter"
    $flutterBat = Join-Path $installRoot "bin\flutter.bat"

    if (Test-Path -LiteralPath $flutterBat) {
        return $flutterBat
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        throw "Flutter setup requires Git. Install Git for Windows, then rerun .\launch.ps1 -SetupFlutter."
    }

    New-Item -ItemType Directory -Force -Path $installParent | Out-Null
    if (Test-Path -LiteralPath $installRoot) {
        Remove-Item -LiteralPath $installRoot -Recurse -Force
    }

    Write-Host "Installing Flutter SDK stable branch into $installRoot ..." -ForegroundColor Cyan
    & $git.Source clone --depth 1 --branch stable https://github.com/flutter/flutter.git $installRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter SDK clone failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path -LiteralPath $flutterBat)) {
        throw "Flutter install completed but flutter.bat was not found at $flutterBat"
    }
    return $flutterBat
}

$flutterExe = Resolve-FlutterExecutable
if (-not $flutterExe) {
    if (-not $InstallIfMissing) {
        throw "Flutter is not installed. Rerun with -InstallIfMissing or use .\launch.ps1 -SetupFlutter."
    }
    $flutterExe = Install-LocalFlutter
}

$flutterBin = Split-Path -Parent $flutterExe
if ($env:PATH -notlike "*$flutterBin*") {
    $env:PATH = "$flutterBin;$env:PATH"
}

if ($EnableWindowsDesktop) {
    Write-Host "Enabling Flutter Windows desktop support..." -ForegroundColor Cyan
    & $flutterExe config --enable-windows-desktop | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "flutter config --enable-windows-desktop failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Running flutter doctor -v..." -ForegroundColor Cyan
& $flutterExe doctor -v | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Warning "flutter doctor reported issues. Windows desktop builds usually require Visual Studio with the Desktop development with C++ workload."
}

if ($PassThruFlutter) {
    Write-Output $flutterExe
}
