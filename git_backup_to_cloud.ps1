param(
    [string]$RepoPath = "C:\Projects\__CSPM",
    [string]$Remote = "origin",
    [string]$Message = "",
    [string]$Branch = "",
    [switch]$Confirmed,
    [switch]$PushTags,
    [switch]$ForcePush
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($GitArgs -join ' ')"
    }
}

function Get-RepoRelativePath {
    param([string]$FullPath, [string]$RepoRoot)
    $full = [System.IO.Path]::GetFullPath($FullPath)
    $root = [System.IO.Path]::GetFullPath($RepoRoot)
    if (-not $root.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $root += [System.IO.Path]::DirectorySeparatorChar
    }
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }
    return ($full.Substring($root.Length) -replace "\\", "/")
}

function Get-FileSha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stream = $null
    $sha256 = $null
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        if ($null -ne $sha256) { $sha256.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Test-ExcludedArtifact {
    param([string]$RelativePath)
    $p = ($RelativePath -replace "\\", "/")
    $lower = $p.ToLowerInvariant()

    $excludedPrefixes = @(
        "_copilot_full_project_dump/",
        "_fix_backups/",
        "_gpt_agent_shell/",
        "_cspm_workspace/change_backups/",
        "_cspm_workspace/dump_packs/",
        "_cspm_workspace/workbook_backups/",
        "_cspm_workspace/handoff/",
        "data/__backup/",
        "data/recovery_backups/",
        "scratch/",
        "src/web/practice_briefing/dist/",
        "src/web/productivity_dashboard/dist/"
    )
    foreach ($prefix in $excludedPrefixes) {
        if ($lower.StartsWith($prefix)) { return $true }
    }

    if ($lower -match '(^|/).*backup.*\.(xls|xlsx|xlsm|xlsb)$') { return $true }
    if ($lower -match '(^|/).*before.*\.(xls|xlsx|xlsm|xlsb)$') { return $true }
    if ($lower -match '(^|/).*pre_patch.*\.(xls|xlsx|xlsm|xlsb)$') { return $true }
    if ($lower -match '\.(bak|tmp|temp|pyc|pyo)$') { return $true }
    if ($lower -match '(^|/)~\$') { return $true }
    if ($lower -match '(^|/)project_text_dump_') { return $true }
    if ($lower -match '(^|/)copilot_dump_') { return $true }
    if ($lower -match '(^|/)[^/]*_backup\.qml$') { return $true }
    return $false
}

function Get-ApprovedDatabaseArtifacts {
    param([string]$RepoRoot)
    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($databaseRoot in @("data", "src/python/data")) {
        $rootPath = Join-Path $RepoRoot ($databaseRoot -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $rootPath -PathType Container)) { continue }
        foreach ($item in Get-ChildItem -LiteralPath $rootPath -Recurse -File -Force) {
            $relative = Get-RepoRelativePath -FullPath $item.FullName -RepoRoot $RepoRoot
            if ([string]::IsNullOrWhiteSpace($relative)) { continue }
            if (Test-ExcludedArtifact -RelativePath $relative) { continue }
            $paths.Add($relative)
        }
    }
    return @($paths | Sort-Object -Unique)
}

function Get-RequiredToolPaths {
    param([string]$RepoRoot)
    $results = @()
    foreach ($name in @("git_backup_to_cloud.ps1", "git_restore_from_cloud.ps1")) {
        $path = Join-Path $RepoRoot $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required Git backup/restore tool is missing: $path"
        }
        $results += $name
    }
    return $results
}

function Write-InclusionManifest {
    param([string]$RepoRoot, [string[]]$Paths, [string]$CommitMessage)
    $manifestPath = Join-Path $RepoRoot "docs\GIT_RECREATABLE_BACKUP_MANIFEST.json"
    $entries = @()
    foreach ($relative in ($Paths | Sort-Object -Unique)) {
        $full = Join-Path $RepoRoot ($relative -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
        $item = Get-Item -LiteralPath $full
        $entries += [ordered]@{
            path = $relative
            bytes = $item.Length
            sha256 = Get-FileSha256 -Path $full
        }
    }
    $manifest = [ordered]@{
        schemaVersion = 1
        generatedUtc = (Get-Date).ToUniversalTime().ToString("o")
        scope = "Recreatable application including current workbooks and active data; excluding archives, temporary files, caches, dumps, and backups."
        commitMessage = $CommitMessage
        files = $entries
    }
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    return "docs/GIT_RECREATABLE_BACKUP_MANIFEST.json"
}

Set-Location $RepoPath
Invoke-Git rev-parse --is-inside-work-tree | Out-Null

$currentBranch = (git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($currentBranch)) { throw "Not on a Git branch." }
if (-not [string]::IsNullOrWhiteSpace($Branch) -and $currentBranch -ne $Branch) {
    throw "Expected branch '$Branch' but current branch is '$currentBranch'."
}
if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "Recreatable CSPM checkpoint - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}

$databasePaths = Get-ApprovedDatabaseArtifacts -RepoRoot $RepoPath
$toolPaths = Get-RequiredToolPaths -RepoRoot $RepoPath
$requiredPaths = @(
    "data/CSPM.xlsm",
    "data/Dockets.xlsm",
    "src/python/domain/ap_lifecycle.py",
    "tests/test_ap_lifecycle.py",
    "docs/AP_DISBURSEMENTS_SOURCE_OF_TRUTH.md",
    "docs/AP_WORKBOOK_SCHEMA_PROPOSAL.md",
    "docs/FUTURE_DATA_ARCHITECTURE.md",
    "schema/workbook_schema.ap.patch.yml"
)

foreach ($required in $requiredPaths) {
    $full = Join-Path $RepoPath ($required -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
        throw "Required checkpoint file is missing: $required"
    }
}

Write-Host "===================================================="
Write-Host "CSPM RECREATABLE PRIVATE GIT BACKUP"
Write-Host "Repo: $RepoPath"
Write-Host "Remote: $Remote"
Write-Host "Branch: $currentBranch"
Write-Host "Message: $Message"
Write-Host "Approved database artifacts: $($databasePaths.Count)"
Write-Host "===================================================="

if (-not $Confirmed) {
    Write-Host "This will commit current application files, active workbooks, and active data."
    Write-Host "Archives, temporary files, caches, dump packs, and backups are excluded."
    Write-Host "The remote must be private."
    $answer = Read-Host "Type YES to continue"
    if ($answer -ne "YES") {
        Write-Host "Cancelled."
        exit 0
    }
}

Write-Host "Staging approved workspace..."
Invoke-Git add -A

foreach ($path in @($toolPaths + $databasePaths + $requiredPaths | Sort-Object -Unique)) {
    Invoke-Git add --force -- $path
}

$tracked = @(git ls-files)
foreach ($trackedPath in $tracked) {
    if (Test-ExcludedArtifact -RelativePath $trackedPath) {
        throw "Excluded file remains tracked after cleanup: $trackedPath"
    }
}

$manifestPath = Write-InclusionManifest -RepoRoot $RepoPath -Paths @($tracked + $databasePaths + $toolPaths + $requiredPaths) -CommitMessage $Message
Invoke-Git add --force -- $manifestPath

foreach ($required in @($toolPaths + $databasePaths + $requiredPaths + $manifestPath | Sort-Object -Unique)) {
    & git ls-files --error-unmatch -- $required *> $null
    if ($LASTEXITCODE -ne 0) { throw "Required file was not staged/tracked: $required" }
}

& git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    Invoke-Git commit -m $Message
} else {
    Write-Host "No changes to commit; existing HEAD will be verified and pushed."
}

$head = (git rev-parse HEAD).Trim()
foreach ($required in @($toolPaths + $databasePaths + $requiredPaths + $manifestPath | Sort-Object -Unique)) {
    $headBlob = (& git rev-parse --verify "HEAD:$required" 2>$null | Select-Object -First 1).ToString().Trim()
    if ([string]::IsNullOrWhiteSpace($headBlob)) { throw "Required file is absent from HEAD: $required" }
    $workingBlob = (& git hash-object -- $required | Select-Object -First 1).ToString().Trim()
    if ($headBlob -ne $workingBlob) { throw "HEAD differs from working file: $required" }
}

if ($ForcePush) {
    Invoke-Git push -u $Remote $currentBranch --force-with-lease
} else {
    Invoke-Git push -u $Remote $currentBranch
}
if ($PushTags) {
    if ($ForcePush) { Invoke-Git push $Remote --tags --force-with-lease }
    else { Invoke-Git push $Remote --tags }
}

Invoke-Git fetch $Remote --prune
$remoteHead = (& git rev-parse "$Remote/$currentBranch").Trim()
if ($remoteHead -ne $head) {
    throw "Remote verification mismatch. Local=$head Remote=$remoteHead"
}

Write-Host "DONE - private recreatable backup verified."
Write-Host "Commit: $head"
Write-Host "Remote commit: $remoteHead"
Write-Host "Manifest: $manifestPath"
