param(
    [switch]$ForceRebuild,
    [switch]$SetupOnly,
    [switch]$SetupFlutter,
    [switch]$ExpertFlutter,
    [switch]$FlutterDebug,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$EnsureScript = Join-Path $ProjectRoot "scripts\ensure_venv.ps1"
$EnsureFlutterScript = Join-Path $ProjectRoot "scripts\ensure_flutter.ps1"
$MainScript = Join-Path $ProjectRoot "src\python\main.py"
$ExpertFlutterDir = Join-Path $ProjectRoot "expert_flutter"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CSPM Launcher ($env:COMPUTERNAME / $env:USERNAME)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $EnsureScript)) {
    Write-Error "Missing ensure script: $EnsureScript"
    exit 1
}

function Invoke-ExpertFlutter {
    param(
        [string]$ResolvedFlutterExe = ""
    )
    if (-not (Test-Path -LiteralPath $EnsureFlutterScript)) {
        Write-Error "Missing Flutter ensure script: $EnsureFlutterScript"
        exit 1
    }
    $flutterExe = $ResolvedFlutterExe
    if ([string]::IsNullOrWhiteSpace($flutterExe)) {
        $flutterExe = & $EnsureFlutterScript -ProjectRoot $ProjectRoot -InstallIfMissing -EnableWindowsDesktop -PassThruFlutter
    }
    $flutterExe = ([string]$flutterExe).Trim()
    if (-not $flutterExe -or -not (Test-Path -LiteralPath $flutterExe)) {
        Write-Error "Unable to resolve a working Flutter executable."
        exit 1
    }
    if (-not (Test-Path -LiteralPath $ExpertFlutterDir)) {
        Write-Error "Missing Expert Flutter app folder: $ExpertFlutterDir"
        exit 1
    }

    function Get-ExpertFlutterNewestInputUtc {
        $inputs = @()
        $libDir = Join-Path $ExpertFlutterDir "lib"
        $testDir = Join-Path $ExpertFlutterDir "test"
        $windowsDir = Join-Path $ExpertFlutterDir "windows"
        $pubspecPath = Join-Path $ExpertFlutterDir "pubspec.yaml"
        $lockPath = Join-Path $ExpertFlutterDir "pubspec.lock"

        foreach ($path in @($libDir, $testDir, $windowsDir)) {
            if (Test-Path -LiteralPath $path) {
                $inputs += @(Get-ChildItem -LiteralPath $path -Recurse -File -ErrorAction SilentlyContinue)
            }
        }
        foreach ($path in @($pubspecPath, $lockPath)) {
            if (Test-Path -LiteralPath $path) {
                $inputs += @(Get-Item -LiteralPath $path)
            }
        }

        if ($inputs.Count -eq 0) {
            return [DateTime]::MinValue
        }
        return ($inputs | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
    }

    Push-Location $ExpertFlutterDir
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $ExpertFlutterDir "windows"))) {
            Write-Host "Generating Flutter Windows runner..." -ForegroundColor Cyan
            & $flutterExe create --platforms=windows --project-name cspm_expert_flutter .
            if ($LASTEXITCODE -ne 0) {
                throw "flutter create failed with exit code $LASTEXITCODE"
            }
        }
        Write-Host "Resolving Flutter packages..." -ForegroundColor Cyan
        & $flutterExe pub get
        if ($LASTEXITCODE -ne 0) {
            throw "flutter pub get failed with exit code $LASTEXITCODE"
        }
        if ($FlutterDebug) {
            Write-Host "Launching Expert Flutter preview in debug mode..." -ForegroundColor Cyan
            & $flutterExe run -d windows
            exit $LASTEXITCODE
        }

        $releaseExe = Join-Path $ExpertFlutterDir "build\windows\x64\runner\Release\cspm_expert_flutter.exe"
        $buildNeeded = $ForceRebuild -or -not (Test-Path -LiteralPath $releaseExe)
        if (-not $buildNeeded) {
            $newestInput = Get-ExpertFlutterNewestInputUtc
            $releaseItem = Get-Item -LiteralPath $releaseExe
            $buildNeeded = $newestInput -gt $releaseItem.LastWriteTimeUtc
        }
        if ($buildNeeded) {
            Write-Host "Building Expert Flutter release preview..." -ForegroundColor Cyan
            & $flutterExe build windows --release
            if ($LASTEXITCODE -ne 0) {
                throw "flutter build windows --release failed with exit code $LASTEXITCODE"
            }
        } else {
            Write-Host "Using existing Expert Flutter release build." -ForegroundColor Green
        }

        if (-not (Test-Path -LiteralPath $releaseExe)) {
            throw "Expert Flutter release executable was not found: $releaseExe"
        }
        Write-Host "Launching Expert Flutter release preview..." -ForegroundColor Cyan
        Start-Process -FilePath $releaseExe -WorkingDirectory (Split-Path -Parent $releaseExe)
        exit 0
    } finally {
        Pop-Location
    }
}

if ($SetupFlutter -or $ExpertFlutter) {
    if (-not (Test-Path -LiteralPath $EnsureFlutterScript)) {
        Write-Error "Missing Flutter ensure script: $EnsureFlutterScript"
        exit 1
    }
    $flutterExe = & $EnsureFlutterScript -ProjectRoot $ProjectRoot -InstallIfMissing -EnableWindowsDesktop -PassThruFlutter
    $flutterExe = ([string]$flutterExe).Trim()
    if (-not $flutterExe -or -not (Test-Path -LiteralPath $flutterExe)) {
        Write-Error "Unable to resolve a working Flutter executable."
        exit 1
    }
    Write-Host "Using Flutter: $flutterExe" -ForegroundColor Green
    if ($SetupFlutter -and -not $ExpertFlutter) {
        Write-Host "Flutter setup complete." -ForegroundColor Green
        return
    }
    Invoke-ExpertFlutter -ResolvedFlutterExe $flutterExe
    return
}

try {
    $pythonOutput = & $EnsureScript -ProjectRoot $ProjectRoot -ForceRebuild:$ForceRebuild -InstallRequirements -PassThruPython
    $PythonExe = $null
    foreach ($line in @($pythonOutput)) {
        $candidate = [string]$line
        if ($candidate -match "([A-Za-z]:\\.*python\.exe)$") {
            $PythonExe = $matches[1]
        }
    }
    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        $PythonExe = [string]$pythonOutput
    }
    $PythonExe = $PythonExe.Trim()
    if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe)) {
        throw "Unable to resolve a working project Python interpreter."
    }
} catch {
    Write-Error $_
    Read-Host "Launch failed. Press Enter to close..."
    exit 1
}

Write-Host "Using interpreter: $PythonExe" -ForegroundColor Green
if ($SetupOnly) {
    Write-Host "Setup complete." -ForegroundColor Green
    return
}

$transcriptPath = Join-Path $ProjectRoot "logs\powershell_verbose_run.log"
New-Item -ItemType Directory -Path (Join-Path $ProjectRoot "logs") -Force -ErrorAction SilentlyContinue | Out-Null
$transcriptStarted = $false
try {
    Start-Transcript -Path $transcriptPath -Force -ErrorAction Stop | Out-Null
    $transcriptStarted = $true
} catch {
    Write-Warning "PowerShell transcript logging is unavailable in this host; continuing launch without transcript. $($_.Exception.Message)"
}

$env:CSPM_SPLASH_WEBENGINE = "1"
$env:CSPM_SPLASH_FORCE_WEBENGINE = "1"
$env:CSPM_SPLASH_WEBVIEW = "0"
$env:CSPM_SPLASH_LOGO_VARIANT = "animated"
$env:CSPM_PREINIT_WEBENGINE = "1"
$env:CSPM_SPLASH_TOTAL_MS = "500"

trap {
    if (Test-Path -LiteralPath $transcriptPath) {
        $transcriptContent = Get-Content -LiteralPath $transcriptPath -ErrorAction SilentlyContinue
        if ($transcriptContent) {
            try { $transcriptContent -join "`r`n" | Set-Clipboard } catch {}
        }
    }
    continue
}

try {
    Write-Host "Launching application..." -ForegroundColor Cyan
    $capturedOutput = @()
    & $PythonExe $MainScript @AppArgs 2>&1 | Tee-Object -Variable capturedOutput
    $AppExitCode = $LASTEXITCODE
} finally {
    if ($transcriptStarted) {
        Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
    }
    
    $finalOutput = ""
    if ($capturedOutput -and $capturedOutput.Count -gt 0) {
        $finalOutput = $capturedOutput -join "`r`n"
    } elseif (Test-Path -LiteralPath $transcriptPath) {
        $transcriptContent = Get-Content -LiteralPath $transcriptPath -ErrorAction SilentlyContinue
        if ($transcriptContent) {
            $finalOutput = $transcriptContent -join "`r`n"
        }
    }

    if (![string]::IsNullOrWhiteSpace($finalOutput)) {
        try {
            Set-Clipboard -Value $finalOutput -ErrorAction Stop
            Write-Host "Console output has been automatically copied to your clipboard!" -ForegroundColor Yellow
        } catch {
            try {
                $finalOutput | clip.exe
                Write-Host "Console output has been automatically copied to your clipboard!" -ForegroundColor Yellow
            } catch {}
        }
    }
}

if ($AppExitCode -ne 0) {
    Write-Host "Application exited with code $AppExitCode" -ForegroundColor Red
    Read-Host "Press Enter to close..."
    exit $AppExitCode
} else {
    Write-Host "Application closed." -ForegroundColor Green
    Remove-Item -LiteralPath $transcriptPath -ErrorAction SilentlyContinue
}
