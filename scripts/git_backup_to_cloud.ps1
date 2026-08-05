param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
$VerbosePreference = "Continue"

Write-Host "=================================================="
Write-Host "       CSPM GOVERNED GIT CLOUD BACKUP"
Write-Host "=================================================="

if ($DryRun) {
    Write-Host ">>> DRY-RUN MODE: No changes will be staged, committed, or pushed. <<<" -ForegroundColor Yellow
}

# 1. Repository check
if (-not (Test-Path ".git")) {
    Write-Host "ERROR: Must be run from repository root." -ForegroundColor Red
    exit 1
}

$branch = git branch --show-current
if (-not $branch) {
    Write-Host "ERROR: Not on a branch." -ForegroundColor Red
    exit 1
}

# 2. Check pre-existing staged state
$staged_pre = git diff --name-only --cached
if ($staged_pre) {
    Write-Host "ERROR: Pre-existing staged files detected. Safe refusal triggered to avoid mixing context." -ForegroundColor Red
    Write-Host $staged_pre
    exit 1
}

# 3. Candidate inventory (Untracked and Modified)
$candidates = (git ls-files --others --modified --exclude-standard) -split "`n" | Where-Object { $_ -ne "" }
if (-not $candidates) {
    Write-Host "No changes detected. Repository is already up to date." -ForegroundColor Yellow
    exit 0
}

Write-Host "Discovered candidates for backup:"
$candidates | ForEach-Object { Write-Host " - $_" }

$blocked_patterns = @(
    "\.db$", "\.sqlite$", "\.sqlite3$", 
    "^backups/", "^archive/", "^recovery/", "^logs/",
    "^\.venv", "^venv/", "^secrets", "\.pem$", "\.key$",
    "^dist/", "^build/", "^_test_env/", "\.bak$", "\.log$",
    "^outputs/", "\.exe$", "check_.*\.ps1$", "start_.*\.ps1$"
)

$approved_workbooks = @("data/CSPM.xlsm", "data/Dockets.xlsm")

$valid_candidates = @()
$hashes = @{}

foreach ($file in $candidates) {
    $normalized_file = $file -replace '\\', '/'
    
    # 4. Check Blocklist
    $blocked = $false
    foreach ($pattern in $blocked_patterns) {
        if ($normalized_file -match $pattern) {
            Write-Host "INFO: Skipping blocked or transient file: $normalized_file (Matched: $pattern)" -ForegroundColor Cyan
            $blocked = $true
            break
        }
    }
    
    if ($blocked) { continue }
    
    # 5. Check Workbooks Strict Governance
    if ($normalized_file -match "^data/.*\.xlsm$" -or $normalized_file -match "^data/.*\.xlsx$") {
        if ($approved_workbooks -notcontains $normalized_file) {
            Write-Host "ERROR: Policy violation. Unapproved workbook detected: $normalized_file" -ForegroundColor Red
            exit 1
        }
        
        # Structural Sanity Check & Hash
        if (Test-Path $file) {
            try {
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                $zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $file).Path)
                $has_rels = $false
                foreach ($entry in $zip.Entries) {
                    if ($entry.FullName -like "*_rels/.rels*") { $has_rels = $true; break }
                }
                $zip.Dispose()
                if (-not $has_rels) { throw "Missing _rels (Not a valid Office ZIP)" }
            } catch {
                Write-Host "ERROR: Workbook structural validation failed for $normalized_file : $_" -ForegroundColor Red
                exit 1
            }
            
            $size = (Get-Item $file).Length
            if ($size -gt 100MB) {
                Write-Host "WARNING: Anomalous growth detected for $normalized_file ($size bytes). Proceeding." -ForegroundColor Yellow
            }
            
            try {
                $hashes[$normalized_file] = (Get-FileHash $file -ErrorAction Stop).Hash
            } catch {
                Write-Host "WARNING: Get-FileHash unavailable, falling back to .NET Crypto provider for $normalized_file" -ForegroundColor Yellow
                $stream = [System.IO.File]::OpenRead((Resolve-Path $file).Path)
                $sha256 = [System.Security.Cryptography.SHA256]::Create()
                $hashBytes = $sha256.ComputeHash($stream)
                $stream.Close()
                $sha256.Dispose()
                $hashes[$normalized_file] = -join ($hashBytes | ForEach-Object { $_.ToString("X2") })
            }
        }
    }
    
    $valid_candidates += $normalized_file
}

if (-not $valid_candidates) {
    Write-Host "No governable files changed. Repository is already up to date." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nGoverned files to stage:"
$valid_candidates | ForEach-Object { Write-Host " + $_" }

if ($DryRun) {
    Write-Host "`n[DRY RUN] Would have staged the above files, committed, and pushed." -ForegroundColor Green
    exit 0
}

# 6. Stage and commit
Write-Host "Staging files..."
foreach ($file in $valid_candidates) {
    git add $file
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to stage $file. Rolling back index." -ForegroundColor Red
        git reset HEAD
        exit 1
    }
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$msg = "Auto-backup: $timestamp`n`n"
if ($hashes.Count -gt 0) {
    $msg += "Hashes:`n"
    foreach ($k in $hashes.Keys) { $msg += "$k : $($hashes[$k])`n" }
}

Write-Host "Committing..."
git commit -m $msg | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Commit failed. Rolling back index." -ForegroundColor Red
    git reset HEAD
    exit 1
}
Write-Host "Commit successful." -ForegroundColor Green

# 7. Push
Write-Host "Pushing to origin..."
git push origin HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to push." -ForegroundColor Red
    exit 1
}

$manifest = @{
    timestamp = Get-Date -Format "o"
    commit = (git rev-parse HEAD)
    branch = $branch
    workbook_hashes = $hashes
}
$json_output = $manifest | ConvertTo-Json -Depth 5
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $PWD "outputs/git_backup_manifest.json"), $json_output, $utf8NoBom)

Write-Host "Cloud backup completed safely and successfully!" -ForegroundColor Green
