param(
    [string]$ProjectRoot,
    [switch]$NoArchive
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$archiveRoot = Join-Path $ProjectRoot ("archive\repo_hygiene_lockdown_" + $timestamp)

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Move-IntoArchive {
    param([string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return $false
    }
    if ($NoArchive) {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force -ErrorAction Stop
        return $true
    }
    $resolved = (Resolve-Path -LiteralPath $LiteralPath).Path
    $relative = $resolved.Substring($ProjectRoot.Length).TrimStart('\')
    $target = Join-Path $archiveRoot $relative
    Ensure-Dir (Split-Path -Parent $target)
    Move-Item -LiteralPath $resolved -Destination $target -Force
    return $true
}

$rootArtifacts = @(
    "fix_main.py",
    "test_error.log",
    "startup_profile2.txt",
    "append_tests.py",
    "bad_lines.txt",
    "bad_strings.txt",
    "debug.txt",
    "err.log",
    "err8.log",
    "errors.txt",
    "err_time.txt",
    "err_utf8.log",
    "extract_panels.py",
    "fix_grids.py",
    "fix_qml_lint.py",
    "fix_qml_lint_id.py",
    "fix_report.py",
    "fix_table_ref.py",
    "fix_table_ref_2.py",
    "lint_summary.txt",
    "migration_debug.txt",
    "my_test_runner.py",
    "out.txt",
    "pytest_errors.log",
    "pytest_errors2.log",
    "qml_lint.log",
    "remaining_warnings.txt",
    "remaining_warnings_utf8.txt",
    "run_out.txt",
    "test_handover.ps1",
    "test_handover.py",
    "test_out.log",
    "test_out.txt",
    "test_output.log",
    "test_run.ps1",
    "tests_error.txt",
    "tests_output.txt",
    "tests_output_fixed.txt",
    "tests_output_fixed2.txt",
    "tests_output_utf8.txt",
    "tmp_startup_err.log",
    "tmp_startup_out.log"
)

$rootArtifactPatterns = @(
    "fix_*.py",
    "test_*.log",
    "startup_profile*.txt"
)

$moved = 0
$deleted = 0

if (-not $NoArchive) {
    Ensure-Dir $archiveRoot
}

foreach ($name in $rootArtifacts) {
    $path = Join-Path $ProjectRoot $name
    if (Move-IntoArchive -LiteralPath $path) {
        $moved += 1
    }
}

foreach ($pattern in $rootArtifactPatterns) {
    Get-ChildItem -Path $ProjectRoot -File -Filter $pattern -ErrorAction SilentlyContinue |
        ForEach-Object {
            if (Move-IntoArchive -LiteralPath $_.FullName) {
                $moved += 1
            }
        }
}

$qmlArtifacts = Get-ChildItem -Path (Join-Path $ProjectRoot "src\qml") -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "*.pre_*" -or
        $_.Name -like "*.base_*" -or
        $_.Name -like "*.copilot-broken" -or
        $_.Name -like "*_broken*"
    }
foreach ($item in $qmlArtifacts) {
    if (Move-IntoArchive -LiteralPath $item.FullName) {
        $moved += 1
    }
}

$pycacheRoots = @(
    (Join-Path $ProjectRoot "__pycache__"),
    (Join-Path $ProjectRoot "src"),
    (Join-Path $ProjectRoot "tests"),
    (Join-Path $ProjectRoot "scripts")
)

foreach ($root in $pycacheRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    Get-ChildItem -Path $root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "__pycache__" } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            $deleted += 1
        }
    Get-ChildItem -Path $root -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".pyc", ".pyo") } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
            $deleted += 1
        }
}

$tempRoots = @(
    (Join-Path $ProjectRoot ".codex_tmp"),
    (Join-Path $ProjectRoot ".pytest_cache"),
    (Join-Path $ProjectRoot ".pytest_tmp"),
    (Join-Path $ProjectRoot ".pytest_tmp_live"),
    (Join-Path $ProjectRoot ".pytest_tmp_runs"),
    (Join-Path $ProjectRoot "tmpvdmuz3yk")
)
foreach ($tempRoot in $tempRoots) {
    if (-not (Test-Path -LiteralPath $tempRoot)) { continue }
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    $deleted += 1
}

Write-Host "[HYGIENE-REPAIR] moved=$moved deleted=$deleted archive=$archiveRoot"
