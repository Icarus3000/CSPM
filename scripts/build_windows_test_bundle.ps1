param(
    [string]$OutputRoot = "dist",
    [string]$BundleName = "CSPM-TestBundle",
    [switch]$NoZip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[CSPM-BUILD] $Message"
}

function Assert-Exists([string]$Path, [string]$Label) {
    if (-not (Test-Path -Path $Path)) {
        throw "$Label not found: $Path"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRootAbs = (Join-Path $repoRoot $OutputRoot)
$bundleDir = Join-Path $outputRootAbs $BundleName
$runtimeDir = Join-Path $bundleDir "runtime"
$launcherSource = Join-Path $bundleDir "CSPMLauncher.cs"
$launcherExe = Join-Path $bundleDir "CSPM.exe"
$zipPath = Join-Path $outputRootAbs ("{0}.zip" -f $BundleName)

New-Item -ItemType Directory -Path $outputRootAbs -Force | Out-Null
if (Test-Path $bundleDir) {
    Write-Step "Removing previous bundle: $bundleDir"
    Remove-Item -Path $bundleDir -Recurse -Force
}
if ((-not $NoZip) -and (Test-Path $zipPath)) {
    Remove-Item -Path $zipPath -Force
}

Write-Step "Resolving Python runtime"
$pythonCmd = Get-Command python -ErrorAction Stop
$pythonExe = $pythonCmd.Source
$pythonRoot = Split-Path -Parent $pythonExe

Assert-Exists $pythonExe "Python executable"
Assert-Exists (Join-Path $pythonRoot "pythonw.exe") "pythonw.exe"
Assert-Exists (Join-Path $pythonRoot "Lib") "Python Lib directory"

Write-Step "Creating bundle directories"
New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

Write-Step "Copying Python runtime (this can take a while)"
$runtimeTopFiles = @(
    "python.exe",
    "pythonw.exe",
    "python3.dll",
    "python314.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "ucrtbase.dll"
)
foreach ($file in $runtimeTopFiles) {
    $src = Join-Path $pythonRoot $file
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $runtimeDir -Force
    }
}

$runtimeDirs = @("Lib", "DLLs", "libs")
foreach ($dir in $runtimeDirs) {
    $srcDir = Join-Path $pythonRoot $dir
    if (Test-Path $srcDir) {
        Copy-Item -Path $srcDir -Destination $runtimeDir -Recurse -Force
    }
}

Write-Step "Copying application files"
$projectDirs = @("src", "assets", "schema", "data", "docs")
foreach ($dir in $projectDirs) {
    $srcDir = Join-Path $repoRoot $dir
    Assert-Exists $srcDir "Project directory"
    Copy-Item -Path $srcDir -Destination $bundleDir -Recurse -Force
}

$projectFiles = @("requirements.txt", "user_settings.json")
foreach ($file in $projectFiles) {
    $srcFile = Join-Path $repoRoot $file
    if (Test-Path $srcFile) {
        Copy-Item -Path $srcFile -Destination $bundleDir -Force
    }
}

Write-Step "Resolving launcher source"
$projectLauncherSource = Join-Path $repoRoot "src\csharp\Launcher.cs"
Assert-Exists $projectLauncherSource "C# Launcher source file"
Copy-Item -Path $projectLauncherSource -Destination $launcherSource -Force

Write-Step "Compiling launcher exe"
$cscCandidates = @(
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$cscPath = $null
foreach ($candidate in $cscCandidates) {
    if (Test-Path $candidate) {
        $cscPath = $candidate
        break
    }
}
if (-not $cscPath) {
    throw "C# compiler (csc.exe) not found."
}

$iconPath = Join-Path $repoRoot "src\assets\app_icon.ico"
& $cscPath "/nologo" "/target:winexe" "/optimize+" "/win32icon:$iconPath" "/out:$launcherExe" "$launcherSource"
Assert-Exists $launcherExe "Launcher executable"

Remove-Item -Path $launcherSource -Force

Write-Step "Writing debug launcher script"
$debugCmd = @'
@echo off
setlocal
set "APP_ROOT=%~dp0"
set "PYTHONHOME=%APP_ROOT%runtime"
set "PYTHONPATH=%APP_ROOT%src\python"
"%APP_ROOT%runtime\python.exe" "%APP_ROOT%src\python\main.py"
endlocal
'@
Set-Content -Path (Join-Path $bundleDir "run_debug_console.cmd") -Value $debugCmd -Encoding ASCII

if (-not $NoZip) {
    Write-Step "Creating zip archive"
    Compress-Archive -Path (Join-Path $bundleDir "*") -DestinationPath $zipPath -Force
    Assert-Exists $zipPath "Bundle archive"
}

Write-Step "Bundle ready"
Write-Host "Bundle directory: $bundleDir"
if (-not $NoZip) {
    Write-Host "Bundle archive:   $zipPath"
}
