param(
    [string]$ProjectRoot,
    [switch]$RebuildVenv,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$EnsureScript = Join-Path $PSScriptRoot "ensure_venv.ps1"
if (-not (Test-Path -LiteralPath $EnsureScript)) {
    throw "Missing venv bootstrap script: $EnsureScript"
}

$ensureParams = @{
    ProjectRoot = $ProjectRoot
    InstallRequirements = $true
    InstallDevRequirements = $true
    PassThruPython = $true
}
if ($RebuildVenv) {
    $ensureParams.ForceRebuild = $true
}

$pythonOutput = & $EnsureScript @ensureParams
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve a working project Python runtime."
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
    throw "Unable to resolve a working project Python runtime."
}

$tmpTag = if ($env:USERNAME) { $env:USERNAME } else { "user" }
$tmpRoot = Join-Path $ProjectRoot ("outputs\pytest_tmp\run_" + $tmpTag + "_" + $PID)
$null = & (Join-Path $PSScriptRoot "ensure_pytest_cache.ps1") -ProjectRoot $ProjectRoot
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot "outputs\pycache\pytest"
$env:CSPM_PYTEST_TMP_BASE = $tmpRoot
$env:TMP = $tmpRoot
$env:TEMP = $tmpRoot
$env:TMPDIR = $tmpRoot

Write-Host "[PYTEST] Python: $pythonExe"
Write-Host "[PYTEST] TMP root: $tmpRoot"

if (-not $PytestArgs -or $PytestArgs.Count -eq 0) {
    $PytestArgs = @("tests", "-q")
}

& $pythonExe -m pytest @PytestArgs
exit $LASTEXITCODE
