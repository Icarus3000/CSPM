param(
    [string]$ProjectRoot,
    [int]$OlderThanDays = 10,
    [string]$ArchiveRoot,
    [switch]$WhatIfMode
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

if (-not $ArchiveRoot) {
    $workspaceUser = $null
    if ($ProjectRoot -match '^[A-Za-z]:\\Users\\([^\\]+)\\') {
        $workspaceUser = $Matches[1]
    }

    if ($workspaceUser) {
        $ArchiveRoot = "C:\Users\$workspaceUser\Documents\CSPM_Archive"
    } elseif ($env:USERPROFILE) {
        $ArchiveRoot = (Join-Path $env:USERPROFILE "Documents\CSPM_Archive")
    } else {
        $userName = if ($env:USERNAME) { $env:USERNAME } else { "User" }
        $ArchiveRoot = "C:\Users\$userName\Documents\CSPM_Archive"
    }
}

$now = Get-Date
$cutoff = $now.AddDays(-1 * [math]::Abs($OlderThanDays))
$batchId = $now.ToString("yyyyMMdd_HHmmss")
$archiveBatchRoot = Join-Path $ArchiveRoot $batchId

$candidateDirs = @(
    "archive",
    "backups",
    "dumps",
    "logs",
    "outputs",
    "dist",
    ".pytest_cache",
    ".pytest_tmp",
    ".pytest_tmp_runs",
    ".pytest_tmp_live",
    ".codex_tmp",
    "__pycache__",
    "tmp*"
)

$fileCandidates = New-Object System.Collections.Generic.List[System.IO.FileInfo]
foreach ($pattern in $candidateDirs) {
    Get-ChildItem -Path (Join-Path $ProjectRoot $pattern) -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { $fileCandidates.Add($_) }
}

# Also include loose top-level temp/log dumps older than cutoff.
$topLevelPatterns = @("*.log", "*.tmp", "*.bak", "*.old", "*.orig", "err*.txt", "out*.txt", "test*.log")
foreach ($pattern in $topLevelPatterns) {
    Get-ChildItem -Path (Join-Path $ProjectRoot $pattern) -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        ForEach-Object { $fileCandidates.Add($_) }
}

$unique = $fileCandidates |
    Sort-Object -Property FullName -Unique

if ($unique.Count -eq 0) {
    Write-Host "[ARCHIVE] No artifacts older than $OlderThanDays day(s) found."
    return
}

Write-Host "[ARCHIVE] Project root : $ProjectRoot"
Write-Host "[ARCHIVE] Archive root : $archiveBatchRoot"
Write-Host "[ARCHIVE] Cutoff       : $($cutoff.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "[ARCHIVE] Files found  : $($unique.Count)"

if (-not $WhatIfMode) {
    New-Item -ItemType Directory -Path $archiveBatchRoot -Force | Out-Null
}

$moved = 0
$failed = 0

foreach ($file in $unique) {
    $relative = $file.FullName.Substring($ProjectRoot.Length).TrimStart('\', '/')
    $target = Join-Path $archiveBatchRoot $relative
    $targetDir = Split-Path -Path $target -Parent
    if (-not $WhatIfMode) {
        try {
            New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            Move-Item -LiteralPath $file.FullName -Destination $target -Force
            $moved += 1
        } catch {
            $failed += 1
            Write-Warning ("[ARCHIVE] Failed to move: " + $file.FullName + " -> " + $target + " | " + $_.Exception.Message)
        }
    } else {
        Write-Host ("[ARCHIVE][WHATIF] " + $relative)
    }
}

if (-not $WhatIfMode) {
    # Clean empty directories after move.
    Get-ChildItem -Path $ProjectRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Sort-Object -Property FullName -Descending |
        ForEach-Object {
            try {
                if ((Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
                    Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                }
            } catch {
            }
        }
}

Write-Host "[ARCHIVE] Moved  : $moved"
Write-Host "[ARCHIVE] Failed : $failed"
if ($WhatIfMode) {
    Write-Host "[ARCHIVE] WhatIf only - no files moved."
}
