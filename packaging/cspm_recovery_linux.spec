from pathlib import Path

project_root = Path(SPECPATH).parent
a = Analysis(
    [str(project_root / "scripts/cspm_recovery.py")],
    pathex=[str(project_root / "src/python")],
    binaries=[], datas=[],
    hiddenimports=["services.paths", "services.data_locations", "services.sync_service", "backend.native_candidate", "backend.data_verification"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6", "PyQt5", "PyQt6", "PySide2", "tkinter", "win32com", "pythoncom", "pywintypes"],
    noarchive=False,
)
pyz = PYZ(a.pure)
# One file can sit beside the main CSPM executable without merging its Qt
# runtime directory or making recovery depend on the graphical application.
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="CSPM_Recovery",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
