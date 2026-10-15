from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

project_root = Path(SPECPATH).parent
# Avoid masking the standard library's platform module during hook discovery.
sys.path.append(str(project_root / "src" / "python"))
hiddenimports = []
for package in ("backend", "bootstrap", "domain", "repositories", "services", "tray", "utils"):
    hiddenimports.extend(collect_submodules(package))
hiddenimports += ["pypdf", "PIL.Image", "PIL.ImageOps", "PIL.ImageSequence"]
hiddenimports += ["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"]
hiddenimports += ["msal", "secretstorage", "cryptography.fernet",
                  "holidays.countries.canada", "holidays.countries.united_states"]

datas = [(str(project_root / source), target) for source, target in (
    ("src/qml", "src/qml"), ("src/templates", "src/templates"),
    ("src/assets", "src/assets"), ("src/resources", "src/resources"),
    ("assets", "assets"), ("schema", "schema"), ("docs/spec", "docs/spec"),
    ("docs/BIBLE.md", "docs"), ("docs/ROADMAP.md", "docs"),
    ("docs/CHANGELOG.md", "docs"), ("version.json", "."),
    ("build/linux/release-provenance.json", "."),
)]
for package in ("holidays", "tzdata"):
    datas.extend(collect_data_files(package))

a = Analysis(
    [str(project_root / "src/python/main.py")],
    pathex=[str(project_root / "src/python")], binaries=[], datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["win32com", "pythoncom", "pywintypes", "PyQt5", "PyQt6", "PySide2", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CSPM",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CSPM")
