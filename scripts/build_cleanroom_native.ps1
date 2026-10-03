param(
    [string]$OutputDirectory = "outputs\native_cleanroom",
    [string]$OutputName = "cspm_cleanroom_composition.dll"
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$nativeSource = Join-Path $projectRoot "src\native\cleanroom_composition\cleanroom_composition.cpp"
$nativeOutput = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
if (-not $nativeOutput.StartsWith($projectRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Native output must remain inside this experimental workspace."
}
if ([System.IO.Path]::GetFileName($OutputName) -ne $OutputName -or $OutputName -notmatch '^[A-Za-z0-9_.-]+\.dll$') {
    throw "Native output name must be a plain DLL filename."
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vswhere)) { throw "Existing Visual Studio discovery tool is unavailable; no toolchain will be installed." }
$visualStudio = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $visualStudio) { throw "Existing MSVC x64 toolchain is unavailable; no toolchain will be installed." }
$vcvars = Join-Path $visualStudio "VC\Auxiliary\Build\vcvars64.bat"
New-Item -ItemType Directory -Path $nativeOutput -Force | Out-Null
$buildBatch = Join-Path $nativeOutput "build_native.cmd"
$batch = @"
@echo off
call "$vcvars" >nul
if errorlevel 1 exit /b %errorlevel%
cd /d "$nativeOutput"
cl.exe /nologo /std:c++17 /EHsc /W4 /O2 /LD /MD "$nativeSource" /Fe:"$nativeOutput\$OutputName" /link d3d11.lib dxgi.lib dcomp.lib d3dcompiler.lib user32.lib ole32.lib
exit /b %errorlevel%
"@
[System.IO.File]::WriteAllText($buildBatch, $batch, [System.Text.Encoding]::ASCII)
$nativeBuildLog = Join-Path $nativeOutput ("build_" + (Get-Date -Format "yyyyMMdd_HHmmss") + "_" + $PID + ".log")
& $env:ComSpec /d /c $buildBatch 2>&1 | Tee-Object -FilePath $nativeBuildLog
if ($LASTEXITCODE -ne 0) { throw "Native bridge compilation failed with exit $LASTEXITCODE." }
Get-FileHash -LiteralPath (Join-Path $nativeOutput $OutputName) -Algorithm SHA256
