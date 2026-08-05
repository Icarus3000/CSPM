param(
    [string]$ProjectRoot,
    [string]$WorkbookPath,
    [string]$SchemaPath,
    [string]$Output,
    [switch]$Json,
    [switch]$WarnAsError,
    [switch]$RebuildVenv
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$ensureScript = Join-Path $PSScriptRoot "ensure_venv.ps1"
if (-not (Test-Path -LiteralPath $ensureScript)) {
    throw "Missing venv bootstrap script: $ensureScript"
}

$ensureParams = @{
    ProjectRoot = $ProjectRoot
    InstallRequirements = $true
    PassThruPython = $true
}
if ($RebuildVenv) {
    $ensureParams.ForceRebuild = $true
}

$pythonOutput = & $ensureScript @ensureParams
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

$checker = Join-Path $PSScriptRoot "check_workbook_integrity.py"
if (-not (Test-Path -LiteralPath $checker)) {
    throw "Missing workbook integrity checker: $checker"
}

$argsList = @(
    $checker,
    "--project-root",
    $ProjectRoot
)
if (-not [string]::IsNullOrWhiteSpace($WorkbookPath)) {
    $argsList += "--workbook"
    $argsList += $WorkbookPath
}
if (-not [string]::IsNullOrWhiteSpace($SchemaPath)) {
    $argsList += "--schema"
    $argsList += $SchemaPath
}
if (-not [string]::IsNullOrWhiteSpace($Output)) {
    $argsList += "--output"
    $argsList += $Output
}
if ($Json) {
    $argsList += "--json"
}
if ($WarnAsError) {
    $argsList += "--warn-as-error"
}

Write-Host "[WORKBOOK] Python: $pythonExe"
Write-Host "[WORKBOOK] Project: $ProjectRoot"

& $pythonExe @argsList
exit $LASTEXITCODE
