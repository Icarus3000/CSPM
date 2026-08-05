param(
    [Parameter(Mandatory = $true)]
    [string] $ChatpackDir,

    [Parameter(Mandatory = $false)]
    [int] $BundleNumber = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$bundlePath = Join-Path $ChatpackDir ("bundles\BUNDLE_{0:D4}.txt" -f $BundleNumber)
if (-not (Test-Path $bundlePath)) {
    throw "Bundle not found: $bundlePath"
}

$text = Get-Content -Path $bundlePath -Raw -Encoding UTF8
Set-Clipboard -Value $text
Write-Host "Copied to clipboard: $bundlePath"
