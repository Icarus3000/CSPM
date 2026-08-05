# PSScriptAnalyzer disable=PSUseApprovedVerbs
# PSScriptAnalyzer: disable=PSUseApprovedVerbs

param(
    [string]$RegistryCsv = "docs/spec/ui_control_registry.csv",
    [string]$OutCsv = "docs/spec/ui_control_contract_matrix.csv",
    [string]$OutSummary = "docs/spec/ui_control_contract_matrix.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function RelPath {
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

function Format-Text {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    return $Value.Trim()
}

function Get-ActionClass {
    param([string]$Handlers)
    $h = (Format-Text $Handlers).ToLowerInvariant()
    if ($h.Contains("onclicked") -or $h.Contains("onaccepted") -or $h.Contains("ondoubleclicked")) { return "command" }
    if ($h.Contains("onactivated")) { return "selection_change" }
    if ($h.Contains("ontextchanged") -or $h.Contains("onedittextchanged") -or $h.Contains("oneditingfinished")) { return "input_change" }
    return "state_binding"
}

function Get-ControlLabel {
    param(
        [string]$Id,
        [string]$TextExpr,
        [string]$PlaceholderExpr
    )
    $text = (Format-Text $TextExpr)
    if ($text.Length -gt 0) {
        return $text
    }
    $idText = (Format-Text $Id)
    if ($idText.Length -gt 0) {
        return $idText
    }
    $ph = (Format-Text $PlaceholderExpr)
    if ($ph.Length -gt 0) {
        return "placeholder:" + $ph
    }
    return "(no_label)"
}

function Resolve-BackendSlots {
    param([object]$Row)

    $file = (Format-Text $Row.file).ToLowerInvariant()
    $line = [int]$Row.line
    $id = (Format-Text $Row.control_id).ToLowerInvariant()
    $text = (Format-Text $Row.text_expr).ToLowerInvariant()
    $handlers = (Format-Text $Row.handlers).ToLowerInvariant()

    if ($file -like "*\views\timedocketview.qml") {
        if ($text -match 'run report') { return "getDocketActivityReport" }
        if ($text -match 'export csv') { return "exportDocketActivityCsv" }
        if ($text -match 'start|stop|save docket|mark ready|mark billed|set draft') { return "saveTimeDocketEntry" }
        if ($text -match 'take over|release|lock') { return "acquireGlobalTimerLock|releaseGlobalTimerLock|getGlobalTimerLock" }
        if ($id -match 'client') { return "listClientNames|getTimeDocketAggregate" }
        if ($id -match 'matter') { return "listMatterNames|getTimeDocketAggregate" }
        if ($id -match 'date|time|timer') { return "getTimeDocketAggregate" }
        if ($handlers -match 'ontextchanged|onactivated') { return "getTimeDocketAggregate" }
        return "saveTimeDocketEntry"
    }

    if ($file -like "*\views\transactionsmasterview.qml") {
        if ($text -match 'refresh') { return "listTransactionAccounts|listTransactionBusinessUnits|listTransactionPayees|listParentNames|listClientNames|listMatterNames|listTransactionCategories|listTransactions" }
        if ($text -match 'reset draft') { return "local_qml_only" }
        if ($id -match 'category') { return "listTransactionCategories" }
        if ($id -match 'account|businessunit|payee|parent|client|matter') { return "listTransactionAccounts|listTransactionBusinessUnits|listTransactionPayees|listParentNames|listClientNames|listMatterNames" }
        if ($id -match 'amount|tax|status|invoice|void|notes|expense|class|type|currency|member') { return "saveTransaction" }
        return "saveTransaction"
    }

    if ($file -like "*\views\placeholdersubmenuview.qml") {
        if ($text -match 'load profile') {
            if ($id -match 'matter' -or $text -match 'matter' -or $line -ge 3300) { return "getMatterProfile" }
            return "getClientProfile"
        }
        if ($text -match 'save anyway|save|submit') { return "saveClientProfile|saveMatterProfile" }
        if ($text -match 'edit client|new client') { return "saveClientProfile" }
        if ($text -match 'edit matter') { return "saveMatterProfile" }
        if ($text -match 'directory') {
            if ($id -match 'matter' -or $text -match 'matter') { return "listMatterDirectory" }
            return "listClientDirectory"
        }
        if ($text -match 'auto') { return "previewMatterNumber" }
        if ($text -match 'run search|search|boolean|any') { return "searchGlobalEntities" }
        if ($id -match 'search') { return "searchGlobalEntities" }
        if ($id -match 'parent') { return "listParentNames|saveClientProfile|saveMatterProfile" }
        if ($id -match 'client') { return "listClientNames|listClientDirectory|getClientProfile|saveClientProfile" }
        if ($id -match 'matter') { return "listMatterNames|listMatterDirectory|getMatterProfile|saveMatterProfile|previewMatterNumber" }
        return "saveClientProfile|saveMatterProfile"
    }

    if ($file -like "*\views\homegrid.qml") {
        if ($id -match 'search|omni' -or $text -match 'search') { return "handleOmniSearchCommand|getHomeDashboardSummary" }
        return "getHomeDashboardSummary"
    }

    if ($file -like "*\views\maincontent.qml") {
        if ($text -match 'search' -or $id -match 'search') { return "handleOmniSearchCommand" }
        if ($text -match 'undock|dock') { return "recordUndockRequest" }
        return "getHomeDashboardSummary|recordUndockRequest"
    }

    return "local_qml_only"
}

function Resolve-DataEffect {
    param([string]$Slots)
    $slotEffects = @{
        "getHomeDashboardSummary" = "Reads dashboard aggregates for home hub cards and counters."
        "handleOmniSearchCommand" = "Routes omni-search commands into target module/view actions."
        "recordUndockRequest" = "Records undock telemetry/state for shell window routing."
        "getTimeDocketAggregate" = "Reads aggregated time bucket state for date/client/matter context."
        "saveTimeDocketEntry" = "Creates or updates time docket rows; recalculates fees/status."
        "acquireGlobalTimerLock" = "Claims single-owner global timer lock across windows."
        "releaseGlobalTimerLock" = "Releases global timer lock for owner window."
        "getGlobalTimerLock" = "Reads current global timer lock holder."
        "getDocketActivityReport" = "Builds docket activity result set for report panel filters."
        "exportDocketActivityCsv" = "Exports current docket activity report result set to CSV."
        "listClientNames" = "Reads active client list for selectors; clients are grouped by matter."
        "listMatterNames" = "Reads matter list for selectors; active matters are highlighted."
        "listActiveMatterNames" = "Reads active matter list for selectors."
        "listClientDirectory" = "Reads client directory rows for listing/search."
        "listMatterDirectory" = "Reads matter directory rows for listing/search."
        "listActiveMatterDirectory" = "Reads active matter directory rows for listing/search."
        "getClientProfile" = "Reads full client profile payload for edit/view."
        "getMatterProfile" = "Reads full matter profile payload for edit/view."
        "saveClientProfile" = "Creates/updates client profile and related directory fields."
        "saveMatterProfile" = "Creates/updates matter profile and related directory fields."
        "previewMatterNumber" = "Calculates suggested matter number from client/type/date."
        "searchGlobalEntities" = "Runs global entity search across clients/matters/keys."
        "listParentNames" = "Reads parent client names for relational selectors."
        "listTransactionAccounts" = "Reads account lookup options."
        "listTransactionBusinessUnits" = "Reads business unit lookup options."
        "listTransactionPayees" = "Reads payee lookup options."
        "listTransactionCategories" = "Reads filtered category lookup options."
        "listTransactions" = "Reads transactions for recent/history lists."
        "saveTransaction" = "Creates/updates transaction row and derived amounts."
        "local_qml_only" = "Local UI state only; no backend persistence invocation."
    }
    $parts = @()
    foreach ($slot in ((Format-Text $Slots) -split "\|")) {
        $s = (Format-Text $slot)
        if ($s.Length -le 0) { continue }
        if ($slotEffects.ContainsKey($s)) {
            $parts += $slotEffects[$s]
        } else {
            $parts += ("Backend effect not yet documented for slot: " + $s)
        }
    }
    if ($parts.Count -le 0) {
        return "No explicit effect mapped."
    }
    return ($parts -join " ")
}

function Resolve-Precondition {
    param(
        [string]$ActionClass,
        [string]$Status,
        [string]$Slots
    )
    $base = "Control must be visible and enabled in active module context."
    switch ($ActionClass) {
        "command" { $base = "Required form fields must pass validation before command execution." }
        "selection_change" { $base = "Lookup/model options must be loaded before selection change." }
        "input_change" { $base = "Field must accept user input and stay within type/format rules." }
        default { $base = "Control binding must evaluate in active context without runtime errors." }
    }
    if ((Format-Text $Status).ToLowerInvariant() -eq "placeholder") {
        return $base + " Placeholder behavior must be replaced by live workflow implementation."
    }
    if ((Format-Text $Slots).Contains("local_qml_only")) {
        return $base + " Backend call is not expected for this control."
    }
    return $base
}

function Resolve-Postcondition {
    param(
        [string]$ActionClass,
        [string]$Slots
    )
    $slots = Format-Text $Slots
    if ($slots.Contains("local_qml_only")) {
        return "UI state updates deterministically (dirty/selection/visibility) without persistence."
    }
    switch ($ActionClass) {
        "command" { return "Requested backend operation completes with success/failure feedback and observable state change." }
        "selection_change" { return "Dependent fields/lists refresh and remain coherent with selected value." }
        "input_change" { return "Derived values and dirty-state tracking update immediately and consistently." }
        default { return "Control state/binding updates without side effects or stale state." }
    }
}

function Resolve-Priority {
    param(
        [string]$Status,
        [string]$ActionClass,
        [string]$Label
    )
    $s = (Format-Text $Status).ToLowerInvariant()
    $l = (Format-Text $Label).ToLowerInvariant()
    if ($s -eq "placeholder" -or $s -eq "unwired") {
        if ($ActionClass -eq "command" -and $l -match '\b(save|run|export|submit|mark|start|stop|search|load profile)\b') { return "P0" }
        return "P1"
    }
    if ($ActionClass -eq "command") { return "P1" }
    return "P2"
}

$repoRoot = Resolve-RepoRoot
$registryCsvAbs = Join-Path $repoRoot $RegistryCsv
$outCsvAbs = Join-Path $repoRoot $OutCsv
$outSummaryAbs = Join-Path $repoRoot $OutSummary

if (-not (Test-Path -LiteralPath $registryCsvAbs)) {
    throw "Registry CSV not found: $registryCsvAbs. Run scripts/80_generate_ui_control_registry.ps1 first."
}

New-Item -ItemType Directory -Path (Split-Path -Parent $outCsvAbs) -Force | Out-Null

$sourceRows = Import-Csv -LiteralPath $registryCsvAbs

# High-priority scope for NP-02: all interactive controls under views (excluding shell/chrome internals).
$highPriorityRows = @(
    $sourceRows |
    Where-Object {
        $file = (Format-Text $_.file).ToLowerInvariant()
        $lane = (Format-Text $_.lane).ToLowerInvariant()
        $file.StartsWith("src\qml\views\") -and $lane -ne "window shell"
    } |
    Sort-Object file, @{Expression={[int]$_.line}}, control_type, control_id
)

$matrixRows = New-Object System.Collections.Generic.List[object]
$counter = 1

foreach ($row in $highPriorityRows) {
    $label = Get-ControlLabel -Id $row.control_id -TextExpr $row.text_expr -PlaceholderExpr $row.placeholder_expr
    $actionClass = Get-ActionClass -Handlers $row.handlers
    $slots = Resolve-BackendSlots -Row $row
    $dataEffect = Resolve-DataEffect -Slots $slots
    $precondition = Resolve-Precondition -ActionClass $actionClass -Status $row.status -Slots $slots
    $postcondition = Resolve-Postcondition -ActionClass $actionClass -Slots $slots
    $priority = Resolve-Priority -Status $row.status -ActionClass $actionClass -Label $label

    $matrixRows.Add([pscustomobject]@{
        contract_id = ("NP02-{0:D4}" -f $counter)
        lane = [string]$row.lane
        file = [string]$row.file
        line = [int]$row.line
        control_type = [string]$row.control_type
        control_id = [string]$row.control_id
        control_label = $label
        handlers = [string]$row.handlers
        action_class = $actionClass
        backend_slots = $slots
        data_effect = $dataEffect
        preconditions = $precondition
        postconditions = $postcondition
        current_status = [string]$row.status
        priority = $priority
        target_state = "live"
    }) | Out-Null

    $counter += 1
}

$finalRows = @($matrixRows.ToArray())
$finalRows | Export-Csv -LiteralPath $outCsvAbs -NoTypeInformation -Encoding UTF8

$total = $finalRows.Count
$byPriority = @($finalRows | Group-Object priority | Sort-Object Name)
$byStatus = @($finalRows | Group-Object current_status | Sort-Object Name)
$bySlot = @(
    $finalRows |
    ForEach-Object {
        $slots = (Format-Text $_.backend_slots) -split "\|"
        foreach ($s in $slots) {
            $slot = Format-Text $s
            if ($slot.Length -gt 0) {
                [pscustomobject]@{ slot = $slot }
            }
        }
    } |
    Group-Object slot |
    Sort-Object Count -Descending
)
$topP0 = @($finalRows | Where-Object { $_.priority -eq "P0" } | Select-Object -First 120)

$md = New-Object System.Text.StringBuilder
[void]$md.AppendLine("# UI Control Contract Matrix (NP-02)")
[void]$md.AppendLine("")
[void]$md.AppendLine("Generated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
[void]$md.AppendLine("")
[void]$md.AppendLine("Scope: high-priority interactive controls under `src/qml/views` (excluding shell chrome).")
[void]$md.AppendLine("")
[void]$md.AppendLine("## Totals")
[void]$md.AppendLine("")
[void]$md.AppendLine("- Contracts generated: $total")
[void]$md.AppendLine("")
[void]$md.AppendLine("### By Current Status")
foreach ($group in $byStatus) {
    [void]$md.AppendLine("- " + $group.Name + ": " + $group.Count)
}
[void]$md.AppendLine("")
[void]$md.AppendLine("### By Priority")
foreach ($group in $byPriority) {
    [void]$md.AppendLine("- " + $group.Name + ": " + $group.Count)
}
[void]$md.AppendLine("")
[void]$md.AppendLine("## Backend Slot Coverage")
[void]$md.AppendLine("")
[void]$md.AppendLine("| Slot | Controls |")
[void]$md.AppendLine("|---|---:|")
foreach ($group in $bySlot) {
    [void]$md.AppendLine("| " + $group.Name + " | " + $group.Count + " |")
}
[void]$md.AppendLine("")
[void]$md.AppendLine("## P0 Queue (First 120)")
[void]$md.AppendLine("")
[void]$md.AppendLine("| Contract | Lane | File | Line | Type | Label | Status | Slots |")
[void]$md.AppendLine("|---|---|---|---:|---|---|---|---|")
foreach ($row in $topP0) {
    $label = ([string]$row.control_label).Replace("|", "\|")
    $slots = ([string]$row.backend_slots).Replace("|", "\|")
    [void]$md.AppendLine("| $($row.contract_id) | $($row.lane) | $($row.file) | $($row.line) | $($row.control_type) | $label | $($row.current_status) | $slots |")
}
[void]$md.AppendLine("")
[void]$md.AppendLine("## Output Files")
[void]$md.AppendLine("")
[void]$md.AppendLine("- CSV: " + (RelPath -BasePath $repoRoot -FullPath $outCsvAbs))
[void]$md.AppendLine("- Summary: " + (RelPath -BasePath $repoRoot -FullPath $outSummaryAbs))

Set-Content -LiteralPath $outSummaryAbs -Value $md.ToString() -Encoding UTF8

Write-Host "UI control contract matrix generated."
Write-Host ("CSV: " + $outCsvAbs)
Write-Host ("Summary: " + $outSummaryAbs)
Write-Host ("Contracts: " + $total)
