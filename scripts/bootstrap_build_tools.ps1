<#
.SYNOPSIS
    Governed Build Tool Bootstrap Script (Non-Administrative).
.DESCRIPTION
    Provisions Inno Setup for compiling the CSPM installer.
    Uses the official JRSoftware current-user installation mode (/CURRENTUSER)
    to safely provision the compiler without requiring Administrator privileges or UAC.
#>

$ErrorActionPreference = "Stop"

Write-Host "=================================================="
Write-Host "       CSPM BUILD TOOL BOOTSTRAP"
Write-Host "=================================================="

# 1. Check if ISCC is already installed in the non-admin path
$iscc_path = "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe"
if (Test-Path $iscc_path) {
    Write-Host "Inno Setup is already installed at: $iscc_path" -ForegroundColor Green
    & $iscc_path "/?" | Select-Object -First 5
    exit 0
}

Write-Host "Inno Setup compiler (ISCC.exe) not found."
Write-Host "Attempting official non-administrative installation..."

# 2. Download Official Installer
$url = "https://github.com/jrsoftware/issrc/releases/download/is-7_0_2/innosetup-7.0.2-x64.exe"
$installerPath = "$env:TEMP\innosetup-7.0.2-x64.exe"
$expectedHash = "5AD54CA3DEF786F8F4212552E54CC6D8D61329E2D24A1CFEE0571D42C2684FF1"

Write-Host "Downloading Inno Setup 7.0.2 from $url..."
Invoke-WebRequest -Uri $url -OutFile $installerPath

# 3. Verify Hash and Signature
$actualHash = (Get-FileHash $installerPath).Hash
if ($actualHash -ne $expectedHash) {
    Write-Host "ERROR: Hash mismatch! Expected: $expectedHash, Actual: $actualHash" -ForegroundColor Red
    exit 1
}

$sig = Get-AuthenticodeSignature $installerPath
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch "Pyrsys B.V.") {
    Write-Host "ERROR: Authenticode signature validation failed." -ForegroundColor Red
    exit 1
}
Write-Host "Signature and hash validated successfully." -ForegroundColor Green

# 4. Install silently for current user
Write-Host "Installing Inno Setup without administrative elevation..."
$args = "/VERYSILENT", "/CURRENTUSER", "/LOG=$env:TEMP\iscc_install.log"
Start-Process -FilePath $installerPath -ArgumentList $args -Wait -NoNewWindow

if (Test-Path $iscc_path) {
    Write-Host "Build tools successfully provisioned at: $iscc_path" -ForegroundColor Green
} else {
    Write-Host "ERROR: Installation failed or ISCC.exe not found." -ForegroundColor Red
    exit 1
}
