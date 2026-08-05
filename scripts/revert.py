import os
import re
from pathlib import Path

# --- CONFIGURATION ---
# The name of the dump file you want to restore from
BUNDLE_FILENAME = "BUNDLE_0001.txt"

def find_bundle():
    """Looks for the bundle in root or bundles/ folder."""
    if os.path.exists(BUNDLE_FILENAME):
        return BUNDLE_FILENAME
    
    # Check bundles folder
    bundle_path = os.path.join("bundles", BUNDLE_FILENAME)
    if os.path.exists(bundle_path):
        return bundle_path
    
    return None

def revert_project():
    bundle_path = find_bundle()
    if not bundle_path:
        print(f"❌ ERROR: Could not find '{BUNDLE_FILENAME}' in the current folder or 'bundles/' folder.")
        print("   Please make sure the dump file is present.")
        return

    print(f"🔄 Reading from {bundle_path}...")
    
    try:
        with open(bundle_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ ERROR reading bundle file: {e}")
        return

    # Regex to split the bundle into individual files
    # Matches: ===== FILE START =====\nPATH: <path>\n... content ...\n===== FILE END =====
    file_pattern = re.compile(
        r"===== FILE START =====\s+PATH: (.*?)\s+.*?"  # Capture Path
        r"===== CONTENT START =====\n(.*?)===== CONTENT END =====", # Capture Content
        re.DOTALL
    )

    matches = file_pattern.findall(content)
    
    if not matches:
        print("⚠️  No files found in the bundle. Check the file format.")
        return

    print(f"📦 Found {len(matches)} files to restore.")

    for file_path_str, file_content in matches:
        # Normalize path separators for Windows
        clean_path = file_path_str.strip().replace("/", os.sep).replace("\\", os.sep)
        
        # Security check: prevent writing outside project root
        if ".." in clean_path or clean_path.startswith("/") or clean_path.startswith("\\"):
            print(f"⚠️  SKIPPING suspicious path: {clean_path}")
            continue

        target_path = Path(clean_path)
        
        # Create directories if they don't exist
        if not target_path.parent.exists():
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"   📁 Created directory: {target_path.parent}")
            except OSError as e:
                print(f"   ❌ Error creating directory {target_path.parent}: {e}")
                continue

        # Write the file
        try:
            with open(target_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(file_content)
            print(f"   ✅ Restored: {clean_path}")
        except Exception as e:
            print(f"   ❌ Failed to write {clean_path}: {e}")

    print("\n🎉 Revert complete. Try running your app now.")

if __name__ == "__main__":
    revert_project()
