param(
    [string]$ProjectRoot,
    [switch]$RebuildVenv,
    [switch]$InstallRequirements,
    [switch]$OutputJson,
    [string]$JsonOut = "logs\\quality_pyright.json",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PyrightArgs
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$ensureParams = @{
    ProjectRoot = $ProjectRoot
    PassThruPython = $true
}
if ($InstallRequirements) {
    $ensureParams.InstallRequirements = $true
    $ensureParams.InstallDevRequirements = $true
}
if ($RebuildVenv) {
    $ensureParams.ForceRebuild = $true
}

$pythonOutput = & (Join-Path $PSScriptRoot "ensure_venv.ps1") @ensureParams
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve project Python runtime."
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

$venvDir = Split-Path -Parent (Split-Path -Parent $pythonExe)
$venvName = Split-Path -Leaf $venvDir
$runtimeConfig = Join-Path $ProjectRoot ".pyrightconfig.runtime.json"
$runtimeConfigDir = Split-Path -Parent $runtimeConfig
if (-not (Test-Path -LiteralPath $runtimeConfigDir)) {
    New-Item -ItemType Directory -Path $runtimeConfigDir | Out-Null
}

$configJson = @"
{
  "include": ["src/python"],
  "exclude": ["archive", "backups", "dumps", "dist", "outputs", "**/__pycache__"],
  "extraPaths": ["src/python"],
  "typeCheckingMode": "basic",
  "venvPath": ".",
  "venv": "$venvName"
}
"@
Set-Content -LiteralPath $runtimeConfig -Value $configJson -Encoding ascii

$args = @("-m", "pyright", "-p", $runtimeConfig)
if ($OutputJson) {
    $args += "--outputjson"
}
if ($PyrightArgs) {
    $args += $PyrightArgs
}

& $pythonExe @args
exit $LASTEXITCODE
