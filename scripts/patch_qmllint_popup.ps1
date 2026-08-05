param(
    [string[]]$VenvDirs = @(),
    [switch]$IncludeGlobalPython,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host $Message
    }
}

function Get-RepoRoot {
    (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-PysideToolPath {
    param([string]$RootDir)
    if ([string]::IsNullOrWhiteSpace($RootDir)) { return $null }
    $candidate = Join-Path $RootDir "Lib\site-packages\PySide6\scripts\pyside_tool.py"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    return $null
}

function Patch-PysideToolFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{ path = $Path; status = "missing"; changed = $false }
    }

    try {
        $original = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    } catch {
        return [pscustomobject]@{
            path = $Path
            status = "read_failed"
            changed = $false
            error = $_.Exception.Message
        }
    }

    $patched = $original
    # Core fix: keep tool output in the existing console pipeline to avoid GUI popup probes.
    $patched = $patched.Replace(
        "returncode = subprocess.call(cmd)",
        "returncode = subprocess.call(cmd, stdout=sys.stdout, stderr=sys.stderr)"
    )
    # Additional wrappers used by entrypoint scripts; harmless when already attached.
    $patched = $patched.Replace(
        "sys.exit(subprocess.call(command))",
        "sys.exit(subprocess.call(command, stdout=sys.stdout, stderr=sys.stderr))"
    )

    if ($patched -ceq $original) {
        return [pscustomobject]@{ path = $Path; status = "already_patched"; changed = $false }
    }

    try {
        Set-Content -LiteralPath $Path -Value $patched -Encoding UTF8
        return [pscustomobject]@{ path = $Path; status = "patched"; changed = $true }
    } catch {
        return [pscustomobject]@{
            path = $Path
            status = "write_failed"
            changed = $false
            error = $_.Exception.Message
        }
    }
}

$repoRoot = Get-RepoRoot
$targets = New-Object System.Collections.Generic.List[string]

if ($VenvDirs.Count -gt 0) {
    foreach ($venvDir in $VenvDirs) {
        $full = $venvDir
        if (-not [System.IO.Path]::IsPathRooted($full)) {
            $full = Join-Path $repoRoot $venvDir
        }
        $resolved = Resolve-PysideToolPath -RootDir $full
        if ($resolved) {
            $targets.Add($resolved) | Out-Null
        }
    }
} else {
    $venvRoots = Get-ChildItem -LiteralPath $repoRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like ".venv*" -or $_.Name -like "venv*" }
    foreach ($root in $venvRoots) {
        $resolved = Resolve-PysideToolPath -RootDir $root.FullName
        if ($resolved) {
            $targets.Add($resolved) | Out-Null
        }
    }
}

if ($IncludeGlobalPython) {
    $pythonRoot = Join-Path $env:LocalAppData "Programs\Python"
    if (Test-Path -LiteralPath $pythonRoot) {
        $installs = Get-ChildItem -LiteralPath $pythonRoot -Directory -ErrorAction SilentlyContinue
        foreach ($install in $installs) {
            $resolved = Resolve-PysideToolPath -RootDir $install.FullName
            if ($resolved) {
                $targets.Add($resolved) | Out-Null
            }
        }
    }
}

$targets = @($targets | Select-Object -Unique)
if ($targets.Count -eq 0) {
    Write-Info "[QMLLINT-PATCH] No PySide6 pyside_tool.py targets found."
    exit 0
}

$results = @()
foreach ($target in $targets) {
    $result = Patch-PysideToolFile -Path $target
    $results += $result
}

foreach ($result in $results) {
    switch ($result.status) {
        "patched" { Write-Info "[QMLLINT-PATCH] patched: $($result.path)" }
        "already_patched" { Write-Info "[QMLLINT-PATCH] already patched: $($result.path)" }
        "missing" { Write-Info "[QMLLINT-PATCH] missing: $($result.path)" }
        default {
            $err = if ($result.PSObject.Properties.Name -contains "error") { $result.error } else { "unknown error" }
            Write-Warning "[QMLLINT-PATCH] $($result.status): $($result.path) :: $err"
        }
    }
}

$changedCount = @($results | Where-Object { $_.changed }).Count
Write-Info "[QMLLINT-PATCH] done. changed=$changedCount scanned=$($results.Count)"

