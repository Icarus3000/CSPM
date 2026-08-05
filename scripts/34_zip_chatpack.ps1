<#
Single Runner: Dump -> Verify -> Create Copilot Upload Set (FAIL FAST)  [PS 5.1 SAFE]

Assumes canonical script names and parameters:
- 31_dump_chatpack.ps1  (creates chatpack)
- 36_verify_chatpack.ps1 (throws if NOT OK)
- 35_make_copilot_upload_set.ps1 (creates copilot_upload files)

USAGE:
  .\scripts\99_update_context_dump.ps1 -OpenUploadDir
  .\scripts\99_update_context_dump.ps1 -MaxBundleChars 180000 -UploadMaxChars 350000 -OpenUploadDir
#>

[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $false)]
    [switch] $IncludeArchive,

    [Parameter(Mandatory = $false)]
    [switch] $IncludeOutputs,

    [Parameter(Mandatory = $false)]
    [switch] $IncludeBackups,

    [Parameter(Mandatory = $false)]
    [switch] $IncludeStateJson,

    [Parameter(Mandatory = $false)]
    [ValidateRange(50000, 2000000)]
    [int] $MaxBundleChars = 220000,

    [Parameter(Mandatory = $false)]
    [ValidateRange(50000, 2000000)]
    [int] $UploadMaxChars = 350000,

    [Parameter(Mandatory = $false)]
    [switch] $OpenUploadDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ScriptDir {
    $dir = $PSScriptRoot
    if (-not [string]::IsNullOrWhiteSpace($dir)) { return $dir }
    if ($PSCommandPath) { return (Split-Path -Parent $PSCommandPath) }
    if ($MyInvocation -and $MyInvocation.MyCommand -and $MyInvocation.MyCommand.Path) {
        return (Split-Path -Parent $MyInvocation.MyCommand.Path)
    }
    return (Get-Location).Path
}

function Find-ProjectRoot {
    param([Parameter(Mandatory = $true)][string] $StartDir)

    $dir = (Resolve-Path -LiteralPath $StartDir).Path
    while ($true) {
        $hasScripts = Test-Path -LiteralPath (Join-Path $dir "scripts")
        $hasDumps   = Test-Path -LiteralPath (Join-Path $dir "dumps")
        $hasReq     = Test-Path -LiteralPath (Join-Path $dir "requirements.txt")
        $hasWs      = Test-Path -LiteralPath (Join-Path $dir "__CSPM.code-workspace")
        if ($hasScripts -and $hasDumps -and ($hasReq -or $hasWs)) { return $dir }

        $parent = Split-Path -Parent $dir
        if ([string]::IsNullOrWhiteSpace($parent) -or ($parent -eq $dir)) { throw "Could not find project root." }
        $dir = $parent
    }
}

function Get-NewestChatpackDir {
    param([Parameter(Mandatory = $true)][string] $RootPath)

    $base = Join-Path $RootPath "dumps\chatpack"
    $timestampPattern = '^\d{4}-\d{2}-\d{2}_\d{6}$'
    $dirsAll = @(Get-ChildItem -LiteralPath $base -Directory)
    $dirs = @(
        $dirsAll |
        Where-Object { $_.Name -notmatch '^_' -and $_.Name -match $timestampPattern } |
        Sort-Object LastWriteTimeUtc -Descending
    )
    if ($dirs.Count -eq 0) { throw "No valid chatpack folders found under: $base" }
    return $dirs[0].FullName
}

$scriptDir = Resolve-ScriptDir
$root = Find-ProjectRoot -StartDir $scriptDir

$dumpScript   = Join-Path $scriptDir "31_dump_chatpack.ps1"
$verifyScript = Join-Path $scriptDir "36_verify_chatpack.ps1"
$uploadScript = Join-Path $scriptDir "35_make_copilot_upload_set.ps1"

if (-not (Test-Path -LiteralPath $dumpScript))   { throw "Missing script: $dumpScript" }
if (-not (Test-Path -LiteralPath $verifyScript)) { throw "Missing script: $verifyScript" }
if (-not (Test-Path -LiteralPath $uploadScript)) { throw "Missing script: $uploadScript" }

Write-Host "RUN: 31_dump_chatpack.ps1"
$paramsDump = @{
    MaxBundleChars = $MaxBundleChars
}
if ($IncludeArchive)   { $paramsDump.IncludeArchive = $true }
if ($IncludeOutputs)   { $paramsDump.IncludeOutputs = $true }
if ($IncludeBackups)   { $paramsDump.IncludeBackups = $true }
if ($IncludeStateJson) { $paramsDump.IncludeStateJson = $true }

& $dumpScript @paramsDump

$chatpackDir = Get-NewestChatpackDir -RootPath $root
Write-Host ("Chatpack selected: {0}" -f $chatpackDir)

Write-Host "RUN: 36_verify_chatpack.ps1"
& $verifyScript -ChatpackDir $chatpackDir

Write-Host "RUN: 35_make_copilot_upload_set.ps1"
$paramsUpload = @{
    ChatpackDir     = $chatpackDir
    MaxCharsPerFile = $UploadMaxChars
}
if ($OpenUploadDir) { $paramsUpload.OpenOutputDir = $true }

& $uploadScript @paramsUpload

Write-Host ""
Write-Host "DONE."
Write-Host ("Chatpack:   {0}" -f $chatpackDir)
Write-Host ("Upload dir: {0}" -f (Join-Path $chatpackDir "copilot_upload"))