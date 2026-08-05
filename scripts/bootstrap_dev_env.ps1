param(
    [string]$ProjectRoot,
    [switch]$ForceRebuild,
    [switch]$PassThruPython
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$ensureParams = @{
    ProjectRoot = $ProjectRoot
    InstallRequirements = $true
    InstallDevRequirements = $true
    PassThruPython = $true
}
if ($ForceRebuild) {
    $ensureParams.ForceRebuild = $true
}

$pythonOutput = & (Join-Path $PSScriptRoot "ensure_venv.ps1") @ensureParams
if ($LASTEXITCODE -ne 0) {
    throw "Unable to bootstrap project virtual environment."
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
    throw "Unable to resolve project Python runtime."
}

$bootstrapRoot = Join-Path $ProjectRoot "outputs\bootstrap"
if (-not (Test-Path -LiteralPath $bootstrapRoot)) {
    New-Item -ItemType Directory -Path $bootstrapRoot | Out-Null
}

$null = & (Join-Path $PSScriptRoot "ensure_pytest_cache.ps1") -ProjectRoot $ProjectRoot
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot "outputs\pycache\bootstrap"

Write-Host "[BOOTSTRAP] Python: $pythonExe"

& $pythonExe -c "import PySide6, pytest, pyright, yaml, openpyxl, reportlab; print('BOOTSTRAP_OK')" *> (Join-Path $bootstrapRoot "python_probe.log")
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency probe failed. See outputs/bootstrap/python_probe.log"
}

& $pythonExe -m pyright --version *> (Join-Path $bootstrapRoot "pyright_probe.log")
if ($LASTEXITCODE -ne 0) {
    throw "Pyright probe failed. See outputs/bootstrap/pyright_probe.log"
}

$qmllintCommand = "& .\qmllint.ps1 -Targets @('src/qml/Main.qml')"
& "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command $qmllintCommand *> (Join-Path $bootstrapRoot "qmllint_probe.log")
if ($LASTEXITCODE -ne 0) {
    throw "qmllint probe failed. See outputs/bootstrap/qmllint_probe.log"
}

Write-Host "[BOOTSTRAP] PASS"
if ($PassThruPython) {
    Write-Output $pythonExe
}
