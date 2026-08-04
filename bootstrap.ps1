
$iscc_path = $null
if (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") {
    $iscc_path = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
} elseif (Test-Path "C:\Program Files\Inno Setup 6\ISCC.exe") {
    $iscc_path = "C:\Program Files\Inno Setup 6\ISCC.exe"
}

if ($iscc_path) {
    Write-Host "Found ISCC at: $iscc_path"
    & $iscc_path /? | Select-Object -First 5
} else {
    Write-Host "ISCC not found. Attempting winget..."
    winget install --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements --silent
}

