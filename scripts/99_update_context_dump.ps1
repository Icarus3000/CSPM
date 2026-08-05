param(
    [int]$MaxBundleChars = 160000,
    [switch]$IncludeSrc,
    [switch]$IncludeDocsExtras,
    [string]$Descriptor = "",
    [switch]$NoPromptForDescriptor
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$script31 = Join-Path $PSScriptRoot "31_dump_chatpack.ps1"
$script36 = Join-Path $PSScriptRoot "36_verify_chatpack.ps1"
$script35 = Join-Path $PSScriptRoot "35_make_copilot_upload_set.ps1"

Write-Host "RUN: 31_dump_chatpack.ps1"

$args31 = @{ MaxBundleChars = [int]$MaxBundleChars }
if ($IncludeSrc) {
    Write-Host "INFO: -IncludeSrc is now implicit (default dump already includes src and all repo text files)."
}
if ($IncludeDocsExtras) {
    Write-Host "INFO: -IncludeDocsExtras is now implicit (default dump already includes docs)."
}

if (-not $NoPromptForDescriptor) {
    if (-not $PSBoundParameters.ContainsKey("Descriptor")) {
        $Descriptor = ""
    }
    while ([string]::IsNullOrWhiteSpace($Descriptor)) {
        $Descriptor = Read-Host "Enter required descriptor to append after timestamp"
        if ([string]::IsNullOrWhiteSpace($Descriptor)) {
            Write-Host "Descriptor is required (or pass -NoPromptForDescriptor to bypass)."
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($Descriptor)) {
    $args31.Descriptor = $Descriptor
}

$out = & $script31 @args31 2>&1 | ForEach-Object { $_.ToString() }
$out | ForEach-Object { Write-Host $_ }

$chatpackDir = $null
foreach ($line in $out) {
    if ($line -match 'Chatpack generated at:\s*(.+)$') { $chatpackDir = $Matches[1].Trim(); break }
}

if (-not $chatpackDir) {
    $chatpackRoot = Join-Path $root "dumps\chatpack"
    if (Test-Path -LiteralPath $chatpackRoot) {
        $latest = Get-ChildItem -LiteralPath $chatpackRoot -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latest) { $chatpackDir = $latest.FullName }
    }
}

if (-not $chatpackDir) { throw "Could not determine ChatpackDir." }

Write-Host ("Chatpack selected: " + $chatpackDir)

Write-Host "RUN: 36_verify_chatpack.ps1"
& $script36 -ChatpackDir $chatpackDir

Write-Host "RUN: 35_make_copilot_upload_set.ps1"
& $script35 -ChatpackDir $chatpackDir

Write-Host ""
Write-Host "DONE."
Write-Host ("Chatpack:   " + $chatpackDir)
Write-Host ("Upload dir: " + (Join-Path $chatpackDir "copilot_upload"))
