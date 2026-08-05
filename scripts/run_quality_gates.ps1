param(
    [string]$ProjectRoot,
    [switch]$RebuildVenv,
    [switch]$UpdateQmlBaseline,
    [switch]$UpdatePyrightBaseline,
    [switch]$RepairHygiene,
    [switch]$SkipPyright,
    [switch]$SkipPytest,
    [switch]$SkipWorkbookIntegrity,
    [switch]$WorkbookWarnAsError
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$ensureScript = Join-Path $PSScriptRoot "ensure_venv.ps1"
$ensureParams = @{
    ProjectRoot = $ProjectRoot
    InstallRequirements = $true
    InstallDevRequirements = $true
    PassThruPython = $true
}
if ($RebuildVenv) {
    $ensureParams.ForceRebuild = $true
}

$pythonOutput = & $ensureScript @ensureParams
if ($LASTEXITCODE -ne 0) {
    throw "Failed to resolve project Python runtime."
}
$pythonExe = $null
foreach ($line in @($pythonOutput)) {
    $candidate = [string]$line
    if ($candidate -match "([A-Za-z]:\\.*python\.exe)$") {
        $pythonExe = $matches[1]
    }
}
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    $pythonExe = [string]$pythonOutput
}
$pythonExe = $pythonExe.Trim()
if ([string]::IsNullOrWhiteSpace($pythonExe)) {
    throw "Failed to resolve project Python runtime."
}

$tmpTag = if ($env:USERNAME) { $env:USERNAME } else { "user" }
$tmpRoot = Join-Path $ProjectRoot ("outputs\pytest_tmp\run_" + $tmpTag + "_" + $PID)
$null = & (Join-Path $PSScriptRoot "ensure_pytest_cache.ps1") -ProjectRoot $ProjectRoot
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot "outputs\pycache\quality"
$env:CSPM_PYTEST_TMP_BASE = $tmpRoot
$env:TMP = $tmpRoot
$env:TEMP = $tmpRoot
$env:TMPDIR = $tmpRoot

Write-Host "[GATES] Python: $pythonExe"
Write-Host "[GATES] TMP root: $tmpRoot"

Push-Location $ProjectRoot
try {
    if ($RepairHygiene) {
        Write-Host "[GATES] hygiene repair"
        & (Join-Path $PSScriptRoot "repair_repo_hygiene.ps1") -ProjectRoot $ProjectRoot
        if ($LASTEXITCODE -ne 0) { throw "Repo hygiene repair failed." }
    }

    Write-Host "[GATES] hygiene"
    & $pythonExe "scripts/check_repo_hygiene.py"
    if ($LASTEXITCODE -ne 0) { throw "Repo hygiene gate failed." }

    Write-Host "[GATES] compileall"
    & $pythonExe -m compileall -q src/python
    if ($LASTEXITCODE -ne 0) { throw "Python compileall failed." }

    if (-not $SkipWorkbookIntegrity) {
        Write-Host "[GATES] workbook integrity"
        $workbookIntegrityArgs = @(
            "-ProjectRoot",
            $ProjectRoot
        )
        if ($WorkbookWarnAsError) {
            $workbookIntegrityArgs += "-WarnAsError"
        }
        & "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File (Join-Path $PSScriptRoot "check_workbook_integrity.ps1") `
            @workbookIntegrityArgs
        if ($LASTEXITCODE -ne 0) { throw "Workbook integrity gate failed." }
    }

    $qmlTargets = @(
        "src/qml/Main.qml",
        "src/qml/BootstrapRoot.qml",
        "src/qml/DetachedShellWindow.qml",
        "src/qml/views/MainContent.qml",
        "src/qml/views/TimeDocketView.qml",
        "src/qml/views/TransactionsMasterView.qml",
        "src/qml/views/TrademarkFilingView.qml",
        "src/qml/views/PlaceholderSubmenuView.qml",
        "src/qml/components/JellyCalendar.qml",
        "src/qml/windows/FloatingDocketWindow.qml"
    )
    $quotedTargets = ($qmlTargets | ForEach-Object { "'$_'" }) -join ","
    $qmlLog = Join-Path $ProjectRoot "logs\quality_qmllint.log"

    Write-Host "[GATES] qmllint"
    $qmllintCommand = "& .\qmllint.ps1 -Targets @($quotedTargets)"
    & "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command $qmllintCommand *> $qmlLog
    if ($LASTEXITCODE -ne 0) { throw "qmllint execution failed. See $qmlLog" }

    Write-Host "[GATES] qmllint baseline check"
    $baselineArgs = @(
        "scripts/check_qmllint_warnings.py",
        "--log", "logs/quality_qmllint.log",
        "--baseline", "docs/quality/qmllint_warning_baseline.txt"
    )
    if ($UpdateQmlBaseline) {
        $baselineArgs += "--update-baseline"
    }
    & $pythonExe @baselineArgs
    if ($LASTEXITCODE -ne 0) { throw "qmllint warning gate failed." }

    if (-not $SkipPyright) {
        Write-Host "[GATES] pyright"
        & $pythonExe -c "import pyright" 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "pyright is not installed in the project venv. Install optional dev tools with: `"$pythonExe`" -m pip install -r requirements-dev.txt"
        }
        $pyrightLog = Join-Path $ProjectRoot "logs\quality_pyright.json"
        & (Join-Path $PSScriptRoot "run_pyright.ps1") -ProjectRoot $ProjectRoot -OutputJson *> $pyrightLog
        if ($LASTEXITCODE -ne 0) {
            # The wrapper returns pyright's exit code; keep the JSON and continue to baseline evaluation.
            if (-not (Test-Path -LiteralPath $pyrightLog)) {
                throw "pyright execution failed before producing output."
            }
        }
        $pyrightBaselineArgs = @(
            "scripts/check_pyright_baseline.py",
            "--json", "logs/quality_pyright.json",
            "--baseline", "docs/quality/pyright_issue_baseline.txt"
        )
        if ($UpdatePyrightBaseline) {
            $pyrightBaselineArgs += "--update-baseline"
        }
        & $pythonExe @pyrightBaselineArgs
        if ($LASTEXITCODE -ne 0) { throw "pyright gate failed." }
    }

    if (-not $SkipPytest) {
        Write-Host "[GATES] pytest"
        & $pythonExe -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw "pytest failed." }
    }

    Write-Host "[GATES] PASS"
}
finally {
    Pop-Location
}
