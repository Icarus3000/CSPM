param(
    [string]$SourceRoot = "src/qml",
    [string]$OutCsv = "docs/spec/ui_control_registry.csv",
    [string]$OutSummary = "docs/spec/ui_control_registry_summary.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Normalize-RelPath {
    param(
        [string]$BasePath,
        [string]$FullPath
    )
    $baseUri = New-Object System.Uri(($BasePath.TrimEnd("\") + "\"))
    $fullUri = New-Object System.Uri($FullPath)
    $rel = $baseUri.MakeRelativeUri($fullUri).ToString()
    $rel = [System.Uri]::UnescapeDataString($rel)
    return ($rel -replace "/", "\")
}

function Compact-Expression {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $text = $Value.Trim()
    if ($text.Length -gt 180) {
        return $text.Substring(0, 180) + "..."
    }
    return $text
}

function Detect-LaneFromPath {
    param([string]$RelPath)
    $p = $RelPath.ToLowerInvariant()
    if ($p -like "*timedocketview.qml") { return "Docketing & Deadlines" }
    if ($p -like "*transactionsmasterview.qml") { return "Billing, Payments & Tax" }
    if ($p -like "*placeholdersubmenuview.qml") { return "Placeholder Host (multi-lane)" }
    if ($p -like "*homegrid.qml") { return "Home Hub" }
    if ($p -like "*maincontent.qml") { return "Main Module Host" }
    if ($p -like "*detachedshellwindow.qml") { return "Window Shell" }
    return "Unclassified"
}

$repoRoot = Resolve-RepoRoot
$sourceAbs = Join-Path $repoRoot $SourceRoot
$outCsvAbs = Join-Path $repoRoot $OutCsv
$outSummaryAbs = Join-Path $repoRoot $OutSummary

if (-not (Test-Path -LiteralPath $sourceAbs)) {
    throw "Source root not found: $sourceAbs"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $outCsvAbs) -Force | Out-Null

$interactiveTypes = @(
    "Action",
    "Button",
    "CheckBox",
    "ComboBox",
    "Dial",
    "IconButton",
    "MenuItem",
    "MouseArea",
    "PillButton",
    "PillTextField",
    "RadioButton",
    "RoundButton",
    "Slider",
    "SpinBox",
    "Switch",
    "TabButton",
    "TextArea",
    "TextField",
    "ToolButton",
    "ModernTextField"
)
$interactiveTypeSet = @{}
foreach ($entry in $interactiveTypes) {
    $interactiveTypeSet[$entry] = $true
}
$interactiveSuffixRegex = '(Button|TextField|TextArea|ComboBox|CheckBox|RadioButton|Switch|SpinBox|Slider|Dial|MouseArea)$'
$placeholderRegex = '(placeholder|coming soon|open placeholder|stub|todo|workflow placeholders|pathway placeholder)'

$rows = New-Object System.Collections.Generic.List[object]
$qmlFiles = Get-ChildItem -LiteralPath $sourceAbs -Recurse -File -Filter *.qml | Sort-Object FullName

foreach ($file in $qmlFiles) {
    $relPath = Normalize-RelPath -BasePath $repoRoot -FullPath $file.FullName
    $lane = Detect-LaneFromPath -RelPath $relPath
    $lines = Get-Content -LiteralPath $file.FullName -Encoding UTF8
    $stack = New-Object System.Collections.Generic.List[object]
    $braceDepth = 0

    for ($idx = 0; $idx -lt $lines.Count; $idx++) {
        $line = [string]$lines[$idx]
        $lineNo = $idx + 1

        if ($stack.Count -gt 0) {
            $active = $stack[$stack.Count - 1]
            if ((-not $active.id) -and ($line -match '^\s*id\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*$')) {
                $active.id = $Matches[1]
            }
            if ((-not $active.textExpr) -and ($line -match '^\s*text\s*:\s*(.+?)\s*$')) {
                $active.textExpr = Compact-Expression -Value $Matches[1]
            }
            if ((-not $active.placeholderExpr) -and ($line -match '^\s*placeholderText\s*:\s*(.+?)\s*$')) {
                $active.placeholderExpr = Compact-Expression -Value $Matches[1]
            }
            if ($line -match '^\s*(on[A-Z][A-Za-z0-9_]*)\s*:') {
                $handler = $Matches[1]
                if ($active.handlers -notcontains $handler) {
                    $active.handlers += $handler
                }
            }
        }

        if ($line -match '^\s*([A-Z][A-Za-z0-9_]*)\s*\{') {
            $type = $Matches[1]
            $isControl = $false
            if ($interactiveTypeSet.ContainsKey($type)) {
                $isControl = $true
            } elseif ($type -match $interactiveSuffixRegex) {
                $isControl = $true
            }

            $ctx = [pscustomobject]@{
                type = $type
                file = $relPath
                lane = $lane
                line = [int]$lineNo
                startDepth = [int]$braceDepth
                isControl = [bool]$isControl
                id = ""
                textExpr = ""
                placeholderExpr = ""
                handlers = @()
            }
            $stack.Add($ctx) | Out-Null
        }

        $openBraces = ([regex]::Matches($line, '\{')).Count
        $closeBraces = ([regex]::Matches($line, '\}')).Count
        $braceDepth += ($openBraces - $closeBraces)

        while ($stack.Count -gt 0 -and $braceDepth -le [int]$stack[$stack.Count - 1].startDepth) {
            $closed = $stack[$stack.Count - 1]
            $stack.RemoveAt($stack.Count - 1)

            if (-not $closed.isControl) {
                continue
            }

            $handlers = @($closed.handlers | Sort-Object -Unique)
            $handlerText = ""
            if ($handlers.Count -gt 0) {
                $handlerText = ($handlers -join ", ")
            }

            $heuristicBlob = (
                [string]$closed.file + " " +
                [string]$closed.type + " " +
                [string]$closed.textExpr + " " +
                [string]$closed.placeholderExpr + " " +
                [string]$handlerText
            ).ToLowerInvariant()
            $likelyPlaceholder = $heuristicBlob -match $placeholderRegex

            $status = "unwired"
            if ($likelyPlaceholder) {
                $status = "placeholder"
            } elseif ($handlers.Count -gt 0) {
                $status = "wired"
            }

            $rows.Add([pscustomobject]@{
                lane = $closed.lane
                file = $closed.file
                line = [int]$closed.line
                control_type = $closed.type
                control_id = [string]$closed.id
                text_expr = [string]$closed.textExpr
                placeholder_expr = [string]$closed.placeholderExpr
                handlers = $handlerText
                status = $status
                likely_placeholder = [bool]$likelyPlaceholder
            }) | Out-Null
        }
    }
}

$orderedRows = @($rows.ToArray() | Sort-Object file, line, control_type, control_id)
$orderedRows | Export-Csv -LiteralPath $outCsvAbs -NoTypeInformation -Encoding UTF8

$totalControls = $orderedRows.Count
$wiredCount = @($orderedRows | Where-Object { $_.status -eq "wired" }).Count
$placeholderCount = @($orderedRows | Where-Object { $_.status -eq "placeholder" }).Count
$unwiredCount = @($orderedRows | Where-Object { $_.status -eq "unwired" }).Count

$byFile = @($orderedRows | Group-Object file | Sort-Object Count -Descending)
$topPlaceholder = @(
    $orderedRows |
    Where-Object { $_.status -eq "placeholder" -or $_.status -eq "unwired" } |
    Sort-Object file, line |
    Select-Object -First 120
)

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# UI Control Registry Summary")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Totals")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("- Total controls: $totalControls")
[void]$sb.AppendLine("- Wired controls: $wiredCount")
[void]$sb.AppendLine("- Placeholder controls: $placeholderCount")
[void]$sb.AppendLine("- Unwired controls: $unwiredCount")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Files By Control Count")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("| File | Count |")
[void]$sb.AppendLine("|---|---:|")
foreach ($group in $byFile) {
    [void]$sb.AppendLine("| " + $group.Name + " | " + $group.Count + " |")
}
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Priority Queue (Placeholder/Unwired First 120)")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("| Lane | File | Line | Type | Id | Text | Status | Handlers |")
[void]$sb.AppendLine("|---|---|---:|---|---|---|---|---|")
foreach ($row in $topPlaceholder) {
    $lane = [string]$row.lane
    $fileCol = [string]$row.file
    $lineCol = [string]$row.line
    $typeCol = [string]$row.control_type
    $idCol = ([string]$row.control_id).Replace("|", "\|")
    $textCol = ([string]$row.text_expr).Replace("|", "\|")
    $statusCol = [string]$row.status
    $handlerCol = ([string]$row.handlers).Replace("|", "\|")
    [void]$sb.AppendLine("| $lane | $fileCol | $lineCol | $typeCol | $idCol | $textCol | $statusCol | $handlerCol |")
}
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Output Files")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("- CSV: " + (Normalize-RelPath -BasePath $repoRoot -FullPath $outCsvAbs))
[void]$sb.AppendLine("- Summary: " + (Normalize-RelPath -BasePath $repoRoot -FullPath $outSummaryAbs))

Set-Content -LiteralPath $outSummaryAbs -Value $sb.ToString() -Encoding UTF8

Write-Host "UI control registry generated."
Write-Host ("CSV: " + $outCsvAbs)
Write-Host ("Summary: " + $outSummaryAbs)
Write-Host ("Totals => all: {0}, wired: {1}, placeholder: {2}, unwired: {3}" -f $totalControls, $wiredCount, $placeholderCount, $unwiredCount)
