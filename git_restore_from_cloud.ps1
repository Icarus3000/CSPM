param(
    [string]$RepoPath = "C:\Projects\__CSPM",
    [string]$Remote = "origin",
    [string]$DefaultBranch = "main",
    [string]$MaxCommits = "25",
    [string]$WorkbookRelativePath = "data/CSPM.xlsm"
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$GitArgs
    )

    & git @GitArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($GitArgs -join ' ')"
    }
}

function Invoke-GitClean {
    param(
        [string[]]$PreservePatterns
    )

    $cleanArgs = @("clean", "-fdx")
    foreach ($pattern in $PreservePatterns) {
        if ([string]::IsNullOrWhiteSpace($pattern)) {
            continue
        }

        $cleanArgs += "-e"
        $cleanArgs += ($pattern -replace "\\", "/")
    }

    Invoke-Git @cleanArgs
}

function Get-RepoRelativePath {
    param(
        [string]$FullPath,
        [string]$RepoRoot
    )

    $resolvedFullPath = [System.IO.Path]::GetFullPath($FullPath)
    $resolvedRepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)

    if (-not $resolvedRepoRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $resolvedRepoRoot = $resolvedRepoRoot + [System.IO.Path]::DirectorySeparatorChar
    }

    if (-not $resolvedFullPath.StartsWith($resolvedRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }

    $relativePath = $resolvedFullPath.Substring($resolvedRepoRoot.Length)
    return ($relativePath -replace "\\", "/")
}

function Get-FileSha256 {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-GitCommitBlobHash {
    param(
        [string]$Commitish,
        [string]$RelativePath
    )

    $spec = "${Commitish}:$RelativePath"
    $hash = & git rev-parse --verify $spec 2>$null

    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    return (($hash | Select-Object -First 1).ToString().Trim())
}

function Export-GitCommitFile {
    param(
        [string]$Commitish,
        [string]$RelativePath,
        [string]$DestinationPath
    )

    $destinationDir = Split-Path -Parent $DestinationPath
    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null

    $spec = "${Commitish}:$RelativePath"
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = "git"
    $process.StartInfo.Arguments = "show --no-textconv ""$spec"""
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true

    $outputStream = [System.IO.File]::Open(
        $DestinationPath,
        [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )

    try {
        [void]$process.Start()
        $process.StandardOutput.BaseStream.CopyTo($outputStream)
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
    } finally {
        $outputStream.Dispose()
    }

    if ($process.ExitCode -ne 0) {
        Remove-Item -LiteralPath $DestinationPath -Force -ErrorAction SilentlyContinue
        throw "Unable to export '$RelativePath' from selected commit '$Commitish': $stderr"
    }
}

function Get-GitWorkingTreeBlobHash {
    param(
        [string]$RelativePath
    )

    $hash = & git hash-object -- $RelativePath

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to hash restored working tree file: $RelativePath"
    }

    return (($hash | Select-Object -First 1).ToString().Trim())
}

function Test-DatabaseArtifactExcluded {
    param(
        [string]$RelativePath
    )

    if ($RelativePath -match '__BACKUP') { return $true }
    if ($RelativePath -match 'recovery_backups') { return $true }
    if ($RelativePath -match '\.bak$') { return $true }
    if ($RelativePath -match '\.backup') { return $true }

    return $false
}

function Get-DatabaseArtifactRelativePaths {
    param(
        [string]$RepoRoot,
        [string]$PrimaryWorkbookRelativePath
    )

    $databaseRoots = @("data", "src/python/data")
    $paths = @()

    if (-not [string]::IsNullOrWhiteSpace($PrimaryWorkbookRelativePath)) {
        $paths += ($PrimaryWorkbookRelativePath -replace "\\", "/")
    }

    foreach ($databaseRoot in $databaseRoots) {
        $rootFullPath = Join-Path $RepoRoot ($databaseRoot -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $rootFullPath -PathType Container)) {
            continue
        }

        $items = Get-ChildItem -LiteralPath $rootFullPath -Recurse -File -Force
        foreach ($item in $items) {
            $relativePath = Get-RepoRelativePath -FullPath $item.FullName -RepoRoot $RepoRoot
            if ([string]::IsNullOrWhiteSpace($relativePath)) {
                continue
            }
            if (Test-DatabaseArtifactExcluded -RelativePath $relativePath) {
                continue
            }

            $paths += $relativePath
        }
    }

    $uniquePaths = @()
    foreach ($path in $paths) {
        $normalized = ($path -replace "\\", "/")
        if ([string]::IsNullOrWhiteSpace($normalized)) {
            continue
        }
        if ($uniquePaths -notcontains $normalized) {
            $uniquePaths += $normalized
        }
    }

    return $uniquePaths
}

function Get-GitCommitDatabaseArtifactRelativePaths {
    param(
        [string]$Commitish,
        [string]$PrimaryWorkbookRelativePath
    )

    $databaseRoots = @("data", "src/python/data")
    $paths = @()

    if (-not [string]::IsNullOrWhiteSpace($PrimaryWorkbookRelativePath)) {
        $paths += ($PrimaryWorkbookRelativePath -replace "\\", "/")
    }

    foreach ($databaseRoot in $databaseRoots) {
        $rootPaths = & git ls-tree -r --name-only $Commitish -- $databaseRoot 2>$null
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        foreach ($rootPath in $rootPaths) {
            $normalized = ([string]$rootPath).Trim() -replace "\\", "/"
            if ([string]::IsNullOrWhiteSpace($normalized)) {
                continue
            }
            if (Test-DatabaseArtifactExcluded -RelativePath $normalized) {
                continue
            }

            $paths += $normalized
        }
    }

    return @($paths | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)
}

function Get-RestoreToolRelativePaths {
    return @(
        "git_backup_to_cloud.ps1",
        "git_restore_from_cloud.ps1"
    )
}

function New-PreRestoreWorkbookSafetyCopy {
    param(
        [string]$WorkbookFullPath,
        [string]$RepoRoot,
        [string]$RelativePath
    )

    if (-not (Test-Path -LiteralPath $WorkbookFullPath -PathType Leaf)) {
        Write-Host "No existing active workbook found to safety-copy before restore:"
        Write-Host "  $WorkbookFullPath"
        return $null
    }

    $repoParent = Split-Path -Parent ([System.IO.Path]::GetFullPath($RepoRoot))
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $safetyDir = Join-Path $repoParent "__CSPM_restore_safety\restore_$timestamp"
    New-Item -ItemType Directory -Path $safetyDir -Force | Out-Null

    $destPath = Join-Path $safetyDir (Split-Path -Leaf $WorkbookFullPath)
    Copy-Item -LiteralPath $WorkbookFullPath -Destination $destPath -Force

    $sha256 = Get-FileSha256 -Path $destPath
    $manifestPath = Join-Path $safetyDir "manifest.txt"
    $manifest = @(
        "CSPM pre-restore active workbook safety copy",
        "Created: $(Get-Date -Format o)",
        "Source: $WorkbookFullPath",
        "RelativePath: $RelativePath",
        "Copy: $destPath",
        "SHA-256: $sha256"
    )
    Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding UTF8

    Write-Host "Pre-restore active workbook safety copy created:"
    Write-Host "  Copy: $destPath"
    Write-Host "  SHA-256: $sha256"
    Write-Host ""

    return [PSCustomObject]@{
        Path = $destPath
        Sha256 = $sha256
        Manifest = $manifestPath
    }
}

function New-PreRestoreDatabaseSafetyCopy {
    param(
        [string[]]$ArtifactRelativePaths,
        [string]$RepoRoot
    )

    if (-not $ArtifactRelativePaths -or $ArtifactRelativePaths.Count -eq 0) {
        Write-Host "No database artifacts found for pre-restore safety copy."
        return $null
    }

    $repoParent = Split-Path -Parent ([System.IO.Path]::GetFullPath($RepoRoot))
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $safetyDir = Join-Path $repoParent "__CSPM_restore_safety\database_restore_$timestamp"
    New-Item -ItemType Directory -Path $safetyDir -Force | Out-Null

    $manifest = @(
        "CSPM pre-restore database artifact safety copy",
        "Created: $(Get-Date -Format o)",
        "RepoRoot: $RepoRoot",
        ""
    )

    foreach ($relativePath in $ArtifactRelativePaths) {
        $normalized = ($relativePath -replace "\\", "/")
        $sourcePath = Join-Path $RepoRoot ($normalized -replace "/", [System.IO.Path]::DirectorySeparatorChar)

        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            $manifest += "SKIPPED missing: $normalized"
            continue
        }

        $destPath = Join-Path $safetyDir ($normalized -replace "/", [System.IO.Path]::DirectorySeparatorChar)
        $destDir = Split-Path -Parent $destPath
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destPath -Force

        $sha256 = Get-FileSha256 -Path $destPath
        $manifest += "COPIED: $normalized"
        $manifest += "  Source: $sourcePath"
        $manifest += "  Copy: $destPath"
        $manifest += "  SHA-256: $sha256"
    }

    $manifestPath = Join-Path $safetyDir "manifest.txt"
    Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding UTF8

    Write-Host "Pre-restore database artifact safety copy created:"
    Write-Host "  Directory: $safetyDir"
    Write-Host "  Manifest: $manifestPath"
    Write-Host ""

    return [PSCustomObject]@{
        Path = $safetyDir
        Manifest = $manifestPath
    }
}

function Invoke-WorkbookIntegrityCheck {
    param(
        [string]$RepoRoot,
        [string]$WorkbookFullPath,
        [string]$Label,
        [string]$ReportName,
        [switch]$AllowFailure
    )

    $checker = Join-Path $RepoRoot "scripts\check_workbook_integrity.ps1"
    if (-not (Test-Path -LiteralPath $checker -PathType Leaf)) {
        throw "Missing workbook integrity wrapper required for restore validation: $checker"
    }

    $safeReportName = ($ReportName -replace "[^A-Za-z0-9_.-]", "_")
    if ([string]::IsNullOrWhiteSpace($safeReportName)) {
        $safeReportName = "workbook_integrity"
    }

    $reportRoot = Join-Path $RepoRoot "logs\workbook_integrity"
    New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportPath = Join-Path $reportRoot "${timestamp}_${safeReportName}.json"

    Write-Host ""
    Write-Host "Running workbook integrity check: $Label"
    Write-Host "  Workbook: $WorkbookFullPath"
    Write-Host "  JSON report: $reportPath"

    $checkerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $checker,
        "-ProjectRoot",
        $RepoRoot,
        "-WorkbookPath",
        $WorkbookFullPath,
        "-Output",
        $reportPath
    )

    & "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe" @checkerArgs
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        $message = "Workbook integrity check failed for '$Label'. JSON report: $reportPath"
        if ($AllowFailure) {
            Write-Host "WARNING: $message"
            Write-Host "Continuing because the selected Git restore may be the recovery operation."
            return $false
        }

        throw $message
    }

    Write-Host "Workbook integrity check passed: $Label"
    return $true
}

function Show-CommitSelectionDialog {
    param(
        [string]$Title,
        [string]$Message,
        [array]$Commits
    )

    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing

        $form = New-Object System.Windows.Forms.Form
        $form.Text = $Title
        $form.StartPosition = "CenterScreen"
        $form.TopMost = $true
        $form.FormBorderStyle = "FixedDialog"
        $form.MaximizeBox = $false
        $form.MinimizeBox = $false
        $form.Width = 960
        $form.Height = 520

        $textBox = New-Object System.Windows.Forms.TextBox
        $textBox.Text = $Message
        $textBox.Multiline = $true
        $textBox.ReadOnly = $true
        $textBox.Left = 20
        $textBox.Top = 20
        $textBox.Width = 900
        $textBox.Height = 250
        $textBox.ScrollBars = "Vertical"
        $textBox.Font = New-Object System.Drawing.Font("Segoe UI", 10)
        $form.Controls.Add($textBox)

        $comboLabel = New-Object System.Windows.Forms.Label
        $comboLabel.Text = "Select Commit to Restore:"
        $comboLabel.Left = 20
        $comboLabel.Top = 285
        $comboLabel.Width = 300
        $form.Controls.Add($comboLabel)

        $comboBox = New-Object System.Windows.Forms.ComboBox
        $comboBox.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
        $comboBox.Left = 20
        $comboBox.Top = 305
        $comboBox.Width = 900
        $comboBox.Font = New-Object System.Drawing.Font("Consolas", 10)
        $form.Controls.Add($comboBox)

        $sortCheckBox = New-Object System.Windows.Forms.CheckBox
        $sortCheckBox.Text = "Reverse Sort Order (Oldest First)"
        $sortCheckBox.Left = 20
        $sortCheckBox.Top = 345
        $sortCheckBox.Width = 300
        $form.Controls.Add($sortCheckBox)

        $yesButton = New-Object System.Windows.Forms.Button
        $yesButton.Text = "Restore"
        $yesButton.Width = 120
        $yesButton.Height = 35
        $yesButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Controls.Add($yesButton)

        $noButton = New-Object System.Windows.Forms.Button
        $noButton.Text = "Cancel"
        $noButton.Width = 110
        $noButton.Height = 35
        $noButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
        $form.Controls.Add($noButton)

        $buttonY = 400
        $yesButton.Left = 700
        $yesButton.Top = $buttonY
        $noButton.Left = 830
        $noButton.Top = $buttonY

        $form.AcceptButton = $yesButton
        $form.CancelButton = $noButton

        # Logic for loading commits
        $loadCommits = {
            $comboBox.Items.Clear()
            if ($sortCheckBox.Checked) {
                # Reverse (oldest first)
                for ($i = $Commits.Length - 1; $i -ge 0; $i--) {
                    $comboBox.Items.Add($Commits[$i].Display) | Out-Null
                }
            } else {
                # Chronological (newest first)
                foreach ($c in $Commits) {
                    $comboBox.Items.Add($c.Display) | Out-Null
                }
            }
            if ($comboBox.Items.Count -gt 0) {
                $comboBox.SelectedIndex = 0
            }
        }

        & $loadCommits

        $sortCheckBox.Add_CheckedChanged({
            $selectedItem = $comboBox.SelectedItem
            & $loadCommits
            if ($selectedItem -and $comboBox.Items.Contains($selectedItem)) {
                $comboBox.SelectedItem = $selectedItem
            }
        })

        $result = $form.ShowDialog()

        if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $comboBox.SelectedItem) {
            $selDisplay = $comboBox.SelectedItem.ToString()
            # Find matching commit hash
            foreach ($c in $Commits) {
                if ($c.Display -eq $selDisplay) {
                    return $c.Hash
                }
            }
        }
        return $null
    }
    catch {
        Write-Host ""
        Write-Host $Title
        Write-Host $Message
        Write-Host ""
        Write-Host "Available Commits:"
        for ($i=0; $i -lt $Commits.Length; $i++) {
            Write-Host "[$i] $($Commits[$i].Display)"
        }
        Write-Host ""
        $answer = Read-Host "Enter the number of the commit to restore (or leave blank to cancel)"
        
        if ([int]::TryParse($answer, [ref]$null)) {
            $idx = [int]$answer
            if ($idx -ge 0 -and $idx -lt $Commits.Length) {
                return $Commits[$idx].Hash
            }
        }
        return $null
    }
}

$restoreScriptName = "git_restore_from_cloud.ps1"
$backupScriptName = "git_backup_to_cloud.ps1"
$cleanPreservePatterns = @(
    $restoreScriptName,
    $backupScriptName,
    "backups/",
    "dumps/",
    "archive/",
    "logs/",
    "data/recovery_backups/",
    ".venv/",
    ".venv_*/",
    ".venv*/",
    "venv/",
    "env/"
)
$workbookPathInput = $WorkbookRelativePath -replace "/", [System.IO.Path]::DirectorySeparatorChar
if ([System.IO.Path]::IsPathRooted($WorkbookRelativePath)) {
    $workbookFullPath = $WorkbookRelativePath
} else {
    $workbookFullPath = Join-Path $RepoPath $workbookPathInput
}
$relativeWorkbookPath = Get-RepoRelativePath -FullPath $workbookFullPath -RepoRoot $RepoPath
if ([string]::IsNullOrWhiteSpace($relativeWorkbookPath)) {
    throw "Active workbook must be inside the repo path to be restored from Git: $workbookFullPath"
}
$currentDatabaseArtifactPaths = Get-DatabaseArtifactRelativePaths -RepoRoot $RepoPath -PrimaryWorkbookRelativePath $relativeWorkbookPath
if ($currentDatabaseArtifactPaths -notcontains $relativeWorkbookPath) {
    throw "Active workbook was not included in the database artifact set: $relativeWorkbookPath"
}
$restoreToolPaths = Get-RestoreToolRelativePaths
$cleanPreservePatterns += $relativeWorkbookPath
$cleanPreservePatterns += $currentDatabaseArtifactPaths
$cleanPreservePatterns += $restoreToolPaths
$cleanPreservePatterns = @($cleanPreservePatterns | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

Write-Host "===================================================="
Write-Host "FULL LOCAL RESTORE FROM GIT CLOUD - SAFE MODE"
Write-Host "Repo: $RepoPath"
Write-Host "Remote: $Remote"
Write-Host "Default branch: $DefaultBranch"
Write-Host "Max Commits shown: $MaxCommits"
Write-Host "Preserving during clean:"
foreach ($pattern in $cleanPreservePatterns) {
    Write-Host "  - $pattern"
}
Write-Host "Restoring active workbook: $relativeWorkbookPath"
Write-Host "Backup/restore scripts that selected commits must contain:"
foreach ($restoreToolPath in $restoreToolPaths) {
    Write-Host "  - $restoreToolPath"
}
Write-Host "Current full database artifacts that will be safety-copied before restore:"
foreach ($databaseArtifactPath in $currentDatabaseArtifactPaths) {
    Write-Host "  - $databaseArtifactPath"
}
Write-Host "===================================================="

Set-Location $RepoPath

Write-Host ""
Write-Host "Fetching all remotes and pruning deleted branches..."
Invoke-Git fetch --all --prune

$currentBranch = git branch --show-current

$remoteTrackingBranch = "$Remote/$DefaultBranch"

git show-ref --verify --quiet "refs/remotes/$remoteTrackingBranch"
if ($LASTEXITCODE -ne 0) {
    throw "Remote default branch '$remoteTrackingBranch' does not exist."
}

# Get commits
$logArgs = @("log", $remoteTrackingBranch, "--format=%H|%ai|%an|%s")
if ($MaxCommits -notmatch "^(?i)ALL$") {
    $logArgs += "-n"
    $logArgs += $MaxCommits
}

$rawLog = & git @logArgs
$commits = @()
foreach ($line in $rawLog) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $parts = $line.Split('|', 4)
    if ($parts.Length -eq 4) {
        $hash = $parts[0]
        $shortHash = $hash.Substring(0, 7)
        $date = $parts[1]
        $author = $parts[2]
        $msg = $parts[3]
        $display = "[$shortHash] $date - $msg"
        
        $commits += [PSCustomObject]@{
            Hash = $hash
            ShortHash = $shortHash
            Date = $date
            Author = $author
            Message = $msg
            Display = $display
        }
    }
}

if ($commits.Length -eq 0) {
    throw "No commits found on '$remoteTrackingBranch'."
}

$cloudInfoText = @"

Latest commit on '$remoteTrackingBranch' (cloud):
  Hash:    $($commits[0].ShortHash)
  Author:  $($commits[0].Author)
  Date:    $($commits[0].Date)
  Message: $($commits[0].Message)
"@

$confirmMessage = @"
This will RESTORE the local repository from Git cloud.

It will:
- reset tracked files with git reset --hard;
- delete untracked and ignored files with git clean -fdx;
- force local branches to match remote branches;
- end on '$DefaultBranch' and reset it to your CHOSEN COMMIT.

This will discard local uncommitted changes.

The script will preserve these local paths during git clean:
$($cleanPreservePatterns | ForEach-Object { "- $_" } | Out-String)

The selected commit must contain both backup/restore scripts and its full database artifact set under:
- data/
- src/python/data/

Current branch: $currentBranch
Repo: $RepoPath$cloudInfoText
"@

$selectedHash = Show-CommitSelectionDialog -Title "Confirm Git Restore From Cloud" -Message $confirmMessage -Commits $commits

if (-not $selectedHash) {
    Write-Host ""
    Write-Host "Restore cancelled. No destructive Git commands were run."
    exit 0
}

Write-Host ""
Write-Host "Selected commit hash: $selectedHash"

$databaseArtifactPaths = Get-GitCommitDatabaseArtifactRelativePaths `
    -Commitish $selectedHash `
    -PrimaryWorkbookRelativePath $relativeWorkbookPath
if ($databaseArtifactPaths -notcontains $relativeWorkbookPath) {
    throw "Selected commit does not contain the active workbook '$relativeWorkbookPath'. Choose a commit created by the full-database backup script before restoring."
}

$expectedWorkbookBlob = Get-GitCommitBlobHash -Commitish $selectedHash -RelativePath $relativeWorkbookPath
if ([string]::IsNullOrWhiteSpace($expectedWorkbookBlob)) {
    throw "Selected commit does not contain the active workbook '$relativeWorkbookPath'. Choose a commit created by the full-database backup script before restoring."
}
$expectedDatabaseBlobs = @{}
$expectedDatabaseBlobs[$relativeWorkbookPath] = $expectedWorkbookBlob
$expectedRestoreToolBlobs = @{}

foreach ($databaseArtifactPath in $databaseArtifactPaths) {
    if ($databaseArtifactPath -eq $relativeWorkbookPath) {
        continue
    }

    $expectedDatabaseBlob = Get-GitCommitBlobHash -Commitish $selectedHash -RelativePath $databaseArtifactPath
    if ([string]::IsNullOrWhiteSpace($expectedDatabaseBlob)) {
        throw "Selected commit does not contain required database artifact '$databaseArtifactPath'. Choose a commit created by the database-integrated backup script before restoring."
    }

    $expectedDatabaseBlobs[$databaseArtifactPath] = $expectedDatabaseBlob
}

foreach ($restoreToolPath in $restoreToolPaths) {
    $expectedRestoreToolBlob = Get-GitCommitBlobHash -Commitish $selectedHash -RelativePath $restoreToolPath
    if ([string]::IsNullOrWhiteSpace($expectedRestoreToolBlob)) {
        throw "Selected commit does not contain required backup/restore script '$restoreToolPath'. Choose a commit created by the self-contained backup script before restoring."
    }

    $expectedRestoreToolBlobs[$restoreToolPath] = $expectedRestoreToolBlob
}

Write-Host "Selected commit contains active workbook:"
Write-Host "  Path: $relativeWorkbookPath"
Write-Host "  Git blob: $expectedWorkbookBlob"
Write-Host ""
Write-Host "Selected commit contains required database artifacts:"
foreach ($databaseArtifactPath in $databaseArtifactPaths) {
    Write-Host "  $databaseArtifactPath -> $($expectedDatabaseBlobs[$databaseArtifactPath])"
}
Write-Host ""
Write-Host "Selected commit contains required backup/restore scripts:"
foreach ($restoreToolPath in $restoreToolPaths) {
    Write-Host "  $restoreToolPath -> $($expectedRestoreToolBlobs[$restoreToolPath])"
}
Write-Host ""

$cleanPreservePatterns += $databaseArtifactPaths
$cleanPreservePatterns += $restoreToolPaths
$cleanPreservePatterns = @($cleanPreservePatterns | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

Write-Host "Preflighting selected commit workbook before any reset/clean..."
$preflightRoot = Join-Path ([System.IO.Path]::GetTempPath()) "cspm_git_restore_preflight_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$preflightWorkbookPath = Join-Path $preflightRoot (Split-Path -Leaf $relativeWorkbookPath)

try {
    Export-GitCommitFile `
        -Commitish $selectedHash `
        -RelativePath $relativeWorkbookPath `
        -DestinationPath $preflightWorkbookPath

    Invoke-WorkbookIntegrityCheck `
        -RepoRoot $RepoPath `
        -WorkbookFullPath $preflightWorkbookPath `
        -Label "selected Git workbook preflight" `
        -ReportName "selected_git_workbook_preflight" | Out-Null
} catch {
    throw "$($_.Exception.Message)`nSelected commit failed workbook preflight before any reset/clean was run. Choose a different commit or inspect the JSON report above."
} finally {
    if (Test-Path -LiteralPath $preflightRoot -PathType Container) {
        Remove-Item -LiteralPath $preflightRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

New-PreRestoreWorkbookSafetyCopy -WorkbookFullPath $workbookFullPath -RepoRoot $RepoPath -RelativePath $relativeWorkbookPath | Out-Null
New-PreRestoreDatabaseSafetyCopy -ArtifactRelativePaths ($currentDatabaseArtifactPaths + $restoreToolPaths) -RepoRoot $RepoPath | Out-Null
Invoke-WorkbookIntegrityCheck `
    -RepoRoot $RepoPath `
    -WorkbookFullPath $workbookFullPath `
    -Label "pre-restore active workbook" `
    -ReportName "pre_restore_active_workbook" `
    -AllowFailure | Out-Null

Write-Host ""
Write-Host "Resetting tracked files on current branch..."
Invoke-Git reset --hard

Write-Host ""
Write-Host "Cleaning untracked and ignored files, while preserving local restore artifacts..."
Invoke-GitClean -PreservePatterns $cleanPreservePatterns

Write-Host ""
Write-Host "Getting remote branches..."

$remoteRefs = git for-each-ref --format="%(refname:short)" "refs/remotes/$Remote" |
    ForEach-Object { $_.Trim() } |
    Where-Object {
        $_ -and
        $_ -ne "$Remote/HEAD" -and
        $_.StartsWith("$Remote/")
    }

$remoteBranchNames = @()

foreach ($remoteRef in $remoteRefs) {
    $prefix = "$Remote/"
    $branchName = $remoteRef.Substring($prefix.Length)

    if ([string]::IsNullOrWhiteSpace($branchName)) { continue }

    $remoteBranchNames += $branchName

    Write-Host ""
    Write-Host "Synchronizing local branch '$branchName' with '$remoteRef'..."

    git show-ref --verify --quiet "refs/heads/$branchName"
    if ($LASTEXITCODE -eq 0) {
        Invoke-Git switch $branchName
    } else {
        Invoke-Git switch -c $branchName --track $remoteRef
    }

    Invoke-Git reset --hard $remoteRef
    Invoke-GitClean -PreservePatterns $cleanPreservePatterns
}

Write-Host ""
Write-Host "Switching to default branch '$DefaultBranch'..."
Invoke-Git switch $DefaultBranch

Write-Host ""
Write-Host "Resetting '$DefaultBranch' to selected commit '$selectedHash'..."
Invoke-Git reset --hard $selectedHash
Invoke-GitClean -PreservePatterns $cleanPreservePatterns

Write-Host ""
Write-Host "Deleting local branches that no longer exist on remote..."

$localBranches = git for-each-ref --format="%(refname:short)" refs/heads |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ }

foreach ($localBranch in $localBranches) {
    if ($localBranch -ne $DefaultBranch -and $remoteBranchNames -notcontains $localBranch) {
        Write-Host "Deleting local-only branch: $localBranch"
        Invoke-Git branch -D $localBranch
    }
}

Write-Host ""
Write-Host "Verifying restored active workbook..."
if (-not (Test-Path -LiteralPath $workbookFullPath -PathType Leaf)) {
    throw "Active workbook was not restored: $workbookFullPath"
}

$actualWorkbookBlob = Get-GitWorkingTreeBlobHash -RelativePath $relativeWorkbookPath
if ($actualWorkbookBlob -ne $expectedWorkbookBlob) {
    throw "Restored active workbook hash mismatch. Expected blob $expectedWorkbookBlob but found $actualWorkbookBlob for $relativeWorkbookPath."
}

$restoredWorkbookSha256 = Get-FileSha256 -Path $workbookFullPath
Write-Host "Active workbook restored and verified:"
Write-Host "  Path: $relativeWorkbookPath"
Write-Host "  Git blob: $actualWorkbookBlob"
Write-Host "  SHA-256: $restoredWorkbookSha256"

Write-Host ""
Write-Host "Verifying restored database artifacts..."
foreach ($databaseArtifactPath in $databaseArtifactPaths) {
    $databaseFullPath = Join-Path $RepoPath ($databaseArtifactPath -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $databaseFullPath -PathType Leaf)) {
        throw "Database artifact was not restored: $databaseArtifactPath"
    }

    $actualDatabaseBlob = Get-GitWorkingTreeBlobHash -RelativePath $databaseArtifactPath
    $expectedDatabaseBlob = $expectedDatabaseBlobs[$databaseArtifactPath]
    if ($actualDatabaseBlob -ne $expectedDatabaseBlob) {
        throw "Restored database artifact hash mismatch. Expected blob $expectedDatabaseBlob but found $actualDatabaseBlob for $databaseArtifactPath."
    }

    $restoredDatabaseSha256 = Get-FileSha256 -Path $databaseFullPath
    Write-Host "  $databaseArtifactPath"
    Write-Host "    Git blob: $actualDatabaseBlob"
    Write-Host "    SHA-256: $restoredDatabaseSha256"
}

Write-Host ""
Write-Host "Verifying restored backup/restore scripts..."
foreach ($restoreToolPath in $restoreToolPaths) {
    $restoreToolFullPath = Join-Path $RepoPath ($restoreToolPath -replace "/", [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $restoreToolFullPath -PathType Leaf)) {
        throw "Backup/restore script was not restored: $restoreToolPath"
    }

    $actualRestoreToolBlob = Get-GitWorkingTreeBlobHash -RelativePath $restoreToolPath
    $expectedRestoreToolBlob = $expectedRestoreToolBlobs[$restoreToolPath]
    if ($actualRestoreToolBlob -ne $expectedRestoreToolBlob) {
        throw "Restored backup/restore script hash mismatch. Expected blob $expectedRestoreToolBlob but found $actualRestoreToolBlob for $restoreToolPath."
    }

    $restoredRestoreToolSha256 = Get-FileSha256 -Path $restoreToolFullPath
    Write-Host "  $restoreToolPath"
    Write-Host "    Git blob: $actualRestoreToolBlob"
    Write-Host "    SHA-256: $restoredRestoreToolSha256"
}

Invoke-WorkbookIntegrityCheck `
    -RepoRoot $RepoPath `
    -WorkbookFullPath $workbookFullPath `
    -Label "post-restore active workbook" `
    -ReportName "post_restore_active_workbook" | Out-Null

Write-Host ""
Write-Host "Final status:"
git status

Write-Host ""
Write-Host "Latest local commit:"
git log -1 --oneline

Write-Host ""
Write-Host "DONE - Repo restored to chosen commit. Backup/restore scripts, active workbook, database artifacts, and post-restore workbook integrity were verified."
