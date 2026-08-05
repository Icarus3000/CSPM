param(
    [string[]]$Targets = @("src/qml"),
    [switch]$InstallIfMissing,
    [switch]$FailOnWarnings
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$script:SkippedQmlLintCandidates = New-Object System.Collections.Generic.List[object]

$ensureScript = Join-Path $repoRoot "scripts\ensure_venv.ps1"

function Get-QmlLintCandidates {
    $paths = New-Object System.Collections.Generic.List[string]

    # Prefer workspace-local virtual environments first so tooling is
    # project-portable and not tied to a machine-global Python install.
    $venvRoots = Get-ChildItem -Path $repoRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like ".venv*" -or $_.Name -like "venv*" } |
        Sort-Object -Property Name
    foreach ($root in $venvRoots) {
        $wrapper = Join-Path $root.FullName "Scripts\pyside6-qmllint.exe"
        $direct = Join-Path $root.FullName "Lib\site-packages\PySide6\qmllint.exe"
        if (Test-Path $wrapper) {
            $paths.Add($wrapper) | Out-Null
        }
        if (Test-Path $direct) {
            $paths.Add($direct) | Out-Null
        }
    }

    $globalCmd = Get-Command qmllint -ErrorAction SilentlyContinue
    if ($globalCmd) {
        $paths.Add($globalCmd.Source) | Out-Null
    }
    $globalPythonRoots = Get-ChildItem -Path (Join-Path $env:LocalAppData "Programs\Python") -Directory -ErrorAction SilentlyContinue |
        Sort-Object -Property Name -Descending
    foreach ($root in $globalPythonRoots) {
        $wrapper = Join-Path $root.FullName "Scripts\pyside6-qmllint.exe"
        $direct = Join-Path $root.FullName "Lib\site-packages\PySide6\qmllint.exe"
        if (Test-Path $wrapper) {
            $paths.Add($wrapper) | Out-Null
        }
        if (Test-Path $direct) {
            $paths.Add($direct) | Out-Null
        }
    }
    return @($paths | Select-Object -Unique)
}

function Test-QmlLintPath {
    param([string]$ToolPath)
    if (-not $ToolPath) { return $false }
    if (-not (Test-Path $ToolPath)) { return $false }

    # On Windows, raw qmllint.exe compiled as a GUI application pops up a MessageBox dialog on --version.
    # To prevent any interactive GUI popups, we trust the file if it exists and is non-empty.
    if ($env:OS -match "Windows") {
        $fileObj = Get-Item -LiteralPath $ToolPath -ErrorAction SilentlyContinue
        if ($fileObj -and $fileObj.Length -gt 0) {
            return $true
        }
    }

    $probeCmd = '"' + $ToolPath + '" --version'
    $probeOutput = & cmd /d /c "$probeCmd 2>&1"
    $probeCode = $LASTEXITCODE
    if ($probeCode -eq 0) {
        return $true
    }
    $probeText = ($probeOutput | Out-String)
    if ($probeText -match "Access is denied|cannot be loaded|not recognized|The system cannot find the file specified") {
        $script:SkippedQmlLintCandidates.Add([pscustomobject]@{
            Path = $ToolPath
            Reason = ($probeText.Trim() -replace '\s+', ' ')
            ExitCode = $probeCode
        }) | Out-Null
        return $false
    }
    $script:SkippedQmlLintCandidates.Add([pscustomobject]@{
        Path = $ToolPath
        Reason = "probe failed"
        ExitCode = $probeCode
    }) | Out-Null
    return $false
}

function Resolve-QmlLintPath {
    $candidates = Get-QmlLintCandidates
    foreach ($candidate in $candidates) {
        if (Test-QmlLintPath -ToolPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Get-QmlLintSkipSummary {
    return @($script:SkippedQmlLintCandidates | ForEach-Object {
        $reason = if ($_.Reason) { $_.Reason } else { "probe failed" }
        "  - $($_.Path) (exit=$($_.ExitCode)): $reason"
    }) -join [Environment]::NewLine
}

$qmlLintPath = Resolve-QmlLintPath

if (-not $qmlLintPath) {
    $skipSummary = Get-QmlLintSkipSummary
    if (-not $InstallIfMissing) {
        $message = "[QMLLINT] Lint tool not found. Re-run with -InstallIfMissing."
        if ($skipSummary) {
            $message += [Environment]::NewLine + "[QMLLINT] Probed but could not run:" + [Environment]::NewLine + $skipSummary
        }
        Write-Error $message
        exit 1
    }
    if (-not (Test-Path $ensureScript)) {
        Write-Error "[QMLLINT] Missing ensure_venv bootstrap at '$ensureScript'."
        exit 1
    }
    Write-Host "[QMLLINT] Tool missing in workspace venvs; bootstrapping project environment..."
    & $ensureScript -ProjectRoot $repoRoot -InstallRequirements
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    $qmlLintPath = Resolve-QmlLintPath
    if (-not $qmlLintPath) {
        $skipSummary = Get-QmlLintSkipSummary
        $message = "[QMLLINT] Install completed but qmllint was still not found."
        if ($skipSummary) {
            $message += [Environment]::NewLine + "[QMLLINT] Probed but could not run:" + [Environment]::NewLine + $skipSummary
        }
        Write-Error $message
        exit 1
    }
}

$qmlFiles = @()
foreach ($target in $Targets) {
    $targetPath = Join-Path $repoRoot $target
    if (-not (Test-Path $targetPath)) {
        Write-Warning "[QMLLINT] Skipping missing target: $target"
        continue
    }
    if ((Get-Item $targetPath) -is [System.IO.FileInfo]) {
        if ($targetPath.ToLowerInvariant().EndsWith(".qml")) {
            $qmlFiles += (Resolve-Path $targetPath).Path
        }
        continue
    }
    $qmlFiles += Get-ChildItem -Path $targetPath -Recurse -Filter *.qml | ForEach-Object { $_.FullName }
}

$qmlFiles = @($qmlFiles | Sort-Object -Unique)
if (-not $qmlFiles -or $qmlFiles.Count -eq 0) {
    Write-Error "[QMLLINT] No QML files found for targets: $($Targets -join ', ')"
    exit 1
}

$lintArgs = @()
if (-not $FailOnWarnings) {
    $lintArgs += @("-W", "-1")
}
$lintArgs += $qmlFiles

$toolName = Split-Path -Leaf $qmlLintPath
Write-Host "[QMLLINT] Running $toolName on $($qmlFiles.Count) file(s)..."

$quotedArgs = @()
foreach ($arg in $lintArgs) {
    $safeArg = $arg -replace '"', '\"'
    $quotedArgs += '"' + $safeArg + '"'
}
$cmdLine = '"' + $qmlLintPath + '" ' + ($quotedArgs -join ' ')

$lintOutput = & cmd /d /c "$cmdLine 2>&1"
$exitCode = $LASTEXITCODE

if ($lintOutput) {
    $lintOutput | ForEach-Object { $_ }
}

exit $exitCode
