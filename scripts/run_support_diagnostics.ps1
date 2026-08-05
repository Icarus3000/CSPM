param(
    [string]$ProjectRoot,
    [string]$OutputRoot,
    [switch]$RebuildVenv
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $ProjectRoot "logs\support_diagnostics"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $ProjectRoot $OutputRoot
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bundleDir = Join-Path $OutputRoot "diagnostics_$timestamp"
New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null

$summaryPath = Join-Path $bundleDir "summary.txt"
$workbookTextPath = Join-Path $bundleDir "workbook_integrity.txt"
$workbookJsonPath = Join-Path $bundleDir "workbook_integrity.json"
$gitStatusPath = Join-Path $bundleDir "git_status.txt"
$gitHeadPath = Join-Path $bundleDir "git_head.txt"

$checker = Join-Path $PSScriptRoot "check_workbook_integrity.ps1"
$workbookExitCode = 1

if (Test-Path -LiteralPath $checker -PathType Leaf) {
    $checkerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $checker,
        "-ProjectRoot",
        $ProjectRoot,
        "-Output",
        $workbookJsonPath
    )
    if ($RebuildVenv) {
        $checkerArgs += "-RebuildVenv"
    }

    & "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" @checkerArgs *> $workbookTextPath
    $workbookExitCode = $LASTEXITCODE
} else {
    Set-Content -LiteralPath $workbookTextPath -Value "Missing workbook integrity wrapper: $checker" -Encoding UTF8
}

Push-Location $ProjectRoot
try {
    & git status --short *> $gitStatusPath
    & git log -1 --oneline *> $gitHeadPath
}
finally {
    Pop-Location
}

$summary = @(
    "CSPM support diagnostics",
    "Created: $(Get-Date -Format o)",
    "ProjectRoot: $ProjectRoot",
    "OutputDir: $bundleDir",
    "WorkbookIntegrityExitCode: $workbookExitCode",
    "",
    "Files:",
    "  summary.txt",
    "  workbook_integrity.txt",
    "  workbook_integrity.json",
    "  git_status.txt",
    "  git_head.txt"
)
Set-Content -LiteralPath $summaryPath -Value $summary -Encoding UTF8

Write-Host "[DIAGNOSTICS] Output: $bundleDir"
Write-Host "[DIAGNOSTICS] Workbook integrity exit code: $workbookExitCode"

exit $workbookExitCode
