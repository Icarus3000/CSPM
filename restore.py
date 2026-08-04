from pathlib import Path
from datetime import datetime
import shutil
import re

ROOT = Path(__file__).resolve().parent
QML_DIR = ROOT / "src" / "qml"

TARGETS = [
    "DetachedShellWindow.qml",
    "detachedshellwindow.txt",
]

BACKUP_PATTERN = re.compile(r"\.bak_fix_")

def restore_file(filename: str):
    original = QML_DIR / filename
    if not original.exists():
        print(f"❌ Original file not found: {filename}")
        return

    backups = sorted(
        QML_DIR.glob(filename + ".bak_fix_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        print(f"❌ No backups found for {filename}")
        return

    latest_backup = backups[0]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety_copy = original.with_suffix(original.suffix + f".broken_{ts}")

    shutil.copy2(original, safety_copy)
    shutil.copy2(latest_backup, original)

    print(f"✅ Restored {filename}")
    print(f"   from: {latest_backup.name}")
    print(f"   old file saved as: {safety_copy.name}")


def main():
    if not QML_DIR.exists():
        print("❌ QML directory not found:", QML_DIR)
        return

    print("🔁 Restoring QML files from latest backups...\n")

    for fname in TARGETS:
        restore_file(fname)

    print("\n✅ Restore complete.")
    print("You can now run main.py safely.")


if __name__ == "__main__":
    main()
