from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
QML_FILE = ROOT / "src" / "qml" / "DetachedShellWindow.qml"

BAD_START = "property var activeVisibleRect: ("
BAD_MARKER = "// === FIX v9: canonical settled geometry ==="

SAFE_REPLACEMENT = """property var activeVisibleRect: ({
    "x": Math.round(finalX),
    "y": Math.round(finalY),
    "w": Math.max(1, Math.round(finalW)),
    "h": Math.max(1, Math.round(finalH))
})
"""

def main():
    if not QML_FILE.exists():
        print("❌ File not found:", QML_FILE)
        return

    text = QML_FILE.read_text(encoding="utf-8", errors="replace")

    if BAD_MARKER not in text:
        print("✅ No injected FIX v9 block found. File already clean.")
        return

    start = text.find(BAD_START)
    if start == -1:
        print("❌ activeVisibleRect property not found")
        return

    # Find the matching closing parenthesis of the property initializer
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        print("❌ Could not find end of broken property block")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = QML_FILE.with_suffix(QML_FILE.suffix + f".broken_{ts}")
    shutil.copy2(QML_FILE, backup)

    fixed = text[:start] + SAFE_REPLACEMENT + text[end:]
    QML_FILE.write_text(fixed, encoding="utf-8", newline="\n")

    print("✅ DetachedShellWindow.qml repaired")
    print("   Broken file backed up as:", backup.name)
    print("✅ activeVisibleRect restored to valid QML")

if __name__ == "__main__":
    main()
