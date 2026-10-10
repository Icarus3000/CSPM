param(
    [Parameter(Mandatory)][string]$PackageDirectory,
    [Parameter(Mandatory)][string]$AcceptanceProfile,
    [Parameter(Mandatory)][string]$ValidationManifest,
    [Parameter(Mandatory)][string]$PythonExecutable
)
$ErrorActionPreference = 'Stop'
$package = (Resolve-Path -LiteralPath $PackageDirectory).Path
$profile = (Resolve-Path -LiteralPath $AcceptanceProfile).Path
$validation = Get-Content -LiteralPath $ValidationManifest -Raw | ConvertFrom-Json
if ($validation.schemaVersion -ne 1 -or $validation.ordinaryStartupAndClosePassed -ne $true -or
    $validation.nativeDefaultObserved -ne $true -or $validation.legacyFallbackPassed -ne $true -or
    $validation.reducedMotionPassed -ne $true -or $validation.bridgeUnavailableFallbackPassed -ne $true -or
    $validation.privacyPassed -ne $true -or $validation.materialIntegrationRegressions -ne 0 -or
    $validation.latestDatasetIntegrityPassed -ne $true -or $validation.snapshotWriteChecksPassed -ne $true -or
    $validation.packageSmokePassed -ne $true) {
    throw 'Candidate installation refused: required regression, privacy or data-safety gate is incomplete.'
}
$executable = Join-Path $package 'CSPM.exe'
$marker = Join-Path $package '_internal\native-motion-candidate.json'
if (-not (Test-Path -LiteralPath $executable) -or -not (Test-Path -LiteralPath $marker)) {
    throw 'Not a governed native motion candidate package.'
}
if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $validation.executableSha256) {
    throw 'Candidate executable differs from the validated package.'
}
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONPATH = Join-Path $projectRoot 'src\python'
& $PythonExecutable -c 'from pathlib import Path; import sys; from backend.native_candidate import validate_profile; validate_profile(Path(sys.argv[1]))' $profile
if ($LASTEXITCODE -ne 0) { throw 'Protected snapshot validation failed.' }
$destination = [System.IO.Path]::GetFullPath('C:\Programs\CSPM-NativeMotionCandidate')
if ($destination -ne 'C:\Programs\CSPM-NativeMotionCandidate' -or (Test-Path -LiteralPath $destination)) {
    throw 'Refusing any existing installation overwrite; review the prior candidate first.'
}
Copy-Item -LiteralPath $package -Destination $destination -Recurse
@{schemaVersion=1; profile=$profile} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'candidate-profile.json') -Encoding utf8
$settingsLink = Join-Path $destination 'CSPM Motion Settings.lnk'
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($settingsLink)
$shortcut.TargetPath = Join-Path $destination 'CSPM.exe'
$shortcut.Arguments = '--motion-settings'
$shortcut.WorkingDirectory = $destination
$shortcut.Save()
Write-Host 'Installed CSPM Native Motion Candidate with protected snapshot. Production installation untouched.'
