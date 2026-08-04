# PowerShell Project Backup Automation Script
# Analogous to create_backup.py in diag3

$ErrorActionPreference = "Stop"

$ProjectRoot = (Get-Item .).FullName
$BackupsDir = Join-Path $ProjectRoot "backups"

# Excluded folders / files
$DefaultExclusions = @(
    "backups",
    ".git",
    ".pytest_cache",
    ".pytest_tmp_runs",
    "__pycache__",
    "logs"
)

# Function to recursively copy while ignoring exclusions
function Copy-ProjectFiles {
    param(
        [string]$Src,
        [string]$Dest
    )

    if (-not (Test-Path $Dest)) {
        New-Item -ItemType Directory -Path $Dest | Out-Null
    }

    $items = Get-ChildItem -Path $Src -Force
    foreach ($item in $items) {
        # Check exclusions
        $excludeMatch = $false
        foreach ($ex in $DefaultExclusions) {
            if ($item.Name -eq $ex) {
                $excludeMatch = $true
                break
            }
        }
        # Exclude any .venv folder dynamically
        if ($item.Name -like ".venv*") {
            $excludeMatch = $true
        }

        if ($excludeMatch) {
            continue
        }

        $targetPath = Join-Path $Dest $item.Name
        if ($item.PSIsContainer) {
            Copy-ProjectFiles -Src $item.FullName -Dest $targetPath
        } else {
            Copy-Item -Path $item.FullName -Destination $targetPath -Force
        }
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CSPM Git-Safe Backup Automation" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Scanning workspace: $ProjectRoot"

$timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$backupFolderName = "backup_$timestamp"
$backupFolderPath = Join-Path $BackupsDir $backupFolderName
$snapshotPath = Join-Path $backupFolderPath "snapshot"

# Create backup directory structure
if (-not (Test-Path $BackupsDir)) {
    New-Item -ItemType Directory -Path $BackupsDir | Out-Null
}
New-Item -ItemType Directory -Path $backupFolderPath | Out-Null
New-Item -ItemType Directory -Path $snapshotPath | Out-Null

Write-Host "Creating snapshot..." -ForegroundColor Yellow
Copy-ProjectFiles -Src $ProjectRoot -Dest $snapshotPath

# Generate restore_backup.ps1 dynamically inside the backup folder
$restoreScriptPath = Join-Path $backupFolderPath "restore_backup.ps1"

$restoreScriptContent = @"
# Dynamically generated restore script
`$ErrorActionPreference = "Stop"

`$BackupRoot = `$PSScriptRoot
`$SnapshotDir = Join-Path `$BackupRoot "snapshot"
`$TargetRoot = (Get-Item (Join-Path `$BackupRoot "..\..")).FullName

Write-Host "========================================" -ForegroundColor Red
Write-Host " WARNING: RESTORING WORKSPACE SNAPSHOT" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host "This will OVERWRITE and RESET your workspace at:"
Write-Host "`$TargetRoot" -ForegroundColor Yellow
Write-Host ""
Write-Host "All non-git and non-venv files outside of backups will be purged!" -ForegroundColor Red
Write-Host ""

`$confirm = Read-Host "Type 'RESTORE' to confirm workspace reset"
if (`$confirm -ne "RESTORE") {
    Write-Host "Restore cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host "Purging target directory (preserving .git, .venv*, and backups)..." -ForegroundColor Yellow

# Get all top-level items to clear
`$items = Get-ChildItem -Path `$TargetRoot -Force
foreach (`$item in `$items) {
    if (`$item.Name -eq ".git" -or `$item.Name -eq "backups" -or `$item.Name -like ".venv*") {
        continue
    }
    
    if (`$item.PSIsContainer) {
        Remove-Item -Path `$item.FullName -Recurse -Force | Out-Null
    } else {
        Remove-Item -Path `$item.FullName -Force | Out-Null
    }
}

Write-Host "Restoring snapshot..." -ForegroundColor Yellow

# Copy everything from snapshot back to target
function Copy-RestoreFiles {
    param(
        [string]`$Src,
        [string]`$Dest
    )

    if (-not (Test-Path `$Dest)) {
        New-Item -ItemType Directory -Path `$Dest | Out-Null
    }

    `$subItems = Get-ChildItem -Path `$Src -Force
    foreach (`$subItem in `$subItems) {
        `$targetPath = Join-Path `$Dest `$subItem.Name
        if (`$subItem.PSIsContainer) {
            Copy-RestoreFiles -Src `$subItem.FullName -Dest `$targetPath
        } else {
            Copy-Item -Path `$subItem.FullName -Destination `$targetPath -Force
        }
    }
}

Copy-RestoreFiles -Src `$SnapshotDir -Dest `$TargetRoot

Write-Host "========================================" -ForegroundColor Green
Write-Host " SUCCESS: Restore completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
"@

Set-Content -Path $restoreScriptPath -Value $restoreScriptContent -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Backup successfully completed!" -ForegroundColor Green
Write-Host " Folder: $backupFolderPath" -ForegroundColor Yellow
Write-Host " To restore, run the restore script:"
Write-Host " .\backups\$backupFolderName\restore_backup.ps1" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
