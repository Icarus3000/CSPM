# PSScriptAnalyzer disable=PSUseApprovedVerbs

param(
    [int]$MaxBundleChars = 160000,
    # legacy switches kept for compatibility; they don’t change behavior because
    # the dump now always includes the full source tree (minus excluded paths)
    [switch]$IncludeSrc,
    [switch]$IncludeDocsExtras,
    [string]$Descriptor = ""
)

# guard against accidentally running one of the many backup copies that
# accumulate under scripts/_repair_backup_*.  Backups are for reference only.
if ($PSScriptRoot -match '\\_repair_backup') {
    Write-Host "ERROR: this is a backup copy of the chatpack generator."
    Write-Host "Please invoke 'scripts\\31_dump_chatpack.ps1' directly instead."
    exit 1
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# echo parameters so wrapper can parse location; compatibility with previous
# debug runs and to reassure callers that switches are being ignored.
Write-Host "DEBUG: Params - IncludeSrc=$IncludeSrc IncludeDocsExtras=$IncludeDocsExtras MaxBundleChars=$MaxBundleChars Descriptor='$Descriptor'"
if ($IncludeSrc) {
    Write-Host "INFO: -IncludeSrc no longer necessary; repository text is always included."
}
if ($IncludeDocsExtras) {
    Write-Host "INFO: -IncludeDocsExtras no longer necessary; docs are always included."
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function Get-RepoRoot {
    (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-RelativePath {
    param([string]$BasePath, [string]$FullPath)
    $baseUri = New-Object System.Uri(($BasePath.TrimEnd("\") + "\"))
    $fullUri = New-Object System.Uri($FullPath)
    $rel = $baseUri.MakeRelativeUri($fullUri).ToString()
    $rel = [System.Uri]::UnescapeDataString($rel)
    $rel -replace "/", "\"
}

function Test-IsTextFile {
    param([string]$FullPath)

    $name = [System.IO.Path]::GetFileName($FullPath)
    $ext  = [System.IO.Path]::GetExtension($FullPath).ToLowerInvariant()

    $textExts = @(
        ".md",".txt",".yml",".yaml",".json",
        ".py",".qml",".svg",".js",".mjs",".qmltypes",
        ".toml",".ini",".cfg",".csv",
        ".ts",".tsx",".jsx",".css",".html",".xml"
    )

    $isQmlDirFile = ($name.ToLowerInvariant() -eq "qmldir")
    if (($textExts -notcontains $ext) -and (-not $isQmlDirFile)) { return $false }

    $fs = [System.IO.File]::Open($FullPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $len = [Math]::Min(4096, [int]$fs.Length)
        $buf = New-Object byte[] $len
        [void]$fs.Read($buf, 0, $len)
        foreach ($b in $buf) { if ($b -eq 0) { return $false } }
    }
    finally { $fs.Dispose() }

    return $true
}

function ConvertTo-Array {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [System.Array]) { return $Value }
    return @($Value)
}

function ConvertTo-ChatpackDescriptor {
    param([string]$RawDescriptor)
    if ([string]::IsNullOrWhiteSpace($RawDescriptor)) { return "" }

    $trimmed = $RawDescriptor.Trim()
    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $trimmed.ToCharArray()) {
        if ($invalid -contains $ch) { continue }
        if ([char]::IsWhiteSpace($ch)) {
            [void]$sb.Append("_")
        }
        else {
            [void]$sb.Append($ch)
        }
    }

    $normalized = $sb.ToString()
    $normalized = ($normalized -replace '_{2,}', '_').Trim('_', '.')
    return $normalized
}

function ConvertFrom-YamlScalar {
    param([string]$Raw)
    $value = [string]$Raw
    $value = $value.Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"') -and $value.Length -ge 2) {
        return $value.Substring(1, $value.Length - 2)
    }
    if ($value.StartsWith("'") -and $value.EndsWith("'") -and $value.Length -ge 2) {
        return $value.Substring(1, $value.Length - 2)
    }
    return $value
}

function Get-YamlScalarValue {
    param(
        [string]$YamlPath,
        [string]$Key
    )
    if (-not (Test-Path -LiteralPath $YamlPath)) { return $null }
    $lines = Get-Content -LiteralPath $YamlPath -Encoding UTF8
    foreach ($line in $lines) {
        if ($line -match ("^\s*" + [Regex]::Escape($Key) + "\s*:\s*(.+)\s*$")) {
            return (ConvertFrom-YamlScalar -Raw $Matches[1])
        }
    }
    return $null
}

function Get-SprintWorkItems {
    param([string]$YamlPath)
    if (-not (Test-Path -LiteralPath $YamlPath)) { return @() }
    $lines = Get-Content -LiteralPath $YamlPath -Encoding UTF8
    $items = New-Object System.Collections.Generic.List[object]
    $current = $null
    foreach ($line in $lines) {
        if ($line -match '^\s*-\s*id:\s*(.+)\s*$') {
            if ($null -ne $current) {
                $items.Add([pscustomobject]$current) | Out-Null
            }
            $current = @{
                id = (ConvertFrom-YamlScalar -Raw $Matches[1])
                title = ""
                status = ""
            }
            continue
        }
        if ($null -eq $current) { continue }
        if ($line -match '^\s*title:\s*(.+)\s*$') {
            $current.title = (ConvertFrom-YamlScalar -Raw $Matches[1])
            continue
        }
        if ($line -match '^\s*status:\s*(.+)\s*$') {
            $current.status = (ConvertFrom-YamlScalar -Raw $Matches[1]).ToLowerInvariant()
            continue
        }
    }
    if ($null -ne $current) {
        $items.Add([pscustomobject]$current) | Out-Null
    }
    return @($items.ToArray())
}

function Get-YamlNamedListValues {
    param([string]$YamlPath)
    if (-not (Test-Path -LiteralPath $YamlPath)) { return @() }
    $lines = Get-Content -LiteralPath $YamlPath -Encoding UTF8
    $vals = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match '^\s*-\s*name:\s*(.+)\s*$') {
            $vals.Add((ConvertFrom-YamlScalar -Raw $Matches[1])) | Out-Null
            continue
        }
        if ($line -match '^\s*name:\s*(.+)\s*$') {
            $vals.Add((ConvertFrom-YamlScalar -Raw $Matches[1])) | Out-Null
        }
    }
    return @($vals | Sort-Object -Unique)
}

function Write-Bundle {
    param([string]$Path, [System.Text.StringBuilder]$Builder)
    if ($Builder.Length -le 0) { return }
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Builder.ToString(), $enc)
    $null = $Builder.Clear()
}

function Test-IsExcludedRelativePath {
    param([string]$RelativePath)
    if ([string]::IsNullOrWhiteSpace($RelativePath)) { return $false }
    $lp = $RelativePath.ToLowerInvariant()
    $lp = $lp -replace "/", "\"

    # Skip common generated/build/cache trees.
    if ($lp -match '(^|\\)__pycache__(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.pytest_cache(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.pytest_tmp(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.pytest_tmp_runs(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.pytest_tmp_live(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.mypy_cache(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.ruff_cache(\\|$)') { return $true }
    if ($lp -match '(^|\\)\.codex_tmp(\\|$)') { return $true }

    if ($lp.StartsWith("data\state\")) { return $true }

    # Workspace-local recovery copies and prior packs are diagnostic artifacts,
    # not current project source. Keep the generated chatpack self-contained.
    if ($lp.StartsWith("_cspm_workspace\change_backups\")) { return $true }
    if ($lp.StartsWith("_cspm_workspace\workbook_backups\")) { return $true }
    if ($lp.StartsWith("_cspm_workspace\dump_packs\")) { return $true }
    if ($lp.StartsWith("_cspm_workspace\validation_copies\")) { return $true }

    $first = ($lp -split "\\", 2)[0]
    if ($first -in @(
        "dumps",
        "logs",
        "archive",
        "archives",
        "outputs",
        "output",
        "backups",
        "backup",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "out",
        "coverage"
    )) { return $true }

    # Exclude known repo scaffolding / generated folders that are not needed for restores
    if ($first -like "__DEBUG_GEOMETRY_BUNDLE*") { return $true }
    if ($first -like ".rebuild_backup*") { return $true }
    if ($first -like ".rebuild_*") { return $true }

    # Exclude named virtualenv variants (e.g., .venv_CORY, venv311)
    if ($first -like ".venv*") { return $true }
    if ($first -like "venv*") { return $true }
    if ($first -like "pytest-cache-files-*") { return $true }

    if ($first -like "tmp*") { return $true }
    return $false
}

function Get-EligibleRepoFiles {
    param([string]$RootPath)

    $results = New-Object System.Collections.Generic.List[string]
    $pending = New-Object System.Collections.Generic.Queue[string]
    $pending.Enqueue($RootPath)

    $dirCount = 0
    $fileCount = 0

    while ($pending.Count -gt 0) {
        $dirPath = $pending.Dequeue()
        $dirCount++
        if (($dirCount % 40) -eq 0) {
            Write-Host ("[SCAN] dirs={0} files={1} selected={2}" -f $dirCount, $fileCount, $results.Count)
        }

        $children = @()
        try {
            $children = Get-ChildItem -LiteralPath $dirPath -Force -ErrorAction Stop
        }
        catch {
            $relDir = Get-RelativePath -BasePath $RootPath -FullPath $dirPath
            Write-Host ("WARN: skipping unreadable directory: " + $relDir + " :: " + $_.Exception.Message)
            continue
        }

        foreach ($child in $children) {
            $rel = Get-RelativePath -BasePath $RootPath -FullPath $child.FullName
            if ($child.PSIsContainer) {
                if (Test-IsExcludedRelativePath -RelativePath $rel) { continue }
                $pending.Enqueue($child.FullName)
                continue
            }
            $fileCount++
            if (Test-IsExcludedRelativePath -RelativePath $rel) { continue }
            $results.Add($child.FullName) | Out-Null
        }
    }

    Write-Host ("[SCAN] complete dirs={0} files={1} selected={2}" -f $dirCount, $fileCount, $results.Count)
    return @($results.ToArray())
}

$root = Get-RepoRoot

# Output folder
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$descriptorSuffix = ConvertTo-ChatpackDescriptor -RawDescriptor $Descriptor
$folderName = $stamp
if (-not [string]::IsNullOrWhiteSpace($descriptorSuffix)) {
    $folderName = $stamp + "_" + $descriptorSuffix
}
$outDir = Join-Path $root ("dumps\chatpack\" + $folderName)
$bundlesDir = Join-Path $outDir "bundles"
$stateDir = Join-Path $root "dumps\chatpack\_state"
New-Item -ItemType Directory -Force -Path $bundlesDir | Out-Null
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

# Selection (default: full-repo text context)
$selected = New-Object System.Collections.Generic.List[string]

# Legacy compatibility: docs are now included by default in full-repo mode.
if ($IncludeDocsExtras) {
    Write-Host "INFO: -IncludeDocsExtras is now implicit (default already includes docs)."
}

$allRepoFiles = Get-EligibleRepoFiles -RootPath $root
$allRepoFiles | ForEach-Object { $selected.Add([string]$_) }

$selected = $selected | Sort-Object -Unique

# Build manifest + bundle(s)
$manifest = New-Object System.Collections.Generic.List[object]
$fileTree = New-Object System.Collections.Generic.List[string]

$bundleIndex = 1
$bundlePath = Join-Path $bundlesDir ("BUNDLE_{0:D4}.txt" -f $bundleIndex)
$sb = New-Object System.Text.StringBuilder
$totalSelected = ($selected | Measure-Object).Count
$selectedProcessed = 0

foreach ($fullPath in ($selected | Sort-Object)) {
    $selectedProcessed++
    $relPath = Get-RelativePath -BasePath $root -FullPath $fullPath
    if (($selectedProcessed -eq 1) -or ($selectedProcessed -eq $totalSelected) -or (($selectedProcessed % 250) -eq 0)) {
        Write-Host ("[BUNDLE] {0}/{1} ({2:P0}) :: {3}" -f $selectedProcessed, [Math]::Max(1, $totalSelected), ($selectedProcessed / [double][Math]::Max(1, $totalSelected)), $relPath)
    }

    # Hard exclude (safety net, mirrors selection filter)
    if (Test-IsExcludedRelativePath -RelativePath $relPath) { continue }

    $fi = $null
    $hash = ""
    $bytes = 0
    $isText = $false
    try {
        $fi = Get-Item -LiteralPath $fullPath -ErrorAction Stop
        $fileTree.Add($relPath) | Out-Null
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $fi.FullName -ErrorAction Stop).Hash
        $bytes = $fi.Length
        $isText = Test-IsTextFile -FullPath $fi.FullName
    }
    catch {
        Write-Host ("WARN: skipping unreadable file: " + $relPath + " :: " + $_.Exception.Message)
        continue
    }

    $includeContent = $false
    $bundleName = $null
    $reason = "binary_or_nontext"

    if ($isText) {
        $includeContent = $true
        $reason = "text"
        $bundleName = [System.IO.Path]::GetFileName($bundlePath)

        try {
            # [FIX] Force UTF8 encoding when reading content to prevent Mojibake artifacts.
            # Some empty/special files can still produce $null with -Raw; normalize to string.
            $raw = Get-Content -LiteralPath $fi.FullName -Raw -Encoding UTF8 -ErrorAction Stop
            $rawText = [string]$raw

            $block = ""
            $block += "===== FILE START =====`r`n"
            $block += "PATH: $relPath`r`n"
            $block += "SHA256: $hash`r`n"
            $block += "===== CONTENT START =====`r`n"
            $block += $rawText
            if ($rawText -notmatch "(\r?\n)$") { $block += "`r`n" }
            $block += "===== CONTENT END =====`r`n"
            $block += "===== FILE END =====`r`n`r`n"

            if (($sb.Length + $block.Length) -gt $MaxBundleChars -and $sb.Length -gt 0) {
                Write-Bundle -Path $bundlePath -Builder $sb
                $bundleIndex++
                $bundlePath = Join-Path $bundlesDir ("BUNDLE_{0:D4}.txt" -f $bundleIndex)
                $bundleName = [System.IO.Path]::GetFileName($bundlePath)
            }

            [void]$sb.Append($block)
        }
        catch {
            Write-Host ("WARN: skipping unreadable text content: " + $relPath + " :: " + $_.Exception.Message)
            $includeContent = $false
            $bundleName = $null
            $reason = "text_read_error"
        }
    }

    $manifest.Add([pscustomobject]@{
        path = $relPath
        sha256 = $hash
        bytes = $bytes
        modified_utc = $fi.LastWriteTimeUtc.ToString("o")
        include_content = $includeContent
        bundle = $bundleName
        reason = $reason
    }) | Out-Null
}

Write-Bundle -Path $bundlePath -Builder $sb

# Write outputs
$manifestPath = Join-Path $outDir "03_MANIFEST.json"
$treePath = Join-Path $outDir "04_FILE_TREE.txt"
$readmePath = Join-Path $outDir "00_README_FOR_CHAT.md"
$prefStubPath = Join-Path $outDir "01_PREFERENCES.md"
$summaryPath = Join-Path $outDir "02_PROJECT_SUMMARY.md"
$deltaPath = Join-Path $outDir "05_DELTA_REPORT.md"
$phaseSummaryPath = Join-Path $outDir "08_PHASE_SUMMARY.md"

# Convenience copies of repo docs (so you can upload them directly)
$repoBible = Join-Path $root "docs\BIBLE.md"
$repoPrefs = Join-Path $root "docs\PREFERENCES.md"
$repoPathways = Join-Path $root "docs\MODULE_PATHWAYS.md"
$copyBible = Join-Path $outDir "06_REPO_BIBLE.md"
$copyPrefs = Join-Path $outDir "07_REPO_PREFERENCES.md"
$copyPathways = Join-Path $outDir "09_MODULE_PATHWAYS.md"
if (Test-Path -LiteralPath $repoBible) { Copy-Item -LiteralPath $repoBible -Destination $copyBible -Force }
if (Test-Path -LiteralPath $repoPrefs) { Copy-Item -LiteralPath $repoPrefs -Destination $copyPrefs -Force }
if (-not (Test-Path -LiteralPath $repoPathways)) {
    throw "Required pathways file missing: docs\MODULE_PATHWAYS.md"
}
Copy-Item -LiteralPath $repoPathways -Destination $copyPathways -Force

$manifestArr = $manifest.ToArray()
$manifestJson = ConvertTo-Json -Depth 8 -InputObject $manifestArr
Write-Utf8NoBom -Path $manifestPath -Content $manifestJson
Write-Utf8NoBom -Path $treePath -Content (($fileTree | Sort-Object) -join "`r`n")

$readme = @"
# CSPM Chatpack Ingestion Instructions (Authoritative)
Ingestion order:
1) 01_PREFERENCES.md
2) 02_PROJECT_SUMMARY.md
3) 05_DELTA_REPORT.md
4) 08_PHASE_SUMMARY.md
5) 03_MANIFEST.json
6) 04_FILE_TREE.txt
7) bundles/BUNDLE_0001.txt ... bundles/BUNDLE_XXXX.txt

Optional convenience docs (also uploaded if present):
- 06_REPO_BIBLE.md
- 07_REPO_PREFERENCES.md
- 09_MODULE_PATHWAYS.md
"@
Write-Utf8NoBom -Path $readmePath -Content $readme

$prefStub = @"
# Preferences (Ingestion Stub)
Authoritative: docs/PREFERENCES.md (also copied as 07_REPO_PREFERENCES.md).
Upgrade targets: docs/BIBLE.md (also copied as 06_REPO_BIBLE.md).
"@
Write-Utf8NoBom -Path $prefStubPath -Content $prefStub

# File type counts
$extCounts = @{}
foreach ($e in $manifestArr) {
    $p = [string]$e.path
    $name = [IO.Path]::GetFileName($p)
    $ext = [IO.Path]::GetExtension($name)
    if ([string]::IsNullOrWhiteSpace($ext)) { $ext = "(noext)" }
    $ext = $ext.ToLowerInvariant()
    if (-not $extCounts.ContainsKey($ext)) { $extCounts[$ext] = 0 }
    $extCounts[$ext]++
}

$bundleCount = (Get-ChildItem -LiteralPath $bundlesDir -File -Filter "BUNDLE_*.txt" | Measure-Object).Count
$includedCount = ($manifestArr | Where-Object { $_.include_content -eq $true } | Measure-Object).Count
$binaryCount = ($manifestArr | Where-Object { $_.include_content -eq $false } | Measure-Object).Count

# Improved project summary (with implemented vs missing + targets)
$summary = New-Object System.Text.StringBuilder
[void]$summary.AppendLine("# CSPM Chatpack Summary (Plasma UI v1.0)")
[void]$summary.AppendLine(("Generated: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
[void]$summary.AppendLine(("Root: {0}" -f $root))
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## What This Dump Contains (Always)")
[void]$summary.AppendLine("- Backend code: src/python/**/*.py")
[void]$summary.AppendLine("- UI code: src/qml/**/*.qml")
[void]$summary.AppendLine("- UI assets (text): src/qml/**/*.{json,svg,js,mjs,qmltypes} and src/qml/**/qmldir (when present)")
[void]$summary.AppendLine("- schema/**")
[void]$summary.AppendLine("- docs/BIBLE.md (current state + Practice Console v3.0 targets)")
[void]$summary.AppendLine("- docs/PREFERENCES.md (dump rules + standards)")
[void]$summary.AppendLine("- docs/MODULE_PATHWAYS.md (authoritative 4-tile pathway map)")
[void]$summary.AppendLine("- docs/DECISIONS/**/*.md (architecture decisions, including drag pipeline roadmap)")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## ESTABLISHED RULES & STANDARDS (Plasma UI v1.0)")
[void]$summary.AppendLine("- **Visual Engine**: Strictly use `QtQuick.Effects` (MultiEffect). Legacy `DropShadow` is BANNED.")
[void]$summary.AppendLine("- **Transitions**: Physical border opacity MUST bind to `fadeProgress` to prevent 'flash' artifacts during handover.")
[void]$summary.AppendLine("- **Themes**: 7 Hardcoded Themes. High Contrast Rule: Light Panels = #111111 Text. Dark Panels = White Text.")
[void]$summary.AppendLine("- **Popups**: Must set `dim: false` to prevent square overlay artifacts on rounded glass windows.")
[void]$summary.AppendLine("- **Calendar**: Must be monitor-aware (openAt cursor, clamp to current screen).")
[void]$summary.AppendLine("- **Strict Syntax**: MouseArea handlers must use `function(mouse) { ... }`.")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Snapshot Stats")
[void]$summary.AppendLine(("- Files in manifest: {0}" -f $manifestArr.Length))
[void]$summary.AppendLine(("- Included with content: {0}" -f $includedCount))
[void]$summary.AppendLine(("- Binary/non-text files: {0}" -f $binaryCount))
[void]$summary.AppendLine(("- BundleCount: {0}" -f $bundleCount))
[void]$summary.AppendLine(("- MaxBundleChars: {0}" -f $MaxBundleChars))
[void]$summary.AppendLine("")
[void]$summary.AppendLine("### File Types (Count)")
foreach ($k in ($extCounts.Keys | Sort-Object)) {
    [void]$summary.AppendLine(("- {0}: {1}" -f $k, $extCounts[$k]))
}
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Entry Points (Quick Orientation)")
[void]$summary.AppendLine("- Python boot: src/python/main.py")
[void]$summary.AppendLine("- QML root UI: src/qml/Main.qml")
[void]$summary.AppendLine("- Themes: src/qml/themes/themes.json")
[void]$summary.AppendLine("- Icons: src/qml/assets/icons/*.svg")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Implemented Now (High Signal)")
[void]$summary.AppendLine("- Theme engine + theme picker present (themes.json + ThemePicker).")
[void]$summary.AppendLine("- Console grid + tile navigation present (Main.qml + TileCard).")
[void]$summary.AppendLine("- SVG icon assets present and referenced by tiles.")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Not Implemented Yet (Upgrade Targets / Gaps)")
[void]$summary.AppendLine("- Pop-out / tear-away multi-instance windows.")
[void]$summary.AppendLine("- Two timers concurrently (Timer A popped-out + Timer B in-console).")
[void]$summary.AppendLine("- Ghost indicator on tiles for active floating modules.")
[void]$summary.AppendLine("- Bubble Gum physics applied consistently across click/transition/hover.")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Practice Console v3.0 Targets Included In This Dump")
[void]$summary.AppendLine("- Hybrid multi-instance tear-away windows while main console remains launcher.")
[void]$summary.AppendLine("- Two Timers Rule (concurrent workflows).")
[void]$summary.AppendLine("- Ghost indicator (informational, non-blocking).")
[void]$summary.AppendLine("- Electric Bubble Gum animations + Electric Glass visuals + 7 themes.")
[void]$summary.AppendLine("")
[void]$summary.AppendLine("## Exclusions (Hard)")
[void]$summary.AppendLine("- scripts/**")
[void]$summary.AppendLine("- dumps/**")
[void]$summary.AppendLine("- archive/**")
[void]$summary.AppendLine("- outputs/**")
[void]$summary.AppendLine("- backups/**")
[void]$summary.AppendLine("- data/state/**")
Write-Utf8NoBom -Path $summaryPath -Content $summary.ToString()

# Enhanced Delta (Added/Removed/Changed + Top 10 Modified)
$lastManifestPath = Join-Path $stateDir "last_manifest.json"

$prevMap = @{}
if (Test-Path -LiteralPath $lastManifestPath) {
    $prevObj = Get-Content -LiteralPath $lastManifestPath -Raw | ConvertFrom-Json
    $prevArr = ConvertTo-Array -Value $prevObj
    foreach ($p in $prevArr) { if ($null -ne $p -and $p.path) { $prevMap[$p.path] = $p.sha256 } }
}

$currMap = @{}
foreach ($c in $manifestArr) { if ($null -ne $c -and $c.path) { $currMap[$c.path] = $c.sha256 } }

$added   = @()
$removed = @()
$changed = @()

foreach ($k in $currMap.Keys) {
    if (-not $prevMap.ContainsKey($k)) { $added += $k }
    elseif ($prevMap[$k] -ne $currMap[$k]) { $changed += $k }
}
foreach ($k in $prevMap.Keys) {
    if (-not $currMap.ContainsKey($k)) { $removed += $k }
}

$delta = New-Object System.Text.StringBuilder
[void]$delta.AppendLine("# Delta Report (Enhanced+)")
[void]$delta.AppendLine(("Generated: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
[void]$delta.AppendLine("")
[void]$delta.AppendLine("## Summary")
[void]$delta.AppendLine(("- Added: {0}" -f (($added | Measure-Object).Count)))
[void]$delta.AppendLine(("- Removed: {0}" -f (($removed | Measure-Object).Count)))
[void]$delta.AppendLine(("- Changed: {0}" -f (($changed | Measure-Object).Count)))
[void]$delta.AppendLine("")

[void]$delta.AppendLine("## Added")
if (($added | Measure-Object).Count -eq 0) { [void]$delta.AppendLine("- (none)") }
else { foreach ($x in ($added | Sort-Object)) { [void]$delta.AppendLine("- " + $x) } }
[void]$delta.AppendLine("")

[void]$delta.AppendLine("## Removed")
if (($removed | Measure-Object).Count -eq 0) { [void]$delta.AppendLine("- (none)") }
else { foreach ($x in ($removed | Sort-Object)) { [void]$delta.AppendLine("- " + $x) } }
[void]$delta.AppendLine("")

[void]$delta.AppendLine("## Changed")
if (($changed | Measure-Object).Count -eq 0) { [void]$delta.AppendLine("- (none)") }
else {
    foreach ($x in ($changed | Sort-Object)) {
        [void]$delta.AppendLine(("- {0}`n  - old: {1}`n  - new: {2}" -f $x, $prevMap[$x], $currMap[$x]))
    }
}
[void]$delta.AppendLine("")

[void]$delta.AppendLine("## Most Recently Modified (Top 10 by modified_utc)")
$top = $manifestArr | Sort-Object modified_utc -Descending | Select-Object -First 10
foreach ($e in $top) { [void]$delta.AppendLine(("- {0} ({1})" -f $e.path, $e.modified_utc)) }
[void]$delta.AppendLine("")

Write-Utf8NoBom -Path $deltaPath -Content $delta.ToString()

# Semantic phase summary (spec-aware, delta-aware)
$sprintSpecPath = Join-Path $root "docs\spec\sprint0_execution.yaml"
$backupSpecPath = Join-Path $root "docs\spec\backup_restore_policy.yaml"
$reportSpecPath = Join-Path $root "docs\spec\reporting_ux.yaml"
$workflowSpecPath = Join-Path $root "docs\spec\user_flow_priority.yaml"
$programSpecPath = Join-Path $root "docs\spec\program_manifest.yaml"
$biblePath = Join-Path $root "docs\BIBLE.md"
$roadmapPath = Join-Path $root "docs\ROADMAP.md"
$modulePathwaysPath = Join-Path $root "docs\MODULE_PATHWAYS.md"

$sprintStatus = Get-YamlScalarValue -YamlPath $sprintSpecPath -Key "status"
if ([string]::IsNullOrWhiteSpace($sprintStatus)) { $sprintStatus = "unknown" }
$sprintName = Get-YamlScalarValue -YamlPath $sprintSpecPath -Key "name"
if ([string]::IsNullOrWhiteSpace($sprintName)) { $sprintName = "Unspecified Sprint" }

$autoBackupInterval = Get-YamlScalarValue -YamlPath $backupSpecPath -Key "interval_minutes_default"
if ([string]::IsNullOrWhiteSpace($autoBackupInterval)) { $autoBackupInterval = "unknown" }

$workItems = @(Get-SprintWorkItems -YamlPath $sprintSpecPath)
$doneItems = @($workItems | Where-Object { $_.status -eq "done" })
$inProgressItems = @($workItems | Where-Object { $_.status -eq "in_progress" })
$nextItems = @($workItems | Where-Object { $_.status -eq "next" -or $_.status -eq "pending" })
$unknownItems = @($workItems | Where-Object {
    $_.status -ne "done" -and $_.status -ne "in_progress" -and $_.status -ne "next" -and $_.status -ne "pending"
})

$reportFamilies = @(Get-YamlNamedListValues -YamlPath $reportSpecPath)
$workflowNames = @(Get-YamlNamedListValues -YamlPath $workflowSpecPath)

$phaseSignal = "Steady state"
if (($inProgressItems | Measure-Object).Count -gt 0) {
    $phaseSignal = "Active build in progress"
} elseif (($nextItems | Measure-Object).Count -gt 0) {
    $phaseSignal = "Sprint mostly complete; next queue identified"
}

$phaseTop = @($manifestArr | Sort-Object modified_utc -Descending | Select-Object -First 8)

$phase = New-Object System.Text.StringBuilder
[void]$phase.AppendLine("# Semantic Phase Summary")
[void]$phase.AppendLine(("Generated: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
[void]$phase.AppendLine("")
[void]$phase.AppendLine("## Current Program Phase")
[void]$phase.AppendLine(("- Sprint: {0}" -f $sprintName))
[void]$phase.AppendLine(("- Sprint status: {0}" -f $sprintStatus))
[void]$phase.AppendLine(("- Signal: {0}" -f $phaseSignal))
[void]$phase.AppendLine("")
[void]$phase.AppendLine("## Execution Board (from docs/spec/sprint0_execution.yaml)")
[void]$phase.AppendLine(("- Total work items: {0}" -f (($workItems | Measure-Object).Count)))
[void]$phase.AppendLine(("- Done: {0}" -f (($doneItems | Measure-Object).Count)))
[void]$phase.AppendLine(("- In progress: {0}" -f (($inProgressItems | Measure-Object).Count)))
[void]$phase.AppendLine(("- Next/Pending: {0}" -f (($nextItems | Measure-Object).Count)))
[void]$phase.AppendLine(("- Other status: {0}" -f (($unknownItems | Measure-Object).Count)))
[void]$phase.AppendLine("")

[void]$phase.AppendLine("### In Progress")
if (($inProgressItems | Measure-Object).Count -eq 0) {
    [void]$phase.AppendLine("- (none)")
} else {
    foreach ($item in $inProgressItems) {
        [void]$phase.AppendLine(("- {0}: {1}" -f $item.id, $item.title))
    }
}
[void]$phase.AppendLine("")

[void]$phase.AppendLine("### Next Up")
if (($nextItems | Measure-Object).Count -eq 0) {
    [void]$phase.AppendLine("- (none)")
} else {
    foreach ($item in $nextItems) {
        [void]$phase.AppendLine(("- {0}: {1}" -f $item.id, $item.title))
    }
}
[void]$phase.AppendLine("")

[void]$phase.AppendLine("## Delta Evidence (this dump vs previous)")
[void]$phase.AppendLine(("- Added files: {0}" -f (($added | Measure-Object).Count)))
[void]$phase.AppendLine(("- Removed files: {0}" -f (($removed | Measure-Object).Count)))
[void]$phase.AppendLine(("- Changed files: {0}" -f (($changed | Measure-Object).Count)))
[void]$phase.AppendLine("")
[void]$phase.AppendLine("### Most Recently Modified Files")
foreach ($e in $phaseTop) {
    [void]$phase.AppendLine(("- {0}" -f $e.path))
}
[void]$phase.AppendLine("")

[void]$phase.AppendLine("## Data Safety Posture")
[void]$phase.AppendLine(("- Core database backup cadence target: every {0} minutes" -f $autoBackupInterval))
[void]$phase.AppendLine("- Policy source: docs/spec/backup_restore_policy.yaml")
[void]$phase.AppendLine("- Runtime snapshot service presence: src/python/services/project_snapshot_service.py")
[void]$phase.AppendLine("")

[void]$phase.AppendLine("## Reporting UX Scope")
if (($reportFamilies | Measure-Object).Count -eq 0) {
    [void]$phase.AppendLine("- (report families not found in reporting_ux spec)")
} else {
    foreach ($name in $reportFamilies) {
        [void]$phase.AppendLine(("- " + $name))
    }
}
[void]$phase.AppendLine("")

[void]$phase.AppendLine("## User-Frequency Build Order (Spec Trace)")
if (($workflowNames | Measure-Object).Count -eq 0) {
    [void]$phase.AppendLine("- (workflow order names not found)")
} else {
    foreach ($name in $workflowNames) {
        [void]$phase.AppendLine(("- " + $name))
    }
}
[void]$phase.AppendLine("")

[void]$phase.AppendLine("## Source Files Checked")
$phaseSources = @(
    $programSpecPath,
    $sprintSpecPath,
    $workflowSpecPath,
    $backupSpecPath,
    $reportSpecPath,
    $biblePath,
    $roadmapPath,
    $modulePathwaysPath,
    $deltaPath
)
foreach ($src in $phaseSources) {
    if (Test-Path -LiteralPath $src) {
        $rel = Get-RelativePath -BasePath $root -FullPath (Resolve-Path $src).Path
        [void]$phase.AppendLine(("- [found] " + $rel))
    } else {
        $name = [IO.Path]::GetFileName($src)
        [void]$phase.AppendLine(("- [missing] " + $name))
    }
}

Write-Utf8NoBom -Path $phaseSummaryPath -Content $phase.ToString()

# Persist last manifest
Write-Utf8NoBom -Path $lastManifestPath -Content $manifestJson

Write-Host ("Chatpack generated at: " + $outDir)
Write-Host ("Bundles: " + $bundleCount)
Write-Host ("Files in manifest: " + $manifestArr.Length)
Write-Host ("Binary/non-text files: " + $binaryCount)
