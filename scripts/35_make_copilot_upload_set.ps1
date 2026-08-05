param(
    [Parameter(Mandatory = $true)][string]$ChatpackDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Copy-IfExists {
    param([string]$Src, [string]$DstDir)
    if (Test-Path -LiteralPath $Src) { Copy-Item -LiteralPath $Src -Destination $DstDir -Force }
}

$uploadDir = Join-Path $ChatpackDir "copilot_upload"
New-Item -ItemType Directory -Force -Path $uploadDir | Out-Null

# Standard ingestion files
Copy-IfExists -Src (Join-Path $ChatpackDir "00_README_FOR_CHAT.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "01_PREFERENCES.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "02_PROJECT_SUMMARY.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "05_DELTA_REPORT.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "08_PHASE_SUMMARY.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "03_MANIFEST.json") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "04_FILE_TREE.txt") -DstDir $uploadDir

# Optional convenience copies (explicit repo docs at top-level)
Copy-IfExists -Src (Join-Path $ChatpackDir "06_REPO_BIBLE.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "07_REPO_PREFERENCES.md") -DstDir $uploadDir
Copy-IfExists -Src (Join-Path $ChatpackDir "09_MODULE_PATHWAYS.md") -DstDir $uploadDir

# Bundles folder
$bundlesSrc = Join-Path $ChatpackDir "bundles"
if (Test-Path -LiteralPath $bundlesSrc) {
    $bundlesDst = Join-Path $uploadDir "bundles"
    New-Item -ItemType Directory -Force -Path $bundlesDst | Out-Null
    Get-ChildItem -LiteralPath $bundlesSrc -File -Filter "BUNDLE_*.txt" | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $bundlesDst -Force
    }
}

# -------------------------------------------------------------------------
# GENERATE RESTORE.PY
# -------------------------------------------------------------------------
# This python script allows you to reverse the dump: it reads the bundles
# in this folder and overwrites the workspace files (4 levels up).
# -------------------------------------------------------------------------
$restorePyContent = @'
import os
import sys
from pathlib import Path

def parse_bundle_and_restore(bundle_path, target_root):
    print(f"Reading bundle: {bundle_path.name}")
    try:
        with open(bundle_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Failed to read {bundle_path.name}: {e}")
        return

    current_path = None
    in_content = False
    buffer = []
    
    # Markers must match 31_dump_chatpack.ps1
    MARKER_CONTENT_START = "===== CONTENT START ====="
    MARKER_CONTENT_END   = "===== CONTENT END ====="
    PREFIX_PATH          = "PATH: "

    for line in lines:
        stripped = line.strip()

        # Check for Path header
        if stripped.startswith(PREFIX_PATH) and not in_content:
            current_path = stripped[len(PREFIX_PATH):].strip()
            continue
        
        # Check for Content Start
        if stripped == MARKER_CONTENT_START:
            in_content = True
            buffer = [] # Reset buffer
            continue
            
        # Check for Content End (Trigger Write)
        if stripped == MARKER_CONTENT_END:
            in_content = False
            if current_path:
                full_dest = target_root / current_path
                
                # Safety check
                if ".." in current_path or Path(current_path).is_absolute():
                    print(f"  [SKIP] Unsafe path detected: {current_path}")
                else:
                    try:
                        full_dest.parent.mkdir(parents=True, exist_ok=True)
                        with open(full_dest, 'w', encoding='utf-8', newline='') as out_f:
                            out_f.write("".join(buffer))
                        print(f"  [RESTORED] {current_path}")
                    except Exception as e:
                        print(f"  [ERROR] Could not write {current_path}: {e}")
            
            current_path = None
            continue

        # Accumulate content
        if in_content:
            buffer.append(line)

def main():
    # 1. Determine locations
    script_dir = Path(__file__).parent.resolve()
    bundles_dir = script_dir / "bundles"
    
    # Assume standard depth: [RepoRoot]/dumps/chatpack/[Timestamp]/copilot_upload/restore.py
    # So we go up 4 levels to get to RepoRoot.
    repo_root = script_dir.parents[3].resolve()
    required_pathways = repo_root / "docs" / "MODULE_PATHWAYS.md"
    packaged_pathways = script_dir / "09_MODULE_PATHWAYS.md"

    print("-" * 50)
    print("CHATPACK RESTORE UTILITY")
    print("-" * 50)
    print(f"Source (Bundles): {bundles_dir}")
    print(f"Target (Root):    {repo_root}")
    print("-" * 50)
    print("WARNING: This will OVERWRITE files in the Target Root with versions from this dump.")
    if not packaged_pathways.exists():
        print(f"WARNING: packaged pathways doc missing in upload set: {packaged_pathways}")
    
    if not bundles_dir.exists():
        print("Error: 'bundles' folder missing.")
        return

    confirm = input("Type 'restore' to proceed: ")
    if confirm.strip().lower() != 'restore':
        print("Aborted.")
        return

    # 2. Iterate and restore
    files = sorted(list(bundles_dir.glob("BUNDLE_*.txt")))
    if not files:
        print("No bundle files found.")
        return

    for bundle_file in files:
        parse_bundle_and_restore(bundle_file, repo_root)

    if required_pathways.exists():
        print(f"[VERIFY] Pathways restored: {required_pathways}")
    elif packaged_pathways.exists():
        try:
            required_pathways.parent.mkdir(parents=True, exist_ok=True)
            required_pathways.write_text(packaged_pathways.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[VERIFY][RECOVERED] Pathways restored from packaged copy: {required_pathways}")
        except Exception as e:
            print(f"[VERIFY][WARN] Could not recover required pathways file: {e}")
    else:
        print(f"[VERIFY][WARN] Required pathways file missing after restore: {required_pathways}")

    print("-" * 50)
    print("Restore complete.")

if __name__ == "__main__":
    main()
'@

$restorePyPath = Join-Path $uploadDir "restore.py"
[System.IO.File]::WriteAllText($restorePyPath, $restorePyContent, (New-Object System.Text.UTF8Encoding($false)))

$count = (Get-ChildItem -LiteralPath $uploadDir -Recurse -File | Measure-Object).Count
Write-Host ("Copilot upload set created: " + $uploadDir)
Write-Host ("Upload files: " + $count)
Write-Host ("Restore script generated: " + $restorePyPath)
