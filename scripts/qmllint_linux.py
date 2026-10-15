"""Run Qt's native Linux lint tool with repository imports and warning policy."""
from pathlib import Path
import subprocess
import sys
import PySide6

root = Path(__file__).resolve().parents[1]
tool = Path(PySide6.__file__).parent / "qmllint"
files = []
for value in sys.argv[1:] or ["src/qml"]:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    files.extend(sorted(path.rglob("*.qml")) if path.is_dir() else [path])
if not files:
    raise SystemExit("No QML files selected")
result = 0
for offset in range(0, len(files), 16):
    batch = subprocess.run([str(tool), "-W", "-1", "-I", str(root / "src/qml"), *map(str, files[offset:offset + 16])])
    result = max(result, batch.returncode)
raise SystemExit(result)
