import shutil
import stat
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = ROOT / f"__DEBUG_GEOMETRY_BUNDLE_{TIMESTAMP}"
ZIP_PATH = ROOT / f"__DEBUG_GEOMETRY_BUNDLE_{TIMESTAMP}.zip"

QML_DIRS = [
    ROOT / "src" / "qml",
]

PY_DIRS = [
    ROOT / "src" / "python",
]

QML_NAME_HINTS = [
    "Detached",
    "Window",
    "Overlay",
    "Debug",
    "Canvas",
    "Geometry",
]

PY_CONTENT_HINTS = [
    "QScreen",
    "screenAt",
    "availableGeometry",
    "virtualGeometry",
]

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    count = 0

    # ---- QML FILES ----
    for base in QML_DIRS:
        if not base.exists():
            continue

        for path in base.rglob("*.qml"):
            if any(hint in path.name for hint in QML_NAME_HINTS):
                rel = path.relative_to(ROOT)
                dest = OUT_DIR / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                manifest.append(str(rel))
                count += 1

    # ---- PY FILES ----
    for base in PY_DIRS:
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if any(hint in text for hint in PY_CONTENT_HINTS):
                rel = path.relative_to(ROOT)
                dest = OUT_DIR / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                manifest.append(str(rel))
                count += 1

    # ---- MANIFEST ----
    manifest_path = OUT_DIR / "MANIFEST.txt"
    manifest_path.write_text(
        "DEBUG GEOMETRY BUNDLE (NARROW)\n"
        f"Generated: {datetime.now().isoformat()}\n\n"
        + "\n".join(sorted(manifest)),
        encoding="utf-8",
    )

    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", OUT_DIR)

    print("✅ Debug geometry bundle created successfully")
    print(f"   Files included: {count}")
    print(f"   Folder: {OUT_DIR.name}")
    print(f"   Zip: {ZIP_PATH.name}")

if __name__ == "__main__":
    main()
