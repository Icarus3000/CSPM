param(
    [string]$ProjectRoot,
    [switch]$ForceRebuild,
    [switch]$InstallRequirements,
    [switch]$InstallDevRequirements,
    [switch]$PassThruPython,
    [switch]$NoPythonInstall
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

$ComputerName = if ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { "MACHINE" }
$UserName = if ($env:USERNAME) { $env:USERNAME } else { "USER" }

$PreferredVenvName = ".venv_${ComputerName}_${UserName}"
$CandidateVenvNames = @(
    $PreferredVenvName,
    ".venv_$ComputerName",
    ".venv"
)

$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"
$DevRequirementsFile = Join-Path $ProjectRoot "requirements-dev.txt"

function Add-UniqueCandidate {
    param(
        [System.Collections.Generic.List[string]]$Candidates,
        [string]$Candidate
    )

    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        return
    }

    $trimmed = $Candidate.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        return
    }

    foreach ($existing in $Candidates) {
        if ($existing -ieq $trimmed) {
            return
        }
    }

    [void]$Candidates.Add($trimmed)
}

function Get-RegistryPythonCandidates {
    $registryRoots = @(
        "HKCU:\Software\Python\PythonCore",
        "HKLM:\Software\Python\PythonCore",
        "HKLM:\Software\WOW6432Node\Python\PythonCore"
    )

    foreach ($root in $registryRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        foreach ($versionKey in Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue) {
            $installPathKey = Join-Path $versionKey.PSPath "InstallPath"
            if (-not (Test-Path -LiteralPath $installPathKey)) {
                continue
            }

            $props = Get-ItemProperty -LiteralPath $installPathKey -ErrorAction SilentlyContinue
            if ($props.ExecutablePath) {
                Write-Output $props.ExecutablePath
            }

            $defaultInstallPath = $props."(default)"
            if ($defaultInstallPath) {
                Write-Output (Join-Path $defaultInstallPath "python.exe")
            }
        }
    }
}

function Get-KnownPythonCandidates {
    $knownRoots = @()
    if ($env:LocalAppData) {
        $knownRoots += (Join-Path $env:LocalAppData "Python")
        $knownRoots += (Join-Path $env:LocalAppData "Programs\Python")
    }
    if ($env:ProgramFiles) {
        $knownRoots += $env:ProgramFiles
    }
    if (${env:ProgramFiles(x86)}) {
        $knownRoots += ${env:ProgramFiles(x86)}
    }

    foreach ($root in $knownRoots) {
        if ([string]::IsNullOrWhiteSpace($root) -or -not (Test-Path -LiteralPath $root)) {
            continue
        }

        foreach ($match in Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue) {
            if ($match.Name -notmatch "^(python|pythoncore)[-_]?\d") {
                continue
            }

            $candidate = Join-Path $match.FullName "python.exe"
            if (Test-Path -LiteralPath $candidate) {
                Write-Output $candidate
            }
        }
    }
}

function Get-WindowsAppsExecutable {
    param([string]$Name)

    if (-not $env:LocalAppData) {
        return $null
    }

    $windowsApps = Join-Path $env:LocalAppData "Microsoft\WindowsApps"
    if (-not (Test-Path -LiteralPath $windowsApps)) {
        return $null
    }

    $direct = Join-Path $windowsApps $Name
    if (Test-Path -LiteralPath $direct) {
        return $direct
    }

    $nested = Get-ChildItem -LiteralPath $windowsApps -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName $Name } |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1

    return $nested
}

function Resolve-PythonLauncherCandidate {
    param(
        [string]$LauncherPath,
        [string[]]$Arguments
    )

    if ([string]::IsNullOrWhiteSpace($LauncherPath) -or -not (Test-Path -LiteralPath $LauncherPath)) {
        return $null
    }

    try {
        $resolved = & $LauncherPath @Arguments -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($resolved)) {
            return $resolved.Trim()
        }
    } catch {
        return $null
    }

    return $null
}

function Test-BasePython {
    param([string]$PythonExe)

    if ([string]::IsNullOrWhiteSpace($PythonExe) -or -not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }

    try {
        & $PythonExe -c "import sys, venv, ensurepip; print(sys.executable)" 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Set-BasePythonPreference {
    param([string]$PythonExe)

    if ([string]::IsNullOrWhiteSpace($PythonExe) -or -not (Test-Path -LiteralPath $PythonExe)) {
        return
    }

    $resolved = (Resolve-Path -LiteralPath $PythonExe).Path
    $env:CSPM_BASE_PYTHON = $resolved

    try {
        $currentUserValue = [Environment]::GetEnvironmentVariable("CSPM_BASE_PYTHON", "User")
        if ($currentUserValue -ne $resolved) {
            [Environment]::SetEnvironmentVariable("CSPM_BASE_PYTHON", $resolved, "User")
            Write-Host "[VENV] Saved CSPM_BASE_PYTHON user setting: $resolved"
        }
    } catch {
        Write-Warning "[VENV] Could not save CSPM_BASE_PYTHON user setting: $($_.Exception.Message)"
    }
}

function Get-WingetExecutable {
    $wingetCommand = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetCommand) {
        return $wingetCommand.Source
    }

    return (Get-WindowsAppsExecutable -Name "winget.exe")
}

function Install-BasePython {
    $winget = Get-WingetExecutable
    if ([string]::IsNullOrWhiteSpace($winget) -or -not (Test-Path -LiteralPath $winget)) {
        throw "Unable to locate a working system Python interpreter, and winget is unavailable for automatic install."
    }

    $packages = @(
        "Python.Python.3.14",
        "Python.Python.3.13",
        "Python.Python.3.12"
    )

    foreach ($package in $packages) {
        Write-Host "[VENV] No working base Python found. Installing $package with winget..."
        & $winget install --id $package --exact --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) {
            return
        }

        Write-Warning "[VENV] winget install failed for $package with exit code $LASTEXITCODE."
    }

    throw "Unable to install Python automatically with winget."
}

function Update-VSCodePythonSettings {
    param(
        [string]$PythonExe
    )

    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        return
    }

    $vscodeDir = Join-Path $ProjectRoot ".vscode"
    $settingsPath = Join-Path $vscodeDir "settings.json"
    $qmllintNoop = Join-Path $vscodeDir "qmllint-noop.bat"

    try {
        if (-not (Test-Path -LiteralPath $vscodeDir)) {
            New-Item -ItemType Directory -Path $vscodeDir | Out-Null
        }

        $settings = [ordered]@{}
        if (Test-Path -LiteralPath $settingsPath) {
            $existing = Get-Content -LiteralPath $settingsPath -Raw
            if (-not [string]::IsNullOrWhiteSpace($existing)) {
                $cleanJson = $existing -replace '(?m)^\s*//.*$', '' -replace '(?s)/\*.*?\*/', ''
                $parsed = $cleanJson | ConvertFrom-Json
                foreach ($property in $parsed.PSObject.Properties) {
                    $settings[$property.Name] = $property.Value
                }
            }
        }

        $settings["python.defaultInterpreterPath"] = $PythonExe
        if (Test-Path -LiteralPath $qmllintNoop) {
            $settings["qtForPython.qmllint.path"] = $qmllintNoop
        }

        $settings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $settingsPath -Encoding ascii
    } catch {
        Write-Warning "[VENV] Could not update VS Code Python settings: $($_.Exception.Message)"
    }
}

function Get-FileSha256Hex {
    param([string]$FilePath)

    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        throw "Cannot calculate a requirements hash because no file path was provided."
    }
    if (-not [System.IO.File]::Exists($FilePath)) {
        throw "Cannot calculate a requirements hash because the file does not exist: $FilePath"
    }

    $stream = $null
    $sha256 = $null
    try {
        $stream = [System.IO.File]::Open(
            $FilePath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        $digest = $sha256.ComputeHash($stream)
        return ([System.BitConverter]::ToString($digest)).Replace("-", "")
    } finally {
        if ($null -ne $sha256) {
            $sha256.Dispose()
        }
        if ($null -ne $stream) {
            $stream.Dispose()
        }
    }
}

function Install-RequirementFile {
    param(
        [string]$PythonExe,
        [string]$RequirementsFilePath,
        [string]$StampSuffix,
        [bool]$CreatedFresh
    )

    if (-not (Test-Path -LiteralPath $RequirementsFilePath)) {
        return
    }

    $RequirementsHash = Get-FileSha256Hex -FilePath $RequirementsFilePath
    $RequirementsStamp = Join-Path $SelectedVenvDir (".requirements_" + $StampSuffix + ".sha256")
    $ExistingHash = ""

    if (Test-Path -LiteralPath $RequirementsStamp) {
        $ExistingHash = (Get-Content -LiteralPath $RequirementsStamp -Raw).Trim()
    }

    if ($CreatedFresh -or ($ExistingHash -ne $RequirementsHash)) {
        Write-Host "[VENV] Installing requirements from $RequirementsFilePath"
        & $PythonExe -m pip install --upgrade pip --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "[VENV] pip self-upgrade skipped (offline/restricted environment)."
        }

        & $PythonExe -m pip install -r $RequirementsFilePath --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            throw "pip install -r $RequirementsFilePath failed."
        }

        Set-Content -LiteralPath $RequirementsStamp -Value $RequirementsHash -NoNewline -Encoding ascii
    }
}

function Test-VenvPython {
    param(
        [string]$PythonExe,
        [switch]$RequirePip
    )

    # This is a candidate probe, so an empty candidate is simply unusable.
    # Guard it before Test-Path so a failed resolver cannot turn into an
    # unhelpful LiteralPath parameter-binding error in launch.ps1.
    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        return $false
    }

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }

    try {
        & $PythonExe -c "import sys; print(sys.executable)" 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        if ($RequirePip) {
            & $PythonExe -c "import pip" 1>$null 2>$null
            if ($LASTEXITCODE -ne 0) {
                return $false
            }
        }
        return $true
    } catch {
        return $false
    }
}

function Resolve-BasePython {
    param([switch]$SkipInstall)

    $Candidates = [System.Collections.Generic.List[string]]::new()

    if ($env:CSPM_BASE_PYTHON) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate $env:CSPM_BASE_PYTHON
    }

    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate $PythonCmd.Source
    }

    $Python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($Python3Cmd) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate $Python3Cmd.Source
    }

    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate (Resolve-PythonLauncherCandidate -LauncherPath $PyLauncher.Source -Arguments @("-3"))
    }

    Add-UniqueCandidate -Candidates $Candidates -Candidate (Resolve-PythonLauncherCandidate -LauncherPath (Get-WindowsAppsExecutable -Name "python.exe") -Arguments @())
    Add-UniqueCandidate -Candidates $Candidates -Candidate (Resolve-PythonLauncherCandidate -LauncherPath (Get-WindowsAppsExecutable -Name "py.exe") -Arguments @("-3"))

    foreach ($Candidate in Get-RegistryPythonCandidates) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate $Candidate
    }

    foreach ($Candidate in Get-KnownPythonCandidates) {
        Add-UniqueCandidate -Candidates $Candidates -Candidate $Candidate
    }

    foreach ($Candidate in $Candidates) {
        if (Test-BasePython -PythonExe $Candidate) {
            $resolved = (Resolve-Path -LiteralPath $Candidate).Path
            Set-BasePythonPreference -PythonExe $resolved
            return $resolved
        }
    }

    if ((-not $NoPythonInstall) -and (-not $SkipInstall)) {
        Install-BasePython
        return (Resolve-BasePython -SkipInstall)
    }

    throw "Unable to locate or install a working system Python interpreter. Set CSPM_BASE_PYTHON to a Python with venv and ensurepip support."
}

$SelectedVenvDir = $null
$SelectedPythonExe = $null
$CreatedFresh = $false

if ($ForceRebuild) {
    $SelectedVenvDir = Join-Path $ProjectRoot $PreferredVenvName
    if (Test-Path -LiteralPath $SelectedVenvDir) {
        Write-Host "[VENV] Force rebuild requested. Removing $SelectedVenvDir"
        Remove-Item -LiteralPath $SelectedVenvDir -Recurse -Force
    }
} else {
    foreach ($VenvName in $CandidateVenvNames) {
        $ProbeDir = Join-Path $ProjectRoot $VenvName
        $ProbePython = Join-Path $ProbeDir "Scripts\python.exe"
        if (Test-VenvPython -PythonExe $ProbePython -RequirePip) {
            $SelectedVenvDir = $ProbeDir
            $SelectedPythonExe = $ProbePython
            break
        }
    }
}

if (-not $SelectedVenvDir) {
    $SelectedVenvDir = Join-Path $ProjectRoot $PreferredVenvName
}

if (-not $SelectedPythonExe) {
    $SelectedPythonExe = Join-Path $SelectedVenvDir "Scripts\python.exe"
}

if (-not (Test-VenvPython -PythonExe $SelectedPythonExe -RequirePip)) {
    $CreateError = $null
    try {
        if (Test-Path -LiteralPath $SelectedVenvDir) {
            Write-Host "[VENV] Removing invalid environment at $SelectedVenvDir"
            Remove-Item -LiteralPath $SelectedVenvDir -Recurse -Force
        }

        $BasePython = Resolve-BasePython
        Write-Host "[VENV] Creating environment at $SelectedVenvDir using $BasePython"
        & $BasePython -m venv $SelectedVenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment at $SelectedVenvDir"
        }

        if (-not (Test-VenvPython -PythonExe $SelectedPythonExe -RequirePip)) {
            throw "Created virtual environment is not usable: $SelectedVenvDir"
        }

        $CreatedFresh = $true
    } catch {
        $CreateError = $_
    }

    if ($CreateError) {
        if (-not $ForceRebuild) {
            foreach ($FallbackName in @(".venv_$ComputerName", ".venv")) {
                $FallbackDir = Join-Path $ProjectRoot $FallbackName
                $FallbackPython = Join-Path $FallbackDir "Scripts\python.exe"
                if (Test-VenvPython -PythonExe $FallbackPython -RequirePip) {
                    Write-Warning "[VENV] Falling back to existing environment: $FallbackDir"
                    $SelectedVenvDir = $FallbackDir
                    $SelectedPythonExe = $FallbackPython
                    $CreatedFresh = $false
                    $CreateError = $null
                    break
                }
            }
        }

        if ($CreateError) {
            throw $CreateError
        }
    }
}

if ($InstallRequirements) {
    Install-RequirementFile -PythonExe $SelectedPythonExe -RequirementsFilePath $RequirementsFile -StampSuffix "runtime" -CreatedFresh $CreatedFresh
}

if ($InstallDevRequirements) {
    Install-RequirementFile -PythonExe $SelectedPythonExe -RequirementsFilePath $DevRequirementsFile -StampSuffix "dev" -CreatedFresh $CreatedFresh
}

Update-VSCodePythonSettings -PythonExe (Resolve-Path -LiteralPath $SelectedPythonExe).Path

$PatchScript = Join-Path $PSScriptRoot "patch_qmllint_popup.ps1"
if (Test-Path -LiteralPath $PatchScript) {
    try {
        & $PatchScript -VenvDirs @($SelectedVenvDir) -Quiet | Out-Null
    } catch {
        Write-Warning "[VENV] qmllint popup patch step failed: $($_.Exception.Message)"
    }
}

if ($PassThruPython) {
    Write-Output (Resolve-Path -LiteralPath $SelectedPythonExe).Path
}
