param(
    [Parameter(Mandatory = $true)][string]$ChatpackDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-Array {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [System.Array]) { return $Value }
    return @($Value)
}

Write-Host ("ChatpackDir: " + $ChatpackDir)

$manifestPath = Join-Path $ChatpackDir "03_MANIFEST.json"
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Missing 03_MANIFEST.json: $manifestPath" }

# [FIX] Use UTF8 to safely parse non-ASCII filenames or content in manifest
$manifestObj = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest = ConvertTo-Array -Value $manifestObj

Write-Host ("Total manifest files: " + ($manifest | Measure-Object).Count)

$bundlesDir = Join-Path $ChatpackDir "bundles"
if (-not (Test-Path -LiteralPath $bundlesDir)) { throw "Missing bundles dir: $bundlesDir" }

$included = @($manifest | Where-Object { $_.include_content -eq $true })
$bundleNames = @($included | Where-Object { $_.bundle } | Select-Object -ExpandProperty bundle -Unique)

$missingBundles = @()
foreach ($b in $bundleNames) {
    $p = Join-Path $bundlesDir $b
    if (-not (Test-Path -LiteralPath $p)) { $missingBundles += $b }
}

Write-Host ("Missing referenced bundle files: " + ($missingBundles | Measure-Object).Count)
if (($missingBundles | Measure-Object).Count -gt 0) { throw ("Missing bundles: " + ($missingBundles -join ", ")) }

$missingInBundle = @()
foreach ($item in $included) {
    $bundlePath = Join-Path $bundlesDir $item.bundle
    
    # [FIX] Use UTF8 to read bundle text so characters match the source
    $text = Get-Content -LiteralPath $bundlePath -Raw -Encoding UTF8
    
    $needle = "PATH: " + $item.path
    if ($text -notmatch [Regex]::Escape($needle)) {
        $missingInBundle += $item.path
    }
}

Write-Host ("Included files missing from bundle text: " + ($missingInBundle | Measure-Object).Count)
if (($missingInBundle | Measure-Object).Count -gt 0) { throw ("Missing in bundle: " + ($missingInBundle -join ", ")) }

Write-Host "OK: Verification passed."