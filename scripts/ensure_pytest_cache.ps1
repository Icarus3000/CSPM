param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$outputsRoot = Join-Path $ProjectRoot "outputs"
$cacheRoot = Join-Path $outputsRoot "pytest_cache"

if (-not (Test-Path -LiteralPath $outputsRoot)) {
    New-Item -ItemType Directory -Path $outputsRoot | Out-Null
}
if (-not (Test-Path -LiteralPath $cacheRoot)) {
    New-Item -ItemType Directory -Path $cacheRoot | Out-Null
}

$readmePath = Join-Path $cacheRoot "README.md"
$gitignorePath = Join-Path $cacheRoot ".gitignore"
$cacheTagPath = Join-Path $cacheRoot "CACHEDIR.TAG"

if (-not (Test-Path -LiteralPath $readmePath)) {
    @"
# pytest cache directory #

This directory contains data from pytest's cache plugin.
Do not commit this directory or its contents.
"@ | Set-Content -LiteralPath $readmePath -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $gitignorePath)) {
    @"
# Created by CSPM bootstrap.
*
"@ | Set-Content -LiteralPath $gitignorePath -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $cacheTagPath)) {
    $cacheTagBytes = [System.Text.Encoding]::ASCII.GetBytes(
        "Signature: 8a477f597d28d172789f06886806bc55`n" +
        "# This file is a cache directory tag created by pytest.`n" +
        "# For information about cache directory tags, see:`n" +
        "#`thttps://bford.info/cachedir/spec.html`n"
    )
    [System.IO.File]::WriteAllBytes($cacheTagPath, $cacheTagBytes)
}

Get-ChildItem -LiteralPath $outputsRoot -Directory -Filter "pytest-cache-files-*" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Output $cacheRoot
